"""
Game rooms: every game the app hosts, online (2 to 5 players, each on their own
device) or on one device (a "local" room).

One Streamlit server process serves every browser session, so a single
RoomStore held in that process is the source of truth for all games. Each
browser only sends actions ("roll", "reroll", "score", "cross") and renders a
copy of the shared state; nothing game-related lives in a browser session.

With a repository (abaka/repository.py; the app uses one JSON file per room in
a save folder), every room is saved after each change and read back when someone
opens it, so games survive reloads, dropped sessions, code updates and server
restarts (as long as the storage does).

This module has no Streamlit dependency so it can be unit-tested directly.

It logs to the "abaka" logger: warnings (a failed save, an unreadable file) and,
with `report_every`, a stats line per period (the app: once a minute).
"""

from __future__ import annotations

import gc
import logging
import os
import re
import secrets
import sys
import threading
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Union

from .engine import GameEngine
from .models import Category
from .repository import FileRepository
from .saving import engine_from_data, engine_to_data
from .scoring import is_royal_full, score_category

# No 0/O or 1/I, so codes are easy to read aloud and type.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 5
MIN_PLAYERS = 2
MAX_PLAYERS = 5
MAX_NAME_LENGTH = 20
ROOM_TTL_SECONDS = 7 * 24 * 60 * 60  # rooms nobody touched for a week are dropped

# Rooms in memory (with a save folder; the files stay on disk and are loaded again on demand).
IDLE_IN_MEMORY_SECONDS = 30 * 60      # no page has looked at the room for this long
FINISHED_IN_MEMORY_SECONDS = 10 * 60  # a finished game, sooner
MAX_ROOMS_IN_MEMORY = 2000            # beyond this, the rooms seen least recently leave first
SWEEP_EVERY_SECONDS = 60
DISK_SWEEP_EVERY_SECONDS = 60 * 60    # expired files are deleted this often
RESULTS_KEPT = 100                    # finished games a room remembers for its running score

# Reactions players send each other in an online game, and the effects everyone sees
# after a great throw or a bonus. Both live in the room's memory only (never saved).
REACTIONS = ("lucky", "mrlucky", "nice", "wow", "ouch", "hurry", "gg", "haha", "fire")
REACTION_EVERY_SECONDS = 2.0          # one reaction per seat this often
EVENTS_KEPT = 20                      # recent reactions and effects a room keeps for the pages
# Effects, shown on every screen as the dice land (owner, 2026-11-19; see _celebration).
GRAND_FIREWORKS = "grand_fireworks"   # Abaka or the royal full house on the first roll
FIREWORKS = "fireworks"               # Abaka or the royal full house after a reroll
SPARKLES = "sparkles"                 # a straight, full house or four of a kind on the first roll; a bonus earned
CHAT_KEPT = 50                        # chat messages a room keeps (memory only; deleted when the game ends)
MAX_MESSAGE_LENGTH = 200
MESSAGES_PER_WINDOW = 3               # a player may send this many messages...
MESSAGE_WINDOW_SECONDS = 3.0          # ...in this many seconds (about one a second, a short burst allowed)
# Thrown on the first roll, these bring sparkles. When the dice make more than one (a wild joker),
# the banner names the first in this list.
_SPARKLE_HITS = (Category.KARE, Category.FULL, Category.LARGE_STRAIGHT, Category.SMALL_STRAIGHT)
_CODE_PATTERN = re.compile("^[%s]{%d}$" % (CODE_ALPHABET, CODE_LENGTH))

log = logging.getLogger("abaka")


class RoomError(ValueError):
    """A request the room refused; the message is safe to show to the player."""


class TooFast(RoomError):
    """A reaction sent too soon after the last one from the same seat. Nothing was sent."""


class OutdatedPage(RoomError):
    """A move made on a page drawn before the room's latest change (a double tap, or a
    move by someone else meanwhile). Nothing was changed; the page only needs redrawing."""


# Characters never kept in a name or a message: control characters, invisible format
# characters (such as right-to-left overrides), and halves of surrogate pairs. JSON can carry
# half a pair ("\ud83d") but UTF-8 cannot, so one in a name or a message would break every
# page and connection that shows it, and the game's row in the database.
_NEVER_KEPT = ("Cc", "Cf", "Cs")


def clean_name(name: str, fallback: str, limit: int = MAX_NAME_LENGTH) -> str:
    """Spaces collapsed, at most `limit` characters, no control, invisible or broken
    characters (_NEVER_KEPT); `fallback` if nothing is left."""
    visible = "".join(ch for ch in (name or "") if unicodedata.category(ch) not in _NEVER_KEPT)
    name = " ".join(visible.split())[:limit]
    return name or fallback


def clean_message(text: str) -> str:
    """A chat message: no control, invisible or broken characters (_NEVER_KEPT), spaces
    collapsed, at most MAX_MESSAGE_LENGTH characters. Empty if nothing is left."""
    visible = "".join(" " if ch.isspace() else ch for ch in (text or "")
                      if ch.isspace() or unicodedata.category(ch) not in _NEVER_KEPT)
    return " ".join(visible.split())[:MAX_MESSAGE_LENGTH]


