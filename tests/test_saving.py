"""
Saved games: GameEngine <-> JSON data, and RoomStore rooms saved to disk and loaded
by a new store (as after a server restart or a code update).
"""

import json
import random
import tempfile
import time
import unittest
from pathlib import Path

from abaka.engine import GameEngine
from abaka.models import Category
from abaka.rooms import ROOM_TTL_SECONDS, RoomEngine, RoomError, RoomStore
from abaka.saving import engine_from_data, engine_to_data, engines_equal
from abaka.moves import cross_options, score_options


def play_some(engine, rng, turns):
    """Play `turns` turns with legal random moves (also through a RoomEngine); a starting throw counts as one."""
    for _ in range(turns):
        plain = _refresh(engine)
        if plain.is_game_over():
            return
        if getattr(plain, "choosing_first_player", False):
            engine.throw_for_start()
            continue
        engine.start_turn()
        plain = _refresh(engine)
        if rng.random() < 0.5:
            engine.reroll([0, 2, 4])
            plain = _refresh(engine)
        moves = score_options(plain) + cross_options(plain)
        move = rng.choice(moves)
        (engine.record_cross if move.cross else engine.record_score)(move.category, move.slot)


def _refresh(engine):
    if isinstance(engine, RoomEngine):
        engine._engine = engine._store.view(engine._code).engine
        return engine._engine
    return engine


class TestEngineData(unittest.TestCase):
    def test_round_trip_at_every_stage(self):
        rng = random.Random(5)
        random.seed(5)
        g = GameEngine(["Ann", "Bob", "Cy"], starting_throw=True)
        self.assertTrue(engines_equal(engine_from_data(engine_to_data(g)), g))  # before the starting throw
        g.throw_for_start()
        self.assertTrue(engines_equal(engine_from_data(engine_to_data(g)), g))  # in the middle of it
        for _ in range(60):
            play_some(g, rng, 1)
            data = engine_to_data(g)
            json.dumps(data)  # plain JSON
            copy_ = engine_from_data(json.loads(json.dumps(data)))
            self.assertTrue(engines_equal(copy_, g))
        g.start_turn()  # dice on the table, rerolls left
        restored = engine_from_data(json.loads(json.dumps(engine_to_data(g))))
        self.assertEqual([(d.value, d.is_joker) for d in restored.dice], [(d.value, d.is_joker) for d in g.dice])
        self.assertEqual([m.label for m in score_options(restored)], [m.label for m in score_options(g)])

    def test_a_restored_game_plays_on_to_the_end(self):
        rng = random.Random(9)
        g = GameEngine(["Ann", "Bob"], starting_throw=True)
        play_some(g, rng, 37)
        g = engine_from_data(json.loads(json.dumps(engine_to_data(g))))
        play_some(g, rng, 200)
        self.assertTrue(g.is_game_over())
        self.assertIsInstance(g.players[0].table[Category.SUM][0], (int, str))

    def test_unknown_format_is_refused(self):
        data = engine_to_data(GameEngine(["Ann", "Bob"]))
        data["format"] = 99
        with self.assertRaises(ValueError):
            engine_from_data(data)


class TestStoreOnDisk(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name) / "games"

    def test_a_new_store_carries_on_every_game(self):
        rng = random.Random(3)
        a = RoomStore(save_dir=self.dir)
        code, ann = a.create("Ann", players=3)
        bob = a.join(code, "Bob", a.view(code).key)
        cy = a.join(code, "Cy", a.view(code).key)
        tokens = [ann, bob, cy]
        for _ in range(7):  # throws and turns, each by whoever is due
            g = a.view(code).engine
            play_some(RoomEngine(a, code, tokens[g.current], g), rng, 1)
        local, key = a.create_local(["Dee", "Eve"])
        play_some(RoomEngine(a, local, key, a.view(local).engine), rng, 5)
        waiting, host = a.create("Fay", players=4)
        self.assertEqual(sorted(p.name for p in self.dir.glob("*.json")), sorted(f"{c}.json" for c in (code, local, waiting)))

        b = RoomStore(save_dir=self.dir)  # e.g. after a restart or a code update
        for c in (code, local, waiting):
            va, vb = a.view(c), b.view(c)
            self.assertEqual((vb.names, vb.version, vb.capacity, vb.local, vb.games_played),
                             (va.names, va.version, va.capacity, va.local, va.games_played))
            self.assertTrue(engines_equal(va.engine, vb.engine))
        # Every seat still belongs to the same player, and the game goes on in the new store.
        self.assertEqual([b.seat_of(code, t) for t in tokens], [0, 1, 2])
        g = b.view(code).engine
        play_some(RoomEngine(b, code, tokens[g.current], g), rng, 1)
        self.assertGreater(b.version(code), a.version(code))
        self.assertEqual(b.resume_local(local, b.view(local).key), key)
        self.assertFalse(b.view(waiting).started)
        b.join(waiting, "Gus", b.view(waiting).key)
        self.assertEqual(RoomStore(save_dir=self.dir).view(waiting).names, ["Fay", "Gus"])
        self.assertEqual(list(self.dir.glob("*.tmp")), [])  # writes are atomic

    def test_unreadable_or_expired_files_are_skipped(self):
        a = RoomStore(save_dir=self.dir)
        good, _ = a.create_local(["Ann", "Bob"])
        old, _ = a.create_local(["Cy", "Dee"])
        data = json.loads((self.dir / f"{old}.json").read_text())
        data["updated_at"] = time.time() - ROOM_TTL_SECONDS - 60
        (self.dir / f"{old}.json").write_text(json.dumps(data))
        (self.dir / "BROKN.json").write_text("{not json")
        b = RoomStore(save_dir=self.dir)
        self.assertTrue(b.exists(good))
        self.assertFalse(b.exists(old))
        self.assertFalse(b.exists("BROKN"))

    def test_closed_rooms_are_removed_from_disk(self):
        a = RoomStore(save_dir=self.dir)
        code, ann = a.create("Ann", players=3)
        self.assertTrue((self.dir / f"{code}.json").exists())
        a.leave(code, ann)
        self.assertFalse((self.dir / f"{code}.json").exists())

    def test_without_a_save_dir_nothing_is_written(self):
        store = RoomStore()
        store.create_local(["Ann", "Bob"])
        self.assertFalse(self.dir.exists())


