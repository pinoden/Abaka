"""
Reactions and celebrations (owner, 2026-11-19): players of an online game send each other
reactions ("Lucky!", "GG", ...). Everyone sees effects as the dice land: bigger fireworks
for Abaka or the royal full house on the first roll, fireworks for either after a reroll,
sparkles for a straight, a full house or four of a kind on the first roll; and sparkles
when a move earns a row or column bonus. None of it is a move or saved.
"""

import os
import re
import tempfile
import time
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka.constants import COMBO_CATS, SCHOOL_CATS
from abaka.models import Category, Die
from abaka.repository import FileRepository
from abaka.rooms import REACTIONS, RoomError, RoomStore, TooFast

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

BUBBLE = '<div class="ab-bubble'
GRAND_HTML = '<div class="ab-fx-grand"'
SPARKLES_HTML = '<div class="ab-fx-small"'
APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def started_game(store, names=("Ann", "Bob")):
    """An online game past the starting throw, nobody rolled yet. Returns code, tokens by seat."""
    code, first = store.create(names[0], players=len(names))
    tokens = [first] + [store.join(code, name, store.view(code).key) for name in names[1:]]
    for _ in range(100):
        engine = store.view(code).engine
        if not engine.choosing_first_player:
            break
        store.throw_for_start(code, tokens[engine.current])
    return code, tokens


def dice(values):
    """Five dice showing `values`; the last one is the joker (wild when it shows 1)."""
    return [Die(v) for v in values[:4]] + [Die(values[4], is_joker=True)]


def throw(store, code, token, values):
    """The first roll of the turn, landing on `values`."""
    with mock.patch("abaka.engine.roll_dice", lambda: dice(values)):
        store.roll(code, token)


