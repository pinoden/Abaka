"""
Room lifecycle (stage 0.6): with a save folder, rooms nobody looks at leave memory and are
loaded again when opened; expired files are deleted, unreadable ones quarantined; codes are
checked before they become file names; limits on rooms in memory and on starting games.
"""

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

import abaka.rooms as rooms
from abaka.rooms import RoomError, RoomStore, is_valid_code, within_limit
from abaka.saving import engine_to_data


class Base(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        self.store = RoomStore(save_dir=self.dir, starting_throw=False)

    def age(self, code, seconds):
        """Pretend no page has looked at the room for `seconds`."""
        self.store._rooms[code].last_seen = time.time() - seconds

    def sweep(self):
        with self.store._lock:
            self.store._sweep(force=True)


class TestMemory(Base):
    def test_rooms_nobody_looks_at_leave_memory_and_come_back_unchanged(self):
        code, key = self.store.create_local(["Ann", "Bob"])
        self.store.roll(code, key)
        before = (engine_to_data(self.store.view(code).engine), self.store.version(code))
        self.age(code, rooms.IDLE_IN_MEMORY_SECONDS + 5)
        self.sweep()
        self.assertNotIn(code, self.store._rooms)  # left memory...
        self.assertTrue((self.dir / f"{code}.json").exists())  # ...but not the disk
        self.assertEqual((engine_to_data(self.store.view(code).engine), self.store.version(code)), before)
        self.assertIn(code, self.store._rooms)  # loaded again on demand
        self.store.score(code, key, *_any_move(self.store, code))  # and the game goes on

    def test_a_room_that_is_polled_stays(self):
        code, _ = self.store.create_local(["Ann", "Bob"])
        self.age(code, rooms.IDLE_IN_MEMORY_SECONDS + 5)
        self.store.version(code)  # a page polls it
        self.sweep()
        self.assertIn(code, self.store._rooms)

    def test_finished_games_leave_sooner(self):
        finished, _ = self.store.create_local(["Ann", "Bob"])
        playing, _ = self.store.create_local(["Cy", "Dee"])
        self.store._rooms[finished].engine.is_game_over = lambda: True
        for code in (finished, playing):
            self.age(code, rooms.FINISHED_IN_MEMORY_SECONDS + 5)
        self.sweep()
        self.assertNotIn(finished, self.store._rooms)
        self.assertIn(playing, self.store._rooms)

    def test_beyond_the_cap_the_rooms_seen_least_recently_leave_first(self):
        codes = [self.store.create_local(["A", "B"])[0] for _ in range(6)]
        for i, code in enumerate(codes):
            self.age(code, 600 - i * 60)  # codes[0] seen longest ago
        with mock.patch.object(rooms, "MAX_ROOMS_IN_MEMORY", 3):
            self.sweep()
        self.assertEqual(sorted(self.store._rooms), sorted(codes[3:]))
        self.assertTrue(self.store.exists(codes[0]))  # still there when opened

    def test_rooms_seen_in_the_last_minute_never_leave_for_the_cap(self):
        codes = [self.store.create_local(["A", "B"])[0] for _ in range(4)]
        with mock.patch.object(rooms, "MAX_ROOMS_IN_MEMORY", 1):
            self.sweep()
        self.assertEqual(len(self.store._rooms), 4)

    def test_without_a_save_folder_nothing_leaves_memory_and_the_cap_refuses(self):
        store = RoomStore()
        codes = [store.create_local(["A", "B"])[0] for _ in range(3)]
        for code in codes:
            store._rooms[code].last_seen = 0
        with store._lock:
            store._sweep(force=True)
        self.assertEqual(len(store._rooms), 3)
        with mock.patch.object(rooms, "MAX_ROOMS_IN_MEMORY", 3):
            with self.assertRaises(RoomError) as caught:
                store.create("Ann")
        self.assertIn("busy", str(caught.exception))


class TestDisk(Base):
    def test_codes_are_checked_before_they_become_file_names(self):
        self.assertTrue(is_valid_code("AB2CD"))
        for bad in ("../X", "AB/CD", "ab2cd", "AB0CD", "ABCDEF", ""):
            self.assertFalse(is_valid_code(bad), bad)
        (self.dir.parent / "OUTSIDE.json").write_text("{}")
        self.addCleanup(lambda: (self.dir.parent / "OUTSIDE.json").unlink())
        for probe in ("../OUTSIDE", "..%2FOUTSIDE", "/etc/passwd"):
            self.assertFalse(self.store.exists(probe))
        self.assertEqual(list((self.dir).glob("quarantine/*")), [])

    def test_expired_files_are_deleted_at_start_and_when_opened(self):
        old, _ = self.store.create_local(["Ann", "Bob"])
        stale, _ = self.store.create_local(["Cy", "Dee"])
        week_ago = time.time() - rooms.ROOM_TTL_SECONDS - 60
        os.utime(self.dir / f"{old}.json", (week_ago, week_ago))  # not written for a week
        data = json.loads((self.dir / f"{stale}.json").read_text())
        data["updated_at"] = week_ago  # fresh file, old game
        (self.dir / f"{stale}.json").write_text(json.dumps(data))
        again = RoomStore(save_dir=self.dir)
        self.assertFalse((self.dir / f"{old}.json").exists())  # deleted at start
        self.assertFalse(again.exists(stale))
        self.assertFalse((self.dir / f"{stale}.json").exists())  # deleted when opened

    def test_unreadable_files_are_quarantined(self):
        (self.dir / "AB2CD.json").write_text("{not json")
        self.assertFalse(self.store.exists("AB2CD"))
        self.assertTrue((self.dir / "quarantine" / "AB2CD.json").exists())
        self.assertFalse((self.dir / "AB2CD.json").exists())

    def test_the_hourly_sweep_deletes_expired_files_of_rooms_not_in_memory(self):
        code, _ = self.store.create_local(["Ann", "Bob"])
        self.age(code, rooms.IDLE_IN_MEMORY_SECONDS + 5)
        self.sweep()
        week_ago = time.time() - rooms.ROOM_TTL_SECONDS - 60
        os.utime(self.dir / f"{code}.json", (week_ago, week_ago))
        self.sweep()
        self.assertFalse((self.dir / f"{code}.json").exists())

    def test_new_codes_never_reuse_a_code_saved_on_disk(self):
        code, _ = self.store.create_local(["Ann", "Bob"])
        self.age(code, rooms.IDLE_IN_MEMORY_SECONDS + 5)
        self.sweep()
        with mock.patch.object(rooms.secrets, "choice", side_effect=list(code) + list("XYZ23")):
            new_code, _ = self.store.create("Cy")
        self.assertEqual(new_code, "XYZ23")

    def test_a_retired_store_never_reads_the_disk(self):
        code, _ = self.store.create_local(["Ann", "Bob"])
        self.store.retire()
        self.assertFalse(self.store.exists(code))
        self.assertEqual(self.store._rooms, {})


class TestStartLimit(unittest.TestCase):
    def test_within_limit(self):
        times, now = [], 1000.0
        for i in range(3):
            allowed, times = within_limit(times, now + i, limit=3, window=60)
            self.assertTrue(allowed)
        allowed, times = within_limit(times, now + 5, limit=3, window=60)
        self.assertFalse(allowed)
        allowed, times = within_limit(times, now + 61, limit=3, window=60)  # the first one expired
        self.assertTrue(allowed)


def _any_move(store, code):
    from abaka.moves import cross_options, score_options
    g = store.view(code).engine
    move = (score_options(g) or cross_options(g))[0]
    return move.category, move.slot


if __name__ == "__main__":
    unittest.main()
