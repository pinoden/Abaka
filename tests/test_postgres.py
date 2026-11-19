"""
Games in a database (stage 2): PostgresRepository against a real Postgres, and
MirroredRepository (the database plus a copy in files).

The Postgres tests need a server: set ABAKA_TEST_DATABASE_URL (CI runs a Postgres
service; locally, any throwaway database or a Neon branch). Each test uses its own
tables and drops them, and touches no other connection. Without the variable or the psycopg package they are skipped. The mirrored
tests use the in-memory repository and run everywhere.
"""

import os
import secrets
import tempfile
import time
import unittest
from pathlib import Path

import abaka.rooms as rooms
from abaka.repository import FileRepository, MirroredRepository, PostgresRepository
from abaka.rooms import RoomStore
from abaka.saving import engine_to_data
try:
    from test_repository import MemoryRepository  # unittest discover -s tests
except ImportError:
    from tests.test_repository import MemoryRepository  # python -m unittest tests.test_postgres

try:
    import psycopg
except ImportError:  # the base Python 3.8, or no database driver installed
    psycopg = None

DATABASE_URL = os.environ.get("ABAKA_TEST_DATABASE_URL", "").strip()


@unittest.skipIf(psycopg is None or not DATABASE_URL, "no test database (ABAKA_TEST_DATABASE_URL) or no psycopg")
class TestPostgresRepository(unittest.TestCase):
    def setUp(self):
        self.table = "abaka_test_" + secrets.token_hex(4)
        self.repo = PostgresRepository(DATABASE_URL, table=self.table, application_name=self.table)
        self.addCleanup(self.drop_tables)

    def drop_tables(self):
        self.repo.close()
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            conn.execute(f"DROP TABLE IF EXISTS {self.table}")
            conn.execute(f"DROP TABLE IF EXISTS {self.table}_quarantine")

    def sql(self, statement, params=()):
        with psycopg.connect(DATABASE_URL, autocommit=True) as conn:
            cur = conn.execute(statement, params)
            return cur.fetchall() if cur.description else None

    def test_save_and_load(self):
        self.assertIsNone(self.repo.load("AB2CD"))
        self.assertTrue(self.repo.save("AB2CD", 1, {"version": 1, "x": [1, 2], "name": "Ann \"<b>\""}))
        self.assertEqual(self.repo.load("AB2CD"), {"version": 1, "x": [1, 2], "name": "Ann \"<b>\""})
        self.assertIn(self.table, self.repo.describe())
        self.assertNotIn("password", self.repo.describe())

    def test_an_older_version_never_replaces_a_newer_one(self):
        self.repo.save("AB2CD", 2, {"v": 2})
        self.assertFalse(self.repo.save("AB2CD", 1, {"v": 1}))
        self.assertFalse(self.repo.save("AB2CD", 2, {"v": "again"}))
        self.assertEqual(self.repo.load("AB2CD"), {"v": 2})
        # The rule holds in the database, so a second server (or store) cannot break it either.
        other = PostgresRepository(DATABASE_URL, table=self.table)
        self.addCleanup(other.close)
        self.assertFalse(other.save("AB2CD", 1, {"v": 1}))
        self.assertTrue(other.save("AB2CD", 3, {"v": 3}))
        self.assertEqual(self.repo.load("AB2CD"), {"v": 3})

    def test_a_deleted_room_stays_deleted_until_its_code_is_claimed_again(self):
        self.repo.save("AB2CD", 1, {"v": 1})
        self.assertFalse(self.repo.claim("AB2CD"))  # in use
        self.assertTrue(self.repo.claim("ZZ2ZZ"))
        self.repo.delete("AB2CD")
        self.assertFalse(self.repo.save("AB2CD", 5, {"v": 5}))  # a late save of the old room
        self.assertIsNone(self.repo.load("AB2CD"))
        self.repo.delete("NEVER")  # deleting a room that was never saved: a late save is refused too
        self.assertFalse(self.repo.save("NEVER", 1, {}))
        self.assertTrue(self.repo.claim("AB2CD"))  # a new room may take the code...
        self.assertTrue(self.repo.save("AB2CD", 0, {"v": "new"}))  # ...and be saved from version 0
        self.assertEqual(self.repo.load("AB2CD"), {"v": "new"})

    def test_prune_deletes_old_rooms_except_those_kept(self):
        for code in ("OLD22", "KEPT2", "NEW22"):
            self.repo.save(code, 1, {"code": code})
        self.sql(f"UPDATE {self.table} SET saved_at = now() - interval '8 days' WHERE code IN ('OLD22', 'KEPT2')")
        self.assertEqual(self.repo.prune(time.time() - 3600, keep={"KEPT2"}), 1)
        self.assertEqual(self.repo.prune(time.time() - 3600), 1)  # an empty keep works too
        self.assertEqual(sorted(self.repo.stored_versions()), ["NEW22"])

    def test_unusable_data_is_quarantined(self):
        self.repo.save("AB2CD", 1, {"v": 1})  # creates the tables
        self.sql(f"INSERT INTO {self.table} (code, version, data) VALUES ('XY2ZW', 1, '[1, 2]')")
        with self.assertLogs("abaka", level="WARNING"):
            self.assertIsNone(self.repo.load("XY2ZW"))
        self.assertEqual(self.sql(f"SELECT code, data FROM {self.table}_quarantine"), [("XY2ZW", "[1, 2]")])
        self.assertTrue(self.repo.claim("XY2ZW"))

    def test_a_dropped_connection_is_made_again(self):
        self.repo.save("AB2CD", 1, {"v": 1})
        self.repo._conn.close()  # as when Neon suspends an idle database
        self.assertEqual(self.repo.load("AB2CD"), {"v": 1})
        # Only this test's own connection: the test database may be shared (a Neon branch).
        self.sql("SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE application_name = %s",
                 (self.table,))
        self.assertTrue(self.repo.save("AB2CD", 2, {"v": 2}))

    def test_an_unreachable_database_never_stops_a_game(self):
        down = PostgresRepository("postgresql://nobody:secret@127.0.0.1:1/none", connect_timeout=2)
        with self.assertLogs("abaka", level="WARNING") as logs:
            self.assertIsNone(down.load("AB2CD"))
            self.assertTrue(down.claim("AB2CD"))
            down.delete("AB2CD")
            self.assertEqual(down.prune(time.time()), 0)
        self.assertNotIn("secret", "\n".join(logs.output))
        self.assertGreater(down._down_until, time.monotonic())  # not tried again for a while...
        down.url = DATABASE_URL
        started = time.monotonic()
        with self.assertLogs("abaka", level="WARNING"):
            self.assertIsNone(down.load("AB2CD"))  # ...so callers fail at once
        self.assertLess(time.monotonic() - started, 0.5)
        down._down_until = 0.0
        self.assertIsNone(down.load("AB2CD"))  # and then it connects again
        self.assertIsNotNone(down._conn)
        down.close()
        down.url = "postgresql://nobody:secret@127.0.0.1:1/none"
        with self.assertRaises(psycopg.OperationalError):
            down.save("AB2CD", 1, {})  # the store logs it as a failed save
        with self.assertLogs("abaka", level="WARNING"):
            store = RoomStore(repository=down, starting_throw=False)
            code, key = store.create_local(["Ann", "Bob"])
            store.roll(code, key)  # the game goes on in memory
        self.assertTrue(store.view(code).engine.dice)

    def test_a_store_keeps_its_games_in_postgres(self):
        store = RoomStore(repository=self.repo, starting_throw=False)
        code, key = store.create_local(["Ann", "Bob"])
        store.roll(code, key)
        saved = engine_to_data(store.view(code).engine)
        self.assertEqual(self.repo.stored_versions()[code], store.version(code))

        store.retire()  # a code update, or a new server after a reboot: same database
        self.assertIsNone(self.repo._conn)  # the retired store's connection is closed
        again = RoomStore(repository=PostgresRepository(DATABASE_URL, table=self.table), starting_throw=False)
        self.assertEqual(engine_to_data(again.view(code).engine), saved)
        online, host = again.create("Cy", players=3)
        self.assertIn(online, self.repo.stored_versions())
        again.leave(online, host)  # the room closes...
        self.assertNotIn(online, self.repo.stored_versions())  # ...and is deleted
        again._repository.close()


