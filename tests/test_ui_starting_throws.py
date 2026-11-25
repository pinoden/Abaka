"""
The starting throws stay on screen after the first player is decided (owner's report, 2026-11-18):
the last thrower's total used to vanish the moment the lowest one was known. Checked through the
real app script (Streamlit AppTest; skipped without Streamlit).
"""

import os
import tempfile
import unittest
from unittest import mock

import abaka.engine as engine_module
import abaka.rooms as rooms
import code_version
from abaka.engine import GameEngine
from abaka.models import Category, Die
from abaka.rooms import full_code

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # e.g. the base Python 3.8 on the owner's machine
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def throw(*faces):
    """Five faces, the joker last: the dice of one starting throw."""
    return [Die(v) for v in faces[:4]] + [Die(faces[4], is_joker=True)]


# Ann 17, Bob 9 (the lowest), Cy 22: Cy, the last thrower, is not the first player.
THROWS = [throw(3, 3, 3, 4, 4), throw(1, 2, 2, 2, 2), throw(4, 4, 4, 5, 5)]


def link(store, code):
    """A game's link: its full code (the code alone opens nothing)."""
    return full_code(code, store.view(code).key)


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestStartingThrowsOnScreen(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        self.base = rooms.RoomStore
        self.stores = []
        self.fresh_store_class()
        code_version.mark_current()  # so the app uses these (patched) modules

    def fresh_store_class(self):
        """A new RoomStore class, so the app makes a new store (as after a restart)."""
        stores = self.stores

        class FreshRoomStore(self.base):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        rooms.RoomStore = FreshRoomStore

    def page(self, room=None):
        at = AppTest.from_file(APP, default_timeout=30)
        if room:
            at.query_params["room"] = room
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def html(at):
        return "\n".join(n.proto.body for n in at.get("html"))

    def test_every_throw_stays_visible_after_the_first_player_is_decided(self):
        self.page()
        store = self.stores[-1]
        code, key = store.create_local(["Ann", "Bob", "Cy"])
        with mock.patch.object(engine_module, "roll_dice", side_effect=THROWS):
            for _ in range(3):
                store.throw_for_start(code, key)

        html = self.html(self.page(room=link(store, code)))
        self.assertIn("Bob threw the lowest (9) and goes first.", html)
        for total in ("17", "9", "22"):  # Ann's, Bob's and Cy's totals, Cy's included
            self.assertIn(f"<b>{total}</b>", html)
        self.assertIn('class="ab-throw next"', html)  # Bob is the first player
        self.assertNotIn('class="ab-throw out"', html)  # nobody is dimmed once the first player is decided

        # The summary goes once the game has moved on (the first move was made).
        store.roll(code, key)
        store.score(code, key, Category.SUM, 0)
        self.assertNotIn('class="ab-start-note"', self.html(self.page(room=link(store, code))))


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestStartingSummary(unittest.TestCase):
    def test_online_wording_and_every_throw(self):
        from ui_components.main_ui import _starter_summary
        g = GameEngine(["Ann", "Bob", "Cy"], starting_throw=True)
        with mock.patch.object(engine_module, "roll_dice", side_effect=THROWS):
            for _ in range(3):
                g.throw_for_start()
        html = _starter_summary(g, 1)  # Bob's own screen
        self.assertIn("You threw the lowest (9) and go first.", html)
        self.assertIn("<b>22</b>", html)
        self.assertIn('<span class="ab-you">You</span>', html)
        self.assertEqual(_starter_summary(GameEngine(["Ann", "Bob"]), None), "")  # no starting throw


if __name__ == "__main__":
    unittest.main()
