"""
What the current player can write this turn, and what each choice would score.

No Streamlit here, so it can be unit-tested. Previews are exact: each option is
tried on a copy of the game with the real engine rules, and only moves the
engine accepts are offered.
"""

import copy
from typing import List, Optional

from abaka.constants import COMBO_CATS, SCHOOL_CATS
from abaka.engine import GameEngine
from abaka.models import Category
from ui_components.i18n import t

ROW_ORDER = SCHOOL_CATS + COMBO_CATS

_COMBO_NAMES = {
    Category.PAIR: "Pair",
    Category.TWO_PAIRS: "Two pairs",
    Category.TRIPS: "Three of a kind",
    Category.SMALL_STRAIGHT: "Small straight",
    Category.LARGE_STRAIGHT: "Large straight",
    Category.FULL: "Full house",
    Category.KARE: "Four of a kind",
    Category.ABAKA: "Abaka",
    Category.SUM: "Sum",
}

ROW_HINTS = {
    Category.PAIR: "Two dice of the same number. Scores the pair.",
    Category.TWO_PAIRS: "Two different pairs. Scores both pairs.",
    Category.TRIPS: "Three of the same number. Scores the three.",
    Category.SMALL_STRAIGHT: "Exactly 1-2-3-4-5. Scores 15.",
    Category.LARGE_STRAIGHT: "Exactly 2-3-4-5-6. Scores 20.",
    Category.FULL: "Three of one number and two of another. Scores all dice; 1-1-1-2-2 adds 50.",
    Category.KARE: "Four of the same number. Scores the four, plus 20.",
    Category.ABAKA: "All five dice the same. Scores all dice, plus 50.",
    Category.SUM: "Any dice. Scores the total.",
}


def is_school(category: Category) -> bool:
    return category.name.startswith("SCHOOL_")


def school_number(category: Category) -> int:
    return int(category.name.split("_")[1])


def row_name(category: Category) -> str:
    if is_school(category):
        return t("School {n}", n=school_number(category))
    return t(_COMBO_NAMES[category])


def row_hint(category: Category) -> str:
    if is_school(category):
        return t("Three {n}s are par. Extra {n}s add to your school balance; fewer {n}s are paid from it, "
                 "which crosses out this row's bonus.", n=school_number(category))
    return t(ROW_HINTS[category])


def _signed(n: int) -> str:
    return f"+{n}" if n > 0 else (f"−{abs(n)}" if n < 0 else "±0")


class Move:
    """One cell the current player could fill now."""

    def __init__(self, category: Category, slot: int, cross: bool,
                 value: object = None, balance_change: Optional[int] = None,
                 bonus_lost: bool = False) -> None:
        self.category = category
        self.slot = slot                      # 0..2, the leftmost free cell of the row
        self.cross = cross
        self.value = value                    # what the cell would show (int or 'X')
        self.balance_change = balance_change  # school rows only
        self.bonus_lost = bonus_lost          # the move crosses out this row's (still open) bonus

    @property
    def name(self) -> str:
        return row_name(self.category)

    @property
    def label(self) -> str:
        """Short text for the option list."""
        if self.cross:
            return self.name
        if is_school(self.category):
            if self.value == "X":
                return t("{name} · exactly 3", name=self.name)
            return f"{self.name} · {_signed(self.balance_change)}"
        return f"{self.name} · {self.value}"

    @property
    def action_text(self) -> str:
        """Text for the confirm button: says exactly what will happen."""
        if self.cross:
            return t("Cross out {name}", name=self.name)
        if is_school(self.category):
            if self.value == "X":
                return t("Write {name} (exactly three)", name=self.name)
            if self.balance_change > 0:
                return t("Write {name} (+{n} balance)", name=self.name, n=self.balance_change)
            if self.bonus_lost:
                return t("Write {name} (pay {n} from balance, lose the row bonus)",
                         name=self.name, n=abs(self.balance_change))
            return t("Write {name} (pay {n} from balance)", name=self.name, n=abs(self.balance_change))
        return t("Score {value} in {name}", value=self.value, name=self.name)

    @property
    def preview(self) -> str:
        """What the target cell on the scoreboard will show."""
        if self.cross:
            return "✕"
        if self.value == "X":
            return "✓"
        return _signed(self.value) if isinstance(self.value, int) and self.value < 0 else str(self.value)

    def __repr__(self) -> str:
        return f"Move({self.label!r})"


def plain_engine(engine) -> GameEngine:
    """The GameEngine behind `engine` (online games wrap one in a RoomEngine)."""
    return getattr(engine, "_engine", engine)


def free_slot(engine, category: Category) -> Optional[int]:
    slots = engine.players[engine.current].table[category][:3]
    for i, v in enumerate(slots):
        if v is None:
            return i
    return None


def score_options(engine) -> List[Move]:
    """Every row the current player may score with the dice on the table, in board order."""
    base = plain_engine(engine)
    if not base.dice:
        return []
    me = base.current
    options = []
    for category in ROW_ORDER:
        slot = free_slot(base, category)
        if slot is None:
            continue
        trial = copy.deepcopy(base)
        balance_before = trial.players[me].school_balance
        bonus_open = trial.players[me].table[category][3] is None
        try:
            trial.record_score(category, slot)
        except (ValueError, RuntimeError):
            continue  # the engine would refuse it
        after = trial.players[me]
        change = after.school_balance - balance_before if is_school(category) else None
        # Paying from the balance crosses out the row bonus at once (owner's rule, 2026-11-16).
        bonus_lost = is_school(category) and bonus_open and after.table[category][3] == "X"
        options.append(Move(category, slot, False, after.table[category][slot], change, bonus_lost))
    return options


def cross_options(engine) -> List[Move]:
    """Combination rows that can be crossed out (school rows cannot)."""
    base = plain_engine(engine)
    options = []
    for category in COMBO_CATS:
        slot = free_slot(base, category)
        if slot is not None:
            options.append(Move(category, slot, True, "X"))
    return options
