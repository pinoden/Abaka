"""
Player names are shown to other players, so they must never turn into links, images or
formatting. HTML places use html.escape (see the scoreboard tests); Markdown places
(captions, toasts, button labels) use i18n.md(). Invisible characters are removed.
"""

import os
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka.rooms import clean_name
from abaka.i18n import md
from abaka.rooms import full_code

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # e.g. the base Python 3.8 on the owner's machine
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")
IMAGE = "![i](http://e.vil/a)"
LINK = "[x](http://e.vil)"


def link(store, code):
    """A game's link: its full code (the code alone opens nothing)."""
    return full_code(code, store.view(code).key)


class TestMarkdownEscaping(unittest.TestCase):
    def test_links_images_and_formatting_stay_text(self):
        z = "​"  # zero-width space: breaks bare addresses up, invisible
        self.assertEqual(md(IMAGE), r"\!\[i\]\(http\:" + z + r"//e\." + z + r"vil/a\)")
        self.assertEqual(md(LINK), r"\[x\]\(http\:" + z + r"//e\." + z + r"vil\)")
        self.assertEqual(md("**b** _i_ `c` $x$"), r"\*\*b\*\* \_i\_ \`c\` \$x\$")
        self.assertEqual(md(":red[x]"), r"\:" + z + r"red\[x\]")
        for address in ("www.e.vil", "http://e.vil", "a@e.vil"):
            self.assertNotIn(address, md(address).replace("\\", "").replace(z, "|"))
        self.assertEqual(md("Аня Ann 2"), "Аня Ann 2")  # ordinary names are unchanged

    def test_half_a_surrogate_pair_is_removed(self):
        """JSON can carry half a pair, UTF-8 cannot: a name holding one could be neither shown nor saved."""
        self.assertEqual(clean_name("Ann\ud83d Lee\udc00", "P"), "Ann Lee")
        self.assertEqual(clean_name("\ud800", "Player 1"), "Player 1")
        self.assertEqual(clean_name("Ann \U0001F3B2", "P"), "Ann \U0001F3B2")  # a whole emoji is kept
        clean_name("Ann\ud83d \U0001F3B2", "P").encode("utf-8")  # can be sent and saved

    def test_invisible_and_control_characters_are_removed(self):
        self.assertEqual(clean_name("Ann‮​\x07 Lee", "P"), "Ann Lee")
        self.assertEqual(clean_name("​‮", "Player 1"), "Player 1")


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestNamesInTheApp(unittest.TestCase):
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

    def page(self, room=None, **state):
        at = AppTest.from_file(APP, default_timeout=30)
        if room:
            at.query_params["room"] = room
        for key, value in state.items():
            at.session_state[key] = value
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    def test_hostile_names_reach_markdown_escaped(self):
        self.page()
        store = self.stores[-1]
        code, host = store.create(IMAGE)
        store.join(code, LINK, store.view(code).key)

        # A visitor sees "Rejoin as" buttons with both names: escaped.
        labels = [b.label for b in self.page(room=link(store, code)).button if b.key and b.key.startswith("rejoin-")]
        self.assertEqual(labels, [md(IMAGE), md(LINK)])

        # The guest waits while the host throws: the caption names the host, escaped.
        guest = store.reclaim(code, 1, store.view(code).key)
        captions = [c.value for c in self.page(room=code, room_code=code, seat_token=guest).caption]
        self.assertTrue(any(md(IMAGE) in c for c in captions), captions)
        self.assertFalse(any(IMAGE in c for c in captions), captions)

        # A same-device game: the Throw button names the player, escaped.
        local, _ = store.create_local([LINK, "Bob"])
        at = self.page(room=link(store, local))
        self.assertEqual(at.button(key="start-throw").label, "Throw for " + md(LINK))


if __name__ == "__main__":
    unittest.main()
