"""
Clubs: a leaderboard for a group of friends. No Streamlit imports.

A club has a code (6 characters, shared like a game code) and a table of its
players. A game started from a club's page carries the club's code; when it ends,
RoomStore reports the result (RoomStore(on_game_over=...)) and ClubStore.record
adds it to the club:

- the players are matched by name, ignoring capital letters and spaces, so "Ann"
  and " ann " are one player;
- each player's rating moves by the Elo rule, extended to 3-5 players by treating
  the game as head-to-head results between every pair of players (the higher
  score beats the lower one; equal scores draw). A player's change is the sum
  over their pairs, scaled by 1/(players - 1), so a game is worth the same
  however many play it. Everyone starts at START_RATING;
- the club keeps each player's games, wins, total and best score, and the most
  recent games.

A club is saved through a repository (abaka/repository.py: files, Postgres or
both), like rooms but in its own folder or table. A result is recorded once: its
id ("ROOM:game") is remembered.
"""

import logging
import secrets
import threading
import time
import unicodedata
from typing import Dict, List, Optional

from .rooms import CODE_ALPHABET, MAX_NAME_LENGTH, normalize_code

log = logging.getLogger("abaka")

CLUB_CODE_LENGTH = 6            # room codes have 5, so the two never look alike
MAX_CLUB_NAME_LENGTH = 30
START_RATING = 1000.0
K_FACTOR = 32.0                 # the most a rating can move in one two-player game
GAMES_KEPT = 200                # recent games a club shows and remembers
CLUB_TTL_SECONDS = 365 * 24 * 60 * 60   # clubs nobody played in for a year are deleted
CLUBS_IN_MEMORY = 500


class ClubError(ValueError):
    """A request about clubs that cannot be met; the text is shown to the player."""


def member_key(name: str) -> str:
    """Who a name is in a club: the same name, whatever its capitals and spacing."""
    return " ".join(name.split()).casefold()


def rating_changes(ratings: List[float], scores: List[int], k: float = K_FACTOR) -> List[float]:
    """
    How each player's rating moves after one game (Elo, every pair of players a
    head-to-head match). The changes add up to zero.
    """
    n = len(ratings)
    changes = [0.0] * n
    if n < 2:
        return changes
    weight = k / (n - 1)
    for i in range(n):
        for j in range(i + 1, n):
            actual = 1.0 if scores[i] > scores[j] else 0.5 if scores[i] == scores[j] else 0.0
            expected = 1.0 / (1.0 + 10 ** ((ratings[j] - ratings[i]) / 400.0))
            changes[i] += weight * (actual - expected)
            changes[j] -= weight * (actual - expected)
    return changes


def is_club_code(code: str) -> bool:
    return len(code) == CLUB_CODE_LENGTH and all(c in CODE_ALPHABET for c in code)


