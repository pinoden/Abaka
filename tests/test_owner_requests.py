"""Rules and engine behaviour asked for by the owner (2026-11-15; School bonus rule changed 2026-11-16)."""
import unittest

from abaka.engine import GameEngine
from abaka.models import Category, Die


def dice(*values, joker=6):
    return [Die(v) for v in values] + [Die(joker, is_joker=True)]


class TestTwoPairsFromFourOfAKind(unittest.TestCase):
    """Owner (2026-11-19): four sixes (joker 6, 6, 6, 6, 1) could not be written in Two pairs."""

    def test_four_or_five_of_a_kind_holds_two_pairs(self):
        from abaka.scoring import score_category
        self.assertEqual(score_category(dice(6, 6, 6, 1, joker=6), Category.TWO_PAIRS), 24)  # the owner's roll
        self.assertEqual(score_category(dice(4, 4, 4, 4, joker=4), Category.TWO_PAIRS), 16)  # five of a kind
        self.assertEqual(score_category(dice(6, 6, 6, 6, joker=6), Category.TWO_PAIRS, first_roll=True), 48)
        # The rest is as before: two different pairs, a full house, one pair only.
        self.assertEqual(score_category(dice(2, 2, 5, 5, joker=6), Category.TWO_PAIRS), 14)
        self.assertEqual(score_category(dice(5, 5, 5, 3, joker=3), Category.TWO_PAIRS), 16)
        self.assertEqual(score_category(dice(6, 6, 6, 2, joker=5), Category.TWO_PAIRS), 0)
        # A wild joker (showing 1) still picks its best value: 6, 6, 6 and a wild joker -> four sixes.
        self.assertEqual(score_category(dice(6, 6, 6, 2, joker=1), Category.TWO_PAIRS), 24)

    def test_the_move_is_offered(self):
        from ui_components.moves import score_options
        g = GameEngine(["Denis", "Andrey"])
        g.start_turn()
        g.dice = dice(6, 6, 6, 1, joker=6)
        g.rolls_left, g.first_roll = 0, False
        offered = {m.category: m.value for m in score_options(g)}
        self.assertEqual(offered.get(Category.TWO_PAIRS), 24)


class TestSchoolBonusAfterPaying(unittest.TestCase):
    """
    Owner's rule (2026-11-16, reversing the 2026-11-15 decision): paying from the balance
    ("minus") in a School row gives up that row's bonus, and its bonus cell is crossed out at once.
    """

    def test_paying_from_balance_crosses_the_row_bonus_at_once(self):
        g = GameEngine(["Ann", "Bob"])
        g.players[0].school_balance = 10
        g.dice = dice(6, 6, 1, 2, joker=3)  # two 6s: one short, costs 6
        g.record_score(Category.SCHOOL_6, 0)
        self.assertEqual(g.players[0].school_balance, 4)
        self.assertEqual(g.players[0].table[Category.SCHOOL_6][3], 'X')
        self.assertIsNone(g.players[1].table[Category.SCHOOL_6][3])  # only the payer loses it

    def test_a_row_with_a_payment_never_gets_its_bonus(self):
        g = GameEngine(["Ann", "Bob"])
        ann = g.players[0]
        ann.school_balance = 20
        # One die short (pays 4), then exactly three twice: Ann completes the row first.
        for hand in (dice(4, 4, 1, 2), dice(4, 4, 4, 1), dice(4, 4, 4, 2)):
            g.current = 0
            g.dice = hand
            g.record_score(Category.SCHOOL_4, g.leftmost_slot(ann, Category.SCHOOL_4))
        self.assertEqual(ann.school_balance, 16)
        self.assertEqual(ann.table[Category.SCHOOL_4][3], 'X')
        # As with a crossed-out combination, the first to complete the row decides: nobody gets it.
        self.assertEqual(g.players[1].table[Category.SCHOOL_4][3], 'X')
        self.assertEqual(ann.calculate_score(), 16)  # the balance cell only

    def test_exactly_three_or_extra_dice_keep_the_bonus(self):
        g = GameEngine(["Ann", "Bob"])
        ann = g.players[0]
        for hand in (dice(4, 4, 4, 1), dice(4, 4, 4, 4), dice(4, 4, 4, 2)):
            g.current = 0
            g.dice = hand
            g.record_score(Category.SCHOOL_4, g.leftmost_slot(ann, Category.SCHOOL_4))
        self.assertEqual(ann.table[Category.SCHOOL_4][3], 12)  # 3 x 4
        self.assertEqual(g.players[1].table[Category.SCHOOL_4][3], 'X')  # first to complete claims it

    def test_crossing_a_combination_still_cancels_its_bonus(self):
        g = GameEngine(["Ann", "Bob"])
        g.dice = dice(1, 2, 3, 5)
        g.record_cross(Category.ABAKA, 0)
        self.assertEqual(g.players[0].table[Category.ABAKA][3], 'X')


class TestCrossingOutCostsTheColumnBonus(unittest.TestCase):
    """Owner (2026-11-16): crossing out a combination gives up that column's bonus, like the row's, at once."""

    def test_the_column_bonus_is_crossed_out_at_once(self):
        g = GameEngine(["Ann", "Bob"])
        g.dice = dice(1, 2, 3, 5)
        g.record_cross(Category.ABAKA, 0)  # column I
        ann = g.players[0]
        self.assertEqual(ann.column_bonus, ['X', None, None])
        self.assertEqual(ann.table[Category.ABAKA][3], 'X')  # and the row bonus
        self.assertEqual(g.players[1].column_bonus, [None, None, None])  # only for the player who crossed

    def test_a_column_with_a_crossed_out_combination_never_pays(self):
        g = GameEngine(["Ann", "Bob"])
        ann = g.players[0]
        for cat in Category:  # columns I and II full of numbers
            ann.table[cat][0], ann.table[cat][1] = 5, 5
        g.dice = dice(1, 2, 3, 5)
        g.record_cross(Category.ABAKA, 2)  # cross out in column III
        self.assertEqual(ann.column_bonus[2], 'X')
        for cat in Category:  # fill the rest of column III with numbers
            if ann.table[cat][2] is None and cat is not Category.SUM:
                ann.table[cat][2] = 6
        g.current = 0
        g.dice = dice(6, 6, 6, 6)
        g.record_score(Category.SUM, 2)  # completes column III
        self.assertEqual(ann.column_bonus[2], 'X')  # still no bonus

    def test_paying_in_school_leaves_the_column_bonuses(self):
        g = GameEngine(["Ann", "Bob"])
        g.players[0].school_balance = 10
        g.dice = dice(6, 6, 1, 2, joker=3)
        g.record_score(Category.SCHOOL_6, 0)
        self.assertEqual(g.players[0].column_bonus, [None, None, None])


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
