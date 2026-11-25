"""
The races for the shared bonuses (Backlog item 30, from a tester): "how many cells are left to
the column, for you and the opponent", and a warning "that you have been caught up in a row
when you have one cell left to the bonus". abaka/races.py works them out from the game; the
web page draws them under the dice, and the API sends them to apps with their words.
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
from abaka.races import bonus_races
from abaka.rooms import RoomStore

try:
    from streamlit.testing.v1 import AppTest
except ImportError:  # the base Python 3.8
    AppTest = None

APP = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "abaka_ui.py")


def write(g, seat, cat, slot, value=5):
    """Seat `seat` writes `value` in a cell ("X": crosses it out), bonuses decided as by a move."""
    g.current = seat
    if value == "X":
        g.record_cross(cat, slot)
    else:
        g.players[seat].record(cat, slot, value)
        g.last_move = (seat, cat, slot)
        g._after_record(cat, slot)


def columns(races):
    return [(c["column"], c["left"], c["open"]) for c in races["columns"]]


class TestColumns(unittest.TestCase):
    def test_nothing_to_tell_before_the_first_cell(self):
        self.assertIsNone(bonus_races(GameEngine(["Ann", "Bob"]), 0))
        self.assertIsNone(bonus_races(GameEngine(["Ann", "Bob"], starting_throw=True), 0))

    def test_cells_left_for_every_player_in_columns_one_and_two(self):
        g = GameEngine(["Ann", "Bob"])
        for cat in (C.SUM, C.PAIR, C.SCHOOL_3):
            write(g, 0, cat, 0)
        write(g, 0, C.SUM, 1)
        write(g, 1, C.TRIPS, 0)
        races = bonus_races(g, 0)
        self.assertEqual(columns(races), [(0, [12, 14], [True, True]), (1, [14, 15], [True, True])])
        self.assertEqual(races["heads"], ["You", "Bob"])
        self.assertEqual([c["label"] for c in races["columns"]], ["Column I", "Column II"])
        self.assertEqual(races["rows"], [])
        self.assertIsNone(races["note"])

    def test_a_crossed_out_combination_still_counts_and_is_marked(self):
        g = GameEngine(["Ann", "Bob"])
        write(g, 0, C.SUM, 0)
        write(g, 1, C.PAIR, 0, "X")  # Bob can no longer earn column I, but can still close it
        races = bonus_races(g, 1)
        self.assertEqual(columns(races), [(0, [14, 14], [True, False])])
        self.assertIn("closes it for the others", races["note"])

    def test_column_three_is_no_race(self):
        g = GameEngine(["Ann", "Bob"])
        for slot in range(3):
            write(g, 0, C.SUM, slot)
        self.assertEqual([c["column"] for c in bonus_races(g, 0)["columns"]], [0, 1])

    def test_the_first_to_complete_a_column_decides_it_and_the_race_ends(self):
        g = GameEngine(["Ann", "Bob"])
        cats = list(C)
        for cat in cats[:-1]:
            write(g, 0, cat, 0)
        write(g, 1, C.SUM, 0)
        self.assertEqual(columns(bonus_races(g, 1))[0], (0, [1, 14], [True, True]))
        write(g, 0, cats[-1], 0)  # Ann's last cell of column I
        self.assertTrue(g.col_bonus_claimed[0])
        self.assertEqual(g.players[1].column_bonus[0], "X")
        self.assertIsNone(bonus_races(g, 1))  # column I decided, column II untouched, no row race

    def test_no_race_once_a_column_is_decided_or_nobody_can_earn_it(self):
        g = GameEngine(["Ann", "Bob"])
        for cat in C:  # Ann completes column I: its bonus is decided for both
            write(g, 0, cat, 0)
        self.assertTrue(g.col_bonus_claimed[0])
        write(g, 1, C.PAIR, 0)
        write(g, 1, C.PAIR, 1)
        self.assertEqual([c["column"] for c in bonus_races(g, 1)["columns"]], [1])
        write(g, 0, C.TRIPS, 1, "X")  # both cross out in column II: nobody can earn it
        write(g, 1, C.TRIPS, 0)
        write(g, 1, C.TRIPS, 1, "X")
        self.assertIsNone(bonus_races(g, 1))


class TestRows(unittest.TestCase):
    def setUp(self):
        self.addCleanup(set_language, "en")

    def test_two_players_one_cell_from_the_same_row_bonus(self):
        g = GameEngine(["Ann", "Bob"])
        for seat in (0, 1):
            for cat in (C.SUM, C.FULL):
                write(g, seat, cat, 0)
                write(g, seat, cat, 1)
        write(g, 1, C.PAIR, 0)
        write(g, 1, C.PAIR, 1)  # only Bob is one cell from Pair's bonus: no race to warn about
        self.assertEqual(bonus_races(g, 1)["rows"], [{
            "rows": ["FULL", "SUM"], "seats": [0, 1],
            "text": "One cell to the bonus for you and Ann: Full house, Sum."}])

    def test_the_warning_goes_once_the_row_is_decided(self):
        g = GameEngine(["Ann", "Bob"])
        for seat in (0, 1):
            write(g, seat, C.SUM, 0)
            write(g, seat, C.SUM, 1)
        self.assertEqual(len(bonus_races(g, 0)["rows"]), 1)
        write(g, 1, C.SUM, 2)  # Bob was first: the bonus is his, Ann's cell is crossed out
        self.assertTrue(g.row_bonus_claimed[C.SUM])
        self.assertEqual(bonus_races(g, 0)["rows"], [])

    def test_a_race_counts_while_one_of_its_players_can_win_it(self):
        g = GameEngine(["Ann", "Bob"])
        write(g, 0, C.SUM, 0)
        write(g, 0, C.SUM, 1, "X")  # Ann gave Sum's bonus up, but can still close it for Bob
        write(g, 1, C.SUM, 0)
        write(g, 1, C.SUM, 1)
        self.assertEqual([r["rows"] for r in bonus_races(g, 1)["rows"]], [["SUM"]])
        g2 = GameEngine(["Ann", "Bob"])
        for seat in (0, 1):
            write(g2, seat, C.SUM, 0)
            write(g2, seat, C.SUM, 1, "X")  # neither can win it: nothing to warn about
        self.assertEqual(bonus_races(g2, 0)["rows"], [])

    def test_three_players_grouped_by_who_is_close_the_viewer_first(self):
        g = GameEngine(["Ann", "Bob", "Cid"])
        for seat in (0, 1, 2):
            write(g, seat, C.SUM, 0)
            write(g, seat, C.SUM, 1)
        for seat in (0, 2):
            write(g, seat, C.PAIR, 0)
            write(g, seat, C.PAIR, 1)
        self.assertEqual([r["text"] for r in bonus_races(g, 2)["rows"]], [
            "One cell to the bonus for you, Ann and Bob: Sum.",
            "One cell to the bonus for you and Ann: Pair."])

    def test_russian_and_one_shared_screen(self):
        g = GameEngine(["Ann", "Bob"])
        for seat in (0, 1):
            write(g, seat, C.SUM, 0)
            write(g, seat, C.SUM, 1)
        set_language("ru")
        races = bonus_races(g, 1)
        self.assertEqual(races["title"], "Клеток до бонуса")
        self.assertEqual(races["heads"], ["Ann", "Вы"])
        self.assertEqual(races["columns"][0]["label"], "Столбец I")
        self.assertEqual(races["rows"][0]["text"], "Одна клетка до бонуса — вы и Ann: Сумма.")
        self.assertEqual(bonus_races(g, None)["rows"][0]["text"], "Одна клетка до бонуса — Ann и Bob: Сумма.")


class TestWholeGames(unittest.TestCase):
    def test_a_race_shown_is_the_one_the_next_completion_decides(self):
        """Random games: what the races say matches the board, and agrees with the bonus rules."""
        rng = random.Random(30)
        for number in range(16):
            g = GameEngine(["Ann", "Bob", "Cid"][:2 + number % 2])
            while not g.is_game_over():
                g.start_turn()
                seat = g.current
                races = bonus_races(g, seat)
                for viewer in [None] + list(range(len(g.players))):
                    self.assertEqual(bonus_races(g, viewer) is None, races is None)
                move = rng.choice(score_options(g) or cross_options(g))  # cross out when nothing scores
                shown_rows = {cat for r in (races or {}).get("rows", []) if seat in r["seats"] for cat in r["rows"]}
                shown_columns = {c["column"]: c["left"][seat] for c in (races or {}).get("columns", [])}
                for c in (races or {}).get("columns", []):
                    self.assertFalse(g.col_bonus_claimed[c["column"]])
                    self.assertEqual(c["left"], [sum(p.table[cat][c["column"]] is None for cat in C)
                                                 for p in g.players])
                    self.assertEqual(c["open"], [p.column_bonus[c["column"]] is None for p in g.players])
                last_cell = g.players[seat].table[move.category][:3].count(None) == 1
                (g.record_cross if move.cross else g.record_score)(move.category, move.slot)
                after = bonus_races(g, seat) or {"rows": [], "columns": []}
                if move.category.name in shown_rows and last_cell:
                    self.assertTrue(g.row_bonus_claimed[move.category])
                    self.assertNotIn(move.category.name, {cat for r in after["rows"] for cat in r["rows"]})
                if shown_columns.get(move.slot) == 1:
                    self.assertTrue(g.col_bonus_claimed[move.slot])
                    self.assertNotIn(move.slot, [c["column"] for c in after["columns"]])
            self.assertIsNone(bonus_races(g, 0))


class TestApi(unittest.TestCase):
    def test_a_seat_gets_the_races_in_its_language_an_outsider_none(self):
        store = RoomStore(starting_throw=False)
        made = api.handle({"op": "create", "name": "Ann"}, store)
        code = made["code"]
        key = made["state"]["key"]
        bob = api.handle({"op": "join", "code": code, "key": key, "name": "Bob"}, store)["token"]
        self.assertIsNone(made["state"]["races"])  # the waiting room
        state = api.handle({"op": "roll", "code": code, "token": made["token"],
                            "version": store.view(code).version}, store)["state"]
        move = state["moves"]["score"][0]
        api.handle({"op": "score", "code": code, "token": made["token"], "version": state["version"],
                    "row": move["row"], "slot": move["slot"]}, store)
        races = api.handle({"op": "state", "code": code, "token": bob, "lang": "ru"}, store)["state"]["races"]
        self.assertEqual(races["heads"], ["Ann", "Вы"])
        self.assertEqual(columns(races), [(0, [14, 15], [True, True])])
        self.assertIsNone(api.handle({"op": "state", "code": code, "key": key}, store)["state"]["races"])


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestPage(unittest.TestCase):
    def test_each_player_is_a_row_with_their_whole_name(self):
        """With names as columns, five players' names were cut to "T…" in the play card. Each
        player is a row of the table now, and each column of the board a column."""
        from ui_components.races import races_html
        g = GameEngine(["Ann", "Александра", "<b>Bob</b>", "Cleo", "Dan"])
        for seat in range(5):
            write(g, seat, C.SUM, 0)
        write(g, 1, C.PAIR, 0)
        write(g, 2, C.PAIR, 0, "X")  # Bob can no longer earn column I's bonus
        head, body = races_html(g, 3).split("<tbody>")
        self.assertIn("<th>Column I</th>", head)
        self.assertNotIn("Column II", head)  # nobody has written in it yet
        rows = re.findall(r"<tr>(.*?)</tr>", body)
        self.assertEqual(len(rows), 5)
        for row, name in zip(rows, ["Ann", "Александра", "&lt;b&gt;Bob&lt;/b&gt;", "You", "Dan"]):
            self.assertRegex(row, r'^<th class="ab-race-who( me)?" title="[^"]*">' + re.escape(name) + "</th><td")
        self.assertIn('class="ab-race-who me"', rows[3])
        self.assertTrue(rows[0].endswith("<td>14</td>"))
        self.assertTrue(rows[1].endswith('<td class="lead">13</td>'))
        self.assertTrue(rows[2].endswith('<td class="lead off">13<span class="ab-race-x">✕</span></td>'))

    def test_the_play_card_shows_the_races_with_names_escaped(self):
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
        code, key = store.create_local(["<b>Ann</b>", "Bob"])
        while store.view(code).engine.choosing_first_player:
            store.throw_for_start(code, key)
        for _ in range(2):  # each player writes Sum: both have written in column I
            store.roll(code, key)
            store.score(code, key, C.SUM, 0)
        at = AppTest.from_file(APP, default_timeout=30)
        at.query_params["room"] = code
        at.session_state["room_code"], at.session_state["seat_token"] = code, key
        at.run()
        self.assertFalse(at.exception, [e.value for e in at.exception])
        html = "\n".join(n.proto.body for n in at.get("html"))
        self.assertIn('class="ab-race"', html)
        self.assertIn("Column I", html)
        self.assertIn("&lt;b&gt;Ann&lt;/b&gt;", html)
        self.assertNotIn("<b>Ann</b>", html)


if __name__ == "__main__":
    unittest.main()