def member_key(name: str) -> str:
    """Who a name is in a club: the same name, whatever its capitals and spacing (abaka/clubs.py)."""
    return " ".join(name.split()).casefold()


def normalize_code(code: str) -> str:
    return "".join((code or "").split()).upper()


def within_limit(times: List[float], now: float, limit: int, window: float) -> "tuple[bool, List[float]]":
    """
    A simple rate limit: (allowed, the times to keep). Allowed while fewer than `limit` of
    `times` fall in the last `window` seconds; an allowed event is added to the times.
    """
    recent = [x for x in times if now - x < window]
    if len(recent) < limit:
        return True, recent + [now]
    return False, recent


def is_valid_code(code: str) -> bool:
    """A well-formed game code. Codes become file names, so nothing else ever reaches the disk."""
    return bool(_CODE_PATTERN.match(code))


class RoomView:
    """A point-in-time copy of a room, safe to read without the store lock."""

    def __init__(self, code: str, names: List[str], engine: Optional[GameEngine],
                 version: int, games_played: int, capacity: int, local: bool = False,
                 club: Optional[str] = None, results: Optional[List[dict]] = None,
                 picked: tuple = (), rerolled: tuple = (), picks: int = 0, events: tuple = (),
                 chat: tuple = (), last_event_id: int = 0) -> None:
        self.code = code
        self.names = names            # seated players, in seat order (seat 0 created the game)
        self.engine = engine
        self.version = version
        self.games_played = games_played
        self.capacity = capacity      # how many players the game is for
        self.local = local            # a same-device game: one browser plays every seat
        self.club = club              # the club whose table this room's games count for, if any
        self.results = results or []  # finished games, oldest first: {"game": n, "scores": [...]}
        self.picked = picked          # dice the player whose turn it is has picked to roll again
        self.rerolled = rerolled      # dice the last move rolled again (empty if it was not a reroll)
        self.events = events          # recent reactions and effects, oldest first (see _Room.events)
        self.chat = chat              # this game's chat messages, oldest first (see _Room.chat)
        # Changes with the room, the picked dice, a new event or a chat message: what pages poll.
        self.seen = (version, picks, last_event_id)

    @property
    def started(self) -> bool:
        return self.engine is not None

    def series(self) -> "tuple[List[int], int]":
        """The running score at this table: wins per seat, and the number of drawn games."""
        return series_wins(self.results, len(self.names))


def series_wins(results: List[dict], players: int) -> "tuple[List[int], int]":
    """Wins per seat over finished games (a shared top score is a draw, not a win), and draws."""
    wins, draws = [0] * players, 0
    for result in results:
        scores = result["scores"]
        if len(scores) != players:
            continue
        best = max(scores)
        winners = [i for i, score in enumerate(scores) if score == best]
        if len(winners) == 1:
            wins[winners[0]] += 1
        else:
            draws += 1
    return wins, draws


class _Room:
    def __init__(self, code: str, capacity: int, local: bool = False) -> None:
        self.code = code
        self.capacity = capacity
        self.local = local
        self.names: List[str] = []
        self.tokens: List[str] = []
        self.engine: Optional[GameEngine] = None
        self.version = 0
        self.games_played = 0
        self.club: Optional[str] = None
        self.results: List[dict] = []
        self.updated_at = time.time()
        self.last_seen = self.updated_at  # when a page last looked at it (not saved)
        # Shown to the other players while a turn goes on; not saved, and cleared by every move.
        self.picked: tuple = ()           # dice the player whose turn it is has picked
        self.rerolled: tuple = ()         # dice the latest move rolled again, if it was a reroll
        self.picks = 0                    # counts changes of `picked`, so pages notice them
        # Reactions and effects (not saved; a rematch clears them). Each is a dict with an
        # increasing "id" (from the clock in ms, so ids keep growing after the room is loaded
        # again), "kind" ("reaction" or "effect"), "seat", "at" and its details. Never changed.
        self.events: List[dict] = []
        self.last_event_id = 0
        self.reacted_at: Dict[int, List[float]] = {}  # per seat: when it sent its latest reaction
        # The game's chat (online games): {"id", "seat", "text", "at"}, never saved, deleted by
        # the move that ends the game. Its ids come from the same clock as the events.
        self.chat: List[dict] = []
        self.said_at: Dict[int, List[float]] = {}     # per seat: when it sent its latest messages

    def _next_id(self) -> "tuple[int, float]":
        now = time.time()
        self.last_event_id = max(self.last_event_id + 1, int(now * 1000))
        return self.last_event_id, now

    def add_event(self, event: dict) -> None:
        event_id, now = self._next_id()
        self.events = (self.events + [dict(event, id=event_id, at=now)])[-EVENTS_KEPT:]

    def add_message(self, seat: int, text: str) -> None:
        message_id, now = self._next_id()
        self.chat = (self.chat + [{"id": message_id, "seat": seat, "text": text, "at": now}])[-CHAT_KEPT:]

    def touch(self) -> None:
        self.version += 1
        self.updated_at = time.time()

    def to_data(self) -> dict:
        return {
            "code": self.code, "capacity": self.capacity, "local": self.local,
            "names": list(self.names), "tokens": list(self.tokens),
            "engine": engine_to_data(self.engine) if self.engine is not None else None,
            "version": self.version, "games_played": self.games_played, "updated_at": self.updated_at,
            "club": self.club, "results": [dict(r, scores=list(r["scores"])) for r in self.results],
        }

    @classmethod
    def from_data(cls, d: dict) -> "_Room":
        room = cls(d["code"], int(d["capacity"]), bool(d.get("local", False)))
        room.names = list(d["names"])
        room.tokens = list(d["tokens"])
        room.engine = engine_from_data(d["engine"]) if d.get("engine") else None
        room.version = int(d["version"])
        room.games_played = int(d["games_played"])
        room.updated_at = float(d["updated_at"])
        room.club = d.get("club")
        room.results = [{"game": int(r["game"]), "scores": [int(x) for x in r["scores"]]}
                        for r in d.get("results") or []]
        room.last_seen = time.time()
        return room