class FilesThenMemory(unittest.TestCase):
    """MirroredRepository with the in-memory repository standing in for the database."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.files = FileRepository(self.folder)
        self.db = MemoryRepository()
        self.db.stored_versions = lambda: {c: d["version"] for c, d in self.db.rooms.items()}
        self.repo = MirroredRepository(self.db, self.files)

    def test_every_save_goes_to_both(self):
        store = RoomStore(repository=self.repo, starting_throw=False)
        self.assertEqual(store.save_dir, self.folder)
        code, key = store.create_local(["Ann", "Bob"])
        store.roll(code, key)
        self.assertEqual(self.db.rooms[code], self.files.load(code))
        self.repo.delete(code)
        self.assertIsNone(self.repo.load(code))
        self.assertFalse((self.folder / f"{code}.json").exists())

    def test_a_game_saved_only_in_files_still_loads_and_moves_into_the_database(self):
        before = RoomStore(save_dir=self.folder, starting_throw=False)  # the app before the database
        code, key = before.create_local(["Ann", "Bob"])
        before.roll(code, key)
        saved = engine_to_data(before.view(code).engine)
        before.retire()

        store = RoomStore(repository=self.repo, starting_throw=False)
        self.assertEqual(engine_to_data(store.view(code).engine), saved)
        store.reroll(code, key, [0])
        self.assertEqual(self.db.rooms[code]["version"], store.version(code))

    def test_the_newer_copy_wins(self):
        self.files.save("AB2CD", 3, {"version": 3})
        self.db.save("AB2CD", 2, {"version": 2})  # the database missed a save (unreachable then)
        self.assertEqual(self.repo.load("AB2CD"), {"version": 3})
        self.db.save("AB2CD", 4, {"version": 4})  # the files lost theirs (a new server after a reboot)
        self.assertEqual(self.repo.load("AB2CD"), {"version": 4})
        self.assertFalse(self.repo.claim("AB2CD"))

    def test_import_copies_only_what_the_database_lacks(self):
        self.files.save("AB2CD", 3, {"version": 3})
        self.files.save("XY2ZW", 1, {"version": 1})
        self.db.save("XY2ZW", 5, {"version": 5})  # newer already: left alone
        self.assertEqual(self.repo.import_files(), 1)
        self.assertEqual(self.db.rooms["AB2CD"], {"version": 3})
        self.assertEqual(self.db.rooms["XY2ZW"], {"version": 5})
        self.assertEqual(self.repo.import_files(), 0)

    def test_a_failed_file_copy_does_not_stop_the_database_save(self):
        (self.folder / "blocked").write_text("a file where the folder should be")
        self.files.folder = self.folder / "blocked" / "games"
        with self.assertLogs("abaka", level="WARNING"):
            self.assertTrue(self.repo.save("AB2CD", 1, {"version": 1}))
        self.assertIn("AB2CD", self.db.rooms)


class SlowMemoryRepository(MemoryRepository):
    """The in-memory database, made slow (or broken) on demand, recording what it was asked to save."""

    def __init__(self):
        super().__init__()
        import threading
        self.gate = threading.Event()
        self.gate.set()
        self.saves = []
        self.broken = False

    def save(self, code, version, data):
        self.gate.wait(5)
        if self.broken:
            raise OSError("database down")
        self.saves.append((code, version))
        return super().save(code, version, data)


class TestBackgroundWrites(unittest.TestCase):
    """MirroredRepository(background=True): a move waits for the file, the database follows."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.files = FileRepository(Path(tmp.name))
        self.db = SlowMemoryRepository()
        self.repo = MirroredRepository(self.db, self.files, background=True)
        self.addCleanup(self.db.gate.set)

    def test_a_save_returns_before_the_database_has_it_and_wait_catches_up(self):
        self.db.gate.clear()  # the database is slow
        started = time.monotonic()
        self.assertTrue(self.repo.save("AB2CD", 1, {"version": 1}))
        self.assertLess(time.monotonic() - started, 1)
        self.assertEqual(self.repo.load("AB2CD"), {"version": 1})  # from the file meanwhile
        for version in (2, 3, 4):
            self.repo.save("AB2CD", version, {"version": version})
        self.db.gate.set()
        self.repo.wait()
        self.assertEqual(self.db.rooms["AB2CD"], {"version": 4})
        self.assertLessEqual(len(self.db.saves), 2)  # versions 2 and 3 were skipped: 4 was newer

    def test_a_store_on_background_writes(self):
        store = RoomStore(repository=self.repo, starting_throw=False)
        code, key = store.create_local(["Ann", "Bob"])
        store.roll(code, key)
        version = store.version(code)
        store.retire()  # a code update: everything pending reaches the database first
        self.assertEqual(self.db.rooms[code]["version"], version)

    def test_a_deleted_room_is_not_written_afterwards(self):
        self.db.gate.clear()
        self.repo.save("AB2CD", 1, {"version": 1})  # the writer takes this one and waits on the gate
        time.sleep(0.1)
        self.repo.save("AB2CD", 2, {"version": 2})  # pending behind it
        self.repo.delete("AB2CD")
        self.db.gate.set()
        self.repo.wait()
        self.assertNotIn("AB2CD", self.db.rooms)
        self.assertNotIn(("AB2CD", 2), self.db.saves)

    def test_a_broken_database_loses_nothing(self):
        self.db.broken = True
        with self.assertLogs("abaka", level="WARNING"):
            self.repo.save("AB2CD", 1, {"version": 1})
            self.repo.wait()
        self.assertEqual(self.repo.load("AB2CD"), {"version": 1})  # the file has it

    def test_the_writer_stops_when_idle(self):
        self.repo.IDLE_SECONDS = 0.05
        self.repo.save("AB2CD", 1, {"version": 1})
        self.repo.wait()
        time.sleep(0.3)
        self.assertIsNone(self.repo._worker)
        self.repo.save("AB2CD", 2, {"version": 2})  # starts again
        self.repo.wait()
        self.assertEqual(self.db.rooms["AB2CD"], {"version": 2})


