"""
The shared room store across code updates, through the real app script.

Streamlit Community Cloud applies a new commit by reloading the app's modules while
keeping cached objects. A RoomStore made by the old code must not be handed to the
new code. Uses Streamlit's AppTest, so it is skipped where Streamlit is not installed.
"""

import os
import unittest

import abaka.rooms as rooms
import code_version

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # e.g. the base Python 3.8 on the owner's machine
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestStoreAfterCodeUpdate(unittest.TestCase):
    def setUp(self):
        # A RoomStore class of this test's own (as after a fresh start) that records each store made.
        self.stores = []
        stores = self.stores

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self):
                super().__init__()
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        code_version.mark_current()  # so the app uses these (patched) modules

    def page(self, **state):
        at = AppTest.from_file(APP, default_timeout=30)
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def test_new_code_gets_a_new_store(self):
        self.page()
        self.page()
        self.assertEqual(len(self.stores), 1, "every page of the same code shares one store")
        old_store = self.stores[0]
        code, token = old_store.create("Ann")

        # A code update: the reloaded module has a new RoomStore class.
        class ReloadedRoomStore(rooms.RoomStore):
            pass

        rooms.RoomStore = ReloadedRoomStore
        at = self.page(room_code=code, seat_token=token)
        self.assertEqual(len(self.stores), 2)
        self.assertIs(type(self.stores[1]), ReloadedRoomStore)
        # The game held by the old store is gone, and the player is told so.
        self.assertIn("no longer available", " ".join(w.value for w in at.warning))
        self.page()
        self.assertEqual(len(self.stores), 2, "the new store is shared from then on")


if __name__ == "__main__":
    unittest.main()