class ClubStore:
    """Every club, kept in memory once opened and saved after every change. Thread-safe."""

    def __init__(self, repository=None) -> None:
        self._lock = threading.Lock()
        self._clubs: Dict[str, dict] = {}
        self._repository = repository
        if repository is not None:
            repository.prune(time.time() - CLUB_TTL_SECONDS)

    # ----- the club page -----
    def create(self, name: str) -> str:
        visible = "".join(ch for ch in (name or "") if unicodedata.category(ch) not in ("Cc", "Cf"))
        name = " ".join(visible.split())[:MAX_CLUB_NAME_LENGTH]  # as rooms.clean_name, but longer
        if not name:
            raise ClubError("Give the club a name.")
        now = time.time()
        with self._lock:
            code = self._new_code()
            club = {"code": code, "name": name, "version": 1, "created_at": now, "updated_at": now,
                    "members": {}, "games": []}
            self._clubs[code] = club
            self._save(club)
        return code

    def get(self, code: str) -> Optional[dict]:
        """The club as it is now (a copy: changing it changes nothing), or None."""
        code = normalize_code(code)
        with self._lock:
            club = self._club(code)
            return _copy(club) if club is not None else None

    def exists(self, code: str) -> bool:
        return self.name(code) is not None

    def name(self, code: str) -> Optional[str]:
        """The club's name, or None if there is no such club (without copying the club)."""
        with self._lock:
            club = self._club(normalize_code(code))
            return club["name"] if club is not None else None

    def member_names(self, code: str) -> List[str]:
        """The names of the club's players (as last typed), the most recently played first."""
        with self._lock:
            club = self._club(normalize_code(code))
            if club is None:
                return []
            members = sorted(club["members"].values(), key=lambda m: (-m["last_played"], m["name"].casefold()))
            return [m["name"] for m in members]

    # ----- results -----
    def record(self, result: dict) -> bool:
        """
        Add a finished game (RoomStore's on_game_over result) to its club's table. False if
        the game is not a club game, the club is gone, or the result was recorded before.
        """
        code = result.get("club")
        if not code:
            return False
        game_id = f"{result['room']}:{result['game']}"
        names, scores = list(result["names"]), [int(s) for s in result["scores"]]
        with self._lock:
            club = self._club(code)
            if club is None or any(g["id"] == game_id for g in club["games"]):
                return False
            members = club["members"]
            keys = [member_key(n) for n in names]
            for key, name in zip(keys, names):
                members.setdefault(key, {"name": name, "rating": START_RATING, "games": 0, "wins": 0,
                                         "points": 0, "best": 0, "change": 0.0, "last_played": 0.0})
            changes = rating_changes([members[k]["rating"] for k in keys], scores)
            best = max(scores)
            winners = [i for i, s in enumerate(scores) if s == best]
            at = float(result.get("at") or time.time())
            for i, key in enumerate(keys):
                m = members[key]
                m["name"] = names[i]  # the latest spelling
                m["rating"] += changes[i]
                m["change"] = changes[i]
                m["games"] += 1
                m["wins"] += 1 if winners == [i] else 0
                m["points"] += scores[i]
                m["best"] = scores[i] if m["games"] == 1 else max(m["best"], scores[i])  # scores can be negative
                m["last_played"] = at
            club["games"] = ([{"id": game_id, "at": at,
                               "players": [{"name": names[i], "score": scores[i], "change": changes[i]}
                                           for i in range(len(names))]}]
                             + club["games"])[:GAMES_KEPT]
            club["version"] += 1
            club["updated_at"] = at
            self._save(club)
        return True

    def game(self, code: str, room: str, game: int) -> Optional[dict]:
        """
        One recorded game of a club, for the results screen: its players with their score,
        rating change and rating now, and the club's name. None if it is not recorded (yet).
        Copies only that game (copying a whole club with its 200 games took 0.3 ms).
        """
        game_id = f"{room}:{game}"
        with self._lock:
            club = self._club(normalize_code(code or ""))
            found = next((g for g in club["games"] if g["id"] == game_id), None) if club is not None else None
            if found is None:
                return None
            members = club["members"]
            players = [dict(p, rating=members[member_key(p["name"])]["rating"]) for p in found["players"]]
            return {**found, "players": players, "club": club["name"]}

    # ----- internals (call with self._lock held) -----
    def _club(self, code: str) -> Optional[dict]:
        if not is_club_code(code):
            return None
        club = self._clubs.get(code)
        if club is None and self._repository is not None:
            data = self._repository.load(code)
            if data is not None:
                if not _valid(data, code):
                    self._repository.quarantine(code, "not a club")
                    return None
                if len(self._clubs) >= CLUBS_IN_MEMORY:
                    self._clubs.pop(next(iter(self._clubs)))  # the one opened longest ago
                club = self._clubs[code] = data
        return club

    def _new_code(self) -> str:
        while True:
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(CLUB_CODE_LENGTH))
            if code not in self._clubs and (self._repository is None or self._repository.claim(code)):
                return code

    def _save(self, club: dict) -> None:
        if self._repository is None:
            return
        try:
            # A copy: the repository may write it later (in the background), while the club changes.
            self._repository.save(club["code"], club["version"], _copy(club))
        except Exception as e:  # noqa: BLE001 - the club stays in memory; the next save retries
            log.warning("could not save club %s: %s", club["code"], e)


def _valid(data: dict, code: str) -> bool:
    try:
        return (data["code"] == code and isinstance(data["name"], str) and isinstance(data["members"], dict)
                and isinstance(data["games"], list) and int(data["version"]) >= 1)
    except (KeyError, TypeError, ValueError):
        return False


def _copy(club: dict) -> dict:
    return {**club, "members": {k: dict(m) for k, m in club["members"].items()},
            "games": [{**g, "players": [dict(p) for p in g["players"]]} for g in club["games"]]}


__all__ = ["ClubStore", "ClubError", "member_key", "rating_changes", "is_club_code",
           "CLUB_CODE_LENGTH", "MAX_CLUB_NAME_LENGTH", "MAX_NAME_LENGTH", "START_RATING"]
