"""
Where games are kept between server runs: the storage behind RoomStore.

RoomStore keeps the rooms being played in memory. After every change it hands the
room's data to its repository (outside its own lock), and when someone opens a
room that is not in memory, it asks the repository for it. FileRepository keeps
one JSON file per room in a folder; PostgresRepository keeps one row per room in a
Postgres table (Neon on the live app), and MirroredRepository writes to both. Every
repository has the same methods:

    claim(code)               may a new room use this code? (nothing is saved under it)
    load(code)                the room's saved data, or None
    save(code, version, data) store it, unless a newer version is stored or the room was deleted
    delete(code)              remove the room for good
    prune(cutoff, keep)       delete the rooms last saved before `cutoff`, except those in `keep`
    quarantine(code, reason)  set aside data the store could not use
    wait()                    return once writes under way have finished

Every method may be called from any thread. The data is a dict of JSON types;
the repository does not look inside it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import tempfile
import threading
import time
from pathlib import Path
from typing import Collection, Dict, Optional, Union
from urllib.parse import urlsplit

log = logging.getLogger("abaka")

# Room codes become file names, so only plain codes are ever turned into paths.
_SAFE_CODE = re.compile(r"^[A-Z0-9]{1,16}$")


class FileRepository:
    """One JSON file per room (`<folder>/<CODE>.json`), written atomically."""

    def __init__(self, folder: Union[str, Path]) -> None:
        self.folder = Path(folder)
        # Writes are ordered by this lock, and the newest version written for each code
        # makes sure an older state never replaces a newer file. A deleted room's entry
        # is infinite, so a late write cannot bring it back.
        self._lock = threading.Lock()
        self._versions: Dict[str, float] = {}

    # ----- the repository methods -----
    def claim(self, code: str) -> bool:
        """True if nothing is saved under `code`, so a new room may use it."""
        with self._lock:
            if self._path(code).exists():
                return False
            self._versions.pop(code, None)  # a code deleted earlier may be used again
            return True

    def load(self, code: str) -> Optional[dict]:
        """The saved data, or None. An unreadable file is moved to quarantine/."""
        path = self._path(code)
        try:
            text = path.read_text(encoding="utf-8")
        except FileNotFoundError:
            return None
        except OSError as e:
            log.warning("could not read saved game %s: %s", path.name, e)
            return None
        try:
            data = json.loads(text)
            if not isinstance(data, dict):
                raise ValueError("not a JSON object")
        except ValueError as e:
            self.quarantine(code, e)
            return None
        return data

    def save(self, code: str, version: int, data: dict) -> bool:
        """
        Write the room, unless a newer version of it was written or it was deleted (then
        False). Atomic: a crash never leaves half a file. A failed write raises OSError.
        """
        text = json.dumps(data, separators=(",", ":"))
        with self._lock:
            if version <= self._versions.get(code, -1):
                return False
            self.folder.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=self.folder, prefix=f".{code}-", suffix=".tmp")
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    f.write(text)
                os.replace(tmp, self._path(code))
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise
            self._versions[code] = version
            return True

    def delete(self, code: str) -> None:
        with self._lock:
            self._versions[code] = float("inf")
            try:
                self._path(code).unlink()
            except OSError:
                pass

    def prune(self, cutoff: float, keep: Collection[str] = ()) -> int:
        """Delete rooms whose file was last written before `cutoff` (every change rewrites it)."""
        deleted = 0
        if not self.folder.is_dir():
            return 0
        with self._lock:
            for path in self.folder.glob("*.json"):
                if path.stem in keep:
                    continue
                try:
                    if path.stat().st_mtime < cutoff:
                        path.unlink()
                        deleted += 1
                except OSError:
                    pass
        return deleted

    def quarantine(self, code: str, reason) -> None:
        path = self._path(code)
        log.warning("unreadable saved game %s moved to quarantine/: %s", path.name, reason)
        try:
            (self.folder / "quarantine").mkdir(exist_ok=True)
            os.replace(path, self.folder / "quarantine" / path.name)
        except OSError:
            pass

    def wait(self) -> None:
        with self._lock:
            pass

    # ----- files only -----
    def remove_leftovers(self) -> None:
        """Temp files of writes a crash interrupted."""
        if not self.folder.is_dir():
            return
        for leftover in self.folder.glob(".*.tmp"):
            try:
                leftover.unlink()
            except OSError:
                pass

    def _path(self, code: str) -> Path:
        if not _SAFE_CODE.match(code):
            raise ValueError(f"not a room code: {code!r}")
        return self.folder / f"{code}.json"


_SAFE_TABLE = re.compile(r"^[a-z_][a-z0-9_]{0,40}$")
RETRY_CONNECT_AFTER = 30  # seconds without connection attempts after one failed


class PostgresRepository:
    """
    One row per room in a Postgres table (Neon on the live app). Needs the psycopg package,
    which is imported only here, so the engine and the file storage work without it.

    The table keeps a deleted room as a row without data, so a late save cannot bring it
    back; claiming the code removes that row. Each save is one statement that writes only
    if the stored version is older, so the version rule holds in the database itself.

    The connection is made on first use and made again if it drops (Neon closes idle
    connections when it suspends). A database that cannot be reached never stops a game:
    save() raises, so the store logs a failed save, and every other method logs a warning
    and answers as if nothing were stored. After a failed connection it is not tried
    again for RETRY_CONNECT_AFTER seconds, so callers (some hold the store's lock) fail
    at once instead of waiting for a timeout each time.
    """

    def __init__(self, url: str, table: str = "abaka_rooms", connect_timeout: int = 5) -> None:
        if not _SAFE_TABLE.match(table):
            raise ValueError(f"not a table name: {table!r}")
        self.url = url
        self.table = table
        self.connect_timeout = connect_timeout
        self._lock = threading.Lock()  # one connection, one statement at a time
        self._conn = None
        self._down_until = 0.0

    def describe(self) -> str:
        """Where the rooms are, without the password: for the log."""
        try:
            host = urlsplit(self.url).hostname or "?"
        except ValueError:
            host = "?"
        return f"Postgres at {host}, table {self.table}"

    # ----- the repository methods -----
    def claim(self, code: str) -> bool:
        t = self.table
        row = self._quietly(None, "claim", (
            f"WITH freed AS (DELETE FROM {t} WHERE code = %s AND deleted RETURNING code) "
            f"SELECT count(*) FROM {t} WHERE code = %s AND NOT deleted"), (code, code))
        # Unreachable: a new code is almost surely free (32^5 codes), and refusing every code would hang.
        return row is None or row[0] == 0

    def load(self, code: str) -> Optional[dict]:
        row = self._quietly(None, "load", f"SELECT data FROM {self.table} WHERE code = %s AND NOT deleted", (code,))
        if row is None:
            return None
        if not isinstance(row[0], dict):
            self.quarantine(code, "not a JSON object")
            return None
        return row[0]

    def save(self, code: str, version: int, data: dict) -> bool:
        """Write the room unless a newer version is stored or it was deleted. Raises if unreachable."""
        from psycopg.types.json import Jsonb
        t = self.table
        written = self._run(
            f"INSERT INTO {t} (code, version, data, deleted, saved_at) VALUES (%s, %s, %s, false, now()) "
            f"ON CONFLICT (code) DO UPDATE SET version = EXCLUDED.version, data = EXCLUDED.data, saved_at = now() "
            f"WHERE {t}.version < EXCLUDED.version AND NOT {t}.deleted",
            (code, int(version), Jsonb(data)), fetch=False)
        return written == 1

    def delete(self, code: str) -> None:
        self._quietly(None, "delete", (
            f"INSERT INTO {self.table} (code, version, data, deleted) VALUES (%s, 0, NULL, true) "
            f"ON CONFLICT (code) DO UPDATE SET data = NULL, deleted = true, saved_at = now()"), (code,), fetch=False)

    def prune(self, cutoff: float, keep: Collection[str] = ()) -> int:
        """Delete rooms (and deleted-room rows) last saved before `cutoff`, except those in `keep`."""
        n = self._quietly(0, "prune", (
            f"DELETE FROM {self.table} WHERE saved_at < to_timestamp(%s) AND NOT (code = ANY(%s))"),
            (float(cutoff), list(keep)), fetch=False)
        return n or 0

    def quarantine(self, code: str, reason) -> None:
        log.warning("unusable saved game %s moved to %s_quarantine: %s", code, self.table, reason)
        t = self.table
        self._quietly(None, "quarantine", (
            f"WITH moved AS (DELETE FROM {t} WHERE code = %s AND NOT deleted RETURNING code, data) "
            f"INSERT INTO {t}_quarantine (code, data, reason) SELECT code, data::text, %s FROM moved"),
            (code, str(reason)), fetch=False)

    def wait(self) -> None:
        with self._lock:
            pass

    # ----- Postgres only -----
    def stored_versions(self) -> Dict[str, int]:
        """The stored version of every room (for the import of saved files)."""
        with self._lock:
            return dict(self._execute(f"SELECT code, version FROM {self.table} WHERE NOT deleted", (), "all"))

    def close(self) -> None:
        with self._lock:
            self._disconnect()

    def _quietly(self, default, what: str, sql: str, params, fetch=True):
        try:
            return self._run(sql, params, fetch)
        except Exception as e:  # noqa: BLE001 - storage must never break a game
            log.warning("database %s failed: %s", what, _one_line(e))
            return default

    def _run(self, sql: str, params, fetch=True):
        """One statement: its first row (fetch=True) or the number of rows it changed."""
        with self._lock:
            return self._execute(sql, params, "one" if fetch else None)

    def _execute(self, sql: str, params, fetch):
        """Call with self._lock held. Tries once more on a new connection if the old one dropped."""
        import psycopg
        for attempt in (1, 2):
            conn = self._connect()
            try:
                with conn.cursor() as cur:
                    cur.execute(sql, params)
                    if fetch == "one":
                        return cur.fetchone()
                    if fetch == "all":
                        return cur.fetchall()
                    return cur.rowcount
            except (psycopg.OperationalError, psycopg.InterfaceError):
                # Every statement here may run twice: a save that did arrive is refused the
                # second time (same version), and the others repeat harmlessly.
                self._disconnect()
                if attempt == 2:
                    raise

    def _connect(self):
        if self._conn is not None and not self._conn.closed:
            return self._conn
        import psycopg
        if time.monotonic() < self._down_until:
            raise psycopg.OperationalError("the database was unreachable a moment ago")
        try:
            # prepare_threshold=None: no server-side prepared statements, which a connection
            # pooler (Neon's "-pooler" address) may not keep between statements.
            conn = psycopg.connect(self.url, autocommit=True, connect_timeout=self.connect_timeout,
                                   prepare_threshold=None)
        except Exception:
            self._down_until = time.monotonic() + RETRY_CONNECT_AFTER
            raise
        t = self.table
        for sql in (
            f"CREATE TABLE IF NOT EXISTS {t} (code text PRIMARY KEY, version bigint NOT NULL, data jsonb, "
            f"deleted boolean NOT NULL DEFAULT false, saved_at timestamptz NOT NULL DEFAULT now())",
            f"CREATE INDEX IF NOT EXISTS {t}_saved_at ON {t} (saved_at)",
            f"CREATE TABLE IF NOT EXISTS {t}_quarantine (code text NOT NULL, data text, reason text, "
            f"at timestamptz NOT NULL DEFAULT now())",
        ):
            conn.execute(sql)
        self._conn = conn
        return conn

    def _disconnect(self) -> None:
        conn, self._conn = self._conn, None
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass


class MirroredRepository:
    """
    A database with a copy in files (the live app while the database is new): every save
    goes to both, and a load takes whichever holds the newer version. So a game saved
    only in files (before the database, or while it was unreachable) still loads, and
    its next save puts it in the database too.
    """

    def __init__(self, primary, mirror: FileRepository) -> None:
        self.primary = primary
        self.mirror = mirror
        self.folder = mirror.folder

    def describe(self) -> str:
        describe = getattr(self.primary, "describe", None)
        return f"{describe() if describe else 'the database'}, with a copy in {self.folder}"

    def claim(self, code: str) -> bool:
        return self.primary.claim(code) and self.mirror.claim(code)

    def load(self, code: str) -> Optional[dict]:
        stored = self.primary.load(code)
        copy = self.mirror.load(code)
        if copy is not None and (stored is None or _version_of(copy) > _version_of(stored)):
            return copy
        return stored

    def save(self, code: str, version: int, data: dict) -> bool:
        try:
            self.mirror.save(code, version, data)
        except OSError as e:
            log.warning("could not save the file copy of game %s: %s", code, e)
        return self.primary.save(code, version, data)

    def delete(self, code: str) -> None:
        self.primary.delete(code)
        self.mirror.delete(code)

    def prune(self, cutoff: float, keep: Collection[str] = ()) -> int:
        self.mirror.prune(cutoff, keep)
        return self.primary.prune(cutoff, keep)

    def quarantine(self, code: str, reason) -> None:
        self.primary.quarantine(code, reason)
        self.mirror.quarantine(code, reason)

    def wait(self) -> None:
        self.mirror.wait()
        self.primary.wait()

    def close(self) -> None:
        close = getattr(self.primary, "close", None)
        if close is not None:
            close()

    def remove_leftovers(self) -> None:
        self.mirror.remove_leftovers()

    def import_files(self) -> int:
        """
        Copy the saved files the database does not hold yet (or holds an older version of)
        into it. Run once when the store starts; the version rule keeps it from undoing a
        move saved meanwhile. Returns the number of games copied.
        """
        try:
            stored = self.primary.stored_versions()
        except Exception as e:  # noqa: BLE001
            log.warning("could not import the saved files into the database: %s", _one_line(e))
            return 0
        copied = 0
        if not self.folder.is_dir():
            return 0
        for path in sorted(self.folder.glob("*.json")):
            if not _SAFE_CODE.match(path.stem):
                continue
            data = self.mirror.load(path.stem)
            if data is None or _version_of(data) <= stored.get(path.stem, -1):
                continue
            try:
                if self.primary.save(path.stem, _version_of(data), data):
                    copied += 1
            except Exception as e:  # noqa: BLE001
                log.warning("could not import game %s into the database: %s", path.stem, _one_line(e))
                break
        if copied:
            log.info("imported %d saved games from %s into the database", copied, self.folder)
        return copied


def _version_of(data: dict) -> int:
    try:
        return int(data.get("version", -1))
    except (TypeError, ValueError):
        return -1


def _one_line(e: Exception) -> str:
    """An error for the log: its first line (never a connection URL; psycopg leaves the password out)."""
    text = str(e).strip().splitlines()
    return f"{type(e).__name__}: {text[0] if text else ''}"
