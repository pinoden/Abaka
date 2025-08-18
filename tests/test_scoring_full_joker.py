# tests/test_scoring_full_joker.py
import unittest
from abaka.scoring import score_category
from abaka.models import Category, Die

class TestFullWithJoker(unittest.TestCase):
    def test_full_with_joker_prefers_max_sum(self):
        dice = [Die(6), Die(6), Die(5), Die(5), Die(1, is_joker=True)]
        self.assertEqual(score_category(dice, Category.FULL, first_roll=False), 28)

if __name__ == "__main__":
    unittest.main()
