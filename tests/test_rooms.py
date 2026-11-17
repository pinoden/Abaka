import tempfile
import unittest

from abaka.engine import GameEngine
from abaka.models import Category, Die
from abaka.rooms import OutdatedPage, RoomEngine, RoomError, RoomStore


def started_room():
    store = RoomStore(starting_throw=False)
    code, host = store.create("Ann")
    guest = store.join(code, "Bob")
    return store, code, host, guest


class TestLobby(unittest.TestCase):
    def test_game_starts_when_second_player_joins(self):
        store = RoomStore(starting_throw=False)
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
        store = RoomStore(starting_throw=False)
        self.assertFalse(store.exists("NOPE1"))
        self.assertEqual(store.version("NOPE1"), -1)
        with self.assertRaises(RoomError):
            store.join("NOPE1", "Bob")

    def test_same_name_is_made_distinct(self):
        store = RoomStore(starting_throw=False)
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
        # Views share the room's engine (no copy), but a move installs a new engine
        # (copy-on-write), so a view taken earlier never changes.
        before = store.view(code).engine
        self.assertIs(store.view(code).engine, before)
        store.reroll(code, host, [0, 1, 2, 3, 4])
        self.assertIsNot(store.view(code).engine, before)
        self.assertEqual([(d.value, d.is_joker) for d in before.dice], dice)

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
        store = RoomStore(starting_throw=False)
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


class TestMorePlayers(unittest.TestCase):
    def test_game_starts_when_the_last_seat_is_taken(self):
        store = RoomStore(starting_throw=False)
        code, ann = store.create("Ann", players=4)
        bob = store.join(code, "Bob")
        cy = store.join(code, "Cy")
        view = store.view(code)
        self.assertFalse(view.started)
        self.assertEqual((view.capacity, view.names), (4, ["Ann", "Bob", "Cy"]))
        dee = store.join(code, "Dee")
        view = store.view(code)
        self.assertTrue(view.started)
        self.assertEqual([p.name for p in view.engine.players], ["Ann", "Bob", "Cy", "Dee"])
        with self.assertRaises(RoomError):
            store.join(code, "Eve")

        # Turns go round the table in seat order.
        for token, seat in ((ann, 0), (bob, 1), (cy, 2), (dee, 3), (ann, 0)):
            self.assertEqual(store.view(code).engine.current, seat)
            store.roll(code, token)
            store.cross(code, token, Category.ABAKA, store.view(code).engine.players[seat].table[Category.ABAKA].index(None))

    def test_player_count_limits(self):
        store = RoomStore(starting_throw=False)
        for bad in (1, 6):
            with self.assertRaises(RoomError):
                store.create("Ann", players=bad)
        code, _ = store.create("Ann", players=5)
        for name in ("B", "C", "D", "E"):
            store.join(code, name)
        self.assertEqual(len(store.view(code).engine.players), 5)

    def test_creator_can_start_early(self):
        store = RoomStore(starting_throw=False)
        code, ann = store.create("Ann", players=5)
        with self.assertRaises(RoomError):
            store.start_now(code, ann)  # nobody else yet
        bob = store.join(code, "Bob")
        with self.assertRaises(RoomError):
            store.start_now(code, bob)  # only the creator
        cy = store.join(code, "Cy")
        store.start_now(code, ann)
        view = store.view(code)
        self.assertTrue(view.started)
        self.assertEqual(view.capacity, 3)
        self.assertEqual(len(view.engine.players), 3)
        with self.assertRaises(RoomError):
            store.join(code, "Dee")
        with self.assertRaises(RoomError):
            store.start_now(code, ann)

    def test_names_are_made_distinct(self):
        store = RoomStore(starting_throw=False)
        code, _ = store.create("Ann", players=3)
        store.join(code, "Ann")
        store.join(code, "Ann")
        self.assertEqual(store.view(code).names, ["Ann", "Ann (2)", "Ann (3)"])

    def test_leaving_the_waiting_room_frees_the_seat(self):
        store = RoomStore(starting_throw=False)
        code, ann = store.create("Ann", players=3)
        bob = store.join(code, "Bob")
        version = store.version(code)
        store.leave(code, bob)
        self.assertEqual(store.view(code).names, ["Ann"])
        self.assertGreater(store.version(code), version)  # the others' pages redraw
        self.assertIsNone(store.seat_of(code, bob))
        store.join(code, "Cy")
        store.join(code, "Dee")  # the freed seat is filled: the game starts without Bob
        view = store.view(code)
        self.assertTrue(view.started)
        self.assertEqual([p.name for p in view.engine.players], ["Ann", "Cy", "Dee"])

    def test_when_the_creator_leaves_the_next_player_takes_over(self):
        store = RoomStore(starting_throw=False)
        code, ann = store.create("Ann", players=4)
        bob = store.join(code, "Bob")
        cy = store.join(code, "Cy")
        store.leave(code, ann)
        self.assertEqual(store.view(code).names, ["Bob", "Cy"])
        self.assertEqual((store.seat_of(code, bob), store.seat_of(code, cy)), (0, 1))
        with self.assertRaises(RoomError):
            store.start_now(code, ann)
        store.start_now(code, bob)  # Bob is the creator now
        self.assertEqual([p.name for p in store.view(code).engine.players], ["Bob", "Cy"])

    def test_room_closes_when_everyone_leaves(self):
        store = RoomStore(starting_throw=False)
        code, ann = store.create("Ann", players=3)
        bob = store.join(code, "Bob")
        store.leave(code, ann)
        store.leave(code, bob)
        self.assertFalse(store.exists(code))
        store.leave(code, bob)  # leaving a closed room is harmless

    def test_leaving_after_the_start_keeps_the_seat(self):
        store, code, ann, bob = started_room()
        store.leave(code, bob)
        self.assertEqual(store.view(code).names, ["Ann", "Bob"])
        self.assertEqual(store.seat_of(code, bob), 1)
        store.leave(code, "not-a-token")
        self.assertEqual(len(store.view(code).engine.players), 2)

    def test_rematch_rotates_the_first_player(self):
        store = RoomStore(starting_throw=False)
        code, ann = store.create("Ann", players=3)
        store.join(code, "Bob")
        store.join(code, "Cy")
        room = store._rooms[code]
        for expected in (1, 2, 0):
            room.engine.is_game_over = lambda: True  # pretend the game finished
            store.rematch(code, ann)
            self.assertEqual(store.view(code).engine.current, expected)


