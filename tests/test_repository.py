"""
The repository behind RoomStore (stage 1): FileRepository's contract, and a store that
runs on another repository (an in-memory one here; a database in stage 2) the same way.
"""

import json
import os
import tempfile
import threading
import time
import unittest
from pathlib import Path

import abaka.rooms as rooms
from abaka.repository import FileRepository
from abaka.rooms import RoomStore
from abaka.saving import engine_to_data


class TestFileRepository(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name) / "games"  # created by the first save
        self.repo = FileRepository(self.folder)

    def test_save_and_load(self):
        self.assertIsNone(self.repo.load("AB2CD"))
        self.assertTrue(self.repo.save("AB2CD", 1, {"version": 1, "x": [1, 2]}))
        self.assertEqual(self.repo.load("AB2CD"), {"version": 1, "x": [1, 2]})
        self.assertEqual(list(self.folder.glob(".*.tmp")), [])  # no temp file left behind

    def test_an_older_version_never_replaces_a_newer_one(self):
        self.repo.save("AB2CD", 2, {"v": 2})
        self.assertFalse(self.repo.save("AB2CD", 1, {"v": 1}))
        self.assertFalse(self.repo.save("AB2CD", 2, {"v": "again"}))
        self.assertEqual(self.repo.load("AB2CD"), {"v": 2})

    def test_a_deleted_room_stays_deleted_until_its_code_is_claimed_again(self):
        self.repo.save("AB2CD", 1, {"v": 1})
        self.assertFalse(self.repo.claim("AB2CD"))  # in use
        self.repo.delete("AB2CD")
        self.assertFalse(self.repo.save("AB2CD", 5, {"v": 5}))  # a late save of the old room
        self.assertIsNone(self.repo.load("AB2CD"))
        self.assertTrue(self.repo.claim("AB2CD"))  # a new room may take the code...
        self.assertTrue(self.repo.save("AB2CD", 0, {"v": "new"}))  # ...and be saved from version 0
        self.assertEqual(self.repo.load("AB2CD"), {"v": "new"})

    def test_prune_deletes_old_rooms_except_those_kept(self):
        for code in ("OLD22", "KEPT2", "NEW22"):
            self.repo.save(code, 1, {"code": code})
        week_ago = time.time() - 7 * 24 * 3600
        for code in ("OLD22", "KEPT2"):
            os.utime(self.folder / f"{code}.json", (week_ago, week_ago))
        self.assertEqual(self.repo.prune(time.time() - 3600, keep={"KEPT2"}), 1)
        self.assertEqual(sorted(p.stem for p in self.folder.glob("*.json")), ["KEPT2", "NEW22"])

    def test_unreadable_data_is_quarantined(self):
        self.folder.mkdir()
        (self.folder / "AB2CD.json").write_text("{not json")
        (self.folder / "XY2ZW.json").write_text("[1, 2]")  # JSON, but not an object
        with self.assertLogs("abaka", level="WARNING"):
            self.assertIsNone(self.repo.load("AB2CD"))
            self.assertIsNone(self.repo.load("XY2ZW"))
        self.assertEqual(sorted(p.name for p in (self.folder / "quarantine").iterdir()),
                         ["AB2CD.json", "XY2ZW.json"])

    def test_leftovers_of_interrupted_writes_are_removed(self):
        self.repo.save("AB2CD", 1, {})
        (self.folder / ".AB2CD-x.tmp").write_text("half a file")
        self.repo.remove_leftovers()
        self.assertEqual(list(self.folder.glob(".*.tmp")), [])
        self.assertTrue((self.folder / "AB2CD.json").exists())

    def test_only_plain_codes_become_file_names(self):
        for bad in ("../X", "a/b", "", "AB.CD"):
            with self.assertRaises(ValueError):
                self.repo.load(bad)


class MemoryRepository:
    """The repository methods without files: what a database would provide (stage 2)."""

    def __init__(self):
        self.rooms, self.saved_at, self.versions, self.quarantined = {}, {}, {}, {}

    def put(self, code, data):
        """A room saved by something else (an older app version, another tool)."""
        self.rooms[code], self.saved_at[code] = data, time.time()

    def claim(self, code):
        if code in self.rooms:
            return False
        self.versions.pop(code, None)
        return True

    def load(self, code):
        data = self.rooms.get(code)
        return json.loads(json.dumps(data)) if data is not None else None  # a copy, as storage gives

    def save(self, code, version, data):
        if version <= self.versions.get(code, -1):
            return False
        self.put(code, json.loads(json.dumps(data)))
        self.versions[code] = version
        return True

    def delete(self, code):
        self.rooms.pop(code, None)
        self.versions[code] = float("inf")

    def prune(self, cutoff, keep=()):
        old = [c for c in self.rooms if self.saved_at[c] < cutoff and c not in keep]
        for code in old:
            del self.rooms[code]
        return len(old)

    def quarantine(self, code, reason):
        self.quarantined[code] = self.rooms.pop(code, None)

    def wait(self):
        pass


