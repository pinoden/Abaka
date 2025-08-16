from __future__ import annotations
from typing import Dict, Tuple
from .models import Category

def after_record(engine, category: Category, slot_index: int) -> None:
    _check_row_bonus(engine, engine.current, category)
    if slot_index in (0, 1, 2):
        _check_col_bonus(engine, engine.current, slot_index)

def _check_row_bonus(engine, player_idx: int, category: Category) -> None:
    if engine.row_bonus_claimed.get(category):
        return
    p = engine.players[player_idx]
    if not all(v is not None for v in p.table[category][:3]):
        return

    engine.row_bonus_claimed[category] = True

    if category.name.startswith("SCHOOL_"):
        num = int(category.name.split('_')[1])
        if engine.school_minus_used.get((player_idx, category), False):
            val = 'X'
        else:
            val = num * 3
        if p.table[category][3] is None:
            p.table[category][3] = val
    else:
        blocked = getattr(engine, "row_bonus_blocked", {}).get((player_idx, category), False)
        row = p.table[category][:3]
        if blocked or any(v == 'X' for v in row):
            val = 'X'
        else:
            nums = [v for v in row if isinstance(v, int)]
            val = max(nums) if nums else 'X'
        p.table[category][3] = val

    for i, other in enumerate(engine.players):
        if i != player_idx and other.table[category][3] is None:
            other.table[category][3] = 'X'

def _check_col_bonus(engine, player_idx: int, col: int) -> None:
    p = engine.players[player_idx]
    col_vals = [p.table[cat][col] for cat in Category]

    # Final column: individual bonuses
    if col == 2:
        if p.column_bonus[col] is not None:
            return
        if not all(v is not None for v in col_vals):
            return
        val = 'X' if any(v == 'X' for v in col_vals) else (max(v for v in col_vals if isinstance(v, int)) if any(isinstance(v, int) for v in col_vals) else 'X')
        p.column_bonus[col] = val
        return

    # Columns 0 and 1: first-come, others X
    if engine.col_bonus_claimed[col]:
        return
    if all(v is not None for v in col_vals):
        engine.col_bonus_claimed[col] = True
        val = 'X' if any(v == 'X' for v in col_vals) else (max(v for v in col_vals if isinstance(v, int)) if any(isinstance(v, int) for v in col_vals) else 'X')
        p.column_bonus[col] = val
        for i, other in enumerate(engine.players):
            if i != player_idx and other.column_bonus[col] is None:
                other.column_bonus[col] = 'X'
