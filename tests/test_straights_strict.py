import unittest
from abaka.scoring import score_category
from abaka.models import Category, Die

class TestStraightsStrict(unittest.TestCase):
    def test_not_small_when_only_2345_with_dup(self):
        dice = [Die(3), Die(4), Die(4), Die(5), Die(2, is_joker=True)]  # J(2) не дикарь
        self.assertEqual(score_category(dice, Category.SMALL_STRAIGHT, False), 0)
        self.assertEqual(score_category(dice, Category.LARGE_STRAIGHT, False), 0)

    def test_small_is_exact_1_2_3_4_5(self):
        dice = [Die(1), Die(2), Die(3), Die(4), Die(5)]
        self.assertEqual(score_category(dice, Category.SMALL_STRAIGHT, False), 15)

    def test_large_is_exact_2_3_4_5_6(self):
        dice = [Die(2), Die(3), Die(4), Die(5), Die(6)]
        self.assertEqual(score_category(dice, Category.LARGE_STRAIGHT, False), 20)

    def test_joker1_can_complete_small(self):
        dice = [Die(1), Die(2), Die(3), Die(4), Die(1, is_joker=True)]  # J(1) -> 5
        self.assertEqual(score_category(dice, Category.SMALL_STRAIGHT, False), 15)

    def test_joker1_can_complete_large(self):
        dice = [Die(2), Die(3), Die(4), Die(5), Die(1, is_joker=True)]  # J(1) -> 6
        self.assertEqual(score_category(dice, Category.LARGE_STRAIGHT, False), 20)

if __name__ == "__main__":
    unittest.main()