class TestAnotherRepository(unittest.TestCase):
    def test_a_store_keeps_its_games_in_any_repository(self):
        repo = MemoryRepository()
        store = RoomStore(repository=repo, starting_throw=False)
        self.assertIsNone(store.save_dir)
        code, key = store.create_local(["Ann", "Bob"])
        store.roll(code, key)
        saved = engine_to_data(store.view(code).engine)
        self.assertEqual(repo.rooms[code]["version"], store.version(code))

        store._rooms[code].last_seen = time.time() - rooms.IDLE_IN_MEMORY_SECONDS - 5
        with store._lock:
            store._sweep(force=True)
        self.assertNotIn(code, store._rooms)  # left memory, still in the repository
        self.assertEqual(engine_to_data(store.view(code).engine), saved)  # loaded back

        store.retire()  # a code update: the next store reads the same repository
        again = RoomStore(repository=repo, starting_throw=False)
        self.assertEqual(engine_to_data(again.view(code).engine), saved)
        online, host = again.create("Cy", players=3)
        again.leave(online, host)  # the room closes...
        self.assertNotIn(online, repo.rooms)  # ...and is deleted from the repository

    def test_data_the_store_cannot_use_is_quarantined(self):
        repo = MemoryRepository()
        repo.put("AB2CD", {"code": "AB2CD"})  # saved by something else: fields missing
        store = RoomStore(repository=repo)
        self.assertFalse(store.exists("AB2CD"))
        self.assertIn("AB2CD", repo.quarantined)


class SlowRepository(MemoryRepository):
    """Storage that answers when told to, like a database waking up: load() and claim() wait."""

    def __init__(self):
        super().__init__()
        self.asked, self.go = threading.Event(), threading.Event()
        self.slow, self.loads = set(), 0

    def _wait(self, code):
        if code in self.slow or "*" in self.slow:
            self.asked.set()
            self.go.wait(10)

    def load(self, code):
        self.loads += 1
        data = super().load(code)  # read, then slow to arrive: it may be out of date by then
        self._wait(code)
        return data

    def claim(self, code):
        self._wait("*" if "*" in self.slow else None)
        return super().claim(code)


class TestSlowStorage(unittest.TestCase):
    """
    A game that is not in memory is read from storage with the store's lock released (the site's
    test round of 2026-11-27): the look took a database round trip, seconds if the database had
    to wake up, and every other game's moves and polls waited for it. Anyone could cause it
    with a code that names no game.
    """

    def setUp(self):
        self.repo = SlowRepository()
        self.store = RoomStore(repository=self.repo, starting_throw=False)
        self.code, self.token = self.store.create_local(["Ann", "Bob"])

    def in_background(self, call, *args):
        result = {}

        def run():
            try:
                result["value"] = call(*args)
            except Exception as e:  # noqa: BLE001 - handed to the test
                result["error"] = e
        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        result["thread"] = thread
        return result

    def test_other_games_go_on_while_a_game_is_read(self):
        self.repo.slow.add("ZZZZZ")
        looking = self.in_background(self.store.opens, "ZZZZZ", "AAAAAAAA")
        self.assertTrue(self.repo.asked.wait(5))
        playing = self.in_background(self.store.roll, self.code, self.token)
        playing["thread"].join(3)
        self.assertFalse(playing["thread"].is_alive(), "a move waited for another game's read")
        self.assertNotIn("error", playing)
        self.assertEqual(self.store.seen(self.code)[0], self.store.view(self.code).version)
        self.repo.go.set()
        looking["thread"].join(5)
        self.assertIs(looking["value"], False)

    def test_other_games_go_on_while_a_new_game_asks_for_its_code(self):
        self.repo.slow.add("*")
        making = self.in_background(self.store.create, "Cid")
        self.assertTrue(self.repo.asked.wait(5))
        polling = self.in_background(self.store.seen, self.code)
        polling["thread"].join(3)
        self.assertFalse(polling["thread"].is_alive(), "a poll waited for a new game's code")
        self.repo.go.set()
        making["thread"].join(5)
        code, token = making["value"]
        self.assertEqual(self.store.seat_of(code, token), 0)

    def test_two_pages_reading_one_game_get_the_same_game(self):
        saved = RoomStore(repository=self.repo, starting_throw=False)  # after a restart: nothing in memory
        key = self.store.view(self.code).key
        self.repo.slow.add(self.code)
        first = self.in_background(saved.opens, self.code, key)
        self.assertTrue(self.repo.asked.wait(5))
        second = self.in_background(saved.opens, self.code, key)
        deadline = time.time() + 5
        while self.repo.loads < 2 and time.time() < deadline:
            time.sleep(0.01)
        self.repo.go.set()
        for look in (first, second):
            look["thread"].join(5)
            self.assertIs(look["value"], True)
        token = saved.resume_local(self.code, key)
        saved.roll(self.code, token)
        self.assertEqual(len(saved._rooms), 1)
        self.assertTrue(saved.view(self.code).engine.dice)  # one room: the move is in the game every page sees

    def test_a_game_closed_while_it_was_read_does_not_come_back(self):
        online = RoomStore(repository=self.repo, starting_throw=False)
        code, host = online.create("Ann", device="anns-own-device-0001")
        key = online.view(code).key
        saved = RoomStore(repository=self.repo, starting_throw=False)
        self.repo.slow.add(code)
        looking = self.in_background(saved.opens, code, key)
        self.assertTrue(self.repo.asked.wait(5))
        self.repo.slow.clear()
        token = saved.reclaim(code, 0, key, "anns-own-device-0001")   # another page opens the game meanwhile...
        saved.leave(code, token)              # ...and its only player leaves: the game is closed
        self.repo.go.set()
        looking["thread"].join(5)
        self.assertIs(looking["value"], False)
        self.assertFalse(saved.exists(code))


if __name__ == "__main__":
    unittest.main()