class RoomStore:
    """
    Thread-safe registry of rooms. Streamlit runs each session in its own thread.

    One lock guards the rooms. Engines are copy-on-write: a move works on a clone and
    installs it, and an installed engine is never changed again, so view() hands it
    out without copying (readers must not change it either). Rooms are saved after
    the lock is released (_write), so slow storage never holds up other games.
    """

    def __init__(self, starting_throw: bool = True, save_dir: Union[str, Path, None] = None,
                 report_every: Optional[float] = None, repository=None, on_game_over=None) -> None:
        """
        starting_throw: each game opens with the starting throw (lowest total goes first).
        save_dir: keep every room in a JSON file there (a FileRepository). Saved rooms are
            loaded when someone opens them, and rooms nobody looks at leave memory.
        report_every: log a stats line this often, in seconds (None: never). It is
            written by a poll, so a server nobody has open stays quiet.
        repository: where rooms are kept, instead of save_dir (see abaka/repository.py).
            Without either, rooms live in memory only.
        on_game_over: called with a result dict when a game ends (after the lock is
            released): room, game (its number in the room), club, names, scores, at.
            The app records club games with it (abaka/clubs.py).
        """
        self._lock = threading.Lock()
        self._rooms: Dict[str, _Room] = {}
        self._retired = False
        self.starting_throw = starting_throw
        self.on_game_over = on_game_over
        if repository is None and save_dir is not None:
            repository = FileRepository(save_dir)
        self._repository = repository
        self.save_dir = getattr(repository, "folder", None)  # for files: the save folder
        self._last_sweep = time.time()
        self._last_disk_sweep = 0.0
        # The stats line: counts since the last one (_counts under self._lock; _saves, the
        # count, seconds in total, slowest and failures, under self._stats_lock).
        self.report_every = report_every
        self._counts: Dict[str, int] = {}
        self._stats_lock = threading.Lock()
        self._saves = [0, 0.0, 0.0, 0]
        self._counted_since = time.time()
        self._gc_full_runs = _full_collections()
        if repository is not None:
            self._clean_up_at_start()

    def retire(self) -> None:
        """
        This store's code has been replaced by an update (see abaka_ui.get_store): stop
        serving and free the rooms. The new store reads them back from disk, so writes
        already under way finish first.
        """
        with self._lock:
            self._retired = True
            self._rooms.clear()
        if self._repository is not None:
            self._repository.wait()
            close = getattr(self._repository, "close", None)  # a database connection
            if close is not None:
                close()
        log.info("store retired after a code update; the new store reads the games from disk")

    def storage(self) -> str:
        """
        Where games are kept, for the home page: "database", "files", "memory", or
        "database:<why>" when a database is set up but not in use (see
        PostgresRepository.status: password, unreachable, error, not connected yet).
        """
        repository = self._repository
        if repository is None:
            return "memory"
        status = getattr(repository, "status", None)
        if status is None:
            return "files"
        state = status()
        return "database" if state == "connected" else f"database:{state}"

    # ----- lobby -----
    def create(self, host_name: str, players: int = 2, club: Optional[str] = None) -> "tuple[str, str]":
        """
        Open a new room for `players` players. Returns (room_code, seat_token) for the host.
        With `club`, its games count for that club's table.
        """
        if not MIN_PLAYERS <= int(players) <= MAX_PLAYERS:
            raise RoomError(f"A game is for {MIN_PLAYERS} to {MAX_PLAYERS} players.")
        with self._lock:
            self._make_room_for_one_more()
            code = self._new_code()
            room = _Room(code, int(players))
            room.club = club
            self._rooms[code] = room
            self._count("created")
            token = self._seat(room, clean_name(host_name, "Player 1"))
            pending = self._snapshot(room)
        self._write(pending)
        return code, token

    def create_local(self, names: List[str], club: Optional[str] = None) -> "tuple[str, str]":
        """
        A same-device game: every seat is played from one browser, and the game starts at once.
        It gets a code like an online game, so it can be continued later from its link or code.
        """
        if not MIN_PLAYERS <= len(names) <= MAX_PLAYERS:
            raise RoomError(f"A game is for {MIN_PLAYERS} to {MAX_PLAYERS} players.")
        with self._lock:
            self._make_room_for_one_more()
            code = self._new_code()
            room = _Room(code, len(names), local=True)
            room.club = club
            token = secrets.token_urlsafe(16)
            room.names = [clean_name(n, f"Player {i}") for i, n in enumerate(names, 1)]
            room.tokens = [token] * len(names)  # one browser holds every seat
            room.engine = _new_engine(room, self.starting_throw)
            self._rooms[code] = room
            self._count("created")
            pending = self._snapshot(room)
        self._write(pending)
        return code, token

    def resume_local(self, code: str) -> str:
        """Continue a same-device game from its link or code (on any browser). Returns its token."""
        with self._lock:
            room = self._get(code)
            if not room.local:
                raise RoomError("This is an online game: join it or rejoin as one of its players.")
            return room.tokens[0]

    def join(self, code: str, name: str) -> str:
        """
        Take a free seat in a room. The game starts once every seat is taken. In a club game a
        name already at the table (ignoring capitals and spaces) is refused: the club counts it
        as one member, who would then play against themselves.
        """
        with self._lock:
            room = self._get(code)
            if room.engine is not None or len(room.names) >= room.capacity:
                raise RoomError("This game is already full.")
            seat_no = len(room.names) + 1
            name = clean_name(name, f"Player {seat_no}")
            if room.club is not None and member_key(name) in {member_key(n) for n in room.names}:
                raise RoomError("Each player needs a different name.")
            name = _distinct(name, room.names)
            token = self._seat(room, name)
            if len(room.names) == room.capacity:
                room.engine = _new_engine(room, self.starting_throw)
            room.touch()
            pending = self._snapshot(room)
        self._write(pending)
        return token

    def start_now(self, code: str, token: str) -> None:
        """The creator starts the game early with the players who have joined (at least two)."""
        with self._lock:
            room = self._get(code)
            if not room.tokens or token != room.tokens[0]:
                raise RoomError("Only the player who created the game can start it.")
            if room.engine is not None:
                raise RoomError("The game has already started.")
            if len(room.names) < MIN_PLAYERS:
                raise RoomError("Wait until at least one more player has joined.")
            room.capacity = len(room.names)
            room.engine = _new_engine(room, self.starting_throw)
            room.touch()
            pending = self._snapshot(room)
        self._write(pending)

    def leave(self, code: str, token: str) -> None:
        """
        Give up a seat in the waiting room, before the game starts.

        Later players move up one seat, so if the creator leaves, the next player in
        join order becomes the creator (and can start the game). A room nobody is
        left in is closed. Once the game has started, seats are kept, so a player
        who left can rejoin from the link; this does nothing then.
        """
        with self._lock:
            room = self._room(code)
            if room is None or room.engine is not None or token not in room.tokens:
                return
            seat = room.tokens.index(token)
            del room.names[seat]
            del room.tokens[seat]
            if not room.names:
                del self._rooms[room.code]
                self._unsave(room.code)
                return
            room.touch()
            pending = self._snapshot(room)
        self._write(pending)

    def reclaim(self, code: str, seat: int) -> str:
        """
        Take over an existing seat (after a page refresh or a device switch).
        The seat gets a fresh token, so whichever tab held it before stops controlling it.
        """
        with self._lock:
            room = self._get(code)
            if not 0 <= seat < len(room.names):
                raise RoomError("That seat does not exist.")
            if room.local:
                return room.tokens[0]
            token = secrets.token_urlsafe(16)
            room.tokens[seat] = token
            room.touch()
            pending = self._snapshot(room)
        self._write(pending)
        return token

    # ----- reading -----
    def exists(self, code: str) -> bool:
        with self._lock:
            return self._room(code) is not None

    def seat_of(self, code: str, token: Optional[str]) -> Optional[int]:
        """Seat index for this token, or None if the token no longer controls a seat."""
        with self._lock:
            room = self._room(code)
            if room is None or not token or token not in room.tokens:
                return None
            return room.tokens.index(token)

    def version(self, code: str) -> int:
        """Changes whenever the room changes; -1 if the room is gone. Cheap to poll."""
        with self._lock:
            self._count("polls")
            room = self._room(code)
            version = room.version if room else -1
        self._report_if_due()
        return version

    def view(self, code: str) -> RoomView:
        """The room as it is now. The engine is shared, not copied: do not change it."""
        with self._lock:
            self._count("views")
            room = self._get(code)
            return RoomView(room.code, list(room.names), room.engine, room.version, room.games_played,
                            room.capacity, room.local, room.club, list(room.results),
                            room.picked, room.rerolled, room.picks, tuple(room.events), tuple(room.chat),
                            room.last_event_id)

    def seen(self, code: str):
        """
        (version, picks, latest event id): changes when the room changes, the player whose turn
        it is picks other dice, or a reaction, effect or chat message arrives. Pages poll it
        (RoomView.seen is the value they were drawn from). Cheap.
        """
        with self._lock:
            self._count("polls")
            room = self._room(code)
            seen = (room.version, room.picks, room.last_event_id) if room else (-1, 0, 0)
        self._report_if_due()
        return seen

    # ----- playing -----
    # Each move may name the room version the player's page was drawn from
    # (`expected_version`); if the room has changed since, the move is refused with
    # OutdatedPage, so a double tap or a stale page never makes a move nobody saw.
    def throw_for_start(self, code: str, token: str, expected_version: Optional[int] = None) -> None:
        """This player's throw in the starting throw that decides who goes first."""
        def action(engine: GameEngine) -> None:
            if not engine.choosing_first_player:
                raise RoomError("The first player has already been decided.")
            engine.throw_for_start()
        self._act(code, token, action, expected_version)

    def roll(self, code: str, token: str, expected_version: Optional[int] = None) -> None:
        """First roll of the turn."""
        def action(engine: GameEngine) -> None:
            if engine.dice:
                raise RoomError("You have already rolled this turn.")
            engine.start_turn()
        self._act(code, token, action, expected_version)

    def reroll(self, code: str, token: str, indices: List[int], expected_version: Optional[int] = None) -> None:
        chosen = tuple(sorted(set(indices)))

        def action(engine: GameEngine) -> None:
            _require_rolled(engine)
            if engine.rolls_left <= 0:
                raise RoomError("No rerolls left.")
            engine.reroll(list(chosen))

        def show(room: _Room) -> None:
            room.rerolled = chosen  # the others see exactly which dice were rolled again
        self._act(code, token, action, expected_version, after=show)

    def pick(self, code: str, token: str, indices: List[int]) -> None:
        """
        The dice the player whose turn it is has picked to roll again, so the other players
        see them. Not a move: the game and the room version stay as they are (a reroll pressed
        right after a pick is not refused as outdated), nothing is saved, and the next move
        clears the picks. Same-device games keep their picks in the page.
        """
        with self._lock:
            room = self._get(code)
            if room.local:
                return
            engine = self._check_turn(room, token)
            if not engine.dice or engine.rolls_left <= 0:
                raise RoomError("No rerolls left.")
            picked = tuple(sorted({i for i in indices if 0 <= i < len(engine.dice)}))
            if picked != room.picked:
                room.picked = picked
                room.picks += 1

    def react(self, code: str, token: str, reaction: str, to: Optional[int] = None) -> None:
        """
        A reaction (one of REACTIONS) from this player to everyone at the table, or aimed at
        the player in seat `to`. Online games only; anyone seated may react, at any time. Not
        a move: the room version stays as it is and nothing is saved. One per seat every
        REACTION_EVERY_SECONDS (TooFast otherwise).
        """
        if reaction not in REACTIONS:
            raise RoomError("Unknown reaction.")
        with self._lock:
            room = self._get(code)
            if token not in room.tokens:
                raise RoomError("You are not seated in this game.")
            if room.local:
                return  # everyone shares one screen
            seat = room.tokens.index(token)
            if to is not None and not (0 <= to < len(room.names) and to != seat):
                to = None
            allowed, room.reacted_at[seat] = within_limit(room.reacted_at.get(seat, []), time.time(), 1,
                                                          REACTION_EVERY_SECONDS)
            if not allowed:
                raise TooFast("One reaction every two seconds, please.")
            room.add_event({"kind": "reaction", "seat": seat, "to": to, "reaction": reaction})

    def say(self, code: str, token: str, text: str) -> None:
        """
        A chat message from this player to the table, while an online game is being played.
        Anyone seated may write, whoever's turn it is. Cleaned like a name (no control or
        invisible characters) and cut to MAX_MESSAGE_LENGTH; an empty message is ignored.
        Not a move: the room version stays as it is. Never saved, and the move that ends the
        game deletes the chat (owner: "The chat should be deleted once the game is over").
        At most MESSAGES_PER_WINDOW per seat in MESSAGE_WINDOW_SECONDS (TooFast otherwise).
        """
        text = clean_message(text)
        if not text:
            return
        with self._lock:
            room = self._get(code)
            if token not in room.tokens:
                raise RoomError("You are not seated in this game.")
            if room.local:
                return  # everyone shares one screen
            if room.engine is None:
                raise RoomError("Waiting for the second player to join.")
            if room.engine.is_game_over():
                raise RoomError("The game is over.")
            seat = room.tokens.index(token)
            allowed, room.said_at[seat] = within_limit(room.said_at.get(seat, []), time.time(),
                                                       MESSAGES_PER_WINDOW, MESSAGE_WINDOW_SECONDS)
            if not allowed:
                raise TooFast("Slow down a little: about one message a second.")
            room.add_message(seat, text)

    def score(self, code: str, token: str, category: Category, slot_index: int,
              expected_version: Optional[int] = None) -> None:
        def action(engine: GameEngine) -> None:
            _require_rolled(engine)
            engine.record_score(category, slot_index)
        self._act(code, token, action, expected_version)

    def cross(self, code: str, token: str, category: Category, slot_index: int,
              expected_version: Optional[int] = None) -> None:
        def action(engine: GameEngine) -> None:
            _require_rolled(engine)
            engine.record_cross(category, slot_index)
        self._act(code, token, action, expected_version)

    def rematch(self, code: str, token: str) -> None:
        """Start a fresh game with the same players once the current one is over."""
        with self._lock:
            room = self._get(code)
            if token not in room.tokens:
                raise RoomError("You are not seated in this game.")
            if room.engine is None or not room.engine.is_game_over():
                raise RoomError("The current game is not finished yet.")
            room.games_played += 1
            room.engine = _new_engine(room, self.starting_throw)
            room.events, room.chat = [], []  # last_event_id stays, so ids keep growing
            room.touch()
            pending = self._snapshot(room)
        self._write(pending)

    # ----- internals -----
    @staticmethod
    def _check_turn(room: _Room, token: str, expected_version: Optional[int] = None) -> GameEngine:
        """The room's game, if the player holding `token` may act in it now. Call with the lock held."""
        if token not in room.tokens:
            raise RoomError("You are not seated in this game.")
        if expected_version is not None and room.version != expected_version:
            raise OutdatedPage("This page was out of date, so the move was not made.")
        if room.engine is None:
            raise RoomError("Waiting for the second player to join.")
        if room.engine.is_game_over():
            raise RoomError("The game is over.")
        if not room.local and room.tokens.index(token) != room.engine.current:
            raise RoomError("It is not your turn.")
        return room.engine

    def _act(self, code: str, token: str, action, expected_version: Optional[int] = None,
             after=None) -> None:
        """Run one move for the player holding `token`, atomically. `after(room)` runs once it succeeded."""
        with self._lock:
            room = self._get(code)
            # Work on a copy so a rejected move can never leave the room half-updated, and so the
            # engine that views have handed out never changes (copy-on-write).
            before = self._check_turn(room, token, expected_version)
            engine = before.clone()
            action(engine)
            room.engine = engine
            room.picked, room.rerolled = (), ()
            if after is not None:
                after(room)
            effect = _celebration(before, engine)
            if effect is not None:
                room.add_event(effect)
            finished = None
            if engine.is_game_over():  # this move ended the game
                room.chat = []  # the chat lasts as long as the game (owner)
                scores = [p.calculate_score() for p in engine.players]
                room.results = (room.results + [{"game": room.games_played, "scores": scores}])[-RESULTS_KEPT:]
                finished = {"room": room.code, "game": room.games_played, "club": room.club,
                            "names": list(room.names), "scores": scores, "at": time.time()}
            room.touch()
            self._count("moves")
            pending = self._snapshot(room)
        self._write(pending)
        if finished is not None and self.on_game_over is not None:
            try:
                self.on_game_over(finished)
            except Exception as e:  # noqa: BLE001 - a club table must never break the game
                log.warning("could not record game %s:%s: %s", finished["room"], finished["game"], e)

    def _count(self, what: str, n: int = 1) -> None:
        """Add to a count for the stats line. Call with self._lock held."""
        self._counts[what] = self._counts.get(what, 0) + n

    def _report_if_due(self) -> None:
        """Log the stats line if report_every has passed since the last one (call without the lock)."""
        if self.report_every is None or time.time() - self._counted_since < self.report_every:
            return
        with self._lock:
            now = time.time()
            if now - self._counted_since < self.report_every:
                return  # another thread has just written it
            counts, self._counts = self._counts, {}
            seconds, self._counted_since = now - self._counted_since, now
            rooms = list(self._rooms.values())
            playing = sum(1 for r in rooms if r.engine is not None and not r.engine.is_game_over())
            local = sum(1 for r in rooms if r.local)
        with self._stats_lock:
            (saves, save_seconds, slowest, failed), self._saves = self._saves, [0, 0.0, 0.0, 0]
        full_runs = _full_collections()
        gc_runs, self._gc_full_runs = full_runs - self._gc_full_runs, full_runs
        memory = _memory_mb()
        log.info(
            "stats for %.0f s: rooms in memory %d (%d being played, %d on one device); polls %d, "
            "page views %d, moves %d, new games %d; rooms loaded from disk %d, left memory %d; "
            "saves %d (%.1f ms on average, slowest %.1f ms, failed %d); full garbage collections %d; "
            "memory %s",
            seconds, len(rooms), playing, local, counts.get("polls", 0), counts.get("views", 0),
            counts.get("moves", 0), counts.get("created", 0), counts.get("loaded", 0),
            counts.get("left memory", 0), saves, 1000 * save_seconds / saves if saves else 0.0,
            1000 * slowest, failed, gc_runs, "%.0f MB" % memory if memory is not None else "unknown")

    def _get(self, code: str) -> _Room:
        if self._retired:
            raise RoomError("The app was just updated. Please try again.")
        room = self._room(code)
        if room is None:
            raise RoomError("Game not found. Check the code, or ask for a new invite.")
        return room

    def _room(self, code: str) -> Optional[_Room]:
        """
        The room with this code: from memory, or loaded from the repository if it left memory.
        None if there is none. Marks it as just seen, so rooms people look at stay in memory.
        Call with self._lock held.
        """
        if self._retired:
            return None
        code = normalize_code(code)
        room = self._rooms.get(code)
        if room is None and self._repository is not None and is_valid_code(code):
            room = self._load_room(code)
        if room is not None:
            room.last_seen = time.time()
        return room

    @staticmethod
    def _seat(room: _Room, name: str) -> str:
        token = secrets.token_urlsafe(16)
        room.names.append(name)
        room.tokens.append(token)
        return token

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
            if code not in self._rooms and (self._repository is None or self._repository.claim(code)):
                return code

    def _make_room_for_one_more(self) -> None:
        """Before a new room: let unused rooms go; without a repository, refuse past the cap."""
        self._sweep()
        if self._repository is None and len(self._rooms) >= MAX_ROOMS_IN_MEMORY:
            raise RoomError("The server is busy right now. Please try again later.")

    def _sweep(self, force: bool = False) -> None:
        """
        At most once a minute: drop expired rooms (from the repository too); with a
        repository, let rooms nobody has looked at for a while leave memory (they stay
        saved), and keep at most MAX_ROOMS_IN_MEMORY. Once an hour, delete expired rooms
        that are not in memory from the repository.
        """
        now = time.time()
        if not force and now - self._last_sweep < SWEEP_EVERY_SECONDS:
            return
        self._last_sweep = now
        cutoff = now - ROOM_TTL_SECONDS
        for code, room in list(self._rooms.items()):
            if room.updated_at < cutoff:
                del self._rooms[code]
                self._unsave(code)
                continue
            if self._repository is None:
                continue
            idle = now - room.last_seen
            finished = room.engine is not None and room.engine.is_game_over()
            if idle > IDLE_IN_MEMORY_SECONDS or (finished and idle > FINISHED_IN_MEMORY_SECONDS):
                del self._rooms[code]  # still saved; loaded again when someone opens it
                self._count("left memory")
        if self._repository is not None and len(self._rooms) > MAX_ROOMS_IN_MEMORY:
            # Not the rooms seen in the last minute: their latest write may still be under way.
            quiet = sorted((r.last_seen, c) for c, r in self._rooms.items() if now - r.last_seen > 60)
            for _, code in quiet[:len(self._rooms) - MAX_ROOMS_IN_MEMORY]:
                del self._rooms[code]
                self._count("left memory")
        if self._repository is not None and (force or now - self._last_disk_sweep > DISK_SWEEP_EVERY_SECONDS):
            self._last_disk_sweep = now
            self._repository.prune(cutoff, keep=set(self._rooms))

    # ----- saving (through the repository) -----
    def _snapshot(self, room: _Room):
        """What to save for this room: taken under the lock, saved after it by _write."""
        if self._repository is None:
            return None
        return room.code, room.version, room.to_data()

    def _write(self, pending) -> None:
        """
        Save a room (call it without holding self._lock). The repository never lets an
        older version replace a newer one; a failed save is logged but never stops the game.
        """
        if pending is None:
            return
        code, version, data = pending
        started = time.perf_counter()
        try:
            saved = self._repository.save(code, version, data)
        except Exception as e:  # noqa: BLE001 - saving must never break a move
            with self._stats_lock:
                self._saves[3] += 1
            log.warning("could not save game %s: %s", code, e)
            return
        if saved:
            took = time.perf_counter() - started
            with self._stats_lock:
                self._saves[0] += 1
                self._saves[1] += took
                self._saves[2] = max(self._saves[2], took)

    def _unsave(self, code: str) -> None:
        """Delete a room for good: a late save of it is refused."""
        if self._repository is not None:
            self._repository.delete(code)

    def _clean_up_at_start(self) -> None:
        """Leftovers of writes a crash interrupted, and rooms that expired."""
        remove_leftovers = getattr(self._repository, "remove_leftovers", None)
        if remove_leftovers is not None:
            remove_leftovers()
        self._repository.prune(time.time() - ROOM_TTL_SECONDS)

    def _load_room(self, code: str) -> Optional[_Room]:
        """Load a saved room into memory. Data the store cannot use is quarantined."""
        data = self._repository.load(code)
        if data is None:
            return None
        try:
            room = _Room.from_data(data)
        except (ValueError, KeyError, TypeError, IndexError, AttributeError) as e:
            self._repository.quarantine(code, e)
            return None
        if room.code != code:
            return None
        if room.updated_at < time.time() - ROOM_TTL_SECONDS:
            self._unsave(code)
            return None
        self._rooms[code] = room
        self._count("loaded")
        return room


