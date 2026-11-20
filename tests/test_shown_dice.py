"""
Online, the other players see which dice the player whose turn it is picks to roll
again, and after a reroll exactly which dice were rolled (owner, 2026-11-19).
"""

import os
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka.rooms import RoomEngine, RoomError, RoomStore

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def started_game(store):
    """An online game for Ann and Bob, past the starting throw, the first player rolled.
    Returns code, tokens by seat, and the seat whose turn it is."""
    code, ann = store.create("Ann", players=2)
    bob = store.join(code, "Bob")
    tokens = [ann, bob]
    for _ in range(50):
        engine = store.view(code).engine
        if not engine.choosing_first_player:
            break
        store.throw_for_start(code, tokens[engine.current])
    current = store.view(code).engine.current
    store.roll(code, tokens[current])
    return code, tokens, current


class TestPicksInTheStore(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore()
        self.code, self.tokens, self.me = started_game(self.store)
        self.other = 1 - self.me

    def test_picks_are_shown_but_are_not_a_move(self):
        version, seen = self.store.version(self.code), self.store.seen(self.code)
        self.store.pick(self.code, self.tokens[self.me], [3, 1, 3, 9])
        view = self.store.view(self.code)
        self.assertEqual(view.picked, (1, 3))  # sorted, distinct, only real dice
        self.assertEqual(self.store.version(self.code), version)  # the game did not change...
        self.assertNotEqual(self.store.seen(self.code), seen)     # ...but pages notice the picks
        self.assertEqual(view.seen, self.store.seen(self.code))
        same = self.store.seen(self.code)
        self.store.pick(self.code, self.tokens[self.me], [1, 3])
        self.assertEqual(self.store.seen(self.code), same)  # the same picks again change nothing

    def test_only_the_player_whose_turn_it_is_picks(self):
        with self.assertRaises(RoomError):
            self.store.pick(self.code, self.tokens[self.other], [0])
        with self.assertRaises(RoomError):
            self.store.pick(self.code, "not-a-seat", [0])
        self.assertEqual(self.store.view(self.code).picked, ())

    def test_a_reroll_right_after_a_pick_is_made_and_shows_its_dice(self):
        view = self.store.view(self.code)  # the page as drawn before the pick
        page = RoomEngine(lambda: self.store, self.code, self.tokens[self.me], view.engine, view.version)
        page.pick([0, 4])
        page.reroll([0, 4])  # not refused as outdated: a pick is not a move
        view = self.store.view(self.code)
        self.assertEqual((view.picked, view.rerolled), ((), (0, 4)))
        self.assertEqual(view.engine.rolls_left, 1)
        self.store.score(self.code, self.tokens[self.me], *_a_cell(view.engine))
        view = self.store.view(self.code)
        self.assertEqual((view.picked, view.rerolled), ((), ()))  # the next move clears both

    def test_no_picks_without_a_reroll_left(self):
        for _ in range(2):
            self.store.reroll(self.code, self.tokens[self.me], [0])
        with self.assertRaises(RoomError):
            self.store.pick(self.code, self.tokens[self.me], [0])

    def test_same_device_games_keep_picks_in_the_page(self):
        code, key = self.store.create_local(["Ann", "Bob"])
        seen = self.store.seen(code)
        self.store.pick(code, key, [0])
        self.assertEqual((self.store.view(code).picked, self.store.seen(code)), ((), seen))


def _a_cell(engine):
    from abaka.moves import cross_options, score_options
    move = (score_options(engine) or cross_options(engine))[0]
    return move.category, move.slot


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestPicksOnTheOtherScreen(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        stores = self.stores = []

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        code_version.mark_current()

        # AppTest 1.48 reads every button group's value as a list, but the app's single-choice
        # segmented controls hold one value (as in test_ui_reruns.py; 1.67 needs no help).
        from streamlit.testing.v1 import element_tree
        if not hasattr(element_tree.ButtonGroup, "_is_single_select"):
            group_value = element_tree.ButtonGroup.value.fget

            def one_or_more(group):
                value = group_value(group)
                return [] if value is None else value if isinstance(value, list) else [value]

            patcher = mock.patch.object(element_tree.ButtonGroup, "value", property(one_or_more))
            patcher.start()
            self.addCleanup(patcher.stop)

    def page(self, **state):
        at = AppTest.from_file(APP, default_timeout=30)
        if state:
            at.query_params["room"] = state["room_code"]
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def styles(at):
        return "\n".join(n.proto.body for n in at.get("html"))

    def test_the_watcher_sees_the_picked_and_then_the_rerolled_dice(self):
        self.page()
        store = self.stores[-1]
        code, tokens, me = started_game(store)
        player = self.page(room_code=code, seat_token=tokens[me])
        watcher = self.page(room_code=code, seat_token=tokens[1 - me])
        name = store.view(code).names[me]
        self.assertIn("is choosing a move", " ".join(c.value for c in watcher.caption))

        player.button(key="die-1").click().run()
        player.button(key="die-3").click().run()
        self.assertEqual(store.view(code).picked, (1, 3))
        watcher.run()  # its poll noticed the picks
        css = self.styles(watcher)
        for i in range(5):
            lifted = f".st-key-die-{i} button {{ background-image" in css and \
                f'.st-key-die-{i} button::after {{ content: "\\21BB"' in css
            self.assertEqual(lifted, i in (1, 3), f"die {i}")
        self.assertIn(f"{name} picked 2 dice to roll again", " ".join(c.value for c in watcher.caption))
        self.assertTrue(all(watcher.button(key=f"die-{i}").disabled for i in range(5)))

        player.button(key="reroll").click().run()
        self.assertEqual(store.view(code).rerolled, (1, 3))
        watcher.run()
        css = self.styles(watcher)
        spun = [i for i in range(5) if f".st-key-die-{i} button {{ animation" in css]
        self.assertEqual(spun, [1, 3])  # also a rerolled die that landed on the same face
        self.assertNotIn('content: "\\21BB"', css)  # no picks any more
        self.assertIn(f"{name} rolled 2 dice again", " ".join(c.value for c in watcher.caption))


if __name__ == "__main__":
    unittest.main()
