"""
The computer player (owner, Backlog item 33: "build a bot so you could play abaka against
computer").

Given a game whose current player is the computer, `next_step(engine)` says what it does
next: throw for the first turn, roll, roll some dice again, or write a cell. It only ever
chooses among the moves the rules offer (abaka/moves.py); no rule lives here.

How it chooses
--------------
A move is worth the points it adds now plus the change it makes to what the player's board
can still earn (its "potential"):

- every empty combination cell is worth part of what such a cell usually brings later
  (CELL), so writing a poor score in a valuable row costs more than it brings;
- a row or column whose bonus the player can still win is worth that bonus, times the
  chance that its empty cells all get a number (P_OK) and that the player completes it
  first. Crossing a cell out loses both bonuses at once, so the computer crosses out where
  nothing is left to lose (a row or column that is already dead, Abaka early on);
- the School balance counts as points, but a negative balance costs 100 a point at the end.
  Its expected end is worked out from the School cells still empty, each written later by
  choice (three or more of its number) or by force once the combination cells run out
  (_expected_end). So the computer fills School rows in time and keeps a reserve.

Which dice to keep is an exact expectation over every outcome of the rolls left. A hand is
its four normal dice (as a multiset) and the joker's value: 756 hands. The best move's
value is worked out for each hand, then the expected value of each way to keep dice, two
rolls deep, with the first roll's doubling for standing at once. A decision takes about
6 ms (median; under 15 ms at the 95th percentile, on an M1).

No Streamlit here, and Python 3.8 like the rest of the package.
"""

from __future__ import annotations

import math
import random
from itertools import combinations_with_replacement, product
from typing import Dict, List, Optional, Sequence, Tuple

from .constants import COMBO_CATS, SCHOOL_CATS
from .models import SCHOOL_NUMBERS, Category, Die
from .i18n import t
from .moves import cross_options, plain_engine, score_options
from .scoring import score_category

# What an empty cell of a combination row usually brings later (a number, or nothing when
# it ends crossed out), the chance that it gets a number, and the usual best of a row and
# of a column (for their bonuses). Tuned by playing variants against each other.
TYPICAL = {
    Category.PAIR: 10, Category.TWO_PAIRS: 16, Category.TRIPS: 13,
    Category.SMALL_STRAIGHT: 17, Category.LARGE_STRAIGHT: 23, Category.FULL: 24,
    Category.KARE: 42, Category.ABAKA: 80, Category.SUM: 25,
}
P_OK = {
    Category.PAIR: 0.97, Category.TWO_PAIRS: 0.9, Category.TRIPS: 0.9,
    Category.SMALL_STRAIGHT: 0.7, Category.LARGE_STRAIGHT: 0.7, Category.FULL: 0.8,
    Category.KARE: 0.55, Category.ABAKA: 0.25, Category.SUM: 1.0,
}
CELL_WEIGHT = 0.6                    # how much of TYPICAL x P_OK an empty cell is worth now
CELL = {c: CELL_WEIGHT * TYPICAL[c] * P_OK[c] for c in COMBO_CATS}
ROW_TYPICAL = {c: 1.25 * TYPICAL[c] for c in COMBO_CATS}  # the usual best of a row's three
COLUMN_TYPICAL = 60                  # the usual best of a column
P_PAR = 0.75                         # a School cell later gets three of its number or more
# An empty School cell is written later either by choice, when three or more of its number
# come up (CHOSEN: how many more than three, and how often), or because nothing else is left
# (the end of the game), aiming at its number with all three rolls (_forced). The second
# kind's share grows as the combination cells run out: half of them when there are FORCED
# empty combination cells per empty School cell, all of them when none are left.
CHOSEN = ((0, 0.70), (1, 0.25), (2, 0.05))
FORCED = 0.5

NORMALS: List[Tuple[int, ...]] = list(combinations_with_replacement(range(1, 7), 4))
_NORMAL_INDEX = {n: i for i, n in enumerate(NORMALS)}
HANDS = len(NORMALS) * 6             # 126 multisets of four normal dice, times the joker's value


