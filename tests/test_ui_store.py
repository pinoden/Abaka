"""
The shared room store across code updates, through the real app script.

Streamlit Community Cloud applies a new commit by reloading the app's modules while
keeping cached objects. A RoomStore made by the old code must not be handed to the
new code. Uses Streamlit's AppTest, so it is skipped where Streamlit is not installed.
"""

import os
import unittest
from unittest import mock

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
        self.enterContext_env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": ""})  # no saving to disk
        self.enterContext_env.start()
        self.addCleanup(self.enterContext_env.stop)
        # A RoomStore class of this test's own (as after a fresh start) that records each store made.
        self.stores = []
        stores = self.stores

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
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
        # The old store is retired: nothing keeps it (or its rooms) in memory, and pages
        # still running the old code get the new store.
        self.assertEqual(old_store.version(code), -1)
        self.assertEqual(old_store._rooms, {})
        # The game held by the old store is gone, and the player is told so.
        self.assertIn("no longer available", " ".join(w.value for w in at.warning))
        self.page()
        self.assertEqual(len(self.stores), 2, "the new store is shared from then on")


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestRenderingLeavesTheGameAlone(unittest.TestCase):
    """Views share the room's engine (no copy): drawing the page must never change it."""

    def setUp(self):
        self.stores = []
        stores = self.stores

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        code_version.mark_current()

    def test_drawing_every_phase_changes_nothing(self):
        from abaka.saving import engine_to_data
        first = AppTest.from_file(APP, default_timeout=30)
        first.run()
        store = self.stores[-1]
        code, key = store.create_local(["Ann", "Bob", "Cy"])
        phases = 0
        for step in range(12):  # starting throw, turns with dice (move previews), moves
            engine = store.view(code).engine
            before = engine_to_data(engine)
            at = AppTest.from_file(APP, default_timeout=30)
            at.query_params["room"] = code
            at.run()
            self.assertFalse(at.exception, [e.value for e in at.exception])
            self.assertIs(store.view(code).engine, engine)  # no action happened
            self.assertEqual(engine_to_data(engine), before)  # and nothing was changed in place
            phases += 1
            if engine.choosing_first_player:
                store.throw_for_start(code, key)
            elif not engine.dice:
                store.roll(code, key)
            else:
                from abaka.moves import cross_options, score_options
                move = (score_options(engine) or cross_options(engine))[0]
                (store.cross if move.cross else store.score)(code, key, move.category, move.slot)
        self.assertEqual(phases, 12)


if __name__ == "__main__":
    unittest.main()
