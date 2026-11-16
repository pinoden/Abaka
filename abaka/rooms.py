"""
Shared game rooms for live online games (2 to 5 players).

One Streamlit server process serves every browser session, so a single
RoomStore held in that process is the source of truth for all online games.
Each browser only sends actions ("roll", "reroll", "score", "cross") and
renders a copy of the shared state; nothing game-related lives in a
browser session.

This module has no Streamlit dependency so it can be unit-tested directly.
"""

from __future__ import annotations

import copy
import secrets
import threading
import time
from typing import Dict, List, Optional

from .engine import GameEngine
from .models import Category

# No 0/O or 1/I, so codes are easy to read aloud and type.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
CODE_LENGTH = 5
MIN_PLAYERS = 2
MAX_PLAYERS = 5
MAX_NAME_LENGTH = 20
ROOM_TTL_SECONDS = 12 * 60 * 60  # idle rooms are dropped after this long


class RoomError(ValueError):
    """A request the room refused; the message is safe to show to the player."""


def clean_name(name: str, fallback: str) -> str:
    name = " ".join((name or "").split())[:MAX_NAME_LENGTH]
    return name or fallback


def normalize_code(code: str) -> str:
    return "".join((code or "").split()).upper()


class RoomView:
    """A point-in-time copy of a room, safe to read without the store lock."""

    def __init__(self, code: str, names: List[str], engine: Optional[GameEngine],
                 version: int, games_played: int, capacity: int) -> None:
        self.code = code
        self.names = names            # seated players, in seat order (seat 0 created the game)
        self.engine = engine
        self.version = version
        self.games_played = games_played
        self.capacity = capacity      # how many players the game is for

    @property
    def started(self) -> bool:
        return self.engine is not None


class _Room:
    def __init__(self, code: str, capacity: int) -> None:
        self.code = code
        self.capacity = capacity
        self.names: List[str] = []
        self.tokens: List[str] = []
        self.engine: Optional[GameEngine] = None
        self.version = 0
        self.games_played = 0
        self.updated_at = time.time()

    def touch(self) -> None:
        self.version += 1
        self.updated_at = time.time()


