"""
Reactions and celebrations (owner, 2026-11-19): players of an online game send each other
reactions ("Lucky!", "GG", ...); everyone sees fireworks when someone scores Abaka, and
sparkles for a straight, four of a kind or the royal full house scored on the first roll.
None of it is a move or saved.
"""

import os
import tempfile
import time
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka.models import Category, Die
from abaka.repository import FileRepository
from abaka.rooms import REACTIONS, RoomError, RoomStore, TooFast

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

BUBBLE = '<div class="ab-bubble'
FIREWORKS_HTML = '<div class="ab-fx-big"'
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


def roll(store, code, tokens, values, reroll=False):
    """The player whose turn it is rolls, and the dice show `values` (the last one is the joker,
    never a wild 1 here). With `reroll`, after a reroll (no longer the first roll)."""
    current = store.view(code).engine.current
    token = tokens[current] if tokens else store.resume_local(code)
    store.roll(code, token)
    if reroll:
        store.reroll(code, token, [0])
    engine = store._rooms[code].engine  # the dice the roll "happened" to show
    engine.dice = [Die(v) for v in values[:4]] + [Die(values[4], is_joker=True)]
    return token


class TestReactionsInTheStore(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore()
        self.code, self.tokens = started_game(self.store, ("Ann", "Bob", "Cy"))

    def test_a_reaction_reaches_the_room_but_is_not_a_move(self):
        version, seen = self.store.version(self.code), self.store.seen(self.code)
        self.store.react(self.code, self.tokens[1], "lucky")
        self.assertEqual(self.store.version(self.code), version)
        self.assertNotEqual(self.store.seen(self.code), seen)
        view = self.store.view(self.code)
        self.assertEqual(view.seen, self.store.seen(self.code))
        event = view.events[-1]
        self.assertEqual((event["kind"], event["seat"], event["to"], event["reaction"]),
                         ("reaction", 1, None, "lucky"))

    def test_aimed_at_one_player(self):
        self.store.react(self.code, self.tokens[0], "gg", to=2)
        self.assertEqual(self.store.view(self.code).events[-1]["to"], 2)
        self.store.react(self.code, self.tokens[1], "gg", to=1)  # at yourself: to everyone
        self.store.react(self.code, self.tokens[2], "gg", to=7)  # no such seat: to everyone
        self.assertEqual([e["to"] for e in self.store.view(self.code).events[-2:]], [None, None])

    def test_anyone_seated_may_react_whatever_the_turn(self):
        for token in self.tokens:
            self.store.react(self.code, token, "wow")
        self.assertEqual(len(self.store.view(self.code).events), 3)

    def test_refused(self):
        with self.assertRaises(RoomError):
            self.store.react(self.code, "not-a-seat", "lucky")
        with self.assertRaises(RoomError):
            self.store.react(self.code, self.tokens[0], "<script>")
        self.assertEqual(self.store.view(self.code).events, ())

    def test_one_reaction_every_two_seconds_per_seat(self):
        now = [1000.0]
        with mock.patch("abaka.rooms.time.time", lambda: now[0]):
            self.store.react(self.code, self.tokens[0], "lucky")
            with self.assertRaises(TooFast):
                self.store.react(self.code, self.tokens[0], "nice")
            self.store.react(self.code, self.tokens[1], "nice")  # another seat is not held back
            now[0] += rooms.REACTION_EVERY_SECONDS
            self.store.react(self.code, self.tokens[0], "haha")
        self.assertEqual([e["reaction"] for e in self.store.view(self.code).events], ["lucky", "nice", "haha"])

    def test_ids_grow_and_only_the_latest_are_kept(self):
        now = [1000.0]
        with mock.patch("abaka.rooms.time.time", lambda: now[0]):
            for i in range(rooms.EVENTS_KEPT + 5):
                now[0] += 3
                self.store.react(self.code, self.tokens[0], REACTIONS[i % len(REACTIONS)])
        ids = [e["id"] for e in self.store.view(self.code).events]
        self.assertEqual(len(ids), rooms.EVENTS_KEPT)
        self.assertEqual(ids, sorted(set(ids)))

    def test_same_device_games_have_no_reactions(self):
        code, key = self.store.create_local(["Ann", "Bob"])
        self.store.react(code, key, "lucky")
        self.assertEqual(self.store.view(code).events, ())

    def test_never_saved(self):
        with tempfile.TemporaryDirectory() as folder:
            store = RoomStore(repository=FileRepository(folder))
            code, tokens = started_game(store)
            store.react(code, tokens[0], "gg")
            self.assertNotIn("events", store._rooms[code].to_data())
            again = RoomStore(repository=FileRepository(folder))  # after a restart or a code update
            self.assertEqual(again.view(code).events, ())
            again.react(code, tokens[1], "gg")
            self.assertEqual(len(again.view(code).events), 1)


class TestCelebrations(unittest.TestCase):
    def setUp(self):
        self.store = RoomStore()
        self.code, self.tokens = started_game(self.store)

    def score(self, values, category, reroll=False):
        token = roll(self.store, self.code, self.tokens, values, reroll)
        self.store.score(self.code, token, category, 0)
        events = self.store.view(self.code).events
        return events[-1] if events else None

    def test_abaka_brings_fireworks(self):
        seat = self.store.view(self.code).engine.current
        event = self.score([6, 6, 6, 6, 6], Category.ABAKA)
        self.assertEqual((event["kind"], event["effect"], event["seat"], event["category"], event["score"]),
                         ("effect", rooms.FIREWORKS, seat, "ABAKA", 160))

    def test_abaka_after_a_reroll_too(self):
        self.assertEqual(self.score([2, 2, 2, 2, 2], Category.ABAKA, reroll=True)["effect"], rooms.FIREWORKS)

    def test_first_roll_hits_bring_sparkles(self):
        for values, category in (([1, 2, 3, 4, 5], Category.SMALL_STRAIGHT), ([6, 2, 3, 4, 5], Category.LARGE_STRAIGHT),
                                 ([4, 4, 4, 4, 2], Category.KARE), ([1, 1, 1, 2, 2], Category.FULL)):
            event = self.score(values, category)
            self.assertEqual((event["effect"], event["category"]), (rooms.SPARKLES, category.name))
        self.assertEqual(event["score"], 114)  # the royal full house, doubled

    def test_nothing_for_ordinary_moves(self):
        self.assertIsNone(self.score([3, 3, 3, 5, 5], Category.FULL))  # a full house, not the royal one
        self.assertIsNone(self.score([1, 2, 3, 4, 5], Category.SMALL_STRAIGHT, reroll=True))  # not the first roll
        self.assertIsNone(self.score([6, 6, 6, 6, 6], Category.SUM))
        token = roll(self.store, self.code, self.tokens, [1, 2, 4, 5, 6])
        self.store.cross(self.code, token, Category.ABAKA, 0)  # crossed out
        self.assertEqual(self.store.view(self.code).events, ())

    def test_a_celebration_is_part_of_the_move(self):
        version = self.store.version(self.code)
        self.score([5, 5, 5, 5, 5], Category.ABAKA)
        self.assertEqual(self.store.version(self.code), version + 2)  # the roll and the move, nothing more

    def test_same_device_games_celebrate_too(self):
        code, key = self.store.create_local(["Ann", "Bob"])
        for _ in range(100):
            if not self.store.view(code).engine.choosing_first_player:
                break
            self.store.throw_for_start(code, key)
        roll(self.store, code, None, [3, 3, 3, 3, 3])
        self.store.score(code, key, Category.ABAKA, 0)
        self.assertEqual(self.store.view(code).events[-1]["effect"], rooms.FIREWORKS)

    def test_a_rematch_starts_without_events(self):
        self.score([6, 6, 6, 6, 6], Category.ABAKA)
        room = self.store._rooms[self.code]
        last = room.last_event_id
        room.engine.is_game_over = lambda: True  # as if the game had ended
        self.store.rematch(self.code, self.tokens[0])
        self.assertEqual(self.store.view(self.code).events, ())
        self.store.react(self.code, self.tokens[0], "gg")
        self.assertGreater(self.store.view(self.code).events[-1]["id"], last)


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestOnTheScreens(unittest.TestCase):
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

    def test_a_reaction_shows_on_every_screen(self):
        self.page()
        store = self.stores[-1]
        code, tokens = started_game(store)
        ann = self.page(room_code=code, seat_token=tokens[0])
        bob = self.page(room_code=code, seat_token=tokens[1])
        self.assertNotIn(BUBBLE, self.html(bob))

        ann.button(key="react-lucky").click().run()
        self.assertEqual(store.view(code).events[-1]["reaction"], "lucky")
        self.assertIn(BUBBLE, self.html(ann))  # the sender sees it too
        bob.run()  # its poll noticed the reaction
        bubble = self.html(bob)
        self.assertIn("Lucky!", bubble)
        self.assertIn("<b>Ann</b>", bubble)

        ann.button(key="react-gg").click().run()  # too soon: a gentle note, nothing sent
        self.assertEqual(len(store.view(code).events), 1)
        self.assertIn("One reaction every two seconds", " ".join(n.proto.body for n in ann.get("toast")))

    def test_fireworks_on_every_screen_once(self):
        self.page()
        store = self.stores[-1]
        code, tokens = started_game(store, ("Ann", "Bob <i>"))
        pages = [self.page(room_code=code, seat_token=token) for token in tokens]
        token = roll(store, code, tokens, [6, 6, 6, 6, 6])
        store.score(code, token, Category.ABAKA, 0)
        for page in pages:
            page.run()
            html = self.html(page)
            self.assertIn(FIREWORKS_HTML, html)
            self.assertIn("+160", html)
            self.assertNotIn("Bob <i>", html)  # names are escaped
        # A page that opens the game afterwards (a reload, a new session) does not show it again.
        later = self.page(room_code=code, seat_token=tokens[0])
        self.assertNotIn(FIREWORKS_HTML, self.html(later))
        # Nor does a page that has shown it for its full length.
        event_id = store.view(code).events[-1]["id"]
        state = dict(pages[0].session_state["fx_state"])
        state["first_seen"] = {event_id: time.time() - 10}
        pages[0].session_state["fx_state"] = state
        pages[0].run()
        self.assertNotIn(FIREWORKS_HTML, self.html(pages[0]))

    def test_no_reaction_buttons_on_one_device(self):
        self.page()
        store = self.stores[-1]
        code, key = store.create_local(["Ann", "Bob"])
        at = self.page(room_code=code, seat_token=key)
        self.assertFalse([b for b in at.button if (b.key or "").startswith("react-")])


if __name__ == "__main__":
    unittest.main()