def _full_collections() -> int:
    """How many full (generation 2) garbage collections Python has run in this process."""
    return gc.get_stats()[-1]["collections"]


def _memory_mb() -> Optional[float]:
    """This process's resident memory in MB (Linux), or its peak where only that is known."""
    try:
        with open("/proc/self/statm") as f:
            return int(f.read().split()[1]) * os.sysconf("SC_PAGE_SIZE") / 2 ** 20
    except (OSError, ValueError, IndexError, AttributeError):
        pass
    try:
        import resource
        peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    except (ImportError, OSError, ValueError):
        return None
    return peak / 2 ** 20 if sys.platform == "darwin" else peak / 1024  # bytes on macOS, KB on Linux


def _distinct(name: str, taken: List[str]) -> str:
    """`name`, or `name (2)`, `name (3)`... so every player at the table has a different name."""
    if name not in taken:
        return name
    n = 2
    while True:
        suffix = f" ({n})"
        candidate = name[:MAX_NAME_LENGTH - len(suffix)] + suffix
        if candidate not in taken:
            return candidate
        n += 1


def _new_engine(room: _Room, starting_throw: bool) -> GameEngine:
    engine = GameEngine(list(room.names), starting_throw=starting_throw)
    if not starting_throw:
        # Without the starting throw, alternate who goes first from one game to the next.
        engine.current = room.games_played % len(room.names)
    return engine


