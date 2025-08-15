import unittest
from abaka_engine import Die, Category, score_category, GameEngine, PlayerState

class TestScoringBasics(unittest.TestCase):
    def test_pair(self):
        dice = [Die(3), Die(3), Die(1), Die(4), Die(6)]
        self.assertEqual(score_category(dice, Category.PAIR), 6)

    def test_two_pairs(self):
        dice = [Die(2), Die(2), Die(5), Die(5), Die(6)]
        self.assertEqual(score_category(dice, Category.TWO_PAIRS), 14)

    def test_trips(self):
        dice = [Die(4), Die(4), Die(4), Die(1), Die(2)]
        self.assertEqual(score_category(dice, Category.TRIPS), 12)

    def test_full_exact_3_plus_2(self):
        dice = [Die(6), Die(6), Die(6), Die(2), Die(2)]
        self.assertEqual(score_category(dice, Category.FULL), sum([6,6,6,2,2]))

    def test_full_is_not_kare(self):
        dice = [Die(5), Die(5), Die(5), Die(5), Die(2)]
        self.assertEqual(score_category(dice, Category.FULL), 0)

    def test_kare_with_bonus(self):
        dice = [Die(6), Die(6), Die(6), Die(6), Die(1)]
        self.assertEqual(score_category(dice, Category.KARE), 6*4 + 20)

    def test_abaka_with_bonus_and_first_roll(self):
        dice = [Die(5), Die(5), Die(5), Die(5), Die(5)]
        # 25 + bonus 50 doubled on first roll = 25 + 100 = 125
        self.assertEqual(score_category(dice, Category.ABAKA, first_roll=True), 125)

    def test_royal_full_bonus(self):
        dice = [Die(1), Die(1), Die(1), Die(2), Die(2)]
        self.assertEqual(
            score_category(dice, Category.FULL), sum([1,1,1,2,2]) + 50
        )

class TestStraights(unittest.TestCase):
    def test_small_straight_any_4_seq(self):
        dice = [Die(1), Die(2), Die(3), Die(4), Die(6)]
        self.assertEqual(score_category(dice, Category.SMALL_STRAIGHT), sum([1,2,3,4,6]))
        dice2 = [Die(2), Die(3), Die(4), Die(5), Die(1)]
        self.assertEqual(score_category(dice2, Category.SMALL_STRAIGHT), sum([2,3,4,5,1]))
        dice3 = [Die(3), Die(4), Die(5), Die(6), Die(6)]
        self.assertEqual(score_category(dice3, Category.SMALL_STRAIGHT), sum([3,4,5,6,6]))

    def test_large_straight_1to5_or_2to6(self):
        self.assertEqual(score_category([Die(1),Die(2),Die(3),Die(4),Die(5)], Category.LARGE_STRAIGHT), 15)
        self.assertEqual(score_category([Die(2),Die(3),Die(4),Die(5),Die(6)], Category.LARGE_STRAIGHT), 20)
        # Дубликат ломает большой стрит
        self.assertEqual(score_category([Die(2),Die(3),Die(4),Die(5),Die(5)], Category.LARGE_STRAIGHT), 0)

class TestJoker(unittest.TestCase):
    def test_joker_wild_only_on_one(self):
        # Джокер=1: можно подставить 6 для SUM
        dice = [Die(2), Die(3), Die(4), Die(5), Die(1, is_joker=True)]
        self.assertEqual(score_category(dice, Category.SUM), 2+3+4+5+6)
        # Джокер=3: не вайлд, просто 3
        dice = [Die(2), Die(3, is_joker=True), Die(4), Die(5), Die(1)]
        self.assertEqual(score_category(dice, Category.SUM), 2+3+4+5+1)

class TestEngineRules(unittest.TestCase):
    def test_leftmost_slot_enforced(self):
        p = PlayerState(\"Alice\")
        with self.assertRaises(ValueError):
            p.record(Category.SUM, 1, 10)  # нельзя писать не в самый левый
        p.record(Category.SUM, 0, 10)
        with self.assertRaises(ValueError):
            p.cross(Category.SUM, 2)  # снова нарушаем левую ячейку

    def test_turn_flow(self):
        ge = GameEngine([\"A\",\"B\"])        
        ge.start_turn()
        ge.reroll([0,1])  # можно перебрасывать и джокер, если его индекс попал
        ge.record_score(Category.SUM, 0)
        self.assertEqual(ge.current, 1)

if __name__ == \"__main__\":
    unittest.main()
