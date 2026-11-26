"""
Games as plain JSON data, so they can be saved to disk and loaded by any later
version of the code (unlike pickle, nothing refers to classes or modules).

engine_to_data(engine) -> dict and engine_from_data(dict) -> GameEngine
round-trip every part of the game state.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .engine import GameEngine
from .models import Category, Die
from .player import PlayerState

FORMAT = 1


def _cat(name: str) -> Category:
    return Category[name]


def player_to_data(p: PlayerState) -> Dict[str, Any]:
    return {
        "name": p.name,
        "table": {cat.name: list(cells) for cat, cells in p.table.items()},
        "column_bonus": list(p.column_bonus),
        "school_balance": p.school_balance,
        "school_balance_loc": [p.school_balance_loc[0].name, p.school_balance_loc[1]]
        if p.school_balance_loc is not None else None,
    }


def player_from_data(d: Dict[str, Any]) -> PlayerState:
    p = PlayerState(d["name"])
    for name, cells in d["table"].items():
        p.table[_cat(name)] = list(cells)
    p.column_bonus = list(d["column_bonus"])
    p.school_balance = d["school_balance"]
    loc = d.get("school_balance_loc")
    p.school_balance_loc = (_cat(loc[0]), loc[1]) if loc else None
    return p


def engine_to_data(g: GameEngine) -> Dict[str, Any]:
    return {
        "format": FORMAT,
        "players": [player_to_data(p) for p in g.players],
        "current": g.current,
        "dice": [[d.value, d.is_joker] for d in g.dice],
        "rolls_left": g.rolls_left,
        "first_roll": g.first_roll,
        "row_bonus_claimed": [cat.name for cat, claimed in g.row_bonus_claimed.items() if claimed],
        "col_bonus_claimed": list(g.col_bonus_claimed),
        "row_bonus_blocked": [[player, cat.name] for (player, cat), blocked in g.row_bonus_blocked.items()
                              if blocked],
        "last_move": [g.last_move[0], g.last_move[1].name, g.last_move[2]] if g.last_move else None,
        "throw_round": list(getattr(g, "throw_round", [])),
        "throw_round_no": getattr(g, "throw_round_no", 1),
        "starting_throws": [
            {"round": t["round"], "player": t["player"], "dice": [list(face) for face in t["dice"]],
             "total": t["total"]}
            for t in getattr(g, "starting_throws", [])
        ],
        "first_player": getattr(g, "first_player", None),
        "score_history": [[moves, list(totals)] for moves, totals in getattr(g, "score_history", ())],
    }


def engine_from_data(d: Dict[str, Any]) -> GameEngine:
    if d.get("format") != FORMAT:
        raise ValueError("Unknown save format: %r" % d.get("format"))
    g = GameEngine([p["name"] for p in d["players"]])
    g.players = [player_from_data(p) for p in d["players"]]
    g.current = d["current"]
    g.dice = [Die(v, is_joker=bool(j)) for v, j in d["dice"]]
    g.rolls_left = d["rolls_left"]
    g.first_roll = d["first_roll"]
    for name in d["row_bonus_claimed"]:
        g.row_bonus_claimed[_cat(name)] = True
    g.col_bonus_claimed = list(d["col_bonus_claimed"])
    g.row_bonus_blocked = {(player, _cat(name)): True for player, name in d["row_bonus_blocked"]}
    lm = d.get("last_move")
    g.last_move = (lm[0], _cat(lm[1]), lm[2]) if lm else None
    g.throw_round = list(d.get("throw_round", []))
    g.throw_round_no = d.get("throw_round_no", 1)
    g.starting_throws = [
        {"round": t["round"], "player": t["player"], "dice": [tuple(face) for face in t["dice"]],
         "total": t["total"]}
        for t in d.get("starting_throws", [])
    ]
    g.first_player = d.get("first_player")
    g.score_history = tuple((moves, tuple(totals)) for moves, totals in d.get("score_history", ()))
    return g


def engines_equal(a: Optional[GameEngine], b: Optional[GameEngine]) -> bool:
    """Same game state (used by tests)."""
    if a is None or b is None:
        return a is b
    return engine_to_data(a) == engine_to_data(b)


__all__: List[str] = ["engine_to_data", "engine_from_data", "engines_equal", "FORMAT"]
