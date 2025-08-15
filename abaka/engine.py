from __future__ import annotations

import random
from typing import Dict, List, Optional

from .models import Category, roll_dice
from .scoring import score_category
from .player import PlayerState


# ---- display layout constants ----
ROW_W = 6          # label column width
COL_W = 15         # per-player column width: 4 cells * 3 chars + 3 spaces = 15

SCHOOL_CATS: List[Category] = [
    Category.SCHOOL_1, Category.SCHOOL_2, Category.SCHOOL_3,
    Category.SCHOOL_4, Category.SCHOOL_5, Category.SCHOOL_6,
]
COMBO_CATS: List[Category] = [
    Category.PAIR, Category.TWO_PAIRS, Category.TRIPS,
    Category.SMALL_STRAIGHT, Category.LARGE_STRAIGHT,
    Category.FULL, Category.KARE, Category.ABAKA, Category.SUM,
]


class GameEngine:
    """Core game logic: turn flow, scoring hooks, bonuses, school-balance, and scoreboard rendering."""

    def __init__(self, player_names: List[str]) -> None:
        self.players: List[PlayerState] = [PlayerState(n) for n in player_names]
        self.current: int = 0
        self.dice = []
        self.rolls_left: int = 0
        self.first_roll: bool = True

        # Bonus claims: first to complete wins; others get X.
        self.row_bonus_claimed: Dict[Category, bool] = {cat: False for cat in Category}
        self.col_bonus_claimed: List[bool] = [False, False, False]  # for columns 0..2

    # ----- turn flow -----
    def next_player(self) -> None:
        self.current = (self.current + 1) % len(self.players)

    def start_turn(self) -> None:
        self.dice = roll_dice()
        self.rolls_left = 2
        self.first_roll = True

    def reroll(self, indices: List[int]) -> None:
        if self.rolls_left <= 0:
            raise RuntimeError("No rerolls left")
        for i in indices:
            if i < 0 or i >= len(self.dice):
                raise IndexError("Bad die index")
            self.dice[i].value = random.randint(1, 6)
        self.rolls_left -= 1
        if self.rolls_left < 2:
            self.first_roll = False

    def record_score(self, category: Category, slot_index: int) -> None:
        if category.name.startswith("SCHOOL_"):
            self._record_school(category, slot_index)
        else:
            score = score_category(self.dice, category, first_roll=self.first_roll)
            self.players[self.current].record(category, slot_index, score)

        self._after_record(category, slot_index)
        self.next_player()

    def record_cross(self, category: Category, slot_index: int) -> None:
        self.players[self.current].cross(category, slot_index)
        self._after_record(category, slot_index)
        self.next_player()

    def is_game_over(self) -> bool:
        return all(p.is_complete() for p in self.players)

    def calculate_final_scores(self) -> Dict[str, int]:
        return {p.name: p.calculate_score() for p in self.players}

    # ----- scoreboard rendering -----
    def _category_label(self, cat: Category) -> str:
        if cat.name.startswith("SCHOOL_"):
            return cat.name.split('_')[1]
        mapping = {
            Category.PAIR: 'D',   # pair
            Category.TWO_PAIRS: 'DD',
            Category.TRIPS: 'T',
            Category.SMALL_STRAIGHT: 'LS',  # little straight
            Category.LARGE_STRAIGHT: 'BS',  # big straight
            Category.FULL: 'F',
            Category.KARE: 'C',
            Category.ABAKA: 'A',
            Category.SUM: 'Σ',
        }
        return mapping[cat]

    def _fmt_cell(self, v) -> str:
        if v is None:
            return ' . '
        if v == 'X':
            return ' X '
        return f"{int(v):>3}"

    def print_scoreboard(self) -> None:
        header = f"{'Row':>{ROW_W}} " + ''.join(f"| {p.name:^{COL_W}} " for p in self.players)
        print("\n" + header)
        sep = '-' * len(header)
        print(sep)

        def print_row(cat: Category) -> None:
            label = self._category_label(cat)
            line = f"{label:>{ROW_W}} "
            for p in self.players:
                # 4 cells per row (3 score + 1 bonus):
                cells = ' '.join(self._fmt_cell(v) for v in p.table[cat])
                line += f"| {cells:<{COL_W}} "
            print(line)

        # school section
        for cat in SCHOOL_CATS:
            print_row(cat)
        print(sep)

        # combos
        for cat in COMBO_CATS:
            print_row(cat)

        # column bonuses row (B)
        line = f"{'B':>{ROW_W}} "
        for p in self.players:
            cells3 = ' '.join(self._fmt_cell(v) for v in p.column_bonus)
            cells = f"{cells3} {' . ':>3}"  # pad to 4 cells width
            line += f"| {cells:<{COL_W}} "
        print(line)

        print(sep)
        total = f"{'TOT':>{ROW_W}} " + ''.join(
            f"| {p.calculate_score():>{COL_W}} " for p in self.players
        )
        print(total)

    def leftmost_slot(self, player: PlayerState, category: Category) -> int:
        slots = player.table[category][:3]
        for i, v in enumerate(slots):
            if v is None:
                return i
        raise ValueError("Row already complete")

    # ----- bonuses -----
    def _after_record(self, category: Category, slot_index: int) -> None:
        self._check_row_bonus(self.current, category)
        if slot_index in (0, 1, 2):
            self._check_col_bonus(self.current, slot_index)

    def _check_row_bonus(self, player_idx: int, category: Category) -> None:
        if self.row_bonus_claimed.get(category):
            return
        p = self.players[player_idx]
        if all(v is not None for v in p.table[category][:3]):
            self.row_bonus_claimed[category] = True
            row = p.table[category][:3]
            if any(v == 'X' for v in row):
                val = 'X'
            elif category.name.startswith("SCHOOL_"):
                num = int(category.name.split('_')[1])
                val = num * 3
            else:
                vals = [v for v in row if isinstance(v, int)]
                val = max(vals) if vals else 'X'

            # award to owner, cross for others
            p.table[category][3] = val
            for i, other in enumerate(self.players):
                if i != player_idx and other.table[category][3] is None:
                    other.table[category][3] = 'X'

    def _check_col_bonus(self, player_idx: int, col: int) -> None:
        if self.col_bonus_claimed[col]:
            return
        p = self.players[player_idx]
        col_vals = [p.table[cat][col] for cat in Category]
        if all(v is not None for v in col_vals):
            self.col_bonus_claimed[col] = True
            if any(v == 'X' for v in col_vals):
                val = 'X'
            else:
                vals = [v for v in col_vals if isinstance(v, int)]
                val = max(vals) if vals else 'X'
            p.column_bonus[col] = val
            for i, other in enumerate(self.players):
                if i != player_idx and other.column_bonus[col] is None:
                    other.column_bonus[col] = 'X'

    # ----- school balance -----
    def _record_school(self, category: Category, slot_index: int) -> None:
        """
        Implements school balance rules:

        - Let k = count of dice showing denom right now.
          * All dice with face == denom count (+1 each).
          * Joker showing 2..6 counts as that face (already included above).
          * Joker showing 1 is wild: add +1 for any denom except denom=1
            (for denom=1 it's already counted by face==denom).
        - k == 3  -> cross 'X' (exactly three; no add/subtract).
        - k > 3   -> add (k-3)*denom to balance (move/cross previous balance cell).
        - k < 3   -> need to pay (3-k)*denom from balance; special case k==0: max(required, 2*denom).
        - First-roll rule: written numeric value is doubled.
        """
        p = self.players[self.current]
        denom = int(category.name.split('_')[1])

        # count k
        k = sum(1 for d in self.dice if d.value == denom)
        if denom != 1 and any(d.is_joker and d.value == 1 for d in self.dice):
            # joker(1) can stand in for any denom != 1
            k += 1

        # exactly three: cross out
        if k == 3:
            p.cross(category, slot_index)
            return

        def move_balance(new_value: int) -> None:
            # cross previous balance cell (if any), then write new value here
            if p.school_balance_loc is not None:
                pc, ps = p.school_balance_loc
                p.table[pc][ps] = 'X'
            val = new_value * (2 if self.first_roll else 1)
            p.record(category, slot_index, val)
            p.school_balance = val
            p.school_balance_loc = (category, slot_index)

        if k > 3:
            delta = (k - 3) * denom
            move_balance(p.school_balance + delta)
            return

        # k < 3: need to pay from balance
        required = (3 - k) * denom
        if k == 0:
            required = max(required, 2 * denom)  # special case you specified
        if p.school_balance >= required:
            move_balance(p.school_balance - required)
            return

        raise ValueError(f"Not enough school balance to write this row (need {required}, have {p.school_balance})")
