"""
Fewer script runs (stage 0.7), through the real app script:

- a move costs one script run: the game buttons make their move in an on_click
  callback, before the page is drawn (it used to be drawn twice: once for the
  click, again after st.rerun());
- a click on a page drawn before the game's latest change makes no move and
  shows no error: the page is redrawn with the game as it is now;
- a page checks its room only as often as it needs to: every second while
  another player can change it, every 3 s on the player's own turn, every 10 s
  in a same-device game.

Uses Streamlit's AppTest, so it is skipped where Streamlit is not installed.
"""

import functools
import os
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version

try:
    import streamlit as st
    from streamlit.testing.v1 import AppTest
    from streamlit.testing.v1 import element_tree
except ImportError:  # e.g. the base Python 3.8 on the owner's machine
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestReruns(unittest.TestCase):
    def setUp(self):
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": ""})  # no saving to disk
        env.start()
        self.addCleanup(env.stop)
        # Catch the RoomStore the app creates, so the test can set up rooms in it.
        self.stores = []
        stores = self.stores

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        code_version.mark_current()  # so the app uses these (patched) modules

        # Count full script runs: the app calls code_version.load_current() first on every run.
        self.runs = 0
        load_current = code_version.load_current

        def counted_load_current():
            self.runs += 1
            load_current()

        self.patch(code_version, "load_current", counted_load_current)

        # Record the interval of the polling fragment each run draws.
        self.polls = []
        polls, fragment = self.polls, st.fragment

        def recording_fragment(func=None, *, run_every=None, **kwargs):
            def decorate(f):
                @functools.wraps(f)
                def run(*args, **kw):
                    polls.append(run_every)
                    return f(*args, **kw)
                return fragment(run, run_every=run_every, **kwargs)
            return decorate if func is None else decorate(func)

        self.patch(st, "fragment", recording_fragment)

        # AppTest 1.48 reads every button group's value as a list, but the app's single-choice
        # segmented controls (the language, Score / Cross out) hold one value. Later versions
        # know single-choice groups (ButtonGroup._is_single_select).
        if not hasattr(element_tree.ButtonGroup, "_is_single_select"):
            group_value = element_tree.ButtonGroup.value.fget

            def one_or_more(group):
                value = group_value(group)
                return [] if value is None else value if isinstance(value, list) else [value]

            self.patch(element_tree.ButtonGroup, "value", property(one_or_more))

    def patch(self, target, name, value):
        patcher = mock.patch.object(target, name, value)
        patcher.start()
        self.addCleanup(patcher.stop)

    def page(self, room=None, **state):
        at = AppTest.from_file(APP, default_timeout=30)
        if room:
            at.query_params["room"] = room
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def click(self, at, key):
        """Click a button; check the page ran once and the room changed once."""
        code = at.session_state["room_code"]
        before, self.runs = self.store.version(code), 0
        at.button(key=key).click().run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertEqual(self.runs, 1, f"{key}: the page ran {self.runs} times")
        self.assertEqual(self.store.version(code), before + 1, f"{key}: the move was not made")

    @property
    def store(self):
        return self.stores[0]

    def test_a_move_costs_one_script_run(self):
        self.page()  # the app creates its one store on the first page view
        code, key = self.store.create_local(["Ann", "Bob"])
        at = self.page(room=code, room_code=code, seat_token=key)
        for _ in range(20):  # the starting throw; a tie throws again
            if not self.store.view(code).engine.choosing_first_player:
                break
            self.click(at, "start-throw")
        self.assertFalse(self.store.view(code).engine.choosing_first_player)
        self.click(at, "roll")
        self.assertFalse(at.button(key="die-0").disabled)
        # "Reroll all" keeps its label, so its key changes with every reroll: a second, fast
        # tap on the old page's button can never pick up the next page's reroll.
        self.click(at, "reroll-all-2")
        self.assertEqual([b.key for b in at.button if b.key.startswith("reroll-all")], ["reroll-all-1"])
        self.assertFalse(at.button(key="die-0").disabled)
        at.button(key="die-0").click().run()
        self.assertEqual(at.session_state["selected_dice"], {0})
        self.click(at, "reroll-all-1")
        self.assertTrue(all(at.button(key=f"die-{i}").disabled for i in range(5)))
        self.assertFalse(at.session_state["selected_dice"])
        self.assertEqual(len(at.error), 0, [e.value for e in at.error])

    def test_a_click_on_an_outdated_page_makes_no_move(self):
        self.page()
        code, key = self.store.create_local(["Ann", "Bob"])  # no turn check on the same device
        at = self.page(room=code, room_code=code, seat_token=key)
        self.assertEqual(at.button(key="start-throw").label, "Throw for Ann")
        self.store.throw_for_start(code, key)  # Ann's throw, from another device: the page is outdated
        version = self.store.version(code)
        at.button(key="start-throw").click().run()  # still says "Throw for Ann"
        self.assertEqual(self.store.version(code), version)  # no throw for Bob
        self.assertEqual(len(at.error), 0, [e.value for e in at.error])
        self.assertEqual(at.button(key="start-throw").label, "Throw for Bob")  # the game as it is now
        self.click(at, "start-throw")  # and the redrawn button works

    def test_only_the_online_winner_sees_the_trophy(self):
        from abaka.engine import GameEngine
        from abaka.models import Category
        from ui_components.main_ui import _render_results

        game = GameEngine(["Ann", "Bob", "Cy"])
        game.players[0].table[Category.SUM][0] = 10
        with mock.patch.object(st, "html") as html, mock.patch.object(st, "button", return_value=False):
            for seat in (0, 1, 2, None):
                with self.subTest(seat=seat):
                    _render_results(game, seat, None, None, "Leave")
                    self.assertEqual('class="trophy"' in html.call_args.args[0], seat == 0)
            game.players[1].table[Category.SUM][0] = 10
            _render_results(game, 0, None, None, "Leave")
            self.assertNotIn('class="trophy"', html.call_args.args[0])

    def test_pages_check_their_room_only_as_often_as_needed(self):
        self.page()
        code, ann = self.store.create("Ann", players=3)
        ann_page = self.page(room=code, room_code=code, seat_token=ann)
        self.assertEqual(self.polls[-1], 1.0)  # waiting for players to join

        bob = self.store.join(code, "Bob", self.store.view(code).key)
        self.store.start_now(code, ann)
        ann_page.run()
        self.assertEqual(self.polls[-1], 3.0)  # Ann's throw: nobody else can move
        bob_page = self.page(room=code, room_code=code, seat_token=bob)
        self.assertEqual(self.polls[-1], 1.0)  # Bob watches Ann's throw

        self.store.throw_for_start(code, ann)
        ann_page.run()
        self.assertEqual(self.polls[-1], 1.0)
        bob_page.run()
        self.assertEqual(self.polls[-1], 3.0)

        local, key = self.store.create_local(["Cy", "Dee"])
        self.page(room=local, room_code=local, seat_token=key)
        self.assertEqual(self.polls[-1], 10.0)  # a same-device game


if __name__ == "__main__":
    unittest.main()