class TestWhereGamesAreSaved(unittest.TestCase):
    """The line at the foot of the home page, and the secret that names the database."""

    def test_store_storage(self):
        self.assertEqual(RoomStore().storage(), "memory")
        with tempfile.TemporaryDirectory() as folder:
            self.assertEqual(RoomStore(save_dir=folder).storage(), "files")
            mirrored = MirroredRepository(MemoryRepository(), FileRepository(folder))
            self.assertEqual(RoomStore(repository=mirrored).storage(), "database")

    @unittest.skipIf(psycopg is None, "no psycopg")
    def test_a_database_that_is_not_in_use_says_why(self):
        down = PostgresRepository("postgresql://nobody:secret@127.0.0.1:1/none", connect_timeout=2)
        self.assertEqual(down.status(), "not connected yet")
        with tempfile.TemporaryDirectory() as folder, self.assertLogs("abaka", level="WARNING"):
            store = RoomStore(repository=MirroredRepository(down, FileRepository(folder)))  # tries at start
        self.assertEqual(store.storage(), "database:unreachable")
        self.assertNotIn("secret", store.storage())
        down._last_error = 'OperationalError: password authentication failed for user "nobody"'
        self.assertEqual(down.status(), "password")

    def test_the_database_secret_may_use_neons_name(self):
        try:
            import abaka_ui
        except ImportError:  # no Streamlit
            self.skipTest("Streamlit is not installed")
        from unittest import mock
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("ABAKA_DATABASE_URL", None)
            for secrets_, expected in (({"DATABASE_URL": " postgresql://neon "}, "postgresql://neon"),
                                       ({"ABAKA_DATABASE_URL": "postgresql://a", "DATABASE_URL": "x"}, "postgresql://a"),
                                       ({}, None)):
                with mock.patch.object(abaka_ui.st, "secrets", secrets_):
                    self.assertEqual(abaka_ui._database_url(), expected)
            os.environ["ABAKA_DATABASE_URL"] = ""  # set but empty: no database, whatever the secrets say
            with mock.patch.object(abaka_ui.st, "secrets", {"DATABASE_URL": "postgresql://neon"}):
                self.assertIsNone(abaka_ui._database_url())
        os.environ.pop("ABAKA_DATABASE_URL", None)
        os.environ["DATABASE_URL"] = "postgresql://production"  # Neon's .env.local name: never used
        try:
            with mock.patch.object(abaka_ui.st, "secrets", {}):
                self.assertIsNone(abaka_ui._database_url())
        finally:
            del os.environ["DATABASE_URL"]


if __name__ == "__main__":
    unittest.main()