def hand_index(normal: Sequence[int], joker: int) -> int:
    return _NORMAL_INDEX[tuple(sorted(normal))] * 6 + joker - 1


class _Tables:
    """What every decision needs, made once per process (about 0.2 s, on the first decision)."""

    def __init__(self) -> None:
        self.raw: List[List[int]] = []      # per hand: each combination's score (not doubled)
        self.count: List[List[int]] = []    # per hand: dice counted for School 1..6 (index 1..6)
        for normal in NORMALS:
            for joker in range(1, 7):
                dice = [Die(v) for v in normal] + [Die(joker, is_joker=True)]
                self.raw.append([score_category(dice, c) for c in COMBO_CATS])
                values = list(normal) + [joker]
                self.count.append([0] + [values.count(n) + (1 if n != 1 and joker == 1 else 0)
                                         for n in range(1, 7)])
        # A "keep": the normal dice kept (a sorted tuple) and the joker kept (its value) or 0.
        self.keeps: Dict[Tuple[Tuple[int, ...], int], int] = {}
        self.kept: List[Tuple[Tuple[int, ...], int]] = []  # each keep, by its number
        self.outcomes: List[Tuple[List[int], List[float]]] = []
        for size in range(5):
            for kept in combinations_with_replacement(range(1, 7), size):
                for joker in range(7):
                    self.keeps[(kept, joker)] = len(self.outcomes)
                    self.kept.append((kept, joker))
                    self.outcomes.append(self._outcomes(kept, joker))
        # Per hand: its keeps (except keeping everything, which only wastes a roll).
        self.hand_keeps: List[List[int]] = []
        for normal in NORMALS:
            subsets = {tuple(sorted(s)) for r in range(5) for s in _sub_multisets(normal, r)}
            for joker in range(1, 7):
                ids = [self.keeps[(s, j)] for s in subsets for j in (0, joker)
                       if not (len(s) == 4 and j == joker)]
                self.hand_keeps.append(ids)

    @staticmethod
    def _outcomes(kept: Tuple[int, ...], joker: int) -> Tuple[List[int], List[float]]:
        rolled = 4 - len(kept)
        jokers = [joker] if joker else list(range(1, 7))
        weight = 1.0 / (6 ** rolled * len(jokers))
        found: Dict[int, float] = {}
        for new in product(range(1, 7), repeat=rolled):
            normal = kept + new
            for j in jokers:
                i = hand_index(normal, j)
                found[i] = found.get(i, 0.0) + weight
        return list(found), list(found.values())


def _sub_multisets(values: Sequence[int], size: int):
    from itertools import combinations
    return combinations(values, size)


_tables: Optional[_Tables] = None


def tables() -> _Tables:
    global _tables
    if _tables is None:
        _tables = _Tables()
    return _tables


# ------------------------------------------------------------------ the board ----

