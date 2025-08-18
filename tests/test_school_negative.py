import unittest

from abaka.engine import GameEngine
from abaka.models import Category, Die
from abaka.constants import COMBO_CATS


def fill_bottom_complete(p):
    """Заполнить все 27 ячеек нижней части любыми числами (для простоты — 1)."""
    for cat in COMBO_CATS:
        p.table[cat][0] = 1
        p.table[cat][1] = 1
        p.table[cat][2] = 1


class TestSchoolNegativeEndgame(unittest.TestCase):
    def test_endgame_k0_allows_negative_balance(self):
        g = GameEngine(["P1"])
        p = g.players[0]
        fill_bottom_complete(p)
        # Баланс до записи
        p.school_balance = 2
        p.school_balance_loc = None

        # Кости: ни одной пятёрки, джокер не 1 -> k=0 для denom=5
        g.dice = [Die(1), Die(2), Die(3), Die(4), Die(6, is_joker=True)]
        # Записываем в school_5 (левейшая свободная)
        slot = g.leftmost_slot(p, Category.SCHOOL_5)
        g.record_score(Category.SCHOOL_5, slot)

        # Баланс ушёл в минус на 2*5 = 10: 2 - 10 = -8
        self.assertEqual(p.school_balance, -8)
        self.assertEqual(p.table[Category.SCHOOL_5][slot], -8)
        # Бонус строки школы перечёркнут
        self.assertEqual(p.table[Category.SCHOOL_5][3], 'X')

        # Финальный счёт: 27 единиц внизу + (-8) в школе + штраф -800 = -781
        self.assertEqual(p.calculate_score(), -781)

    def test_endgame_k1_allows_negative_balance(self):
        g = GameEngine(["P1"])
        p = g.players[0]
        fill_bottom_complete(p)
        p.school_balance = 0
        p.school_balance_loc = None

        # Кости: одна единица, джокер не 1 -> k=1 для denom=1, required = 2
        g.dice = [Die(1), Die(2), Die(3), Die(4), Die(6, is_joker=True)]
        slot = g.leftmost_slot(p, Category.SCHOOL_1)
        g.record_score(Category.SCHOOL_1, slot)

        # Баланс: 0 - 2 = -2 (без удвоения)
        self.assertEqual(p.school_balance, -2)
        self.assertEqual(p.table[Category.SCHOOL_1][slot], -2)
        self.assertEqual(p.table[Category.SCHOOL_1][3], 'X')

        # 27 (низ) - 2 - 200 = -175
        self.assertEqual(p.calculate_score(), -175)

    def test_midgame_disallows_negative_when_k0(self):
        g = GameEngine(["P1"])
        p = g.players[0]
        # низ НЕ завершён (пусто)
        p.school_balance = 0
        p.school_balance_loc = None

        # Кости: k=0 для denom=5
        g.dice = [Die(1), Die(2), Die(3), Die(4), Die(6, is_joker=True)]
        slot = g.leftmost_slot(p, Category.SCHOOL_5)
        with self.assertRaises(ValueError):
            g.record_score(Category.SCHOOL_5, slot)


if __name__ == "__main__":
    unittest.main()
