from __future__ import annotations
from typing import List
from .models import Category

ROW_W = 6
# 3 cells (3*3) + 2 spaces between = 11, plus " | " (3) + bonus (3) = 17
COL_W = 17

SCHOOL_CATS: List[Category] = [
    Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
    Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6,
]
COMBO_CATS: List[Category] = [
    Category.PAIR, Category.TWO_PAIRS, Category.TRIPS,
    Category.SMALL_STRAIGHT, Category.LARGE_STRAIGHT,
    Category.FULL, Category.KARE, Category.ABAKA, Category.SUM,
]
