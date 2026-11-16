import unittest

from abaka.constants import COMBO_CATS
from abaka.engine import GameEngine
from abaka.models import Category, Die
from abaka.rooms import RoomEngine, RoomStore
from ui_components.moves import cross_options, plain_engine, row_name, score_options


def game(*values, joker=None, first_roll=True):
    g = GameEngine(["Ann", "Bob"])
    g.dice = [Die(v) for v in values]
    if joker is not None:
        g.dice.append(Die(joker, is_joker=True))
    g.rolls_left = 2 if first_roll else 1
    g.first_roll = first_roll
    return g


def by_row(moves):
    return {m.category: m for m in moves}


class TestScoreOptions(unittest.TestCase):
    def test_previews_match_engine_scoring(self):
        g = game(5, 5, 5, 4, joker=4, first_roll=False)  # full house 5-5-5-4-4
        opts = by_row(score_options(g))
        self.assertEqual(opts[Category.FULL].value, 23)
        self.assertEqual(opts[Category.SUM].value, 23)
        self.assertEqual(opts[Category.TRIPS].value, 15)
        self.assertEqual(opts[Category.TWO_PAIRS].value, 18)
        self.assertEqual(opts[Category.FULL].label, "Full house · 23")
        self.assertEqual(opts[Category.FULL].action_text, "Score 23 in Full house")

    def test_first_roll_doubles(self):
        opts = by_row(score_options(game(5, 5, 5, 4, joker=4)))
        self.assertEqual(opts[Category.FULL].value, 46)

    def test_combos_that_do_not_fit_are_not_offered(self):
        opts = by_row(score_options(game(1, 2, 3, 5, joker=6, first_roll=False)))
        for cat in (Category.PAIR, Category.TRIPS, Category.FULL, Category.KARE, Category.ABAKA,
                    Category.SMALL_STRAIGHT, Category.LARGE_STRAIGHT):
            self.assertNotIn(cat, opts)
        self.assertIn(Category.SUM, opts)

    def test_wild_joker_is_used(self):
        opts = by_row(score_options(game(2, 3, 4, 5, joker=1, first_roll=False)))
        # joker counts as 6 for the large straight
        self.assertEqual(opts[Category.LARGE_STRAIGHT].value, 20)

    def test_school_previews(self):
        g = game(4, 4, 4, 4, joker=2, first_roll=False)
        opts = by_row(score_options(g))
        four = opts[Category.SCHOOL_4]
        self.assertEqual(four.balance_change, 4)
        self.assertEqual(four.label, "School 4 · +4")
        self.assertEqual(four.action_text, "Write School 4 (+4 balance)")
        self.assertFalse(four.bonus_lost)  # extra dice keep the bonus
        self.assertNotIn(Category.SCHOOL_6, opts)  # no 6s and not the endgame
        self.assertNotIn(Category.SCHOOL_2, opts)  # one 2 costs 4; the balance is 0

    def test_school_needing_balance(self):
        g = game(4, 4, 1, 2, joker=3, first_roll=False)
        self.assertNotIn(Category.SCHOOL_4, by_row(score_options(g)))  # balance 0 cannot pay 4
        g.players[0].school_balance = 10
        four = by_row(score_options(g))[Category.SCHOOL_4]
        self.assertEqual(four.balance_change, -4)
        self.assertTrue(four.bonus_lost)  # paying crosses out the row bonus (owner, 2026-11-16)
        self.assertEqual(four.action_text, "Write School 4 (pay 4 from balance, lose the row bonus)")
        # Once the bonus is gone, the button no longer mentions it.
        g.players[0].table[Category.SCHOOL_4][3] = "X"
        four = by_row(score_options(g))[Category.SCHOOL_4]
        self.assertFalse(four.bonus_lost)
        self.assertEqual(four.action_text, "Write School 4 (pay 4 from balance)")

    def test_exactly_three(self):
        four = by_row(score_options(game(4, 4, 4, 1, joker=6, first_roll=False)))[Category.SCHOOL_4]
        self.assertEqual(four.value, "X")
        self.assertEqual(four.balance_change, 0)
        self.assertEqual(four.label, "School 4 · exactly 3")
        self.assertEqual(four.preview, "✓")

    def test_crossing_out_warns_about_the_bonuses_it_gives_up(self):
        g = game(1, 2, 3, 5, joker=6, first_roll=False)
        abaka = {m.category: m for m in cross_options(g)}[Category.ABAKA]
        self.assertTrue(abaka.bonus_lost and abaka.column_bonus_lost)
        self.assertEqual(abaka.action_text, "Cross out Abaka (lose the row and column bonuses)")
        g.players[0].column_bonus[0] = "X"  # column I's bonus is already gone
        abaka = {m.category: m for m in cross_options(g)}[Category.ABAKA]
        self.assertEqual(abaka.action_text, "Cross out Abaka (lose the row bonus)")
        g.players[0].table[Category.ABAKA][3] = "X"  # and the row's
        abaka = {m.category: m for m in cross_options(g)}[Category.ABAKA]
        self.assertEqual(abaka.action_text, "Cross out Abaka")
        g.players[0].column_bonus[0] = None
        abaka = {m.category: m for m in cross_options(g)}[Category.ABAKA]
        self.assertEqual(abaka.action_text, "Cross out Abaka (lose the column bonus)")

    def test_previewing_does_not_change_the_game(self):
        g = game(6, 6, 6, 6, joker=6)
        score_options(g)
        self.assertEqual(g.current, 0)
        self.assertEqual(len(g.dice), 5)
        self.assertTrue(all(v is None for slots in g.players[0].table.values() for v in slots[:3]))

    def test_targets_leftmost_free_cell(self):
        g = game(6, 6, 1, 2, joker=3, first_roll=False)
        g.players[0].table[Category.SUM][0] = 10
        self.assertEqual(by_row(score_options(g))[Category.SUM].slot, 1)

    def test_no_dice_no_options(self):
        self.assertEqual(score_options(GameEngine(["A", "B"])), [])


class TestCrossOptions(unittest.TestCase):
    def test_only_open_combination_rows(self):
        g = game(1, 2, 3, 4, joker=6)
        g.players[0].table[Category.ABAKA][:3] = ["X", "X", "X"]
        opts = cross_options(g)
        self.assertEqual([m.category for m in opts], [c for c in COMBO_CATS if c != Category.ABAKA])
        self.assertTrue(all(m.cross for m in opts))
        self.assertEqual(opts[0].action_text, "Cross out Pair (lose the row and column bonuses)")


class TestOnlineEngine(unittest.TestCase):
    def test_works_through_room_engine(self):
        store = RoomStore(starting_throw=False)
        code, host = store.create("Ann")
        store.join(code, "Bob")
        store.roll(code, host)
        view = store.view(code).engine
        proxy = RoomEngine(store, code, host, view)
        self.assertIs(plain_engine(proxy), view)
        self.assertIn(Category.SUM, by_row(score_options(proxy)))


class TestNames(unittest.TestCase):
    def test_row_names(self):
        self.assertEqual(row_name(Category.SCHOOL_3), "School 3")
        self.assertEqual(row_name(Category.KARE), "Four of a kind")


if __name__ == "__main__":
    unittest.main()
