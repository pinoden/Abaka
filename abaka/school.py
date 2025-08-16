from __future__ import annotations
from .models import Category

def record_school(engine, category: Category, slot_index: int) -> None:
    """
    School balance rules:
      - k = count of dice showing denom; joker(1) adds +1 for any denom != 1.
      - k == 3 -> cross 'X' (exactly three, no balance change).
      - k > 3  -> add (k-3)*denom to balance.
      - k < 3  -> may pay (3-k)*denom from balance ONLY IF k >= 1.
      - First-roll doubling applies to the numeric value written.
      - Any 'minus' (k < 3) crosses this player's school-row bonus immediately and blocks future grant.
    """
    p = engine.players[engine.current]
    denom = int(category.name.split('_')[1])

    # count k
    k = sum(1 for d in engine.dice if d.value == denom)
    if denom != 1 and any(d.is_joker and d.value == 1 for d in engine.dice):
        k += 1

    if k == 3:
        p.cross(category, slot_index)
        return

    def move_balance(new_value: int) -> None:
        if p.school_balance_loc is not None:
            pc, ps = p.school_balance_loc
            p.table[pc][ps] = 'X'
        val = new_value * (2 if engine.first_roll else 1)
        p.record(category, slot_index, val)
        p.school_balance = val
        p.school_balance_loc = (category, slot_index)

    if k > 3:
        delta = (k - 3) * denom
        move_balance(p.school_balance + delta)
        return

    # k < 3 -> must show at least one die of denom
    if k == 0:
        raise ValueError("Cannot write this school row: need at least one die of that denomination")

    required = (3 - k) * denom
    if p.school_balance >= required:
        move_balance(p.school_balance - required)
        engine.school_minus_used[(engine.current, category)] = True
        if p.table[category][3] is None:
            p.table[category][3] = 'X'   # immediate visual cross of row bonus
        return

    raise ValueError(f"Not enough school balance to write this row (need {required}, have {p.school_balance})")
