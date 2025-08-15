import unittest
import random

from abaka_engine import (
    Die, Category, roll_dice, score_category,
    PlayerState, GameEngine
)

class TestDiceAndJoker(unittest.TestCase):
    def test_roll_dice_structure(self):
        dice = roll_dice()
        # Должно быть ровно 5 кубиков, один с is_joker=True
        self.assertEqual(len(dice), 5)
        jokers = [d for d in dice if d.is_joker]
        self.assertEqual(len(jokers), 1)

    def test_joker_fixed_when_not_one(self):
        # Подменим random so joker != 1
        random.seed(0)
        dice = roll_dice()
        joker = next(d for d in dice if d.is_joker)
        # По семени 0, скорее всего joker.value != 1
        if joker.value != 1:
            sc1 = score_category(dice, Category.SUM)
            # При SUM wild-подстановка не влияет — должно быть просто сумма
            vals = sum(d.value for d in dice)
            self.assertEqual(sc1, vals)

    def test_joker_wild_when_one(self):
        # Принудительно сделаем джокер = 1
        dice = [Die(2), Die(3), Die(4), Die(5), Die(1, is_joker=True)]
        # При SUM: лучший вариант — подменить джокер на 6
        self.assertEqual(score_category(dice, Category.SUM), 2+3+4+5+6)

class TestScoring(unittest.TestCase):
    def test_pair(self):
        dice = [Die(3), Die(3), Die(1), Die(4), Die(5)]
        self.assertEqual(score_category(dice, Category.PAIR), 3*2)

    def test_two_pairs(self):
        dice = [Die(2), Die(2), Die(5), Die(5), Die(1)]
        self.assertEqual(score_category(dice, Category.TWO_PAIRS), 2*2 + 5*2)

    def test_trips_and_bonus(self):
        dice = [Die(4), Die(4), Die(4), Die(1), Die(2)]
        # Трипс 4 → 4*3 = 12
        self.assertEqual(score_category(dice, Category.TRIPS), 12)

    def test_kare_with_bonus(self):
        dice = [Die(6), Die(6), Die(6), Die(6), Die(2)]
        # Каре 6*4=24 + бонус20 = 44
        self.assertEqual(score_category(dice, Category.KARE), 44)

    def test_abaka_and_first_roll_double_bonus(self):
        dice = [Die(5), Die(5), Die(5), Die(5), Die(5)]
        # ABAKA: 5*5=25 + bonus50=75, при first_roll=True bonus удваивается: +50 еще => 125
        self.assertEqual(score_category(dice, Category.ABAKA, first_roll=True), 125)

class TestGameFlow(unittest.TestCase):
    def test_player_record_and_cross(self):
        p = PlayerState("Alice")
        p.record(Category.SUM, 0, 10)
        self.assertEqual(p.table[Category.SUM][0], 10)
        p.cross(Category.PAIR, 0)
        self.assertEqual(p.table[Category.PAIR][0], 'X')

    def test_game_engine_turns(self):
        ge = GameEngine(["A", "B"])
        ge.start_turn()
        self.assertEqual(ge.rolls_left, 2)
        # Перебросим все кроме джокера
        idxs = [i for i,d in enumerate(ge.dice) if not d.is_joker]
        ge.reroll(idxs[:2])
        self.assertEqual(ge.rolls_left, 1)
        # Запишем первый бросок
        ge.record_score(Category.SUM, 0)
        self.assertEqual(ge.current, 1)  # ход переходит ко второму игроку

if __name__ == "__main__":
    unittest.main()
