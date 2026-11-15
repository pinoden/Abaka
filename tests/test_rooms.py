import unittest

from abaka.engine import GameEngine
from abaka.models import Category, Die
from abaka.rooms import RoomEngine, RoomError, RoomStore


def started_room():
    store = RoomStore()
    code, host = store.create("Ann")
    guest = store.join(code, "Bob")
    return store, code, host, guest


class TestLobby(unittest.TestCase):
    def test_game_starts_when_second_player_joins(self):
        store = RoomStore()
        code, host = store.create("Ann")
        self.assertFalse(store.view(code).started)

        guest = store.join(code.lower(), "Bob")  # codes are case-insensitive
        view = store.view(code)
        self.assertTrue(view.started)
        self.assertEqual([p.name for p in view.engine.players], ["Ann", "Bob"])
        self.assertEqual(store.seat_of(code, host), 0)
        self.assertEqual(store.seat_of(code, guest), 1)

    def test_third_player_is_refused(self):
        store, code, _, _ = started_room()
        with self.assertRaises(RoomError):
            store.join(code, "Eve")

    def test_unknown_room(self):
        store = RoomStore()
        self.assertFalse(store.exists("NOPE1"))
        self.assertEqual(store.version("NOPE1"), -1)
        with self.assertRaises(RoomError):
            store.join("NOPE1", "Bob")

    def test_same_name_is_made_distinct(self):
        store = RoomStore()
        code, _ = store.create("Ann")
        store.join(code, "Ann")
        names = store.view(code).names
        self.assertEqual(len(set(names)), 2)

    def test_reclaim_moves_the_seat_to_the_new_token(self):
        store, code, host, _ = started_room()
        new_host = store.reclaim(code, 0)
        self.assertIsNone(store.seat_of(code, host))
        self.assertEqual(store.seat_of(code, new_host), 0)
        with self.assertRaises(RoomError):
            store.roll(code, host)
        store.roll(code, new_host)


class TestTurns(unittest.TestCase):
    def test_both_players_see_the_same_dice(self):
        store, code, host, guest = started_room()
        store.roll(code, host)
        dice = [(d.value, d.is_joker) for d in store.view(code).engine.dice]
        self.assertEqual(len(dice), 5)
        # A view is a copy: changing it must not touch the shared game.
        store.view(code).engine.dice.clear()
        self.assertEqual([(d.value, d.is_joker) for d in store.view(code).engine.dice], dice)

    def test_only_the_current_player_can_act(self):
        store, code, host, guest = started_room()
        with self.assertRaises(RoomError):
            store.roll(code, guest)
        store.roll(code, host)
        with self.assertRaises(RoomError):
            store.reroll(code, guest, [0])
        with self.assertRaises(RoomError):
            store.score(code, guest, Category.SUM, 0)
        with self.assertRaises(RoomError):
            store.roll(code, "not-a-token")

    def test_must_roll_before_scoring_and_cannot_roll_twice(self):
        store, code, host, _ = started_room()
        with self.assertRaises(RoomError):
            store.score(code, host, Category.SUM, 0)
        with self.assertRaises(RoomError):
            store.cross(code, host, Category.PAIR, 0)
        store.roll(code, host)
        with self.assertRaises(RoomError):
            store.roll(code, host)

    def test_scoring_passes_the_turn_and_clears_the_dice(self):
        store, code, host, guest = started_room()
        store.roll(code, host)
        store.score(code, host, Category.SUM, 0)
        engine = store.view(code).engine
        self.assertEqual(engine.current, 1)
        self.assertEqual(engine.dice, [])
        self.assertIsInstance(engine.players[0].table[Category.SUM][0], int)
        with self.assertRaises(RoomError):
            store.roll(code, host)
        store.roll(code, guest)
        store.cross(code, guest, Category.ABAKA, 0)
        engine = store.view(code).engine
        self.assertEqual(engine.current, 0)
        self.assertEqual(engine.players[1].table[Category.ABAKA][0], 'X')

    def test_reroll_limit(self):
        store, code, host, _ = started_room()
        store.roll(code, host)
        store.reroll(code, host, [0, 1])
        store.reroll(code, host, [2])
        with self.assertRaises(RoomError):
            store.reroll(code, host, [0])
        self.assertEqual(store.view(code).engine.rolls_left, 0)

    def test_rejected_move_changes_nothing(self):
        store, code, host, _ = started_room()
        store.roll(code, host)
        room = store._rooms[code]
        room.engine.dice = [Die(1), Die(2), Die(3), Die(4), Die(6, is_joker=True)]
        before = store.version(code)
        with self.assertRaises(ValueError):
            store.score(code, host, Category.ABAKA, 0)  # not five of a kind
        self.assertEqual(store.version(code), before)
        engine = store.view(code).engine
        self.assertEqual(engine.current, 0)
        self.assertEqual(len(engine.dice), 5)
        self.assertIsNone(engine.players[0].table[Category.ABAKA][0])

    def test_version_changes_on_every_change(self):
        store = RoomStore()
        code, host = store.create("Ann")
        seen = {store.version(code)}
        guest = store.join(code, "Bob")
        seen.add(store.version(code))
        store.roll(code, host)
        seen.add(store.version(code))
        store.reroll(code, host, [0])
        seen.add(store.version(code))
        store.score(code, host, Category.SUM, 0)
        seen.add(store.version(code))
        self.assertEqual(len(seen), 5)


class TestFullGame(unittest.TestCase):
    def test_two_players_can_finish_a_game_and_rematch(self):
        store, code, host, guest = started_room()
        tokens = [host, guest]
        with self.assertRaises(RoomError):
            store.rematch(code, host)

        for _ in range(500):
            engine = store.view(code).engine
            if engine.is_game_over():
                break
            token = tokens[engine.current]
            proxy = RoomEngine(store, code, token, engine)
            proxy.start_turn()
            player = engine.players[engine.current]
            # Sum always scores; otherwise cross a combo row; otherwise write school.
            open_rows = [c for c, slots in player.table.items() if None in slots[:3]]
            combos = [c for c in open_rows if not c.name.startswith("SCHOOL_")]
            if Category.SUM in open_rows:
                proxy.record_score(Category.SUM, proxy.leftmost_slot(player, Category.SUM))
            elif combos:
                proxy.record_cross(combos[0], proxy.leftmost_slot(player, combos[0]))
            else:
                self._write_school(store, code, token, open_rows)
        else:
            self.fail("game did not finish")

        final = store.view(code).engine
        self.assertTrue(final.is_game_over())
        with self.assertRaises(RoomError):
            store.roll(code, tokens[final.current])

        store.rematch(code, guest)
        fresh = store.view(code)
        self.assertFalse(fresh.engine.is_game_over())
        self.assertEqual(fresh.engine.current, 1)  # the other player starts game two
        self.assertEqual(fresh.names, ["Ann", "Bob"])

    def _write_school(self, store, code, token, open_rows):
        # In the endgame any school row can be written (the balance may go negative).
        for cat in open_rows:
            engine = store.view(code).engine
            slot = engine.leftmost_slot(engine.players[engine.current], cat)
            try:
                store.score(code, token, cat, slot)
                return
            except RoomError:
                raise
            except ValueError:
                continue
        self.fail("no school row could be written")


class TestEngineTurnEnd(unittest.TestCase):
    def test_recording_clears_dice_for_the_next_player(self):
        g = GameEngine(["A", "B"])
        g.start_turn()
        g.record_score(Category.SUM, 0)
        self.assertEqual(g.dice, [])
        self.assertEqual(g.current, 1)


if __name__ == "__main__":
    unittest.main()
