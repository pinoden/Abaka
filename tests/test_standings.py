"""
How the players stand (a tester, 2026-11-26, Backlog item 32): the difference row by row ("how
much you are losing in each row"), and every player's total after each move, for a chart of the
scores by move "like a chess game's". abaka/standings.py works them out; the web page draws them
under a switch and under the board, and the API sends them to apps.
"""

import os
import random
import re
import unittest
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka import api
from abaka.engine import GameEngine
from abaka.i18n import set_language
from abaka.models import Category as C
from abaka.moves import cross_options, score_options
from abaka.rooms import RoomStore
from abaka.saving import engine_from_data, engine_to_data
from abaka.standings import row_differences, score_history

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def write(g, seat, cat, slot, value):
    """Seat `seat` writes `value` in a cell ("X": crosses it out), as a move would."""
    g.current = seat
    if value == "X":
        g.record_cross(cat, slot)
    else:
        g.players[seat].record(cat, slot, value)
        g.last_move = (seat, cat, slot)
        g._after_record(cat, slot)
        g._end_turn()


def play(g, moves, rng):
    for _ in range(moves):
        g.start_turn()
        move = rng.choice(score_options(g) or cross_options(g))
        (g.record_cross if move.cross else g.record_score)(move.category, move.slot)


class TestDifferences(unittest.TestCase):
    def setUp(self):
        self.addCleanup(set_language, "en")

    def test_two_players_row_by_row(self):
        g = GameEngine(["Ann", "Bob"])
        write(g, 0, C.SUM, 0, 20)
        write(g, 1, C.SUM, 0, 26)
        write(g, 0, C.PAIR, 0, 12)
        write(g, 1, C.PAIR, 0, "X")
        d = row_differences(g, 0)
        self.assertEqual((d["seat"], d["rows"]["SUM"], d["rows"]["PAIR"], d["rows"]["ABAKA"]), (0, -6, 12, None))
        self.assertEqual(d["total"], g.players[0].calculate_score() - g.players[1].calculate_score())
        self.assertEqual(d["columns"], 0)
        self.assertEqual(d["hint"], "Your points in each row minus Bob's")
        self.assertEqual(row_differences(g, 1)["rows"]["SUM"], 6)

    def test_a_row_bonus_counts_in_its_row(self):
        g = GameEngine(["Ann", "Bob"])
        for slot in range(3):
            write(g, 0, C.SUM, slot, 20)
        self.assertIsInstance(g.players[0].table[C.SUM][3], int)  # Ann completed Sum first: its bonus
        self.assertEqual(row_differences(g, 0)["rows"]["SUM"], 60 + g.players[0].table[C.SUM][3])

    def test_three_players_against_the_best_of_the_others(self):
        g = GameEngine(["Ann", "Bob", "Cid"])
        for seat, value in ((0, 20), (1, 25), (2, 22)):
            write(g, seat, C.SUM, 0, value)
        self.assertEqual(row_differences(g, 0)["rows"]["SUM"], -5)
        self.assertEqual(row_differences(g, 1)["rows"]["SUM"], 3)
        self.assertEqual(row_differences(g, 2)["hint"], "Your points in each row minus the best of the others'")

    def test_one_shared_screen_reads_it_for_whose_turn_it_is(self):
        g = GameEngine(["Ann", "Bob"])
        write(g, 0, C.SUM, 0, 20)
        self.assertEqual(g.current, 1)
        d = row_differences(g, None)
        self.assertEqual((d["seat"], d["rows"]["SUM"]), (1, -20))
        self.assertEqual(d["hint"], "Bob's points in each row minus Ann's")
        set_language("ru")
        self.assertEqual(row_differences(g, None)["hint"], "Очки игрока Bob в каждой строке минус очки игрока Ann")

    def test_nothing_during_the_starting_throw_or_on_a_shared_screen_after_the_game(self):
        self.assertIsNone(row_differences(GameEngine(["Ann", "Bob"], starting_throw=True), 0))
        g = GameEngine(["Ann", "Bob"])
        play(g, 2 * 45, random.Random(3))
        self.assertTrue(g.is_game_over())
        self.assertIsNone(row_differences(g, None))
        self.assertEqual(row_differences(g, 1)["total"], g.players[1].calculate_score() - g.players[0].calculate_score())

    def test_two_players_differences_add_up_to_the_total(self):
        """Every point is in a row, a column bonus or the School penalty, so with two players the
        rows and columns add up to the total's difference, the penalty aside."""
        rng = random.Random(11)
        for _ in range(10):
            g = GameEngine(["Ann", "Bob"])
            while not g.is_game_over():
                play(g, 1, rng)
                d = row_differences(g, 0) or row_differences(g, 1)
                penalty = [min(0, p.school_balance) * 100 for p in g.players]
                me = d["seat"]
                self.assertEqual(sum(v or 0 for v in d["rows"].values()) + d["columns"]
                                 + penalty[me] - penalty[1 - me], d["total"])


