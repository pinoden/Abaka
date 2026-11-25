"""
Saved games through the real app script (Streamlit AppTest; skipped without Streamlit):
a same-device game comes back from its link in a new session (a reload, or a session
dropped after a pause), and after a restart (a new store reads it from disk).
"""

import os
import tempfile
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka.rooms import full_code

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # e.g. the base Python 3.8 on the owner's machine
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def link(store, code):
    """A game's link: its full code (the code alone opens nothing)."""
    return full_code(code, store.view(code).key)


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestSavedGames(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        self.base = rooms.RoomStore
        self.stores = []
        self.fresh_store_class()  # as after a fresh start
        code_version.mark_current()  # so the app uses these (patched) modules

    def fresh_store_class(self):
        """A new RoomStore class, so the app makes a new store (as after a restart or a code update)."""
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

    def test_a_same_device_game_comes_back(self):
        self.page()
        store = self.stores[-1]
        self.assertIsNotNone(store.save_dir)
        code, key = store.create_local(["Ann", "Bob"])
        store.throw_for_start(code, key)  # Ann throws for the first turn

        # A new browser session with the game's link (a reload, or a session dropped after a pause).
        at = self.page(room=link(store, code))
        self.assertEqual(at.session_state["room_code"], code)
        html = self.html(at)
        self.assertIn(f"Same device · {code}", html)
        self.assertIn("Who goes first?", html)
        self.assertIn("Throw for Bob", [b.label for b in at.button])

        # A restart: the new store reads the game from disk, and the link still opens it.
        self.fresh_store_class()
        at = self.page(room=link(store, code))
        self.assertEqual(len(self.stores), 2)
        self.assertIn("Throw for Bob", [b.label for b in at.button])
        self.assertEqual(len(self.stores[-1].view(code).engine.starting_throws), 1)


if __name__ == "__main__":
    unittest.main()