def _celebration(before: GameEngine, after: GameEngine) -> Optional[dict]:
    """
    The effect every player sees after this move, if it earned one (owner, 2026-11-19):

    - a throw shows what the dice make, as they land, whatever the player then writes:
      Abaka or the royal full house (1-1-1-2-2) bring fireworks, bigger on the first roll;
      a straight, a full house or four of a kind on the first roll bring sparkles;
    - a move that earns its player a row or column bonus brings sparkles.

    `before` is the game as it was before the move (installed engines never change). The
    starting throw brings nothing: it is not a turn and never scores.
    """
    if after.dice:  # only a roll or a reroll leaves dice on the table; a written move clears them
        return _throw_effect(after)
    if after.last_move is not None and after.last_move != before.last_move:
        return _bonus_effect(before, after, after.last_move[0])
    return None


def _throw_effect(engine: GameEngine) -> Optional[dict]:
    dice, first = engine.dice, engine.first_roll
    if score_category(dice, Category.ABAKA):
        what = "ABAKA"
    elif is_royal_full(dice):
        what = "ROYAL"
    else:
        hit = next((c for c in _SPARKLE_HITS if score_category(dice, c)), None) if first else None
        if hit is None:
            return None
        return {"kind": "effect", "effect": SPARKLES, "seat": engine.current, "what": hit.name, "first": True}
    return {"kind": "effect", "effect": GRAND_FIREWORKS if first else FIREWORKS, "seat": engine.current,
            "what": what, "first": first}


