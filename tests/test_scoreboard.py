"""
Scoreboard bonus cells: a bonus the player crossed out themselves (a School row paid
from the balance, or a crossed-out combination) shows a cross; a bonus that went to
another player shows a dash. Skipped where Streamlit is not installed.
"""

import re
import unittest

from abaka.engine import GameEngine
from abaka.models import Category, Die
from ui_components.moves import score_options

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

    def test_a_bonus_taken_by_another_player_shows_a_dash(self):
        g = GameEngine(["Ann", "Bob"])
        for hand in (dice(4, 4, 4, 1), dice(4, 4, 4, 2), dice(4, 4, 4, 3)):
            g.current = 0
            g.dice = hand
            g.record_score(Category.SCHOOL_4, g.leftmost_slot(g.players[0], Category.SCHOOL_4))
        cells = row_cells(build_scoreboard_html(g), "School 4")
        self.assertEqual(cells[4][1], "12")  # Ann completed it first: 3 x 4
        self.assertEqual(cells[9][1], "–")   # Bob: no bonus, but he did not cross it out


if __name__ == "__main__":
    unittest.main()
