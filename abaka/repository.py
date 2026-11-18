"""
Where games are kept between server runs: the storage behind RoomStore.

RoomStore keeps the rooms being played in memory. After every change it hands the
room's data to its repository (outside its own lock), and when someone opens a
room that is not in memory, it asks the repository for it. FileRepository keeps
one JSON file per room in a folder. A database (Stage 2 of the plan in ProjectLibrary.md)
would be another class with the same methods:

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
from pathlib import Path
from typing import Collection, Dict, Optional, Union

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
