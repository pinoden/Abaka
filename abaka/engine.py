from __future__ import annotations

import random
from typing import Dict, List

from .models import Category, roll_dice
from .scoring import score_category
from .player import PlayerState
from .constants import ROW_W, COL_W, SCHOOL_CATS, COMBO_CATS
from .render import render_scoreboard, label_for
from .school import record_school
from .bonus import after_record as _after_record_bonus

class GameEngine:
    """Turn flow + thin facades to school/bonus/rendering."""

    def __init__(self, player_names: List[str]) -> None:
        self.players: List[PlayerState] = [PlayerState(n) for n in player_names]
        self.current: int = 0
        self.dice = []
        self.rolls_left: int = 0
        self.first_roll: bool = True

        self.row_bonus_claimed: Dict[Category, bool] = {cat: False for cat in Category}
        self.col_bonus_claimed: List[bool] = [False, False, False]
        self.school_minus_used: Dict[tuple[int, Category], bool] = {}
        self.row_bonus_blocked: Dict[tuple[int, Category], bool] = {}

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
            record_school(self, category, slot_index)
        else:
            score = score_category(self.dice, category, first_roll=self.first_roll)
            self.players[self.current].record(category, slot_index, score)
        self._after_record(category, slot_index)
        self.next_player()

    def record_cross(self, category: Category, slot_index: int) -> None:
        if category.name.startswith("SCHOOL_"):
            raise ValueError("You can't cross out school directly. Use 'school n' scoring.")
        self.players[self.current].cross(category, slot_index)
        # cancel row & column bonus immediately for this player
        self.row_bonus_blocked[(self.current, category)] = True
        if self.players[self.current].table[category][3] is None:
            self.players[self.current].table[category][3] = 'X'
        if self.players[self.current].column_bonus[slot_index] is None:
            self.players[self.current].column_bonus[slot_index] = 'X'
        self._after_record(category, slot_index)
        self.next_player()

    def is_game_over(self) -> bool:
        return all(p.is_complete() for p in self.players)

    def calculate_final_scores(self):
        return {p.name: p.calculate_score() for p in self.players}

    # ----- rendering -----
    def _category_label(self, cat: Category) -> str:
        # kept for CLI compatibility
        return label_for(cat)

    def print_scoreboard(self) -> None:
        for line in render_scoreboard(self):
            print(line)

    # ----- utilities -----
    def leftmost_slot(self, player: PlayerState, category: Category) -> int:
        slots = player.table[category][:3]
        for i, v in enumerate(slots):
            if v is None:
                return i
        raise ValueError("Row already complete")

    # ----- bonuses -----
    def _after_record(self, category: Category, slot_index: int) -> None:
        _after_record_bonus(self, category, slot_index)
