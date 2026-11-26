"""
How the players stand, for one player reading the board (a tester, 2026-11-26, Backlog item 32):

- the difference row by row: "how much you are losing in each row", the viewer's points in a
  row (its three cells and its bonus) minus the opponent's, or minus the best of the others at
  a table of three or more;
- the scores by move, "like the chart of a chess game": every player's total after each move.

The board already holds all of it; this only adds it up, in one place, for every client: the
web page (ui_components/scoreboard.py, chart.py) draws it, and the API sends it to apps
(`differences`, `game.history`). No Streamlit here, and Python 3.8 like the rest of the package.
"""

from typing import List, Optional

from .i18n import t
from .models import Category


def _points(value) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def row_differences(engine, me: Optional[int]) -> Optional[dict]:
    """
    The differences as the player in seat `me` reads them (None: everyone shares this screen,
    so the player whose turn it is). None during the starting throw, and on a shared screen
    once the game is over (nobody's turn).

    - `seat`: whose points are compared; `rows`: per row name, that player's points in the row
      minus the opponent's (the best of the others' with three or more players), or None while
      nobody has written in the row; `columns`: the same for the column bonuses; `total`: for
      the totals.
    - `title` and `hint`: a heading for the column of differences, and what it means.
    """
    players = engine.players
    if len(players) < 2 or getattr(engine, "choosing_first_player", False):
        return None
    seat = me if me is not None else (None if engine.is_game_over() else engine.current)
    if seat is None:
        return None
    others = [i for i in range(len(players)) if i != seat]

    def against(values: List[int]) -> int:
        return values[seat] - max(values[i] for i in others)

    rows = {}
    for cat in Category:
        if all(all(v is None for v in p.table[cat][:3]) for p in players):
            rows[cat.name] = None
        else:
            rows[cat.name] = against([sum(_points(v) for v in p.table[cat]) for p in players])
    if len(players) == 2:
        hint = t("Your points in each row minus {name}'s", name=players[others[0]].name) if me is not None \
            else t("{name}'s points in each row minus {other}'s", name=players[seat].name,
                   other=players[others[0]].name)
    else:
        hint = t("Your points in each row minus the best of the others'") if me is not None \
            else t("{name}'s points in each row minus the best of the others'", name=players[seat].name)
    return {
        "seat": seat,
        "rows": rows,
        "columns": against([sum(_points(v) for v in p.column_bonus) for p in players]),
        "total": against([p.calculate_score() for p in players]),
        "title": "±",
        "hint": hint,
    }


def score_history(engine) -> List[dict]:
    """
    Every player's total after each move: [{"move": moves made, "totals": [per seat]}], from the
    start of the game (a first point at move 0, everyone at 0). A game saved before the history
    was kept starts where it was then (its first point has a later move), without a point at 0.
    """
    history = [{"move": moves, "totals": list(totals)} for moves, totals in getattr(engine, "score_history", ())]
    if history and history[0]["move"] == 1:
        history.insert(0, {"move": 0, "totals": [0] * len(engine.players)})
    return history


__all__ = ["row_differences", "score_history"]
