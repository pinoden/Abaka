import unittest
from abaka.engine import GameEngine
from abaka.models import Category, Die

class TestRulesSanity(unittest.TestCase):
    def test_school_has_no_first_roll_double(self):
        g = GameEngine(["P1"])
        p = g.players[0]
        # k > 3 для denom=5 → delta = (5-3)*5 = 10
        g.dice = [Die(5), Die(5), Die(5), Die(5), Die(5)]  # джокер не нужен
        g.first_roll = True  # это не должно влиять на школу
        slot = g.leftmost_slot(p, Category.SCHOOL_5)
        g.record_score(Category.SCHOOL_5, slot)
        self.assertEqual(p.school_balance, 10)                 # НЕ 20
        self.assertEqual(p.table[Category.SCHOOL_5][slot], 10) # в клетке тоже 10

    def test_strict_rows_disallow_zero(self):
        g = GameEngine(["P1"])
        p = g.players[0]
        # Псевдо-абака: 1,1,1,1, J(6) — джокер не wild, A записывать нельзя (должен быть ValueError)
        g.dice = [Die(1), Die(1), Die(1), Die(1), Die(6, is_joker=True)]
        with self.assertRaises(ValueError):
            slot = g.leftmost_slot(p, Category.ABAKA)
            g.record_score(Category.ABAKA, slot)

if __name__ == "__main__":
    unittest.main()
