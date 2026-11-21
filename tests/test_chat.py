"""
The chat of an online game (owner, 2026-11-19): "Also is it hard to add a chat during the
game? The chat should be deleted once the game is over". Messages are kept in the room's
memory only, never saved, and the move that ends the game deletes them.
"""

import os
import tempfile
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka.repository import FileRepository
from abaka.rooms import RoomError, RoomStore, TooFast, clean_message

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def started_game(store, names=("Ann", "Bob")):
    """An online game past the starting throw, nobody rolled yet. Returns code, tokens by seat."""
    code, first = store.create(names[0], players=len(names))
    tokens = [first] + [store.join(code, name) for name in names[1:]]
    for _ in range(100):
        engine = store.view(code).engine
        if not engine.choosing_first_player:
            break
        store.throw_for_start(code, tokens[engine.current])
    return code, tokens


def finish_game(store, code, tokens):
    """Play the game to its end with the first move offered each turn."""
    from abaka.moves import cross_options, score_options
    for _ in range(1000):
        engine = store.view(code).engine
        if engine.is_game_over():
            return
        token = tokens[engine.current]
        store.roll(code, token)
        engine = store.view(code).engine
        moves = score_options(engine)
        if moves:
            store.score(code, token, moves[0].category, moves[0].slot)
        else:
            move = cross_options(engine)[0]
            store.cross(code, token, move.category, move.slot)
    raise AssertionError("the game did not end")


