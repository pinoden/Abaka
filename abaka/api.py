"""
The game as JSON, for apps on Android and iOS and any other client (Backlog item 25).

The web app (abaka_ui.py) draws its pages straight from the RoomStore, inside the server's
own process. An app on a phone talks to the server over the network instead, and this
module is what it talks to, whatever carries the messages (HTTP, a WebSocket):

    response = handle(request, store, clubs)

A request and its response are plain JSON data: objects, lists, text, numbers, true, false
and null. A request names its operation ("op") and carries what that needs, for example
{"op": "roll", "code": "Q47CH", "token": "...", "version": 7}. A refused request raises
ApiError: its `code` says what the app should do (for example "outdated": draw the new
state, no message needed), and its message, in the request's language, can be shown to
the player. docs/API.md describes every operation and every field.

The server stays the referee. A game's state lists the moves the player may make now,
with their exact previews (abaka/moves.py), and an app offers just those; it never applies
the rules itself. Every move goes through RoomStore, with the same turn check, lock and
version as a move from the web, so players on the web and in an app can share a game.

No Streamlit here, and Python 3.8 like the rest of the package.
"""

from __future__ import annotations

import time
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional

from .clubs import MAX_CLUB_NAME_LENGTH, ClubStore, is_club_code, member_key
from .effects import REACTION_LOOKS, effect_words, reaction_words
from .i18n import LANGUAGES, error, get_language, set_language, t
from .models import Category
from .moves import ROW_ORDER, cross_options, free_slot, is_school, most_points, row_hint, row_name, score_options
from .races import bonus_races
from .rooms import (MAX_MESSAGE_LENGTH, MAX_NAME_LENGTH, MAX_PLAYERS, MIN_PLAYERS, REACTIONS, OutdatedPage,
                    RoomError, RoomStore, RoomView, TooFast, normalize_code, split_code)
from .rules import rules_blocks

# The version of the messages below. Adding an operation or a field keeps it; anything an
# app already relies on (a field's meaning, an operation's arguments) changing makes it 2,
# with the server answering both while older apps are still in use.
PROTOCOL = 1
DICE = 5
CLUB_GAMES_SHOWN = 10  # the latest games a club's data lists, unless asked for more (at most 200)

# What a refused request's code tells the app to do (docs/API.md, Errors).
ERRORS = {
    "bad_request": "the request is malformed (a bug in the app): no message for the player",
    "protocol": "the app and the server speak different versions: ask the player to update the app",
    "not_found": "no game or club with this code (any more): go back to the start",
    "not_seated": "the token holds no seat in this game (taken over on another device): offer to rejoin",
    "outdated": "the move was made on an old state: draw the new state; nothing to show",
    "too_fast": "too many reactions or messages: show the message",
    "retry": "the server is busy or was just updated: try again in a moment",
    "refused": "the rules or the room refused it (not your turn, game full...): show the message",
}

# Room refusals that call for something other than showing the message.
_ROOM_ERRORS = {
    "Game not found. Check the code, or ask for a new invite.": "not_found",
    "You are not seated in this game.": "not_seated",
    "The app was just updated. Please try again.": "retry",
    "The server is busy right now. Please try again later.": "retry",
}


class ApiError(Exception):
    """
    A request the server refused. `code` is one of ERRORS; the message, in the request's
    language, can be shown to the player (except for bad_request, meant for developers).
    """

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message

    def to_data(self) -> dict:
        return {"error": self.code, "message": self.message}


def handle(request: Any, store: RoomStore, clubs: Optional[ClubStore] = None,
           may_create: Optional[Callable[[], bool]] = None) -> dict:
    """
    Answer one request (JSON data) with JSON data, or raise ApiError. `clubs` is the
    server's ClubStore (without it, the club operations find no club). `may_create`, if
    given, is asked before a new game or club is made: False refuses it as too_fast (the
    server limits how many one client may start, as the web does per browser).
    """
    if not isinstance(request, dict):
        raise ApiError("bad_request", "A request is a JSON object.")
    with _language(request.get("lang")):
        protocol = request.get("protocol", PROTOCOL)
        if protocol != PROTOCOL or isinstance(protocol, bool):
            raise ApiError("protocol", t("This app and the server do not match. Update the app, "
                                         "or try again later."))
        op = request.get("op")
        run = _OPS.get(op) if isinstance(op, str) else None
        if run is None:
            raise ApiError("bad_request", "Unknown operation: %r." % (op,))
        if op in CREATING and may_create is not None and not may_create():
            raise ApiError("too_fast", t("You started a lot of games just now. Please wait a few minutes."))
        try:
            return run(_Request(request), store, clubs)
        except ApiError:
            raise
        except TooFast as e:
            raise ApiError("too_fast", error(str(e))) from None
        except OutdatedPage as e:
            raise ApiError("outdated", error(str(e))) from None
        except RoomError as e:
            raise ApiError(_ROOM_ERRORS.get(str(e), "refused"), error(str(e))) from None
        except (ValueError, RuntimeError, IndexError) as e:  # the engine's rules, and ClubError
            raise ApiError("refused", error(str(e))) from None


