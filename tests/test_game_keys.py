"""
A game opens only with its key (owner, 2026-11-25, Backlog item 31): "one shouldn't be able to
enter a game just knowing the code". A game's link and its full code carry the key
("K7M2Q-8XJ4PN2R"); the code alone, seen on a screen or guessed, opens nothing, and a wrong
key is answered exactly as a game that does not exist.
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka import api
from abaka.api import ApiError
from abaka.rooms import CODE_ALPHABET, KEY_LENGTH, RoomError, RoomStore, full_code, split_code

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # Streamlit is not installed (the engine's own Python 3.8 run)
    AppTest = None

APP = str(Path(__file__).resolve().parent.parent / "abaka_ui.py")
NOT_FOUND = "Game not found. Check the code, or ask for a new invite."


def wrong(key):
    """Another key that differs from `key` in one character."""
    return ("A" if key[0] != "A" else "B") + key[1:]


class TestKeys(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore(starting_throw=False)
        self.code, self.ann = self.store.create("Ann", players=3)
        self.key = self.store.view(self.code).key

    def refused(self, act):
        with self.assertRaises(RoomError) as caught:
            act()
        return str(caught.exception)

    def test_every_game_has_a_key_of_its_own(self):
        local, _ = self.store.create_local(["Ann", "Bob"])
        keys = {self.key, self.store.view(local).key}
        self.assertEqual(len(keys), 2)
        for key in keys:
            self.assertEqual(len(key), KEY_LENGTH)
            self.assertTrue(set(key) <= set(CODE_ALPHABET))

    def test_a_code_alone_or_a_wrong_key_opens_nothing(self):
        for key in (None, "", wrong(self.key), self.key[:-1], self.key + "A", self.code):
            with self.subTest(key=key):
                self.assertEqual(self.refused(lambda: self.store.join(self.code, "Eve", key)), NOT_FOUND)
                self.assertEqual(self.refused(lambda: self.store.reclaim(self.code, 0, key)), NOT_FOUND)
                self.assertFalse(self.store.opens(self.code, key))
        self.assertEqual(self.store.view(self.code).names, ["Ann"])  # nobody got in
        self.assertEqual(self.store.seat_of(self.code, self.ann), 0)  # and Ann's seat is still hers

    def test_a_wrong_key_is_told_what_a_missing_game_is_told(self):
        missing = self.refused(lambda: self.store.join("ZZZZZ", "Eve", self.key))
        self.assertEqual(self.refused(lambda: self.store.join(self.code, "Eve", wrong(self.key))), missing)

    def test_the_key_opens_the_game_however_it_is_typed(self):
        for key in (self.key, self.key.lower(), " " + self.key[:4] + " " + self.key[4:]):
            with self.subTest(key=key):
                self.assertTrue(self.store.opens(self.code, key))
        bob = self.store.join(self.code.lower(), "Bob", self.key.lower())
        self.assertEqual(self.store.seat_of(self.code, bob), 1)
        new = self.store.reclaim(self.code, 1, self.key)
        self.assertIsNone(self.store.seat_of(self.code, bob))  # the old token lost the seat
        self.assertEqual(self.store.seat_of(self.code, new), 1)

    def test_a_same_device_game_continues_only_with_its_key(self):
        local, token = self.store.create_local(["Ann", "Bob"])
        key = self.store.view(local).key
        self.assertEqual(self.refused(lambda: self.store.resume_local(local, None)), NOT_FOUND)
        self.assertEqual(self.refused(lambda: self.store.resume_local(local, wrong(key))), NOT_FOUND)
        self.assertEqual(self.store.resume_local(local, key), token)

    def test_a_seat_needs_no_key(self):
        """A player already seated plays with the seat's token, as before."""
        bob = self.store.join(self.code, "Bob", self.key)
        self.store.start_now(self.code, self.ann)
        self.store.roll(self.code, self.ann)
        self.store.say(self.code, bob, "hi")
        self.assertEqual([m["text"] for m in self.store.view(self.code).chat], ["hi"])


