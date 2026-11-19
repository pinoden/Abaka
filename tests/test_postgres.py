"""
Games in a database (stage 2): PostgresRepository against a real Postgres, and
MirroredRepository (the database plus a copy in files).

The Postgres tests need a server: set ABAKA_TEST_DATABASE_URL (CI runs a Postgres
service; locally, any throwaway database). Each test uses its own tables and drops
them. Without the variable or the psycopg package they are skipped. The mirrored
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
        self.repo = PostgresRepository(DATABASE_URL, table=self.table)
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
        self.sql("SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                 "WHERE pid <> pg_backend_pid() AND datname = current_database() AND application_name = ''")
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


if __name__ == "__main__":
    unittest.main()
