import unittest
from abaka_engine import Die, Category, score_category, PlayerState, GameEngine

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

    def test_kare_first_roll_doubles_bonus(self):
        self.assertEqual(score_category(dice(4,4,4,4,3), Category.KARE, first_roll=True), 16 + 40)

    def test_abaka_first_roll_doubles_bonus(self):
        self.assertEqual(score_category(dice(5,5,5,5,5), Category.ABAKA, first_roll=True), 125)

    def test_royal_full_bonus(self):
        d = dice(1,1,1,2,2)
        self.assertEqual(score_category(d, Category.FULL), sum([1,1,1,2,2]) + 50)

class TestStraights(unittest.TestCase):
    def test_small_straight_any_4_seq(self):
        self.assertEqual(score_category(dice(1,2,3,4,6), Category.SMALL_STRAIGHT), 1+2+3+4+6)
        self.assertEqual(score_category(dice(2,3,4,5,1), Category.SMALL_STRAIGHT), 2+3+4+5+1)
        self.assertEqual(score_category(dice(3,4,5,6,6), Category.SMALL_STRAIGHT), 3+4+5+6+6)

    def test_large_straight(self):
        self.assertEqual(score_category(dice(1,2,3,4,5), Category.LARGE_STRAIGHT), 15)
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