class _Board:
    """The computer's board as it stands this turn: what each kind of move would be worth."""

    def __init__(self, engine, me: int) -> None:
        self.engine = engine
        self.me = me
        self.p = engine.players[me]
        self.others = [q for i, q in enumerate(engine.players) if i != me]
        table = self.p.table
        self.balance = self.p.school_balance
        self.school_empty = sum(v is None for c in SCHOOL_CATS for v in table[c][:3])
        self.endgame = self.p.non_school_complete()
        self.slot = {c: next((i for i, v in enumerate(table[c][:3]) if v is None), None) for c in table}
        # Empty cells of each column, and the best number in it.
        self.column_empty = [[c for c in table if table[c][s] is None] for s in range(3)]
        self.column_best = [max([v for c in table for v in (table[c][s],) if _num(v)], default=0)
                            for s in range(3)]
        self._combo_cache: Dict[Tuple[Category, int], Tuple[float, float]] = {}
        self.school_cells = [SCHOOL_NUMBERS[c] for c in SCHOOL_CATS for v in table[c][:3] if v is None]
        self.combo_empty = sum(v is None for c in COMBO_CATS for v in table[c][:3])
        self.school_now = self._school_future(self.balance, self.school_cells, self.combo_empty)
        # Filling a combination cell leaves fewer ways to avoid a poor School cell later.
        self.school_after_combo = (self._school_future(self.balance, self.school_cells, self.combo_empty - 1)
                                   - self.school_now if self.combo_empty else 0.0)
        self.school_value = {c: [self._school(c, k) for k in range(6)] for c in SCHOOL_CATS}
        self.cross_value = {c: self._cross(c) for c in COMBO_CATS if self.slot[c] is not None}
        self.best_cross = max(self.cross_value.values(), default=None)

    # --- the races for shared bonuses ---
    def _row_chance(self, category: Category, filled: int) -> float:
        if not self.others:
            return 1.0
        rival = max(sum(v is not None for v in q.table[category][:3]) for q in self.others)
        chance = min(0.9, max(0.1, 0.5 + 0.25 * (filled - rival)))
        return chance * 0.8 ** (len(self.others) - 1)

    def _column_chance(self, column: int, empty: int) -> float:
        if column == 2 or not self.others:
            return 1.0  # each player's own
        rival = min(sum(q.table[c][column] is None for c in q.table) for q in self.others)
        chance = min(0.9, max(0.1, 0.5 + 0.1 * (rival - empty)))
        return chance * 0.8 ** (len(self.others) - 1)

    def _row_alive(self, category: Category) -> bool:
        cells = self.p.table[category]
        if category in SCHOOL_NUMBERS:
            return cells[3] is None  # an X there is "exactly three", which keeps the bonus
        return cells[3] is None and "X" not in cells[:3]

    def _row_potential(self, category: Category, written=None) -> float:
        """What the row's bonus is worth now (with `written` put in its next cell, if given)."""
        if not self._row_alive(category):
            return 0.0
        cells = [v for v in self.p.table[category][:3] if v is not None]
        if written is not None:
            if written == "X" and category in COMBO_CATS:
                return 0.0
            cells.append(written)
        empty = 3 - len(cells)
        if empty == 0:
            return 0.0  # completed: the bonus is in the move's points
        chance = self._row_chance(category, len(cells))
        if category in SCHOOL_NUMBERS:
            return chance * P_PAR ** empty * 3 * SCHOOL_NUMBERS[category]
        best = max([v for v in cells if _num(v)] + [ROW_TYPICAL[category]])
        return chance * P_OK[category] ** empty * best

    def _column_potential(self, column: int, filled: Optional[Category] = None, written=None) -> float:
        if self.p.column_bonus[column] is not None:
            return 0.0
        empty = [c for c in self.column_empty[column] if c is not filled]
        if filled is not None and written == "X" and filled in COMBO_CATS:
            return 0.0
        if not empty:
            return 0.0  # completed: the bonus is in the move's points
        chance = self._column_chance(column, len(empty))
        for c in empty:
            if c in P_OK:
                chance *= P_OK[c]
        best = max(self.column_best[column], written if _num(written) else 0, COLUMN_TYPICAL)
        return chance * best

    def _completes(self, category: Category, column: int, written) -> int:
        """The bonus points a number written in `category`'s next cell earns at once (row, column)."""
        points = 0
        cells = self.p.table[category]
        if column == 2 and self._row_alive(category) and not self.engine.row_bonus_claimed[category]:
            if category in SCHOOL_NUMBERS:
                points += 3 * SCHOOL_NUMBERS[category]
            else:
                points += max([v for v in cells[:2] if _num(v)] + [written])
        if (self.p.column_bonus[column] is None and self.column_empty[column] == [category]
                and not (column < 2 and self.engine.col_bonus_claimed[column])):
            points += max(self.column_best[column], written if _num(written) else 0)
        return points

    def _school_future(self, balance: int, cells: List[int], combo_empty: int) -> float:
        """
        What the School cells still empty (`cells`: their numbers) are expected to add to the
        total: the balance at the end counts as points, and a negative one costs 100 a point.
        """
        forced = 1.0 / (1.0 + (combo_empty / len(cells) / FORCED) ** 2) if cells else 0.0
        key = (balance, tuple(sorted(cells)), round(forced, 4))
        found = _FUTURES.get(key)
        if found is None:
            found = _FUTURES[key] = _expected_end(balance, cells, forced) - _end_points(balance)
            if len(_FUTURES) > 20000:
                _FUTURES.clear()
        return found

    # --- each kind of move: (points now, change of the potential) ---
    def combo(self, category: Category, score: int) -> Tuple[float, float]:
        key = (category, score)
        found = self._combo_cache.get(key)
        if found is None:
            column = self.slot[category]
            points = score + self._completes(category, column, score)
            change = (-CELL[category] + self.school_after_combo
                      + self._row_potential(category, score) - self._row_potential(category)
                      + self._column_potential(column, category, score) - self._column_potential(column))
            found = self._combo_cache[key] = (points, change)
        return found

    def _cross(self, category: Category) -> float:
        column = self.slot[category]
        return (-CELL[category] + self.school_after_combo
                - self._row_potential(category) - self._column_potential(column))

    def _school(self, category: Category, k: int) -> Optional[Tuple[float, float]]:
        """Writing School n with k dice of n: None if the rules refuse it (school.py)."""
        column = self.slot[category]
        if column is None:
            return None
        n = SCHOOL_NUMBERS[category]
        if k >= 3:
            change_of_balance, written = (k - 3) * n, ("X" if k == 3 else self.balance + (k - 3) * n)
            kept = True
        else:
            required = (3 - k) * n if k >= 1 else 2 * n
            if k == 0 and not self.endgame:
                return None
            if self.balance < required and not self.endgame:
                return None
            change_of_balance, written, kept = -required, self.balance - required, False
        points = change_of_balance + (self._completes(category, column, written) if kept else 0)
        row_after = self._row_potential(category, written) if kept else 0.0
        balance = self.balance + change_of_balance
        cells = list(self.school_cells)
        cells.remove(n)
        change = (row_after - self._row_potential(category)
                  + self._column_potential(column, category, written) - self._column_potential(column)
                  + self._school_future(balance, cells, self.combo_empty) - self.school_now)
        # A negative balance costs 100 a point at the end (player.py), and the total counts it at once.
        points += _end_points(balance) - _end_points(self.balance) - change_of_balance
        return points, change

    # --- the best move for a hand ---
    def best_value(self, hand: int, double: bool) -> float:
        t = tables()
        raw, count = t.raw[hand], t.count[hand]
        best = self.best_cross if self.best_cross is not None else -1e9
        for i, c in enumerate(COMBO_CATS):
            if self.slot[c] is not None and raw[i]:
                points, change = self.combo(c, raw[i] * 2 if double else raw[i])
                if points + change > best:
                    best = points + change
        for c in SCHOOL_CATS:
            option = self.school_value[c][count[SCHOOL_NUMBERS[c]]]
            if option is not None and option[0] + option[1] > best:
                best = option[0] + option[1]
        return best