def failure(request: Any) -> ApiError:
    """What to answer when the server itself failed on a request (a bug): retry, in its language."""
    with _language(request.get("lang") if isinstance(request, dict) else None):
        return ApiError("retry", t("Something went wrong on the server. Please try again."))


@contextmanager
def _language(lang: Any):
    """Texts in the request's language ("en" unless it asks for another), for this thread only."""
    before = get_language()
    set_language(lang if isinstance(lang, str) and lang in LANGUAGES else "en")
    try:
        yield
    finally:
        set_language(before)


class _Request:
    """A request's fields, checked: a missing or malformed field is a bad_request."""

    def __init__(self, data: dict) -> None:
        self._data = data

    def get(self, name: str, default: Any = None) -> Any:
        return self._data.get(name, default)

    def text(self, name: str, default: Optional[str] = None) -> str:
        value = self._data.get(name, default)
        if not isinstance(value, str):
            raise ApiError("bad_request", f"'{name}' must be text.")
        return value

    def number(self, name: str, default: Optional[int] = None, low: Optional[int] = None,
               high: Optional[int] = None) -> int:
        value = self._data.get(name, default)
        if (isinstance(value, bool) or not isinstance(value, int) or (low is not None and value < low)
                or (high is not None and value > high)):
            limits = "" if low is None else f" from {low}" + ("" if high is None else f" to {high}")
            raise ApiError("bad_request", f"'{name}' must be a whole number{limits}.")
        return value

    def code(self) -> str:
        """The game's code. `code` may also be the full code ("K7M2Q-8XJ4PN2R"): see key()."""
        code, _ = split_code(self.text("code"))
        return normalize_code(code)

    def key(self) -> Optional[str]:
        """The game's key: `key`, or the key part of a full code in `code`. None if neither has one."""
        if self.get("key") is not None:
            return self.text("key")
        _, key = split_code(self.text("code"))
        return key or None

    def token(self) -> str:
        return self.text("token")

    def dice(self) -> List[int]:
        value = self._data.get("dice")
        if (not isinstance(value, list) or len(value) > DICE
                or any(isinstance(i, bool) or not isinstance(i, int) or not 0 <= i < DICE for i in value)):
            raise ApiError("bad_request", f"'dice' must be a list of die positions, 0 to {DICE - 1}.")
        return value

    def row(self) -> Category:
        name = self.text("row")
        try:
            return Category[name]
        except KeyError:
            raise ApiError("bad_request", f"Unknown row: {name!r}.") from None


# ----------------------------------------------------------------- operations ----

