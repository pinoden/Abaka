"""
The original engine's tests (the engine was one module, `abaka_engine`; it is the `abaka`
package now). The first-roll and straight tests follow the rules the owner confirmed on
2026-11-18: a first roll doubles the score and the bonus (Abaka of sixes: 160), and the only
straights are exactly 1-2-3-4-5 (small) and 2-3-4-5-6 (large); four in a row scores nothing.
"""
import unittest
from abaka import Die, Category, score_category, PlayerState, GameEngine

def dice(*vals, joker_idx=None):
    ds = [Die(v) for v in vals]
    if joker_idx is not None:
        ds[joker_idx].is_joker = True
    return ds

class TestScoring(unittest.TestCase):
    def test_pair(self):
        self.assertEqual(score_category(dice(3,3,1,4,6), Category.PAIR), 6)

    def test_two_pairs(self):
        self.assertEqual(score_category(dice(2,2,5,5,6), Category.TWO_PAIRS), 14)

    def test_trips(self):
        self.assertEqual(score_category(dice(4,4,4,1,2), Category.TRIPS), 12)

    def test_full_exact(self):
        d = dice(6,6,6,2,2)
        self.assertEqual(score_category(d, Category.FULL), sum([6,6,6,2,2]))

    def test_full_not_kare(self):
        self.assertEqual(score_category(dice(5,5,5,5,2), Category.FULL), 0)

    def test_kare_with_bonus(self):
        self.assertEqual(score_category(dice(6,6,6,6,1), Category.KARE), 6*4 + 20)

    def test_kare_first_roll_doubles_score_and_bonus(self):
        self.assertEqual(score_category(dice(4,4,4,4,3), Category.KARE, first_roll=True), (16 + 20) * 2)

    def test_abaka_first_roll_doubles_score_and_bonus(self):
        # The owner's example: Abaka of sixes on the first roll is 160.
        self.assertEqual(score_category(dice(6,6,6,6,6), Category.ABAKA, first_roll=True), 160)
        self.assertEqual(score_category(dice(5,5,5,5,5), Category.ABAKA, first_roll=True), (25 + 50) * 2)

    def test_royal_full_bonus(self):
        d = dice(1,1,1,2,2)
        self.assertEqual(score_category(d, Category.FULL), sum([1,1,1,2,2]) + 50)

class TestStraights(unittest.TestCase):
    def test_small_straight_is_exactly_1_to_5(self):
        self.assertEqual(score_category(dice(2,3,4,5,1), Category.SMALL_STRAIGHT), 15)
        self.assertEqual(score_category(dice(1,2,3,4,6), Category.SMALL_STRAIGHT), 0)  # four in a row
        self.assertEqual(score_category(dice(3,4,5,6,6), Category.SMALL_STRAIGHT), 0)  # four in a row
        self.assertEqual(score_category(dice(2,3,4,5,6), Category.SMALL_STRAIGHT), 0)  # that is the large one

    def test_large_straight_is_exactly_2_to_6(self):
        self.assertEqual(score_category(dice(1,2,3,4,5), Category.LARGE_STRAIGHT), 0)  # that is the small one
        self.assertEqual(score_category(dice(2,3,4,5,6), Category.LARGE_STRAIGHT), 20)
        self.assertEqual(score_category(dice(2,3,4,5,5), Category.LARGE_STRAIGHT), 0)

class TestJoker(unittest.TestCase):
    def test_joker_wild_only_on_one(self):
        d = dice(2,3,4,5,1, joker_idx=4)
        self.assertEqual(score_category(d, Category.SUM), 2+3+4+5+6)
        d2 = dice(2,3,4,5,1)
        d2[1].is_joker = True
        d2[1].value = 3
        self.assertEqual(score_category(d2, Category.SUM), 2+3+4+5+1)

    def test_joker_can_complete_kare(self):
        d = dice(2,2,2,1,5, joker_idx=3)
        self.assertEqual(score_category(d, Category.KARE), 2*4 + 20)

class TestEngine(unittest.TestCase):
    def test_leftmost_slot_rule(self):
        p = PlayerState("A")
        with self.assertRaises(ValueError):
            p.record(Category.SUM, 1, 10)
        p.record(Category.SUM, 0, 10)
        with self.assertRaises(ValueError):
            p.cross(Category.SUM, 2)

    def test_basic_turn_flow(self):
        ge = GameEngine(["A", "B"])
        ge.start_turn()
        ge.reroll([0, 1])
        ge.record_score(Category.SUM, 0)
        self.assertEqual(ge.current, 1)

if __name__ == "__main__":
    unittest.main()