_FUTURES: Dict[tuple, float] = {}


def _end_points(balance: int) -> int:
    """What a School balance adds to the total (player.py): itself, and 100 a point below zero."""
    return balance + 100 * balance if balance < 0 else balance


def _forced(n: int) -> List[Tuple[int, float]]:
    """A School cell written because nothing else is left: (balance change, chance), aiming
    every roll at its number (a joker showing 1 counts too, except in School 1)."""
    hit = 1 - (5 / 6) ** 3                      # a die shows n after up to three rolls
    joker = hit if n == 1 else 1 - (4 / 6) ** 3  # ...the joker shows n or 1
    counts = [1.0]
    for p in [hit] * 4 + [joker]:
        counts = [a * (1 - p) + (counts[i - 1] * p if i else 0.0) for i, a in enumerate(counts + [0.0])]
    changes: Dict[int, float] = {}
    for k, chance in enumerate(counts):
        change = (k - 3) * n if k >= 3 else -((3 - k) * n if k >= 1 else 2 * n)
        changes[change] = changes.get(change, 0.0) + chance
    return list(changes.items())


_FORCED = {n: _forced(n) for n in range(1, 7)}


def _expected_end(balance: int, cells: List[int], forced: float) -> float:
    """The expected points of the balance at the end, the empty School cells (`cells`) written
    by choice or, with chance `forced`, by force. Exact while there are few; with more, the
    end is far off and a normal estimate does."""
    spreads = [[(n * extra, (1 - forced) * p) for extra, p in CHOSEN] +
               [(change, forced * p) for change, p in _FORCED[n]] for n in cells]
    if len(cells) <= 4:
        sums = {balance: 1.0}
        for spread in spreads:
            new: Dict[int, float] = {}
            for total, p in sums.items():
                for change, q in spread:
                    new[total + change] = new.get(total + change, 0.0) + p * q
            sums = new
        return sum(_end_points(total) * p for total, p in sums.items())
    mean = balance + sum(c * p for spread in spreads for c, p in spread)
    variance = sum(sum(c * c * p for c, p in spread) - sum(c * p for c, p in spread) ** 2 for spread in spreads)
    sd = math.sqrt(max(variance, 1e-9))
    z = mean / sd
    below = mean * 0.5 * (1 + math.erf(-z / math.sqrt(2))) - sd * math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
    return mean + 100 * below  # E[x] + 100 E[min(x, 0)]


