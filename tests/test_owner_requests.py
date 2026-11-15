"""Rules and engine behaviour asked for by the owner on 2026-11-15."""
import unittest

from abaka.engine import GameEngine
from abaka.models import Category, Die


def dice(*values, joker=6):
    return [Die(v) for v in values] + [Die(joker, is_joker=True)]


class TestSchoolBonusAfterPaying(unittest.TestCase):
    def test_paying_from_balance_keeps_the_row_bonus(self):
        g = GameEngine(["Ann", "Bob"])
        ann = g.players[0]
        ann.school_balance = 20
        # Three School 4 writes: one die short, two dice short, exactly three.
        for hand in (dice(4, 4, 1, 2), dice(4, 1, 2, 3), dice(4, 4, 4, 1)):
            g.current = 0
            g.dice = hand
            g.record_score(Category.SCHOOL_4, g.leftmost_slot(ann, Category.SCHOOL_4))
        self.assertEqual(ann.school_balance, 20 - 4 - 8)
        self.assertEqual(ann.table[Category.SCHOOL_4][3], 12)  # 3 x 4
        self.assertEqual(g.players[1].table[Category.SCHOOL_4][3], 'X')  # first to complete claims it

    def test_bonus_cell_stays_open_after_a_payment(self):
        g = GameEngine(["Ann", "Bob"])
        g.players[0].school_balance = 10
        g.dice = dice(6, 6, 1, 2, joker=3)  # two 6s: one short, costs 6
        g.record_score(Category.SCHOOL_6, 0)
        self.assertEqual(g.players[0].school_balance, 4)
        self.assertIsNone(g.players[0].table[Category.SCHOOL_6][3])

    def test_crossing_a_combination_still_cancels_its_bonus(self):
        g = GameEngine(["Ann", "Bob"])
        g.dice = dice(1, 2, 3, 5)
        g.record_cross(Category.ABAKA, 0)
        self.assertEqual(g.players[0].table[Category.ABAKA][3], 'X')


class TestLastMove(unittest.TestCase):
    def test_last_move_follows_each_move(self):
        g = GameEngine(["Ann", "Bob", "Cy"])
        self.assertIsNone(g.last_move)
        g.dice = dice(6, 6, 5, 4)
        g.record_score(Category.SUM, 0)
        self.assertEqual(g.last_move, (0, Category.SUM, 0))
        g.dice = dice(1, 2, 3, 5)
        g.record_cross(Category.ABAKA, 0)
        self.assertEqual(g.last_move, (1, Category.ABAKA, 0))
        g.players[2].school_balance = 0
        g.dice = dice(3, 3, 3, 1)
        g.record_score(Category.SCHOOL_3, 0)
        self.assertEqual(g.last_move, (2, Category.SCHOOL_3, 0))

    def test_rejected_move_does_not_change_last_move(self):
        g = GameEngine(["Ann", "Bob"])
        g.dice = dice(6, 6, 5, 4)
        g.record_score(Category.SUM, 0)
        g.dice = dice(1, 2, 3, 5)
        with self.assertRaises(ValueError):
            g.record_score(Category.ABAKA, 0)
        self.assertEqual(g.last_move, (0, Category.SUM, 0))


if __name__ == "__main__":
    unittest.main()
