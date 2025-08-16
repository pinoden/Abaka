from __future__ import annotations
from typing import List
from .models import Category
from .constants import SCHOOL_CATS, COMBO_CATS

def after_record(engine, category: Category, slot_index: int) -> None:
    _check_row_bonus(engine, engine.current, category)
    if slot_index in (0, 1, 2):
        _check_col_bonus(engine, engine.current, slot_index)

# ---------- ROW BONUS (unchanged from your rules) ----------
def _check_row_bonus(engine, player_idx: int, category: Category) -> None:
    if engine.row_bonus_claimed.get(category):
        return
    p = engine.players[player_idx]
    # only when first three cells are filled/crossed
    if not all(v is not None for v in p.table[category][:3]):
        return

    engine.row_bonus_claimed[category] = True

    if category.name.startswith("SCHOOL_"):
        num = int(category.name.split('_')[1])
        # minus in school cancels the school *row* bonus only
        val = 'X' if engine.school_minus_used.get((player_idx, category), False) else num * 3
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

    # Others in this row get X
    for i, other in enumerate(engine.players):
        if i != player_idx and other.table[category][3] is None:
            other.table[category][3] = 'X'

# ---------- COLUMN BONUS (fixed per your new rules) ----------
def _check_col_bonus(engine, player_idx: int, col: int) -> None:
    """
    Columns 0 & 1:
      - First player to COMPLETE the column gets the bonus.
      - Requirement: the SCHOOL in this column must be filled (can contain X),
        and the BOTTOM HALF (non-school rows) must have NO crosses (all numeric).
      - Value = max numeric in the column.
      - Others get X.

    Column 2 (final):
      - Each player can get their own bonus when they COMPLETE the column.
      - Same requirement: bottom half has NO crosses; school can have X.
      - Value = max numeric in the column; if bottom has any X -> X.
    """
    p = engine.players[player_idx]

    # Gather column values for this player
    col_vals_all = {cat: p.table[cat][col] for cat in Category}
    col_complete = all(v is not None for v in col_vals_all.values())
    if not col_complete:
        return

    bottom_has_cross = any(col_vals_all[cat] == 'X' for cat in COMBO_CATS)
    # collect numeric values across whole column for max()
    nums = [v for v in col_vals_all.values() if isinstance(v, int)]
    val = 'X' if bottom_has_cross else (max(nums) if nums else 'X')

    # ----- Final column: individual -----
    if col == 2:
        if p.column_bonus[col] is None:
            p.column_bonus[col] = val
        return

    # ----- Columns 0 & 1: first-come, others X -----
    if engine.col_bonus_claimed[col]:
        return  # someone already claimed; others should have X set when it was claimed

    # First claimant
    engine.col_bonus_claimed[col] = True
    p.column_bonus[col] = val
    # Lock out others
    for i, other in enumerate(engine.players):
        if i != player_idx and other.column_bonus[col] is None:
            other.column_bonus[col] = 'X'