def _info(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """What an app needs once: the protocol, the limits, the board's rows and their texts."""
    return {
        "protocol": PROTOCOL,
        "languages": list(LANGUAGES),
        "players": {"min": MIN_PLAYERS, "max": MAX_PLAYERS},
        "limits": {"name": MAX_NAME_LENGTH, "message": MAX_MESSAGE_LENGTH, "club_name": MAX_CLUB_NAME_LENGTH},
        "reactions": list(REACTIONS),
        # The reaction buttons, in their order: an app shows these and need not know the reactions.
        "reaction_list": [{"id": key, "emoji": REACTION_LOOKS[key][0], "label": t(REACTION_LOOKS[key][1])}
                          for key in REACTIONS if key in REACTION_LOOKS],
        "rows": [{"row": c.name, "name": row_name(c), "hint": row_hint(c), "school": is_school(c)}
                 for c in ROW_ORDER],
    }


def _rules(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """The rules, in the request's language, as blocks an app draws itself (abaka/rules.py)."""
    return {"rules": {"title": t("How to play"), "blocks": rules_blocks()}}


def _create(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """An online game; the creator takes seat 0 and shares the code."""
    name = req.text("name", "").strip() or t("Player {i}", i=1)
    players = req.number("players", MIN_PLAYERS, low=MIN_PLAYERS, high=MAX_PLAYERS)
    code, token = store.create(name, players, club=_club_code(req, clubs))
    return _entered(store, clubs, code, token)


def _create_local(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """A game played on one device: one token plays every seat."""
    names = req.get("names")
    if not isinstance(names, list) or not all(isinstance(n, str) for n in names):
        raise ApiError("bad_request", "'names' must be a list of names.")
    names = [n.strip() or t("Player {i}", i=i) for i, n in enumerate(names, 1)]
    club = _club_code(req, clubs)
    if club is not None and len({member_key(n) for n in names}) < len(names):
        raise ApiError("refused", t("Each player needs a different name."))  # they would count as one member
    code, token = store.create_local(names, club=club)
    return _entered(store, clubs, code, token)


def _join(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    code = req.code()
    _admit(req, store, code, seat_will_do=False)
    seated = len(store.view(code).names)
    token = store.join(code, req.text("name", "").strip() or t("Player {i}", i=seated + 1), req.key())
    return _entered(store, clubs, code, token)


def _rejoin(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """Take a seat back (a new device, a lost token), with the game's key: the old token stops working."""
    code = req.code()
    return _entered(store, clubs, code, store.reclaim(code, req.number("seat", low=0), req.key()))


def _resume(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """Carry on with a same-device game from its full code (or its code and key)."""
    code = req.code()
    return _entered(store, clubs, code, store.resume_local(code, req.key()))


def _admit(req: _Request, store: RoomStore, code: str, seat_will_do: bool = True) -> None:
    """
    Only for someone in the game: a token that holds one of its seats (if `seat_will_do`), or
    its key. Anyone else is told there is no such game, as when there is none, so a game's
    code alone tells nothing (Backlog item 31).
    """
    token = req.get("token")
    if seat_will_do and isinstance(token, str) and store.seat_of(code, token) is not None:
        return
    if not store.opens(code, req.key()):
        raise ApiError("not_found", error("Game not found. Check the code, or ask for a new invite."))


def _entered(store: RoomStore, clubs: Optional[ClubStore], code: str, token: str) -> dict:
    return {"code": code, "token": token, "state": _state(store, clubs, code, token)}


def _get_state(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """The game for a seat's token, or, with the game's key, as its invite shows it."""
    token = req.text("token") if req.get("token") is not None else None
    code = req.code()
    _admit(req, store, code)
    return {"state": _state(store, clubs, code, token, req.number("since", 0, low=0))}


def _seen(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """A short text that changes whenever the state does: cheap to ask for every second."""
    code = req.code()
    _admit(req, store, code)
    seen = store.seen(code)
    if seen[0] < 0:
        raise ApiError("not_found", error("Game not found. Check the code, or ask for a new invite."))
    return {"seen": _seen_text(seen)}


def _after(act: Callable[..., None], move: bool = True):
    """
    An operation on a game the player is seated in. A move names the room version of the
    state it was chosen on (`version`): if the room has changed since (a double tap, or
    someone else's move), it is refused as outdated and nothing changes. The response is
    the new state.
    """
    def run(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
        code, token = req.code(), req.token()
        if move:
            act(req, store, code, token, req.number("version", low=0))
        else:
            act(req, store, code, token)
        return {"state": _state(store, clubs, code, token, req.number("since", 0, low=0))}
    return run


def _slot(req: _Request, store: RoomStore, code: str, row: Category) -> int:
    """The cell to write: as asked, or the row's next free one (the only one the rules allow)."""
    if req.get("slot") is not None:
        return req.number("slot", low=0, high=2)
    engine = store.view(code).engine
    slot = free_slot(engine, row) if engine is not None and not engine.is_game_over() else 0
    if slot is None:
        raise ApiError("refused", error("Row already complete"))
    return slot


def _score(req: _Request, store: RoomStore, code: str, token: str, version: int) -> None:
    row = req.row()
    store.score(code, token, row, _slot(req, store, code, row), expected_version=version)


def _cross(req: _Request, store: RoomStore, code: str, token: str, version: int) -> None:
    row = req.row()
    store.cross(code, token, row, _slot(req, store, code, row), expected_version=version)


def _rematch(req: _Request, store: RoomStore, code: str, token: str) -> None:
    try:
        store.rematch(code, token)
    except RoomError as e:
        if str(e) != "The current game is not finished yet.":
            raise
        # Someone at the table started the next game first: the state shows it.


def _leave(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    """Give up a seat in the waiting room (later players move up). After the start, seats are kept."""
    store.leave(req.code(), req.token())
    return {"left": True}


def _club(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    return {"club": _club_data(clubs, normalize_code(req.text("club")),
                               req.number("games", CLUB_GAMES_SHOWN, low=0, high=200))}


def _create_club(req: _Request, store: RoomStore, clubs: Optional[ClubStore]) -> dict:
    if clubs is None:
        raise ApiError("retry", error("The server is busy right now. Please try again later."))
    code = clubs.create(req.text("name", ""))
    return {"club": _club_data(clubs, code, CLUB_GAMES_SHOWN)}


_OPS: Dict[str, Callable[[_Request, RoomStore, Optional[ClubStore]], dict]] = {
    "info": _info,
    "rules": _rules,
    "create": _create,
    "create_local": _create_local,
    "join": _join,
    "rejoin": _rejoin,
    "resume": _resume,
    "state": _get_state,
    "seen": _seen,
    "throw": _after(lambda req, store, code, token, v: store.throw_for_start(code, token, expected_version=v)),
    "roll": _after(lambda req, store, code, token, v: store.roll(code, token, expected_version=v)),
    "reroll": _after(lambda req, store, code, token, v: store.reroll(code, token, req.dice(), expected_version=v)),
    "score": _after(_score),
    "cross": _after(_cross),
    "pick": _after(lambda req, store, code, token: store.pick(code, token, req.dice()), move=False),
    "react": _after(lambda req, store, code, token: store.react(
        code, token, req.text("reaction"), req.number("to", low=0) if req.get("to") is not None else None),
        move=False),
    "say": _after(lambda req, store, code, token: store.say(code, token, req.text("text")), move=False),
    "rematch": _after(_rematch, move=False),
    "start_now": _after(lambda req, store, code, token: store.start_now(code, token), move=False),
    "leave": _leave,
    "club": _club,
    "create_club": _create_club,
}
OPERATIONS = tuple(_OPS)
CREATING = ("create", "create_local", "create_club")  # what may_create limits


# --------------------------------------------------------------------- state ----

def _state(store: RoomStore, clubs: Optional[ClubStore], code: str, token: Optional[str] = None,
           since: int = 0) -> dict:
    """
    The room as the holder of `token` sees it. Without a seat (no token, or one that was
    taken over), only what the invite page shows: the code, the names and what can be done
    to take a seat. `since`: leave out events and chat messages up to this id.
    """
    view = store.view(code)
    seat = store.seat_of(view.code, token) if token else None
    engine = view.engine
    phase = ("waiting" if engine is None else "over" if engine.is_game_over()
             else "starting_throw" if engine.choosing_first_player else "playing")
    state = {
        "protocol": PROTOCOL,
        "code": view.code,
        # Only ever sent to someone in the game (_admit): what opens it, for the link and the full code.
        "key": view.key,
        "version": view.version,
        "seen": _seen_text(view.seen),
        "now": round(time.time(), 3),
        "local": view.local,
        "capacity": view.capacity,
        "club": view.club,
        "names": list(view.names),
        "seated": seat is not None,
        "you": seat if seat is not None and not view.local else None,
        "phase": phase,
        "can": [],
        "game": None,
        "moves": None,
        "races": None,
        "events": [],
        "chat": [],
        "table": _table(view),
        "club_result": None,
    }
    if seat is None:
        state["can"] = ["resume"] if view.local else (
            (["join"] if engine is None and len(view.names) < view.capacity else []) + ["rejoin"])
        return state

    my_turn = phase in ("starting_throw", "playing") and (view.local or engine.current == seat)
    score, cross = ((score_options(engine), cross_options(engine)) if my_turn and engine.dice else ([], []))
    can = state["can"]
    if engine is None:
        can.append("leave")
        if seat == 0 and len(view.names) >= MIN_PLAYERS:
            can.append("start_now")
    elif phase == "over":
        can.append("rematch")
    elif my_turn:
        if engine.choosing_first_player:
            can.append("throw")
        elif not engine.dice:
            can.append("roll")
        else:
            if engine.rolls_left > 0:
                can += ["reroll"] if view.local else ["reroll", "pick"]
            can += (["score"] if score else []) + (["cross"] if cross else [])
    if engine is not None and not view.local:
        can += ["react"] if phase == "over" else ["react", "say"]

    if engine is not None:
        state["game"] = _game(view)
    if score or cross:
        best = set(most_points(score))
        state["moves"] = {"score": [_move(m, i in best) for i, m in enumerate(score)],
                          "cross": [_move(m, False) for m in cross]}
    if phase == "playing":
        state["races"] = bonus_races(engine, state["you"])
    state["events"] = [_event(e, view.names, state["you"]) for e in view.events if e["id"] > since]
    state["chat"] = [dict(m) for m in view.chat if m["id"] > since]
    if phase == "over" and view.club and clubs is not None:
        state["club_result"] = _club_result(clubs.game(view.club, view.code, view.games_played))
    return state


def _game(view: RoomView) -> dict:
    engine = view.engine
    totals = [p.calculate_score() for p in engine.players]
    last = engine.last_move
    return {
        "number": view.games_played + 1,  # games at this table, this one included
        "current": engine.current,
        "dice": [{"value": d.value, "joker": d.is_joker} for d in engine.dice],
        "rolls_left": engine.rolls_left,
        "first_roll": engine.first_roll,
        "picked": list(view.picked),
        "rerolled": list(view.rerolled),
        "last_move": {"seat": last[0], "row": last[1].name, "slot": last[2]} if last else None,
        "starting_throw": {
            "round": engine.throw_round_no,
            "throwing": list(engine.throw_round),
            "throws": [{"round": x["round"], "seat": x["player"], "total": x["total"],
                        "dice": [{"value": v, "joker": bool(j)} for v, j in x["dice"]]}
                       for x in engine.starting_throws],
            "first_player": engine.first_player,
        },
        "players": [_player(p, total) for p, total in zip(engine.players, totals)],
        "winners": ([i for i, total in enumerate(totals) if total == max(totals)]
                    if engine.is_game_over() else []),
    }


def _player(p, total: int) -> dict:
    where = p.school_balance_loc
    return {
        "name": p.name,
        "total": total,
        "school_balance": p.school_balance,
        "balance_cell": {"row": where[0].name, "slot": where[1]} if where else None,
        # Three cells and the row's bonus cell: null (empty), a number, or "X" (docs/API.md).
        "rows": {c.name: list(p.table[c]) for c in ROW_ORDER},
        "column_bonus": list(p.column_bonus),
    }


def _move(m, best: bool) -> dict:
    return {
        "row": m.category.name,
        "slot": m.slot,
        "value": m.value,
        "points": m.points,
        "bonus": m.bonus,
        "best": best,
        "balance_change": m.balance_change,
        "bonus_lost": m.bonus_lost,
        "column_bonus_lost": m.column_bonus_lost,
        "label": m.label,
        "action": m.action_text,
        "preview": m.preview,
    }


def _event(event: dict, names: List[str], me: Optional[int]) -> dict:
    """
    A reaction or an effect with its words for the player in seat `me`, in the request's
    language, so an app shows them as they are (abaka/effects.py; the web page shows the
    same words).
    """
    data = _plain(event)
    if event["kind"] == "reaction":
        data.update(reaction_words(event, names, me))
    elif event["kind"] == "effect":
        data["title"], data["text"] = effect_words(event, names, me)
    return data


def _table(view: RoomView) -> dict:
    """The running score at this table (finished games here, across rematches)."""
    wins, draws = view.series()
    return {"games": len(view.results), "wins": wins, "draws": draws}


def _club_result(game: Optional[dict]) -> Optional[dict]:
    if game is None:  # not recorded yet
        return None
    return {"club": game["club"],
            "players": [{"name": p["name"], "score": p["score"], "change": p["change"], "rating": p["rating"]}
                        for p in game["players"]]}


def _club_code(req: _Request, clubs: Optional[ClubStore]) -> Optional[str]:
    """The club a new game counts for, if the request names one (it must exist)."""
    if req.get("club") is None:
        return None
    code = normalize_code(req.text("club"))
    if clubs is None or not (is_club_code(code) and clubs.exists(code)):
        raise ApiError("not_found", t("No club with that code. Check it and try again."))
    return code


def _club_data(clubs: Optional[ClubStore], code: str, games: int) -> dict:
    club = clubs.get(code) if clubs is not None and is_club_code(code) else None
    if club is None:
        raise ApiError("not_found", t("No club with that code. Check it and try again."))
    members = sorted(club["members"].values(), key=lambda m: (-m["rating"], -m["wins"], m["name"].casefold()))
    fields = ("name", "rating", "change", "games", "wins", "points", "best", "last_played")
    return {
        "code": club["code"],
        "name": club["name"],
        "members": [{k: m[k] for k in fields} for m in members],
        "games": [{"id": g["id"], "at": g["at"], "players": [dict(p) for p in g["players"]]}
                  for g in club["games"][:games]],
        "names": clubs.member_names(code),  # for name pickers: the most recently played first
    }


def _seen_text(seen) -> str:
    return "%d.%d.%d" % tuple(seen)


def _plain(value: Any) -> Any:
    """Tuples as lists, so the data is exactly what JSON gives back."""
    if isinstance(value, dict):
        return {k: _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    return value


__all__ = ["ApiError", "CREATING", "ERRORS", "OPERATIONS", "PROTOCOL", "failure", "handle"]
