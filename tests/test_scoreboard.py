"""
Scoreboard bonus cells show a cross as soon as the bonus is lost.
"""

import re
import unittest

from abaka.engine import GameEngine
from abaka.models import Category, Die
from abaka.moves import cross_options, score_options

try:
    from ui_components.scoreboard import build_scoreboard_html
except ImportError:  # the scoreboard module imports Streamlit
    build_scoreboard_html = None


def dice(*values, joker=6):
    return [Die(v) for v in values] + [Die(joker, is_joker=True)]


def row_cells(html, row_name):
    """[(classes, text), ...] of the <td> cells in the scoreboard row named `row_name`."""
    row = html[html.index(f"{row_name}</th>"):]
    row = row[:row.index("</tr>")]
    return re.findall(r'<td class="([^"]*)"[^>]*>([^<]*)</td>', row)


@unittest.skipIf(build_scoreboard_html is None, "Streamlit is not installed")
class TestBonusCells(unittest.TestCase):
    def test_paying_in_school_shows_a_crossed_bonus(self):
        g = GameEngine(["Ann", "Bob"])
        g.players[0].school_balance = 10
        g.dice = dice(6, 6, 1, 2, joker=3)  # two 6s: one short, costs 6
        g.record_score(Category.SCHOOL_6, 0)
        cells = row_cells(build_scoreboard_html(g), "School 6")
        # per player: gap, three cells, bonus
        ann_bonus, bob_bonus = cells[4], cells[9]
        self.assertIn("ab-x", ann_bonus[0])
        self.assertEqual(ann_bonus[1], "✕")
        self.assertEqual(bob_bonus[1], "·")  # Bob's bonus is still open

    def test_preview_of_a_payment_shows_the_bonus_being_crossed(self):
        g = GameEngine(["Ann", "Bob"])
        g.players[0].school_balance = 10
        g.dice = dice(4, 4, 1, 2, joker=3)
        move = next(m for m in score_options(g) if m.category == Category.SCHOOL_4)
        self.assertTrue(move.bonus_lost)
        cells = row_cells(build_scoreboard_html(g, target=move), "School 4")
        self.assertEqual(cells[1], ("ab-active ab-target", "6"))  # the new balance
        self.assertIn("ab-target", cells[4][0])
        self.assertEqual(cells[4][1], "✕")

    def test_a_bonus_taken_by_another_player_shows_a_cross(self):
        g = GameEngine(["Ann", "Bob", "Cy"])
        for hand in (dice(4, 4, 4, 1), dice(4, 4, 4, 2), dice(4, 4, 4, 3)):
            g.current = 0
            g.dice = hand
            g.record_score(Category.SCHOOL_4, g.leftmost_slot(g.players[0], Category.SCHOOL_4))
        cells = row_cells(build_scoreboard_html(g), "School 4")
        self.assertEqual(cells[4][1], "12")  # Ann completed it first: 3 x 4
        self.assertEqual([cells[i][1] for i in (9, 14)], ["✕", "✕"])


@unittest.skipIf(build_scoreboard_html is None, "Streamlit is not installed")
class TestColumnBonusCells(unittest.TestCase):
    """Crossing out a combination gives up that column's bonus: its cell shows a cross at once."""

    def column_bonus_cells(self, html):
        return row_cells(html, "Column bonus")

    def test_crossing_out_shows_a_crossed_column_bonus(self):
        g = GameEngine(["Ann", "Bob"])
        g.dice = dice(1, 2, 3, 5)
        g.record_cross(Category.ABAKA, 0)
        cells = self.column_bonus_cells(build_scoreboard_html(g))
        # per player: gap, columns I-III, an empty cell under the row bonuses
        self.assertEqual([c[1] for c in cells[1:4]], ["✕", "·", "·"])
        self.assertIn("ab-x", cells[1][0])
        self.assertEqual([c[1] for c in cells[6:9]], ["·", "·", "·"])  # Bob's are untouched

    def test_preview_of_a_cross_shows_both_bonuses_crossed(self):
        g = GameEngine(["Ann", "Bob"])
        g.dice = dice(1, 2, 3, 5)
        move = next(m for m in cross_options(g) if m.category == Category.ABAKA)
        html = build_scoreboard_html(g, target=move)
        abaka = row_cells(html, "Abaka")
        self.assertEqual(abaka[1][1], "✕")             # the cell itself
        self.assertIn("ab-target", abaka[4][0])        # the row bonus
        cells = self.column_bonus_cells(html)
        self.assertIn("ab-target", cells[1][0])        # column I's bonus
        self.assertEqual(cells[1][1], "✕")
        self.assertNotIn("ab-target", cells[2][0])

    def test_completing_a_column_updates_the_other_players_bonus_cells(self):
        for col in range(3):
            for crossed in (False, True):
                with self.subTest(col=col, crossed=crossed):
                    g = GameEngine(["Ann", "Bob", "Cy"])
                    for cat in Category:
                        for slot in range(col + 1):
                            if cat != Category.SUM or slot != col:
                                g.players[0].table[cat][slot] = 6
                    g.dice = dice(6, 6, 6, 6)
                    if crossed:
                        g.record_cross(Category.SUM, col)
                    else:
                        g.record_score(Category.SUM, col)
                    html = build_scoreboard_html(g)
                    cells = self.column_bonus_cells(html)
                    expected = "·" if col == 2 else "✕"
                    self.assertEqual([cells[i + col][1] for i in (6, 11)], [expected] * 2)
                    if crossed and col == 2:
                        row = row_cells(html, "Sum")
                        self.assertEqual([row[i][1] for i in (4, 9, 14)], ["✕"] * 3)


if __name__ == "__main__":
    unittest.main()