class TestEngineTurnEnd(unittest.TestCase):
    def test_recording_clears_dice_for_the_next_player(self):
        g = GameEngine(["A", "B"])
        g.start_turn()
        g.record_score(Category.SUM, 0)
        self.assertEqual(g.dice, [])
        self.assertEqual(g.current, 1)


class TestOutdatedPages(unittest.TestCase):
    """A page's buttons make their move when the next click arrives (stage 0.7)."""

    def page(self, store, code, token):
        view = store.view(code)
        return RoomEngine(store, code, token, view.engine, view.version)

    def test_a_double_tap_makes_one_move(self):
        store = RoomStore()
        code, key = store.create_local(["Ann", "Bob"])  # no turn check on the same device
        page = self.page(store, code, key)
        page.throw_for_start()  # Ann's throw
        with self.assertRaises(OutdatedPage):
            page.throw_for_start()  # the second tap must not throw for Bob
        self.assertEqual(len(store.view(code).engine.starting_throws), 1)
        self.page(store, code, key).throw_for_start()  # the redrawn page can
        self.assertEqual(len(store.view(code).engine.starting_throws), 2)

    def test_a_page_drawn_before_the_latest_change_is_refused(self):
        store, code, host, _ = started_room()
        host_page = self.page(store, code, host)
        store.roll(code, host)  # from the host's other tab
        with self.assertRaises(OutdatedPage):  # rather than "You have already rolled this turn."
            host_page.start_turn()
        with self.assertRaises(OutdatedPage):
            host_page.reroll([0, 1, 2, 3, 4])
        self.assertEqual(store.view(code).engine.rolls_left, 2)
        self.page(store, code, host).reroll([0])  # the redrawn page can
        self.assertEqual(store.view(code).engine.rolls_left, 1)

    def test_the_move_goes_to_the_store_that_is_current_when_it_is_made(self):
        with tempfile.TemporaryDirectory() as folder:
            stores = [RoomStore(save_dir=folder)]
            code, key = stores[0].create_local(["Ann", "Bob"])
            view = stores[0].view(code)
            page = RoomEngine(lambda: stores[-1], code, key, view.engine, view.version)
            stores[0].retire()  # a code update replaces the store between drawing and the click
            stores.append(RoomStore(save_dir=folder))
            page.throw_for_start()
            self.assertEqual(stores[-1].version(code), view.version + 1)
            self.assertEqual(len(stores[-1].view(code).engine.starting_throws), 1)


if __name__ == "__main__":
    unittest.main()