def _bonus_effect(before: GameEngine, after: GameEngine, seat: int) -> Optional[dict]:
    """Sparkles for the row and column bonuses this move earned the player (a crossed-out bonus earns none)."""
    old, new = before.players[seat], after.players[seat]
    rows = [(category.name, new.table[category][3]) for category in Category
            if old.table[category][3] is None and _points(new.table[category][3])]
    columns = [(col, value) for col, value in enumerate(new.column_bonus)
               if old.column_bonus[col] is None and _points(value)]
    if not rows and not columns:
        return None
    return {"kind": "effect", "effect": SPARKLES, "seat": seat, "what": "BONUS",
            "rows": rows, "columns": columns}


def _points(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_rolled(engine: GameEngine) -> None:
    if not engine.dice:
        raise RoomError("Roll the dice first.")


class RoomEngine:
    """
    Looks like a GameEngine to the UI components, but is backed by a shared room.

    Reads come from a snapshot taken for this page render. The five turn actions
    are forwarded to the RoomStore, which checks whose turn it is and applies
    them to the one shared game.

    `store` is the RoomStore, or a function returning the current one: the app
    passes a function, because a button's move runs when the next click arrives,
    and a code update in between replaces the store. `version` is the room
    version the snapshot was taken at; when given, a move is refused
    (OutdatedPage) if the room has changed since.
    """

    def __init__(self, store, code: str, token: str, engine: GameEngine, version: Optional[int] = None,
                 picked: tuple = (), rerolled: tuple = ()) -> None:
        self._store = store
        self._code = code
        self._token = token
        self._engine = engine
        self._version = version
        self.picked = picked        # the dice the player whose turn it is has picked (online)
        self.rerolled = rerolled    # the dice the latest move rolled again

    def __getattr__(self, name: str):
        return getattr(self._engine, name)

    def _room_store(self) -> RoomStore:
        return self._store() if callable(self._store) else self._store

    def throw_for_start(self) -> None:
        self._room_store().throw_for_start(self._code, self._token, expected_version=self._version)

    def start_turn(self) -> None:
        self._room_store().roll(self._code, self._token, expected_version=self._version)

    def reroll(self, indices: List[int]) -> None:
        self._room_store().reroll(self._code, self._token, indices, expected_version=self._version)

    def pick(self, indices: List[int]) -> None:
        """Show the other players which dice this player has picked (not a move)."""
        self._room_store().pick(self._code, self._token, indices)

    def record_score(self, category: Category, slot_index: int) -> None:
        self._room_store().score(self._code, self._token, category, slot_index, expected_version=self._version)

    def record_cross(self, category: Category, slot_index: int) -> None:
        self._room_store().cross(self._code, self._token, category, slot_index, expected_version=self._version)