class TestHistory(unittest.TestCase):
    def test_every_move_adds_everyones_total(self):
        g = GameEngine(["Ann", "Bob", "Cid"])
        play(g, 7, random.Random(5))
        self.assertEqual([moves for moves, _ in g.score_history], list(range(1, 8)))
        self.assertEqual(g.score_history[-1][1], tuple(p.calculate_score() for p in g.players))
        points = score_history(g)
        self.assertEqual(points[0], {"move": 0, "totals": [0, 0, 0]})
        self.assertEqual(len(points), 8)

    def test_a_whole_game_has_a_point_for_every_cell(self):
        g = GameEngine(["Ann", "Bob"])
        play(g, 2 * 45, random.Random(8))
        self.assertTrue(g.is_game_over())
        self.assertEqual(score_history(g)[-1], {"move": 90, "totals": [p.calculate_score() for p in g.players]})

    def test_saved_and_loaded_and_shared_by_a_clone(self):
        g = GameEngine(["Ann", "Bob"])
        play(g, 5, random.Random(2))
        self.assertEqual(engine_from_data(engine_to_data(g)).score_history, g.score_history)
        clone = g.clone()
        play(clone, 1, random.Random(2))
        self.assertEqual(len(g.score_history), 5)  # the copy's move is not the game's
        self.assertEqual(len(clone.score_history), 6)

    def test_a_game_saved_before_starts_its_chart_where_it_is(self):
        g = GameEngine(["Ann", "Bob"])
        play(g, 6, random.Random(4))
        data = engine_to_data(g)
        del data["score_history"]
        old = engine_from_data(data)
        self.assertEqual(score_history(old), [])
        play(old, 1, random.Random(4))
        self.assertEqual([p["move"] for p in score_history(old)], [7])  # no made-up point at 0


class TestApi(unittest.TestCase):
    def test_a_seat_gets_its_differences_and_everyone_the_history(self):
        store = RoomStore(starting_throw=False)
        made = api.handle({"op": "create", "name": "Ann"}, store)
        code, key = made["code"], made["state"]["key"]
        bob = api.handle({"op": "join", "code": code, "key": key, "name": "Bob"}, store)["token"]
        state = api.handle({"op": "roll", "code": code, "token": made["token"],
                            "version": store.view(code).version}, store)["state"]
        move = state["moves"]["score"][0]
        api.handle({"op": "score", "code": code, "token": made["token"], "version": state["version"],
                    "row": move["row"], "slot": move["slot"]}, store)
        seen = api.handle({"op": "state", "code": code, "token": bob, "lang": "ru"}, store)["state"]
        points = store.view(code).engine.players[0].calculate_score()
        self.assertEqual(seen["differences"]["seat"], 1)
        self.assertEqual(seen["differences"]["rows"][move["row"]], -sum(
            v for v in store.view(code).engine.players[0].table[getattr(C, move["row"])] if isinstance(v, int)))
        self.assertEqual(seen["differences"]["hint"], "Ваши очки в каждой строке минус очки игрока Ann")
        self.assertEqual(seen["game"]["history"], [{"move": 0, "totals": [0, 0]}, {"move": 1, "totals": [points, 0]}])
        outsider = api.handle({"op": "state", "code": code, "key": key}, store)["state"]
        self.assertIsNone(outsider["differences"])


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestPage(unittest.TestCase):
    def test_the_board_html(self):
        from ui_components.chart import score_chart_html
        from ui_components.scoreboard import build_scoreboard_html
        g = GameEngine(["<b>Ann</b>", "Bob"])
        write(g, 0, C.SUM, 0, 20)
        write(g, 1, C.SUM, 0, 26)
        write(g, 0, C.PAIR, 0, 12)
        html = build_scoreboard_html(g, 0, None, row_differences(g, 0))
        self.assertIn('<td class="ab-diff down">−6</td>', html)
        self.assertIn('<td class="ab-diff up">+12</td>', html)
        self.assertNotIn("ab-diff", build_scoreboard_html(g, 0))
        # Every row of the table has as many cells as the header says.
        widths = {sum(int(n) if n else 1 for n in re.findall(r'<t[dh](?: colspan="(\d+)")?[ >]', row))
                  for row in re.findall(r"<tr[^>]*>(.*?)</tr>", html)}
        self.assertEqual(widths, {1 + 5 * 2 + 2})
        chart = score_chart_html(g, 0)
        self.assertEqual(chart.count("<polyline"), 2)
        self.assertIn("You <b>32</b>", chart)
        self.assertNotIn("<b>Ann</b>", chart)
        self.assertEqual(score_chart_html(GameEngine(["Ann", "Bob"]), 0), "")

    def test_the_switch_on_the_game_page(self):
        from streamlit.testing.v1 import element_tree
        if not hasattr(element_tree.ButtonGroup, "_is_single_select"):  # AppTest 1.48: single-choice groups
            group_value = element_tree.ButtonGroup.value.fget

            def one_or_more(group):
                value = group_value(group)
                return [] if value is None else value if isinstance(value, list) else [value]

            patcher = mock.patch.object(element_tree.ButtonGroup, "value", property(one_or_more))
            patcher.start()
            self.addCleanup(patcher.stop)
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": ""})
        env.start()
        self.addCleanup(env.stop)
        stores = []

        class FreshRoomStore(rooms.RoomStore):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                stores.append(self)

        self.addCleanup(setattr, rooms, "RoomStore", rooms.RoomStore)
        rooms.RoomStore = FreshRoomStore
        code_version.mark_current()
        AppTest.from_file(APP, default_timeout=30).run()  # the app makes its store
        store = stores[-1]
        code, token = store.create_local(["Ann", "Bob"])
        while store.view(code).engine.choosing_first_player:
            store.throw_for_start(code, token)
        for _ in range(2):
            store.roll(code, token)
            store.score(code, token, C.SUM, 0)
        at = AppTest.from_file(APP, default_timeout=30)
        at.query_params["room"] = code
        at.session_state["room_code"], at.session_state["seat_token"] = code, token
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        html = "".join(h.proto.body for h in at.get("html"))
        self.assertIn('<div class="ab-chart">', html)
        self.assertNotIn('class="ab-diff', html)
        at.toggle(key="diffs-switch").set_value(True).run()
        html = "".join(h.proto.body for h in at.get("html"))
        self.assertIn('class="ab-board ab-diffs"', html)
        at.toggle(key="diffs-switch").set_value(False).run()
        self.assertNotIn('class="ab-diff', "".join(h.proto.body for h in at.get("html")))


if __name__ == "__main__":
    unittest.main()
