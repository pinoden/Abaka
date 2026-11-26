from __future__ import annotations

import random
from typing import Dict, List, Optional, Tuple
from collections import Counter  # <-- for helpful mismatch messages

from .models import Category, Die, is_school, roll_dice
from .scoring import score_category
from .player import PlayerState
# from .constants import ROW_W, COL_W, SCHOOL_CATS, COMBO_CATS
from .render import render_scoreboard, label_for
from .school import record_school
from .bonus import after_record as _after_record_bonus


# Categories where writing a zero should be rejected (must meet the combo)
NON_SCHOOL_STRICT = {
    Category.PAIR, Category.TWO_PAIRS, Category.TRIPS,
    Category.SMALL_STRAIGHT, Category.LARGE_STRAIGHT,
    Category.FULL, Category.KARE, Category.ABAKA,
}


class GameEngine:
    """Turn flow + thin facades to school/bonus/rendering."""

    def __init__(self, player_names: List[str], starting_throw: bool = False) -> None:
        """
        starting_throw: decide who goes first by the starting throw (the owner's rule,
        2026-11-16): before the first round each player throws all five dice and the
        lowest total starts. Players who tie for the lowest throw again. Without it,
        the player at `current` (0 unless changed) starts.
        """
        self.players: List[PlayerState] = [PlayerState(n) for n in player_names]
        self.current: int = 0
        self.dice = []
        self.rolls_left: int = 0
        self.first_roll: bool = True

        self.row_bonus_claimed: Dict[Category, bool] = {cat: False for cat in Category}
        self.col_bonus_claimed: List[bool] = [False, False, False]
        # (player, row) pairs whose row bonus is gone: a crossed-out combination cell, or a
        # School row paid from the balance (school.py).
        self.row_bonus_blocked: Dict[tuple[int, Category], bool] = {}
        # The cell written by the most recent move: (player index, category, slot), or None.
        self.last_move: Optional[Tuple[int, Category, int]] = None
        # Every player's total after each move, for the chart of scores by move (a tester,
        # 2026-11-26): (moves made so far, (total of each seat)). A tuple, never changed in
        # place, so clone() shares it. Games saved before it start theirs where they are.
        self.score_history: Tuple[Tuple[int, Tuple[int, ...]], ...] = ()

        # Starting throw. `throw_round` lists the players throwing in the current round, in
        # order; `current` is the one whose throw is next. It is empty once the first player
        # is decided (or when there is no starting throw).
        self.throw_round: List[int] = list(range(len(self.players))) if starting_throw else []
        self.throw_round_no: int = 1
        # Every throw so far: {"round", "player", "dice": [(value, is_joker), ...], "total"}.
        self.starting_throws: List[dict] = []
        self.first_player: Optional[int] = None  # who won the starting throw

    def clone(self) -> "GameEngine":
        """
        An independent copy of the game, about 20 times cheaper than copy.deepcopy.

        Every attribute is carried over; the mutable ones (players, dice, lists and
        dicts) get new containers, so changing the copy never changes this game.
        tests/test_clone.py checks that no mutable attribute is ever shared.
        """
        g = GameEngine.__new__(GameEngine)
        g.__dict__.update(self.__dict__)
        g.players = [p.clone() for p in self.players]
        g.dice = [Die(d.value, is_joker=d.is_joker) for d in self.dice]
        g.row_bonus_claimed = dict(self.row_bonus_claimed)
        g.col_bonus_claimed = list(self.col_bonus_claimed)
        g.row_bonus_blocked = dict(self.row_bonus_blocked)
        g.throw_round = list(self.throw_round)
        g.starting_throws = [dict(t, dice=list(t["dice"])) for t in self.starting_throws]
        return g

    # ----- starting throw -----
    @property
    def choosing_first_player(self) -> bool:
        """True until the starting throw has decided who goes first."""
        return bool(self.throw_round)

    def throw_for_start(self) -> None:
        """The current player throws all five dice for the starting throw."""
        if not self.throw_round:
            raise ValueError("The first player has already been decided.")
        player = self.current
        dice = roll_dice()
        self.starting_throws.append({
            "round": self.throw_round_no,
            "player": player,
            "dice": [(d.value, d.is_joker) for d in dice],
            "total": sum(d.value for d in dice),  # face values: the joker's wild 1 is for combinations only
        })
        position = self.throw_round.index(player)
        if position + 1 < len(self.throw_round):
            self.current = self.throw_round[position + 1]
            return
        # Everyone in this round has thrown: the lowest total starts; a tie throws again.
        totals = {t["player"]: t["total"] for t in self.starting_throws if t["round"] == self.throw_round_no}
        lowest = min(totals.values())
        tied = [p for p in self.throw_round if totals[p] == lowest]
        if len(tied) == 1:
            self.throw_round = []
            self.first_player = tied[0]
            self.current = tied[0]
        else:
            self.throw_round = tied
            self.throw_round_no += 1
            self.current = tied[0]

    # ----- turn flow -----
    def next_player(self) -> None:
        self.current = (self.current + 1) % len(self.players)

    def start_turn(self) -> None:
        if self.throw_round:
            raise ValueError("Throw for the first turn first: the lowest throw starts.")
        self.dice = roll_dice()
        self.rolls_left = 2
        self.first_roll = True

    def _end_turn(self) -> None:
        """Pass the turn. Dice are cleared, so `not self.dice` means "not rolled yet"."""
        moves = sum(v is not None for p in self.players for cells in p.table.values() for v in cells[:3])
        self.score_history += ((moves, tuple(p.calculate_score() for p in self.players)),)
        self.dice = []
        self.rolls_left = 0
        self.first_roll = True
        self.next_player()

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

    # ----- scoring -----
    def _explain_mismatch(self, category: Category) -> str:
        """Human-friendly hint when a strict row would otherwise record a zero."""
        vals = [d.value for d in self.dice]
        cnt = Counter(vals)
        joker_wild = any(d.is_joker and d.value == 1 for d in self.dice)

        if category == Category.ABAKA:
            v, c = max(cnt.items(), key=lambda kv: kv[1])
            extra = " + wild(1)" if joker_wild else ""
            return (f"Abaka needs five of a kind. You have {c}×{v}{extra}. "
                    f"Joker is wild only when it shows 1.")
        if category == Category.KARE:
            v, c = max(cnt.items(), key=lambda kv: kv[1])
            extra = " + wild(1)" if joker_wild else ""
            return f"Kare needs four of a kind. You have {c}×{v}{extra}."
        if category == Category.FULL:
            return "Full needs 3+2 of different ranks (strict)."
        if category in (Category.SMALL_STRAIGHT, Category.LARGE_STRAIGHT):
            return ("Straights need the exact pattern: "
                    "LS = 1–2–3–4–5, BS = 2–3–4–5–6. "
                    "Joker is wild only when it shows 1.")
        if category == Category.TRIPS:
            return "Trips needs three of a kind."
        if category == Category.TWO_PAIRS:
            return "Two Pairs needs two different pairs."
        if category == Category.PAIR:
            return "Pair needs at least one pair."
        return f"{category.name} conditions not met for this roll."

    def record_score(self, category: Category, slot_index: int) -> None:
        if is_school(category):
            record_school(self, category, slot_index)
        else:
            score = score_category(self.dice, category, first_roll=self.first_roll)
            # Disallow accidental zero on strict rows (forces player to cross instead)
            if category in NON_SCHOOL_STRICT and score == 0:
                raise ValueError(self._explain_mismatch(category))
            self.players[self.current].record(category, slot_index, score)

        self.last_move = (self.current, category, slot_index)
        self._after_record(category, slot_index)
        self._end_turn()

    def record_cross(self, category: Category, slot_index: int) -> None:
        if is_school(category):
            raise ValueError("You can't cross out school directly. Use 'school n' scoring.")
        self.players[self.current].cross(category, slot_index)
        # cancel row & column bonus immediately for this player
        self.row_bonus_blocked[(self.current, category)] = True
        if self.players[self.current].table[category][3] is None:
            self.players[self.current].table[category][3] = 'X'
        if self.players[self.current].column_bonus[slot_index] is None:
            self.players[self.current].column_bonus[slot_index] = 'X'
        self.last_move = (self.current, category, slot_index)
        self._after_record(category, slot_index)
        self._end_turn()

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
