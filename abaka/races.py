"""
The races for the shared bonuses (Backlog item 30), as one player reads them during a game:
how many cells each player still has to fill in column I and column II, and the rows where
two or more players are one cell from the row's bonus.

The first player to complete a row, or column I or II, decides its bonus for everyone
(abaka/bonus.py): the bonus if their cells allow it, a cross for the others. Column III is
each player's own, so it is no race. The score table shows all of this, but on a phone it
sits below the dice, and counting empty cells there means scrolling and counting.

The words are plain text in the viewer's language, for every client: the web page
(ui_components/races.py) escapes them, the app (abaka/api.py, `races`) shows them as they
are. No Streamlit here, and Python 3.8 like the rest of the package.
"""

from itertools import groupby
from typing import Optional

from .i18n import and_join, t
from .models import Category
from .moves import ROW_ORDER, row_name

SHARED_COLUMNS = (0, 1)  # column III is each player's own (bonus.py)
COLUMN_NAMES = ("I", "II", "III")
ROWS = len(Category)  # cells in a column


def bonus_races(engine, me: Optional[int]) -> Optional[dict]:
    """
    What the player in seat `me` (None: everyone shares this screen) is told about the races
    now, or None when there is nothing to tell: during the starting throw, after the game,
    or with no race on.

    - `columns`: column I and II while their bonus is undecided, someone can still earn it,
      and someone has written in it. Per seat: `left`, the cells still empty in it, and
      `open`, whether that player can still earn it (False once they crossed out a
      combination in it; completing the column first still closes it for the others).
    - `rows`: rows whose bonus is undecided, where two or more players have one cell left and
      at least one of them can still earn it. Grouped by those players, with a line to show.
    - `title` and `heads` (one per seat) label the columns' table, and `note` explains a
      crossed-out bonus when one is shown.
    """
    if getattr(engine, "choosing_first_player", False) or engine.is_game_over():
        return None
    players = engine.players
    columns = []
    for col in SHARED_COLUMNS:
        if engine.col_bonus_claimed[col]:
            continue
        left = [sum(1 for cat in Category if p.table[cat][col] is None) for p in players]
        can_earn = [p.column_bonus[col] is None for p in players]
        if not any(can_earn) or all(n == ROWS for n in left):
            continue
        columns.append({"column": col, "label": t("Column {n}", n=COLUMN_NAMES[col]),
                        "left": left, "open": can_earn})

    close = []  # (seats one cell from the bonus, row)
    for cat in ROW_ORDER:
        if engine.row_bonus_claimed.get(cat):
            continue
        last_cell = [i for i, p in enumerate(players) if sum(v is None for v in p.table[cat][:3]) == 1]
        if len(last_cell) >= 2 and any(players[i].table[cat][3] is None for i in last_cell):
            close.append((tuple(last_cell), cat))
    rows = []
    for seats, group in groupby(sorted(close, key=lambda c: c[0]), key=lambda c: c[0]):
        cats = [cat for _, cat in group]
        rows.append({"rows": [cat.name for cat in cats], "seats": list(seats),
                     "text": t("One cell to the bonus for {names}: {rows}.",
                               names=_names(players, seats, me), rows=", ".join(row_name(c) for c in cats))})

    if not columns and not rows:
        return None
    return {
        "title": t("Cells to the bonus"),
        "heads": [t("You") if i == me else p.name for i, p in enumerate(players)],
        "columns": columns,
        "rows": rows,
        "note": (t("✕ — the bonus is crossed out, but whoever completes the column first still closes it "
                   "for the others.") if any(not ok for c in columns for ok in c["open"]) else None),
    }


def _names(players, seats, me: Optional[int]) -> str:
    """'you and Bob', 'Ann, Bob and Cid': the viewer first."""
    ordered = sorted(seats, key=lambda i: (i != me, i))
    return and_join(t("you") if i == me else players[i].name for i in ordered)


__all__ = ["COLUMN_NAMES", "SHARED_COLUMNS", "bonus_races"]
