from __future__ import annotations
from .models import Category

def record_school(engine, category: Category, slot_index: int) -> None:
    """
    School balance rules:
      - k = count of dice showing denom; joker(1) adds +1 for any denom != 1.
      - k == 3 -> cross 'X' (exactly three, no balance change).
      - k > 3  -> add (k-3)*denom to balance (write new balance).
      - k < 3  -> pay (3-k)*denom from balance, BUT:
          * normally you must have k >= 1 (at least one die of denom) and balance >= required;
          * EXCEPTION (endgame): if ALL non-school cells are filled (true endgame),
            and k == 0 for this denom, you may pay 2*denom EVEN IF it drives balance negative.
      - First-roll doubling applies to the numeric value written.
      - Any 'minus' (k < 3) crosses this player's school-row bonus immediately and blocks future grant.
    """
    p = engine.players[engine.current]
    denom = int(category.name.split('_')[1])

    # count k
    k = sum(1 for d in engine.dice if d.value == denom)
    if denom != 1 and any(d.is_joker and d.value == 1 for d in engine.dice):
        k += 1

    # exactly three -> cross
    if k == 3:
        p.cross(category, slot_index)
        return

    def move_balance(new_value: int) -> None:
        # cross previous balance cell (if any), then write new value here
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

    # k < 3
    required = (3 - k) * denom

    # Normal minus path: need at least one die of denom and enough balance
    if k >= 1:
        if p.school_balance >= required:
            move_balance(p.school_balance - required)
            engine.school_minus_used[(engine.current, category)] = True
            if p.table[category][3] is None:
                p.table[category][3] = 'X'
            return
        raise ValueError(f"Not enough school balance to write this row (need {required}, have {p.school_balance})")

    # k == 0  (no dice of denom)
    # Endgame exception: allow 2*denom, even if it makes balance negative,
    # ONLY if all non-school cells are filled (true endgame).
    if k == 0 and p.non_school_complete():
        cost = 2 * denom
        move_balance(p.school_balance - cost)  # may go negative
        engine.school_minus_used[(engine.current, category)] = True
        if p.table[category][3] is None:
            p.table[category][3] = 'X'
        return

    # Otherwise not allowed
    raise ValueError("Cannot write this school row: need at least one die of that denomination")