class TestFullCode(unittest.TestCase):
    def test_what_players_type_or_paste(self):
        cases = {
            "K7M2Q-8XJ4PN2R": ("K7M2Q", "8XJ4PN2R"),
            " k7m2q 8xj4 pn2r ": ("K7M2Q", "8XJ4PN2R"),
            "K7M2Q8XJ4PN2R": ("K7M2Q", "8XJ4PN2R"),
            "https://mipt-abaka.streamlit.app/?room=K7M2Q-8XJ4PN2R": ("K7M2Q", "8XJ4PN2R"),
            "https://example.org/?lang=ru&room=k7m2q-8xj4pn2r#top": ("K7M2Q", "8XJ4PN2R"),
            "https://example.org/?room=K7M2Q%2D8XJ4PN2R": ("K7M2Q", "8XJ4PN2R"),
            "K7M2Q": ("K7M2Q", ""),  # a code alone
            "https://mipt-abaka.streamlit.app/?room=K7M2Q": ("K7M2Q", ""),  # a link from before keys
            "": ("", ""),
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertEqual(split_code(text), expected)
        self.assertEqual(full_code("K7M2Q", "8XJ4PN2R"), "K7M2Q-8XJ4PN2R")


class TestSavedGames(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name

    def test_the_key_is_saved_with_the_game(self):
        a = RoomStore(save_dir=self.dir)
        code, _ = a.create("Ann")
        key = a.view(code).key
        b = RoomStore(save_dir=self.dir)  # a restart, or a code update
        self.assertEqual(b.view(code).key, key)
        self.assertFalse(b.opens(code, wrong(key)))
        self.assertTrue(b.opens(code, key))

    def test_a_game_saved_before_games_had_keys_gets_one_that_lasts(self):
        a = RoomStore(save_dir=self.dir)
        code, token = a.create_local(["Ann", "Bob"])
        path = Path(self.dir) / f"{code}.json"
        data = json.loads(path.read_text())
        del data["key"]  # as the code before this change saved it
        path.write_text(json.dumps(data))

        b = RoomStore(save_dir=self.dir)
        key = b.view(code).key
        self.assertEqual(len(key), KEY_LENGTH)
        self.assertEqual(json.loads(path.read_text())["key"], key)  # saved at once
        self.assertEqual(RoomStore(save_dir=self.dir).view(code).key, key)  # the next load keeps it
        self.assertEqual(b.resume_local(code, key), token)


class TestApi(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore(starting_throw=False)
        made = self.call(op="create", name="Ann", players=3)
        self.code, self.ann, self.key = made["code"], made["token"], made["state"]["key"]

    def call(self, **request):
        return api.handle(request, self.store)

    def refused(self, **request):
        with self.assertRaises(ApiError) as caught:
            self.call(**request)
        return caught.exception.code, caught.exception.message

    def test_the_players_get_the_key_in_the_state(self):
        self.assertEqual(self.key, self.store.view(self.code).key)
        state = self.call(op="state", code=self.code, token=self.ann)["state"]
        self.assertEqual((state["seated"], state["key"]), (True, self.key))

    def test_without_the_key_the_game_is_not_there(self):
        missing = self.refused(op="state", code="ZZZZZ", key=self.key)
        for key in ({}, {"key": wrong(self.key)}, {"key": ""}):
            for op, extra in (("state", {}), ("seen", {}), ("join", {"name": "Eve"}), ("rejoin", {"seat": 0}),
                              ("resume", {})):
                with self.subTest(op=op, key=key):
                    self.assertEqual(self.refused(op=op, code=self.code, **key, **extra), missing)
        self.assertEqual(self.refused(op="state", code=self.code, token="not a seat's token"), missing)
        self.assertEqual(self.store.view(self.code).names, ["Ann"])

    def test_with_the_key_or_the_full_code(self):
        outsider = self.call(op="state", code=self.code, key=self.key)["state"]
        self.assertEqual((outsider["seated"], outsider["can"]), (False, ["join", "rejoin"]))
        self.assertIn("seen", self.call(op="seen", code=self.code, key=self.key.lower()))
        bob = self.call(op="join", code=full_code(self.code, self.key), name="Bob")
        self.assertEqual(bob["state"]["you"], 1)
        again = self.call(op="rejoin", code=full_code(self.code, self.key).lower(), seat=1)
        self.assertEqual(again["state"]["you"], 1)
        # A token that lost its seat still sees the invite, with the key: to offer taking it back.
        lost = self.call(op="state", code=self.code, token=bob["token"], key=self.key)["state"]
        self.assertEqual((lost["seated"], lost["can"]), (False, ["join", "rejoin"]))


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestPages(unittest.TestCase):
    def setUp(self):
        stores = self.stores = []

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

    def page(self, room=None, **state):
        at = AppTest.from_file(APP, default_timeout=30)
        if room is not None:
            at.query_params["room"] = room
        for name, value in state.items():
            at.session_state[name] = value
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        return at

    @staticmethod
    def html(at):
        return "\n".join(n.proto.body for n in at.get("html"))

    def game(self):
        self.page()
        store = self.stores[-1]
        code, ann = store.create("Ann <b>")
        return store, code, ann, store.view(code).key

    def test_a_code_alone_shows_nothing_of_the_game(self):
        store, code, _, key = self.game()
        for room, title in ((code, "This link is not complete"), (full_code(code, wrong(key)), "Game not found")):
            with self.subTest(room=room):
                at = self.page(room=room)
                html = self.html(at)
                self.assertIn(title, html)
                self.assertNotIn("Ann", html)
                self.assertFalse([b for b in at.button if b.key and b.key.startswith("rejoin-")])
                self.assertFalse([w for w in at.text_input if w.key == "join_name"])
        self.assertIn("This link is not complete", self.html(self.page(room="ZZZZZ")))  # no game: the same page

    def test_the_full_link_invites(self):
        store, code, _, key = self.game()
        at = self.page(room=full_code(code, key).lower())
        self.assertIn("Ann &lt;b&gt; invited you to play", self.html(at))
        at.text_input(key="join_name").input("Bob")
        at.button(key="FormSubmitter:join_game-Join game").click().run()
        self.assertEqual(store.view(code).names, ["Ann <b>", "Bob"])

    def test_the_home_page_opens_a_game_only_by_its_full_code(self):
        store, code, _, key = self.game()
        home = self.page()
        home.text_input(key="find_code").input(code)
        home.button(key="FormSubmitter:find_game-Open game").click().run()
        self.assertIn("only the first part", " ".join(e.value for e in home.error))
        self.assertFalse(home.query_params.get("room"))
        home.text_input(key="find_code").input(f"https://example.org/?room={full_code(code, key)}")
        home.button(key="FormSubmitter:find_game-Open game").click().run()
        room = home.query_params["room"]
        self.assertEqual(room[0] if isinstance(room, list) else room, full_code(code, key))

    def test_the_waiting_room_shares_the_full_code(self):
        store, code, ann, key = self.game()
        at = self.page(room=code, room_code=code, seat_token=ann)
        html = self.html(at)
        self.assertIn("".join(f"<span>{c}</span>" for c in key), html)
        room = at.query_params["room"]  # the address bar now holds the link, for a reload
        self.assertEqual(room[0] if isinstance(room, list) else room, full_code(code, key))


if __name__ == "__main__":
    unittest.main()
