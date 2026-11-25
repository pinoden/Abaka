"""
Monitoring and small costs (stage 0.10):

- the store's stats line: what it counts, and that it starts again from zero;
- no stats line unless asked for (tests and tools stay quiet), a failed save is a
  logged warning;
- "Continue a game" keeps at most MY_GAMES_KEPT games and opens no more saved games
  than it shows (through the real app script, skipped without Streamlit).
"""

import os
import tempfile
import time
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka.rooms import RoomStore
from abaka.rooms import full_code

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # e.g. the base Python 3.8 on the owner's machine
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def link(store, code):
    """A game's link: its full code (the code alone opens nothing)."""
    return full_code(code, store.view(code).key)


class TestStatsLine(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = tmp.name

    def report(self, store, code):
        """Pretend the period has passed; return the stats line the next poll writes."""
        store._counted_since -= store.report_every
        with self.assertLogs("abaka", level="INFO") as logs:
            store.version(code)
        self.assertEqual(len(logs.output), 1, logs.output)
        return logs.output[0]

    def test_the_stats_line_counts_what_happened_and_starts_again(self):
        store = RoomStore(save_dir=self.folder, report_every=60)
        code, key = store.create_local(["Ann", "Bob"])
        store.throw_for_start(code, key)
        store.view(code)
        store.version(code)
        line = self.report(store, code)
        for part in ("rooms in memory 1 (1 being played, 1 on one device)", "polls 2,", "page views 1,",
                     "moves 1,", "new games 1;", "saves 2 ("):
            self.assertIn(part, line)
        self.assertIn("polls 1,", self.report(store, code))  # counted again from zero

    def test_rooms_loaded_from_disk_and_leaving_memory_are_counted(self):
        store = RoomStore(save_dir=self.folder, report_every=60)
        code, _ = store.create_local(["Ann", "Bob"])
        store._rooms[code].last_seen = time.time() - rooms.IDLE_IN_MEMORY_SECONDS - 5
        with store._lock:
            store._sweep(force=True)
        store.view(code)  # loads it again
        line = self.report(store, code)
        self.assertIn("rooms loaded from disk 1, left memory 1;", line)

    def test_no_stats_line_unless_asked_for(self):
        store = RoomStore(save_dir=self.folder)
        code, _ = store.create("Ann")
        store._counted_since -= 10 ** 6
        with mock.patch.object(rooms.log, "info") as info:
            store.version(code)
        info.assert_not_called()

    def test_a_failed_save_is_a_logged_warning_and_counted(self):
        blocked = os.path.join(self.folder, "not-a-folder")
        open(blocked, "w").close()  # a file where the save folder should be
        store = RoomStore(save_dir=blocked, report_every=60)
        with self.assertLogs("abaka", level="WARNING") as logs:
            code, _ = store.create("Ann")
        self.assertIn("could not save game " + code, logs.output[0])
        self.assertIn("failed 1)", self.report(store, code))


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestContinueList(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": tmp.name})
        env.start()
        self.addCleanup(env.stop)
        self.stores = []
        stores = self.stores

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        code_version.mark_current()  # so the app uses these (patched) modules

    def home(self, **state):
        at = AppTest.from_file(APP, default_timeout=30)
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def test_the_list_opens_only_the_games_it_shows_and_forgets_gone_ones(self):
        import abaka_ui
        self.home()
        store = self.stores[0]
        games = [store.create_local(["Ann", "Bob"])[0] for _ in range(abaka_ui.MY_GAMES_SHOWN + 2)]
        store._rooms.clear()  # every game left memory; opening one reads it from disk
        my_games = ["GONE2"] + games
        at = self.home(my_games=my_games)
        shown = [b.key for b in at.button if b.key and b.key.startswith("continue-")]
        self.assertEqual(shown, ["continue-" + c for c in games[:abaka_ui.MY_GAMES_SHOWN]])
        self.assertEqual(sorted(store._rooms), sorted(games[:abaka_ui.MY_GAMES_SHOWN]))  # no others opened
        self.assertEqual(at.session_state["my_games"], games)  # the gone game is forgotten

    def test_a_browser_remembers_at_most_the_newest_games(self):
        import abaka_ui
        self.home()
        store = self.stores[0]
        older = ["OLD%02d" % i for i in range(abaka_ui.MY_GAMES_KEPT)]
        code, key = store.create_local(["Ann", "Bob"])
        at = AppTest.from_file(APP, default_timeout=30)
        at.query_params["room"] = link(store, code)  # opening a same-device game's link continues it
        at.session_state["my_games"] = older
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        self.assertEqual(at.session_state["my_games"], ([code] + older)[:abaka_ui.MY_GAMES_KEPT])


if __name__ == "__main__":
    unittest.main()