def reroll(store, code, token, indices, values):
    """A reroll of the dice at `indices`, landing on `values`."""
    with mock.patch("abaka.engine.random.randint", side_effect=list(values)):
        store.reroll(code, token, indices)


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

    def token(self):
        return self.tokens[self.store.view(self.code).engine.current]

    def events(self):
        return self.store.view(self.code).events

    def first_roll(self, values):
        """Roll, landing on `values`. Returns the effect that brought (None if none) and the token."""
        count, token = len(self.events()), self.token()
        throw(self.store, self.code, token, values)
        return (self.events()[-1] if len(self.events()) > count else None), token

    def end_turn(self, token):
        """Cross out a combination cell: never an effect."""
        engine = self.store.view(self.code).engine
        table = engine.players[engine.current].table
        category = next(c for c in COMBO_CATS if None in table[c][:3])
        self.store.cross(self.code, token, category, table[category][:3].index(None))

    def test_abaka_or_the_royal_full_house_on_the_first_roll_bring_bigger_fireworks(self):
        seat = self.store.view(self.code).engine.current
        event, token = self.first_roll([6, 6, 6, 6, 6])
        self.assertEqual((event["kind"], event["effect"], event["seat"], event["what"], event["first"]),
                         ("effect", rooms.GRAND_FIREWORKS, seat, "ABAKA", True))
        self.end_turn(token)
        # The royal full house, also with the joker's wild 1; Abaka with the joker.
        for values, what in (([1, 1, 1, 2, 2], "ROYAL"), ([2, 1, 1, 2, 1], "ROYAL"), ([3, 3, 3, 3, 1], "ABAKA")):
            event, token = self.first_roll(values)
            self.assertEqual((event["effect"], event["what"]), (rooms.GRAND_FIREWORKS, what), values)
            self.end_turn(token)

    def test_after_a_reroll_fireworks(self):
        event, token = self.first_roll([2, 2, 2, 2, 5])
        self.assertEqual((event["effect"], event["what"]), (rooms.SPARKLES, "KARE"))
        reroll(self.store, self.code, token, [4], [2])
        event = self.events()[-1]
        self.assertEqual((event["effect"], event["what"], event["first"]), (rooms.FIREWORKS, "ABAKA", False))
        self.end_turn(token)
        event, token = self.first_roll([1, 1, 1, 2, 6])  # three of a kind: nothing yet
        self.assertIsNone(event)
        reroll(self.store, self.code, token, [4], [2])
        self.assertEqual((self.events()[-1]["effect"], self.events()[-1]["what"]), (rooms.FIREWORKS, "ROYAL"))

    def test_first_roll_sparkles(self):
        for values, what in (([1, 2, 3, 4, 5], "SMALL_STRAIGHT"), ([6, 2, 3, 4, 5], "LARGE_STRAIGHT"),
                             ([3, 3, 5, 5, 3], "FULL"), ([4, 4, 4, 4, 2], "KARE"),
                             ([3, 3, 3, 5, 1], "KARE")):  # the wild joker makes four 3s (or a full house)
            event, token = self.first_roll(values)
            self.assertEqual((event["effect"], event["what"], event["first"]), (rooms.SPARKLES, what, True), values)
            self.end_turn(token)

    def test_nothing_for_other_throws(self):
        for values in ([3, 3, 3, 5, 6], [1, 2, 4, 5, 6], [6, 6, 5, 5, 4]):  # three of a kind, no straight, two pairs
            event, token = self.first_roll(values)
            self.assertIsNone(event, values)
            self.end_turn(token)
        event, token = self.first_roll([1, 2, 3, 4, 6])
        reroll(self.store, self.code, token, [4], [5])  # a straight, but not on the first roll
        self.assertEqual(self.events(), ())

    def test_the_effect_comes_with_the_throw_not_the_move(self):
        version = self.store.version(self.code)
        event, token = self.first_roll([5, 5, 5, 5, 5])
        self.assertEqual(self.store.version(self.code), version + 1)  # the throw, nothing more
        self.store.score(self.code, token, Category.ABAKA, 0)  # writing it down adds nothing
        self.assertEqual(self.events(), (event,))

    def test_the_starting_throw_brings_nothing(self):
        code, first = self.store.create("Ann", players=2)
        tokens = [first, self.store.join(code, "Bob", self.store.view(code).key)]
        with mock.patch("abaka.engine.roll_dice", lambda: dice([6, 6, 6, 6, 6])):
            for _ in range(6):  # every throw ties, so the starting throw goes on
                self.store.throw_for_start(code, tokens[self.store.view(code).engine.current])
        self.assertEqual(self.store.view(code).events, ())

    def table(self):
        """The table of the player whose turn it is, to set up before their move (tests only)."""
        engine = self.store._rooms[self.code].engine
        return engine.current, engine.players[engine.current].table

    def bonus_after(self, values, category, slot):
        """Roll `values`, write them into `category`, return the bonus effect of that move (or None)."""
        event, token = self.first_roll(values)
        count = len(self.events())
        self.store.score(self.code, token, category, slot)
        return self.events()[-1] if len(self.events()) > count else None

    def test_a_row_bonus_brings_sparkles(self):
        seat, table = self.table()
        table[Category.FULL][:2] = [19, 25]
        event = self.bonus_after([2, 2, 2, 6, 6], Category.FULL, 2)  # 36 on the first roll completes the row
        self.assertEqual((event["effect"], event["what"], event["seat"], event["rows"], event["columns"]),
                         (rooms.SPARKLES, "BONUS", seat, [("FULL", 36)], []))
        self.assertEqual(self.store.view(self.code).engine.players[seat].table[Category.FULL][3], 36)

    def test_a_school_row_bonus_too(self):
        seat, table = self.table()
        table[Category.SCHOOL_3][:2] = ["X", "X"]
        event = self.bonus_after([3, 3, 3, 5, 6], Category.SCHOOL_3, 2)  # exactly three 3s
        self.assertEqual(event["rows"], [("SCHOOL_3", 9)])

    def test_row_and_column_bonuses_in_one_move(self):
        seat, table = self.table()
        for category in Category:
            table[category][:3] = ["X"] * 3 if category in SCHOOL_CATS else [10, 10, 10]
        table[Category.FULL][2] = None
        event = self.bonus_after([2, 2, 2, 6, 6], Category.FULL, 2)  # completes the row and column III
        self.assertEqual((event["rows"], event["columns"]), ([("FULL", 36)], [(2, 36)]))

    def test_no_sparkles_for_a_crossed_out_bonus(self):
        seat, table = self.table()
        table[Category.FULL][:2] = [19, "X"]
        self.assertIsNone(self.bonus_after([2, 2, 2, 6, 6], Category.FULL, 2))  # the row is complete, its bonus X
        self.assertEqual(self.store.view(self.code).engine.players[seat].table[Category.FULL][3], "X")

    def test_same_device_games_celebrate_too(self):
        code, key = self.store.create_local(["Ann", "Bob"])
        for _ in range(100):
            if not self.store.view(code).engine.choosing_first_player:
                break
            self.store.throw_for_start(code, key)
        throw(self.store, code, key, [3, 3, 3, 3, 3])
        self.assertEqual(self.store.view(code).events[-1]["effect"], rooms.GRAND_FIREWORKS)

    def test_a_rematch_starts_without_events(self):
        self.first_roll([6, 6, 6, 6, 6])
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

    def test_bigger_fireworks_on_every_screen_once_as_the_dice_land(self):
        self.page()
        store = self.stores[-1]
        code, tokens = started_game(store, ("Ann", "Bob <i>"))
        pages = [self.page(room_code=code, seat_token=token) for token in tokens]
        mover = store.view(code).engine.current
        with mock.patch("abaka.engine.roll_dice", lambda: dice([6, 6, 6, 6, 6])):
            pages[mover].button(key="roll").click().run()  # the thrower's own page, in the same run
        pages[1 - mover].run()  # the other page's poll noticed the throw
        for page in pages:
            html = self.html(page)
            self.assertIn(GRAND_HTML, html)
            self.assertIn("Abaka!", html)
            self.assertIn("first roll", html)
            self.assertNotIn("Bob <i>", html)  # names are escaped
            # It waits for the dice to land (their spin), then plays.
            self.assertGreater(float(re.search(r'class="ab-fx-item" style="--d:(-?[\d.]+)s"', html).group(1)), 0)
        # A page that opens the game afterwards (a reload, a new session) does not show it again.
        later = self.page(room_code=code, seat_token=tokens[0])
        self.assertNotIn(GRAND_HTML, self.html(later))
        # Nor does a page that has shown it for its full length.
        event_id = store.view(code).events[-1]["id"]
        state = dict(pages[0].session_state["fx_state"])
        state["starts"] = {event_id: time.time() - 10}
        pages[0].session_state["fx_state"] = state
        pages[0].run()
        self.assertNotIn(GRAND_HTML, self.html(pages[0]))

    def test_a_bonus_shows_what_it_earned(self):
        self.page()
        store = self.stores[-1]
        code, tokens = started_game(store)
        engine = store._rooms[code].engine
        mover = engine.current
        engine.players[mover].table[Category.FULL][:2] = [19, 25]
        page = self.page(room_code=code, seat_token=tokens[mover], lang="ru")
        throw(store, code, tokens[mover], [2, 2, 2, 6, 6])
        store.score(code, tokens[mover], Category.FULL, 2)
        page.run()
        html = self.html(page)
        self.assertIn(SPARKLES_HTML, html)
        self.assertIn("Бонус!", html)
        self.assertIn("строка «Фулл-хаус» +36", html)
        # The full house thrown, then the bonus: one after the other, never on top of each other.
        from ui_components.effects import SECONDS
        delays = [float(d) for d in re.findall(r'class="ab-fx-item" style="--d:(-?[\d.]+)s"', html)]
        self.assertEqual(len(delays), 2)
        self.assertAlmostEqual(delays[1] - delays[0], SECONDS[rooms.SPARKLES], places=1)

    def test_no_reaction_buttons_on_one_device(self):
        self.page()
        store = self.stores[-1]
        code, key = store.create_local(["Ann", "Bob"])
        at = self.page(room_code=code, seat_token=key)
        self.assertFalse([b for b in at.button if (b.key or "").startswith("react-")])


if __name__ == "__main__":
    unittest.main()