class TestChatInTheStore(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore()
        self.code, self.tokens = started_game(self.store, ("Ann", "Bob", "Cy"))

    def test_a_message_reaches_the_room_but_is_not_a_move(self):
        version, seen = self.store.version(self.code), self.store.seen(self.code)
        self.store.say(self.code, self.tokens[2], "  hi   all ")
        self.assertEqual(self.store.version(self.code), version)
        self.assertNotEqual(self.store.seen(self.code), seen)
        view = self.store.view(self.code)
        self.assertEqual(view.seen, self.store.seen(self.code))
        self.assertEqual([(m["seat"], m["text"]) for m in view.chat], [(2, "hi all")])

    def test_anyone_seated_whatever_the_turn(self):
        for token in self.tokens:
            self.store.say(self.code, token, "hello")
        self.assertEqual([m["seat"] for m in self.store.view(self.code).chat], [0, 1, 2])
        with self.assertRaises(RoomError):
            self.store.say(self.code, "not-a-seat", "hello")

    def test_cleaned_and_cut(self):
        self.assertEqual(clean_message("a‮b\x00c​ d\n\ne"), "abc d e")
        self.assertEqual(len(clean_message("x" * 500)), rooms.MAX_MESSAGE_LENGTH)
        self.assertEqual(clean_message("hi \ud83d there\udc00"), "hi there")  # half a surrogate pair cannot be sent
        self.assertEqual(clean_message("hi \U0001F44B"), "hi \U0001F44B")  # a whole emoji is kept
        self.store.say(self.code, self.tokens[0], " ​\n ")  # nothing left: not sent
        self.store.say(self.code, self.tokens[0], "<b>hi</b> [x](http://e.vil)")  # kept as typed; escaped when shown
        self.assertEqual([m["text"] for m in self.store.view(self.code).chat], ["<b>hi</b> [x](http://e.vil)"])

    def test_about_one_message_a_second(self):
        now = [1000.0]
        with mock.patch("abaka.rooms.time.time", lambda: now[0]):
            for i in range(rooms.MESSAGES_PER_WINDOW):
                self.store.say(self.code, self.tokens[0], f"m{i}")
            with self.assertRaises(TooFast):
                self.store.say(self.code, self.tokens[0], "one too many")
            self.store.say(self.code, self.tokens[1], "another player is not held back")
            now[0] += rooms.MESSAGE_WINDOW_SECONDS
            self.store.say(self.code, self.tokens[0], "later")
        self.assertEqual(len(self.store.view(self.code).chat), rooms.MESSAGES_PER_WINDOW + 2)

    def test_only_the_latest_are_kept(self):
        now = [1000.0]
        with mock.patch("abaka.rooms.time.time", lambda: now[0]):
            for i in range(rooms.CHAT_KEPT + 10):
                now[0] += 5
                self.store.say(self.code, self.tokens[0], f"m{i}")
        chat = self.store.view(self.code).chat
        self.assertEqual(len(chat), rooms.CHAT_KEPT)
        self.assertEqual(chat[-1]["text"], f"m{rooms.CHAT_KEPT + 9}")

    def test_deleted_when_the_game_ends(self):
        self.store.say(self.code, self.tokens[0], "good luck")
        finish_game(self.store, self.code, self.tokens)
        self.assertEqual(self.store.view(self.code).chat, ())
        with self.assertRaises(RoomError):
            self.store.say(self.code, self.tokens[0], "gg")  # the game is over
        self.store.rematch(self.code, self.tokens[1])
        self.assertEqual(self.store.view(self.code).chat, ())  # a new game, a new chat
        self.store.say(self.code, self.tokens[1], "again")
        self.assertEqual(len(self.store.view(self.code).chat), 1)

    def test_not_before_the_game_nor_on_one_device(self):
        code, token = self.store.create("Ann", players=2)
        with self.assertRaises(RoomError):
            self.store.say(code, token, "anyone?")
        code, key = self.store.create_local(["Ann", "Bob"])
        self.store.say(code, key, "hi")
        self.assertEqual(self.store.view(code).chat, ())

    def test_never_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RoomStore(repository=FileRepository(folder))
            code, tokens = started_game(store)
            store.roll(code, tokens[store.view(code).engine.current])  # saved after this move
            store.say(code, tokens[0], "secret plan")
            self.assertNotIn("chat", store._rooms[code].to_data())
            for name in os.listdir(folder):
                if name.endswith(".json"):
                    with open(os.path.join(folder, name), encoding="utf-8") as f:
                        self.assertNotIn("secret plan", f.read())
            self.assertEqual(RoomStore(repository=FileRepository(folder)).view(code).chat, ())


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestChatOnTheScreens(unittest.TestCase):
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

        # AppTest 1.48 reads every button group's value as a list (see test_shown_dice.py).
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
    def html(at):
        return "\n".join(n.proto.body for n in at.get("html"))

    def test_a_message_reaches_the_other_screen_escaped(self):
        self.page()
        store = self.stores[-1]
        code, tokens = started_game(store, ("Ann", "Bob"))
        ann = self.page(room_code=code, seat_token=tokens[0])
        bob = self.page(room_code=code, seat_token=tokens[1])
        self.assertIn("No messages yet", self.html(bob))

        ann.text_input(key="chat-text").input("<img src=x onerror=alert(1)> hi [x](http://e.vil)")
        ann.button(key="FormSubmitter:chat-form-Send").click().run()
        self.assertEqual(len(store.view(code).chat), 1)
        bob.run()  # its poll noticed the message
        html = self.html(bob)
        self.assertIn("&lt;img src=x onerror=alert(1)&gt; hi", html)
        self.assertNotIn("<img src=x", html)
        toasts = " ".join(n.proto.body for n in bob.get("toast"))
        self.assertIn("Ann", toasts)
        self.assertNotIn("](http://e.vil)", toasts)  # Markdown escaped in the toast

    def test_the_chat_is_gone_when_the_game_ends(self):
        self.page()
        store = self.stores[-1]
        code, tokens = started_game(store, ("Ann", "Bob"))
        store.say(code, tokens[0], "good luck")
        ann = self.page(room_code=code, seat_token=tokens[0])
        self.assertIn("good luck", self.html(ann))
        finish_game(store, code, tokens)
        ann.run()
        self.assertNotIn("good luck", self.html(ann))
        self.assertFalse([w for w in ann.text_input if w.key == "chat-text"])


if __name__ == "__main__":
    unittest.main()
