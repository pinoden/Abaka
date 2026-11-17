"""
Game rooms: every game the app hosts, online (2 to 5 players, each on their own
device) or on one device (a "local" room).

One Streamlit server process serves every browser session, so a single
RoomStore held in that process is the source of truth for all games. Each
browser only sends actions ("roll", "reroll", "score", "cross") and renders a
copy of the shared state; nothing game-related lives in a browser session.

With a save directory, every room is written to its own JSON file after each
change and read back when a store is created, so games survive reloads,
dropped sessions, code updates and server restarts (as long as the disk does).

This module has no Streamlit dependency so it can be unit-tested directly.
"""

from __future__ import annotations

import json
import os
import re
import secrets
import sys
import tempfile
import threading
import time
import unicodedata
from pathlib import Path
from typing import Dict, List, Optional, Union

from .engine import GameEngine
from .models import Category
from .saving import engine_from_data, engine_to_data

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
_CODE_PATTERN = re.compile("^[%s]{%d}$" % (CODE_ALPHABET, CODE_LENGTH))


class RoomError(ValueError):
    """A request the room refused; the message is safe to show to the player."""


def clean_name(name: str, fallback: str) -> str:
    """Spaces collapsed, at most MAX_NAME_LENGTH characters, no control or invisible format
    characters (such as right-to-left overrides); `fallback` if nothing is left."""
    visible = "".join(ch for ch in (name or "") if unicodedata.category(ch) not in ("Cc", "Cf"))
    name = " ".join(visible.split())[:MAX_NAME_LENGTH]
    return name or fallback


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
                 version: int, games_played: int, capacity: int, local: bool = False) -> None:
        self.code = code
        self.names = names            # seated players, in seat order (seat 0 created the game)
        self.engine = engine
        self.version = version
        self.games_played = games_played
        self.capacity = capacity      # how many players the game is for
        self.local = local            # a same-device game: one browser plays every seat

    @property
    def started(self) -> bool:
        return self.engine is not None


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
        self.updated_at = time.time()
        self.last_seen = self.updated_at  # when a page last looked at it (not saved)

    def touch(self) -> None:
        self.version += 1
        self.updated_at = time.time()

    def to_data(self) -> dict:
        return {
            "code": self.code, "capacity": self.capacity, "local": self.local,
            "names": list(self.names), "tokens": list(self.tokens),
            "engine": engine_to_data(self.engine) if self.engine is not None else None,
            "version": self.version, "games_played": self.games_played, "updated_at": self.updated_at,
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
        room.last_seen = time.time()
        return room


class RoomStore:
    """
    Thread-safe registry of rooms. Streamlit runs each session in its own thread.

    One lock guards the rooms. Engines are copy-on-write: a move works on a clone and
    installs it, and an installed engine is never changed again, so view() hands it
    out without copying (readers must not change it either). Files are written after
    the lock is released (_write), so a slow disk never holds up other games.
    """

    def __init__(self, starting_throw: bool = True, save_dir: Union[str, Path, None] = None) -> None:
        """
        starting_throw: each game opens with the starting throw (lowest total goes first).
        save_dir: keep every room in a JSON file there. Saved rooms are loaded when someone
            opens them, and rooms nobody looks at leave memory (their files stay).
        """
        self._lock = threading.Lock()
        self._rooms: Dict[str, _Room] = {}
        self._retired = False
        self.starting_throw = starting_throw
        self.save_dir = Path(save_dir) if save_dir is not None else None
        # Writes happen outside self._lock; this lock orders them, and the versions
        # make sure an older state of a room never replaces a newer file.
        self._save_lock = threading.Lock()
        self._saved_versions: Dict[str, float] = {}
        self._last_sweep = time.time()
        self._last_disk_sweep = 0.0
        if self.save_dir is not None:
            self._clean_save_dir()

    def retire(self) -> None:
        """
        This store's code has been replaced by an update (see abaka_ui.get_store): stop
        serving and free the rooms. The new store reads them back from disk, so writes
        already under way finish first.
        """
        with self._lock:
            self._retired = True
            self._rooms.clear()
        with self._save_lock:
            pass

    # ----- lobby -----
    def create(self, host_name: str, players: int = 2) -> "tuple[str, str]":
        """Open a new room for `players` players. Returns (room_code, seat_token) for the host."""
        if not MIN_PLAYERS <= int(players) <= MAX_PLAYERS:
            raise RoomError(f"A game is for {MIN_PLAYERS} to {MAX_PLAYERS} players.")
        with self._lock:
            self._make_room_for_one_more()
            code = self._new_code()
            room = _Room(code, int(players))
            self._rooms[code] = room
            token = self._seat(room, clean_name(host_name, "Player 1"))
            pending = self._snapshot(room)
        self._write(pending)
        return code, token

    def create_local(self, names: List[str]) -> "tuple[str, str]":
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
            token = secrets.token_urlsafe(16)
            room.names = [clean_name(n, f"Player {i}") for i, n in enumerate(names, 1)]
            room.tokens = [token] * len(names)  # one browser holds every seat
            room.engine = _new_engine(room, self.starting_throw)
            self._rooms[code] = room
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
        """Take a free seat in a room. The game starts once every seat is taken."""
        with self._lock:
            room = self._get(code)
            if room.engine is not None or len(room.names) >= room.capacity:
                raise RoomError("This game is already full.")
            seat_no = len(room.names) + 1
            name = _distinct(clean_name(name, f"Player {seat_no}"), room.names)
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
            room = self._room(code)
            return room.version if room else -1

    def view(self, code: str) -> RoomView:
        """The room as it is now. The engine is shared, not copied: do not change it."""
        with self._lock:
            room = self._get(code)
            return RoomView(room.code, list(room.names), room.engine,
                            room.version, room.games_played, room.capacity, room.local)

    # ----- playing -----
    def throw_for_start(self, code: str, token: str) -> None:
        """This player's throw in the starting throw that decides who goes first."""
        def action(engine: GameEngine) -> None:
            if not engine.choosing_first_player:
                raise RoomError("The first player has already been decided.")
            engine.throw_for_start()
        self._act(code, token, action)

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
            room.engine = _new_engine(room, self.starting_throw)
            room.touch()
            pending = self._snapshot(room)
        self._write(pending)

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
            if not room.local and room.tokens.index(token) != room.engine.current:
                raise RoomError("It is not your turn.")
            # Work on a copy so a rejected move can never leave the room half-updated, and so the
            # engine that views have handed out never changes (copy-on-write).
            engine = room.engine.clone()
            action(engine)
            room.engine = engine
            room.touch()
            pending = self._snapshot(room)
        self._write(pending)

    def _get(self, code: str) -> _Room:
        if self._retired:
            raise RoomError("The app was just updated. Please try again.")
        room = self._room(code)
        if room is None:
            raise RoomError("Game not found. Check the code, or ask for a new invite.")
        return room

    def _room(self, code: str) -> Optional[_Room]:
        """
        The room with this code: from memory, or loaded from its file if it left memory.
        None if there is none. Marks it as just seen, so rooms people look at stay in memory.
        Call with self._lock held.
        """
        if self._retired:
            return None
        code = normalize_code(code)
        room = self._rooms.get(code)
        if room is None and self.save_dir is not None and is_valid_code(code):
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
            if code not in self._rooms and not (self.save_dir is not None and self._path(code).exists()):
                with self._save_lock:
                    self._saved_versions.pop(code, None)  # a code freed earlier may be used again
                return code

    def _make_room_for_one_more(self) -> None:
        """Before a new room: let unused rooms go; without a save folder, refuse past the cap."""
        self._sweep()
        if self.save_dir is None and len(self._rooms) >= MAX_ROOMS_IN_MEMORY:
            raise RoomError("The server is busy right now. Please try again later.")

    def _sweep(self, force: bool = False) -> None:
        """
        At most once a minute: drop expired rooms (from disk too); with a save folder, let
        rooms nobody has looked at for a while leave memory (their files stay), and keep at
        most MAX_ROOMS_IN_MEMORY. Once an hour, delete expired files of rooms not in memory.
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
            if self.save_dir is None:
                continue
            idle = now - room.last_seen
            finished = room.engine is not None and room.engine.is_game_over()
            if idle > IDLE_IN_MEMORY_SECONDS or (finished and idle > FINISHED_IN_MEMORY_SECONDS):
                del self._rooms[code]  # still on disk; loaded again when someone opens it
        if self.save_dir is not None and len(self._rooms) > MAX_ROOMS_IN_MEMORY:
            # Not the rooms seen in the last minute: their latest write may still be under way.
            quiet = sorted((r.last_seen, c) for c, r in self._rooms.items() if now - r.last_seen > 60)
            for _, code in quiet[:len(self._rooms) - MAX_ROOMS_IN_MEMORY]:
                del self._rooms[code]
        if self.save_dir is not None and (force or now - self._last_disk_sweep > DISK_SWEEP_EVERY_SECONDS):
            self._last_disk_sweep = now
            self._delete_expired_files(cutoff)

    # ----- saving (one JSON file per room) -----
    def _path(self, code: str) -> Path:
        return self.save_dir / f"{code}.json"

    def _snapshot(self, room: _Room):
        """What to write for this room: taken under the lock, written after it by _write."""
        if self.save_dir is None:
            return None
        return room.code, room.version, room.to_data()

    def _write(self, pending) -> None:
        """
        Write a room's file (call it without holding self._lock). It never replaces a newer
        version, and a failed write is reported but never stops the game.
        """
        if pending is None:
            return
        code, version, data = pending
        text = json.dumps(data, separators=(",", ":"))
        with self._save_lock:
            if version <= self._saved_versions.get(code, -1):
                return  # a newer state of this room is already on disk (or it was closed)
            tmp = None
            try:
                self.save_dir.mkdir(parents=True, exist_ok=True)
                fd, tmp = tempfile.mkstemp(dir=self.save_dir, prefix=f".{code}-", suffix=".tmp")
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(text)
                os.replace(tmp, self._path(code))  # atomic: a crash never leaves half a file
                self._saved_versions[code] = version
            except Exception as e:  # noqa: BLE001 - saving must never break a move
                print(f"abaka: could not save game {code}: {e}", file=sys.stderr)
                if tmp is not None:
                    try:
                        os.unlink(tmp)
                    except OSError:
                        pass

    def _unsave(self, code: str) -> None:
        if self.save_dir is None:
            return
        with self._save_lock:
            self._saved_versions[code] = float("inf")  # a late write must not bring it back
            try:
                self._path(code).unlink()
            except OSError:
                pass

    def _clean_save_dir(self) -> None:
        """At start: remove temp files left by a crash and files of rooms that expired."""
        if not self.save_dir.is_dir():
            return
        for leftover in self.save_dir.glob(".*.tmp"):
            try:
                leftover.unlink()
            except OSError:
                pass
        self._delete_expired_files(time.time() - ROOM_TTL_SECONDS)

    def _delete_expired_files(self, cutoff: float) -> None:
        """Delete saved rooms not written since `cutoff` (every change rewrites a room's file)."""
        with self._save_lock:
            for path in self.save_dir.glob("*.json"):
                if path.stem in self._rooms:
                    continue
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                except OSError:
                    pass

    def _load_room(self, code: str) -> Optional[_Room]:
        """Read a saved room into memory. Unreadable files are moved to quarantine/."""
        path = self._path(code)
        if not path.exists():
            return None
        try:
            room = _Room.from_data(json.loads(path.read_text(encoding="utf-8")))
        except (OSError, ValueError, KeyError, TypeError, IndexError) as e:
            print(f"abaka: unreadable saved game {path.name} moved to quarantine/: {e}", file=sys.stderr)
            try:
                (self.save_dir / "quarantine").mkdir(exist_ok=True)
                os.replace(path, self.save_dir / "quarantine" / path.name)
            except OSError:
                pass
            return None
        if room.code != code:
            return None
        if room.updated_at < time.time() - ROOM_TTL_SECONDS:
            self._unsave(code)
            return None
        self._rooms[code] = room
        with self._save_lock:
            self._saved_versions[code] = max(self._saved_versions.get(code, -1), room.version)
        return room


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

    def throw_for_start(self) -> None:
        self._store.throw_for_start(self._code, self._token)

    def start_turn(self) -> None:
        self._store.roll(self._code, self._token)

    def reroll(self, indices: List[int]) -> None:
        self._store.reroll(self._code, self._token, indices)

    def record_score(self, category: Category, slot_index: int) -> None:
        self._store.score(self._code, self._token, category, slot_index)

    def record_cross(self, category: Category, slot_index: int) -> None:
        self._store.cross(self._code, self._token, category, slot_index)