class RoomStore:
    """Thread-safe registry of rooms. Streamlit runs each session in its own thread."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rooms: Dict[str, _Room] = {}

    # ----- lobby -----
    def create(self, host_name: str, players: int = 2) -> "tuple[str, str]":
        """Open a new room for `players` players. Returns (room_code, seat_token) for the host."""
        if not MIN_PLAYERS <= int(players) <= MAX_PLAYERS:
            raise RoomError(f"A game is for {MIN_PLAYERS} to {MAX_PLAYERS} players.")
        with self._lock:
            self._drop_idle_rooms()
            while True:
                code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CODE_LENGTH))
                if code not in self._rooms:
                    break
            room = _Room(code, int(players))
            self._rooms[code] = room
            token = self._seat(room, clean_name(host_name, "Player 1"))
            return code, token

    def join(self, code: str, name: str) -> str:
        """Take a free seat in a room. The game starts once every seat is taken."""
        with self._lock:
            room = self._get(code)
            if room.engine is not None or len(room.names) >= room.capacity:
                raise RoomError("This game is already full.")
            seat_no = len(room.names) + 1
            name = _distinct(clean_name(name, f"Player {seat_no}"), room.names)
            token = self._seat(room, name)
            if len(room.names) == room.capacity:
                room.engine = _new_engine(room)
            room.touch()
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
            room.engine = _new_engine(room)
            room.touch()

    def leave(self, code: str, token: str) -> None:
        """
        Give up a seat in the waiting room, before the game starts.

        Later players move up one seat, so if the creator leaves, the next player in
        join order becomes the creator (and can start the game). A room nobody is
        left in is closed. Once the game has started, seats are kept, so a player
        who left can rejoin from the link; this does nothing then.
        """
        with self._lock:
            room = self._rooms.get(normalize_code(code))
            if room is None or room.engine is not None or token not in room.tokens:
                return
            seat = room.tokens.index(token)
            del room.names[seat]
            del room.tokens[seat]
            if not room.names:
                del self._rooms[room.code]
                return
            room.touch()

    def reclaim(self, code: str, seat: int) -> str:
        """
        Take over an existing seat (after a page refresh or a device switch).
        The seat gets a fresh token, so whichever tab held it before stops controlling it.
        """
        with self._lock:
            room = self._get(code)
            if not 0 <= seat < len(room.names):
                raise RoomError("That seat does not exist.")
            token = secrets.token_urlsafe(16)
            room.tokens[seat] = token
            room.touch()
            return token

    # ----- reading -----
    def exists(self, code: str) -> bool:
        with self._lock:
            return normalize_code(code) in self._rooms

    def seat_of(self, code: str, token: Optional[str]) -> Optional[int]:
        """Seat index for this token, or None if the token no longer controls a seat."""
        with self._lock:
            room = self._rooms.get(normalize_code(code))
            if room is None or not token or token not in room.tokens:
                return None
            return room.tokens.index(token)

    def version(self, code: str) -> int:
        """Changes whenever the room changes; -1 if the room is gone. Cheap to poll."""
        with self._lock:
            room = self._rooms.get(normalize_code(code))
            return room.version if room else -1

    def view(self, code: str) -> RoomView:
        with self._lock:
            room = self._get(code)
            return RoomView(room.code, list(room.names), copy.deepcopy(room.engine),
                            room.version, room.games_played, room.capacity)

    # ----- playing -----
    def roll(self, code: str, token: str) -> None:
        """First roll of the turn."""
        def action(engine: GameEngine) -> None:
            if engine.dice:
                raise RoomError("You have already rolled this turn.")
            engine.start_turn()
        self._act(code, token, action)

    def reroll(self, code: str, token: str, indices: List[int]) -> None:
        def action(engine: GameEngine) -> None:
            _require_rolled(engine)
            if engine.rolls_left <= 0:
                raise RoomError("No rerolls left.")
            engine.reroll(sorted(set(indices)))
        self._act(code, token, action)

    def score(self, code: str, token: str, category: Category, slot_index: int) -> None:
        def action(engine: GameEngine) -> None:
            _require_rolled(engine)
            engine.record_score(category, slot_index)
        self._act(code, token, action)

    def cross(self, code: str, token: str, category: Category, slot_index: int) -> None:
        def action(engine: GameEngine) -> None:
            _require_rolled(engine)
            engine.record_cross(category, slot_index)
        self._act(code, token, action)

    def rematch(self, code: str, token: str) -> None:
        """Start a fresh game with the same players once the current one is over."""
        with self._lock:
            room = self._get(code)
            if token not in room.tokens:
                raise RoomError("You are not seated in this game.")
            if room.engine is None or not room.engine.is_game_over():
                raise RoomError("The current game is not finished yet.")
            room.games_played += 1
            room.engine = _new_engine(room)
            room.touch()

    # ----- internals -----
    def _act(self, code: str, token: str, action) -> None:
        """Run one move for the player holding `token`, atomically."""
        with self._lock:
            room = self._get(code)
            if token not in room.tokens:
                raise RoomError("You are not seated in this game.")
            if room.engine is None:
                raise RoomError("Waiting for the second player to join.")
            if room.engine.is_game_over():
                raise RoomError("The game is over.")
            if room.tokens.index(token) != room.engine.current:
                raise RoomError("It is not your turn.")
            # Work on a copy so a rejected move can never leave the room half-updated.
            engine = copy.deepcopy(room.engine)
            action(engine)
            room.engine = engine
            room.touch()

    def _get(self, code: str) -> _Room:
        room = self._rooms.get(normalize_code(code))
        if room is None:
            raise RoomError("Game not found. Check the code, or ask for a new invite.")
        return room

    @staticmethod
    def _seat(room: _Room, name: str) -> str:
        token = secrets.token_urlsafe(16)
        room.names.append(name)
        room.tokens.append(token)
        return token

    def _drop_idle_rooms(self) -> None:
        cutoff = time.time() - ROOM_TTL_SECONDS
        for code in [c for c, r in self._rooms.items() if r.updated_at < cutoff]:
            del self._rooms[code]


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


def _new_engine(room: _Room) -> GameEngine:
    engine = GameEngine(list(room.names))
    # Alternate who goes first from one game to the next.
    engine.current = room.games_played % len(room.names)
    return engine


def _require_rolled(engine: GameEngine) -> None:
    if not engine.dice:
        raise RoomError("Roll the dice first.")


class RoomEngine:
    """
    Looks like a GameEngine to the UI components, but is backed by a shared room.

    Reads come from a snapshot taken for this page render. The four turn actions
    are forwarded to the RoomStore, which checks whose turn it is and applies
    them to the one shared game.
    """

    def __init__(self, store: RoomStore, code: str, token: str, engine: GameEngine) -> None:
        self._store = store
        self._code = code
        self._token = token
        self._engine = engine

    def __getattr__(self, name: str):
        return getattr(self._engine, name)

    def start_turn(self) -> None:
        self._store.roll(self._code, self._token)

    def reroll(self, indices: List[int]) -> None:
        self._store.reroll(self._code, self._token, indices)

    def record_score(self, category: Category, slot_index: int) -> None:
        self._store.score(self._code, self._token, category, slot_index)

    def record_cross(self, category: Category, slot_index: int) -> None:
        self._store.cross(self._code, self._token, category, slot_index)