def _num(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


# ------------------------------------------------------------------ decisions ----

def _hand_of(dice) -> int:
    joker = next(d.value for d in dice if d.is_joker)
    return hand_index([d.value for d in dice if not d.is_joker], joker)


def choose_keep(engine, board: Optional[_Board] = None) -> Optional[List[int]]:
    """
    The dice to roll again (their positions), or None to write a cell now. Exact expected
    values over the rolls left (one or two), the board's potential included.
    """
    g = plain_engine(engine)
    if not g.dice or g.rolls_left <= 0:
        return None
    board = board or _Board(g, g.current)
    t = tables()
    hand = _hand_of(g.dice)
    final = [board.best_value(h, False) for h in range(HANDS)]

    def expected(keep: int, values: List[float]) -> float:
        hands, chances = t.outcomes[keep]
        return sum(values[h] * p for h, p in zip(hands, chances))

    if g.rolls_left >= 2:
        # One more roll after this one: what each hand is worth with that roll still to come.
        after = list(final)
        cache: Dict[int, float] = {}
        for h in range(HANDS):
            for keep in t.hand_keeps[h]:
                v = cache.get(keep)
                if v is None:
                    v = cache[keep] = expected(keep, final)
                if v > after[h]:
                    after[h] = v
        values = after
    else:
        values = final
    stand = _best_move_value(g, board)
    best_keep, best = None, stand
    for keep in t.hand_keeps[hand]:
        v = expected(keep, values)
        if v > best + 1e-9:
            best_keep, best = keep, v
    if best_keep is None:
        return None
    return _positions_to_roll(g.dice, t.kept[best_keep])


def _positions_to_roll(dice, kept: Tuple[Tuple[int, ...], int]) -> List[int]:
    normal, joker = kept
    left = list(normal)
    roll = []
    for i, d in enumerate(dice):
        if d.is_joker:
            if not joker:
                roll.append(i)
        elif d.value in left:
            left.remove(d.value)
        else:
            roll.append(i)
    return roll


def _scored(board: _Board, g, move) -> float:
    """A move the rules offer, valued as the computer values it (the points now are exact)."""
    if move.cross:
        return board.cross_value[move.category]
    if move.category in SCHOOL_NUMBERS:
        k = sum(1 for d in g.dice if d.value == SCHOOL_NUMBERS[move.category])
        if SCHOOL_NUMBERS[move.category] != 1 and any(d.is_joker and d.value == 1 for d in g.dice):
            k += 1
        option = board.school_value[move.category][min(k, 5)]
        if option is not None:
            return option[0] + option[1]
        return float(move.points or 0)
    points, change = board.combo(move.category, move.value)
    return float(move.points) + change


def choose_move(engine, board: Optional[_Board] = None):
    """The cell to write now: one of the moves the rules offer (score_options, cross_options)."""
    g = plain_engine(engine)
    board = board or _Board(g, g.current)
    options = score_options(g) + cross_options(g)
    return max(options, key=lambda m: _scored(board, g, m))


def _best_move_value(g, board: _Board) -> float:
    return max(_scored(board, g, m) for m in score_options(g) + cross_options(g))


def next_step(engine) -> Tuple:
    """
    What the computer does next in its turn (the current player must be the computer):
    ("throw",), ("roll",), ("reroll", [positions]), ("score", row, slot) or ("cross", row, slot).
    """
    g = plain_engine(engine)
    if g.choosing_first_player:
        return ("throw",)
    if not g.dice:
        return ("roll",)
    board = _Board(g, g.current)
    if g.rolls_left > 0:
        roll = choose_keep(g, board)
        if roll:
            return ("reroll", roll)
    move = choose_move(g, board)
    return ("cross" if move.cross else "score", move.category, move.slot)


def computer_names(names: List[str], computers: Sequence[int]) -> List[str]:
    """The seats' names, the computer's blank ones named: "Computer", or "Computer 1", "Computer 2"
    with several, in the language of the request or page that makes the game."""
    seats = sorted(set(i for i in computers if 0 <= i < len(names)))
    named = list(names)
    for number, seat in enumerate(seats, 1):
        if not (named[seat] or "").strip():
            named[seat] = t("Computer") if len(seats) == 1 else t("Computer {n}", n=number)
    return named


def fallback_step(engine) -> Tuple:
    """A plain legal step, if next_step ever failed: the game must go on (rooms.py)."""
    g = plain_engine(engine)
    if g.choosing_first_player:
        return ("throw",)
    if not g.dice:
        return ("roll",)
    move = (score_options(g) + cross_options(g))[0]
    return ("cross" if move.cross else "score", move.category, move.slot)


def random_step(engine, rng: Optional[random.Random] = None) -> Tuple:
    """A player who picks at random among what the rules allow (for comparisons)."""
    rng = rng or random
    g = plain_engine(engine)
    if g.choosing_first_player:
        return ("throw",)
    if not g.dice:
        return ("roll",)
    if g.rolls_left > 0 and rng.random() < 0.5:
        return ("reroll", [i for i in range(5) if rng.random() < 0.5] or [rng.randrange(5)])
    move = rng.choice(score_options(g) + cross_options(g))
    return ("cross" if move.cross else "score", move.category, move.slot)


def greedy_step(engine, rng: Optional[random.Random] = None) -> Tuple:
    """A player who writes the most points now, on the first roll (for comparisons)."""
    g = plain_engine(engine)
    if g.choosing_first_player:
        return ("throw",)
    if not g.dice:
        return ("roll",)
    scores = score_options(g)
    if scores:
        move = max(scores, key=lambda m: m.points)
    else:
        move = (rng or random).choice(cross_options(g))
    return ("cross" if move.cross else "score", move.category, move.slot)


def apply_step(engine, step: Tuple) -> None:
    """Make a step on a GameEngine (the store makes them through its own methods)."""
    kind = step[0]
    if kind == "throw":
        engine.throw_for_start()
    elif kind == "roll":
        engine.start_turn()
    elif kind == "reroll":
        engine.reroll(list(step[1]))
    elif kind == "score":
        engine.record_score(step[1], step[2])
    elif kind == "cross":
        engine.record_cross(step[1], step[2])
    else:
        raise ValueError("Unknown step: %r" % (step,))
