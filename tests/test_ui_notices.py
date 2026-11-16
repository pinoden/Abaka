"""
Notices a browser gets when it loses its online game, through the real app script.

Uses Streamlit's AppTest, so it is skipped where Streamlit is not installed.
"""

import os
import unittest

import abaka.rooms as rooms

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # e.g. the base Python 3.8 on the owner's machine
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestLostGameNotices(unittest.TestCase):
    def setUp(self):
        # Catch the RoomStore the app creates, so the test can set up rooms in it.
        self.stores = []
        original = rooms.RoomStore.__init__

        def capture(store):
            original(store)
            self.stores.append(store)

        rooms.RoomStore.__init__ = capture
        self.addCleanup(setattr, rooms.RoomStore, "__init__", original)

    def page(self, room=None, **state):
        at = AppTest.from_file(APP, default_timeout=30)
        if room:
            at.query_params["room"] = room
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def test_notices(self):
        self.page()  # the app creates its one store on the first page view
        self.assertEqual(len(self.stores), 1)
        store = self.stores[0]

        # A tab whose seat was taken over from another tab (refresh + rejoin) keeps the link,
        # so it lands on the invite page. It must be told why it is no longer in the game.
        code, _ = store.create("Ann")
        old_token = store.join(code, "Bob")
        store.reclaim(code, 1)
        old_tab = self.page(room=code, room_code=code, seat_token=old_token)
        warnings = [w.value for w in old_tab.warning]
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("opened in another tab", warnings[0])
        self.assertIsNone(old_tab.session_state["room_code"])
        self.assertEqual(old_tab.query_params["room"], [code])
        self.assertIsNone(old_tab.session_state["lobby_notice"])  # shown once, not again later

        # A tab whose game is gone (expired, server restarted) goes home with a notice.
        code2, token2 = store.create("Cy")
        store.join(code2, "Dee")
        del store._rooms[code2]
        gone = self.page(room=code2, room_code=code2, seat_token=token2)
        warnings = [w.value for w in gone.warning]
        self.assertEqual(len(warnings), 1, warnings)
        self.assertIn("no longer available", warnings[0])
        self.assertNotIn("room", gone.query_params)


if __name__ == "__main__":
    unittest.main()