class TestWritingFiles(unittest.TestCase):
    """Files are written outside the store's lock: the newest version always wins."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def saved_version(self, code):
        return json.loads((self.dir / f"{code}.json").read_text())["version"]

    def test_an_older_state_never_replaces_a_newer_file(self):
        store = RoomStore(save_dir=self.dir, starting_throw=False)
        code, key = store.create_local(["Ann", "Bob"])
        with store._lock:
            old = store._snapshot(store._rooms[code])  # taken before the move...
        store.roll(code, key)
        store._write(old)  # ...but written after it (a slow thread)
        self.assertEqual(self.saved_version(code), store.version(code))
        self.assertEqual(list(self.dir.glob("*.tmp")) + list(self.dir.glob(".*.tmp")), [])

    def test_a_closed_room_is_not_brought_back_by_a_late_write(self):
        store = RoomStore(save_dir=self.dir)
        code, ann = store.create("Ann", players=3)
        bob = store.join(code, "Bob", store.view(code).key)
        with store._lock:
            late = store._snapshot(store._rooms[code])
        store.leave(code, ann)
        store.leave(code, bob)  # the room closes and its file goes
        store._write(late)
        self.assertFalse((self.dir / f"{code}.json").exists())

    def test_many_threads_leave_every_file_at_its_room_version(self):
        import threading
        store = RoomStore(save_dir=self.dir, starting_throw=False)
        rooms = [store.create_local(["A", "B", "C"]) for _ in range(6)]
        errors = []

        def play(code, key):
            try:
                rng = random.Random(code)
                for _ in range(30):
                    play_some(RoomEngine(store, code, key, store.view(code).engine), rng, 1)
            except Exception as e:  # noqa: BLE001
                errors.append(repr(e))

        threads = [threading.Thread(target=play, args=room) for room in rooms for _ in range(2)]
        for th in threads:
            th.start()
        for th in threads:
            th.join()
        self.assertEqual([e for e in errors if "not your turn" not in e and "already rolled" not in e], [])
        for code, _ in rooms:
            self.assertEqual(self.saved_version(code), store.version(code))
        again = RoomStore(save_dir=self.dir)
        for code, _ in rooms:
            self.assertTrue(engines_equal(again.view(code).engine, store.view(code).engine))

    def test_leftover_temp_files_are_removed_on_load(self):
        RoomStore(save_dir=self.dir).create_local(["Ann", "Bob"])
        (self.dir / ".ABCDE-x.tmp").write_text("half a file")
        RoomStore(save_dir=self.dir)
        self.assertEqual(list(self.dir.glob(".*.tmp")), [])


class TestRetire(unittest.TestCase):
    """After a code update the old store is retired: it stops serving and frees its rooms."""

    def test_a_retired_store_stops_serving(self):
        store = RoomStore()
        code, key = store.create_local(["Ann", "Bob"])
        store.retire()
        self.assertEqual(store.version(code), -1)  # its pages rerun into the new code
        self.assertFalse(store.exists(code))
        with self.assertRaises(RoomError) as caught:
            store.throw_for_start(code, key)
        self.assertIn("just updated", str(caught.exception))
        self.assertEqual(store._rooms, {})


class TestLocalRooms(unittest.TestCase):
    def test_one_browser_plays_every_seat(self):
        store = RoomStore(starting_throw=False)
        code, key = store.create_local(["Ann", "", "Cy"])
        view = store.view(code)
        self.assertTrue(view.local and view.started)
        self.assertEqual(view.names, ["Ann", "Player 2", "Cy"])
        for seat in (0, 1, 2):  # the same token acts for whoever's turn it is
            self.assertEqual(store.view(code).engine.current, seat)
            store.roll(code, key)
            store.score(code, key, Category.SUM, 0)
        with self.assertRaises(RoomError):
            store.roll(code, "someone else")
        with self.assertRaises(RoomError):
            store.join(code, "Dan", store.view(code).key)  # nobody joins a same-device game
        self.assertEqual(store.reclaim(code, 1, store.view(code).key), key)  # no seat juggling either

    def test_online_rooms_cannot_be_resumed_as_local(self):
        store = RoomStore()
        code, _ = store.create("Ann")
        with self.assertRaises(RoomError):
            store.resume_local(code, store.view(code).key)

    def test_player_count_limits(self):
        store = RoomStore()
        for names in (["Ann"], ["A", "B", "C", "D", "E", "F"]):
            with self.assertRaises(RoomError):
                store.create_local(names)


if __name__ == "__main__":
    unittest.main()
