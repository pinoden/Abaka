"""
Keep the game's own modules in step with the files on disk.

Streamlit re-reads the main script (abaka_ui.py) on every run, but the modules it
imports stay loaded in the server process. Streamlit's file watcher unloads
changed modules only while a browser session is open. So when Streamlit Cloud
pulled a commit while nobody had the app open, the new main script ran with the
old modules (2026-11-16: "Start game" failed with a TypeError on the live app).

abaka_ui calls load_current() at the top of every run: if the .py files of the
game's packages differ from the code that is loaded, those modules are dropped
and imported again from disk.

The files' contents decide, not their times. To save reading them on every run,
load_current() hashes them again only when a file's size or time changed, or
a minute has passed since it last did. Sizes and times themselves are looked at
at most every CHECK_EVERY_SECONDS: listing and checking the files took 0.6 ms, the
largest cost of our own code in a page run, and an update applied two seconds
later is still applied before anyone notices.
"""

import hashlib
import importlib
import pathlib
import sys
import threading
import time

APP_DIR = pathlib.Path(__file__).resolve().parent
PACKAGES = ("abaka", "ui_components")
REHASH_EVERY_SECONDS = 60  # hash the files at least this often, even if sizes and times look the same
CHECK_EVERY_SECONDS = 2.0  # look at sizes and times at most this often
_lock = threading.Lock()
_last_hash = None  # (sizes and times of the files, their fingerprint, when it was taken)
_last_check = None  # (when sizes and times were last looked at, the fingerprint then)


def _files() -> list:
    return [path for package in PACKAGES for path in sorted((APP_DIR / package).rglob("*.py"))]


def fingerprint() -> str:
    """Changes whenever any .py file of the game's packages changes."""
    return _hash(_files())


def _hash(files: list) -> str:
    digest = hashlib.sha1()
    for path in files:
        digest.update(path.relative_to(APP_DIR).as_posix().encode() + b"\0")
        try:
            digest.update(path.read_bytes())
        except FileNotFoundError:  # deleted meanwhile (a checkout under way): the next run sees it
            pass
    return digest.hexdigest()


def _sizes_and_times(files: list) -> tuple:
    out = []
    for path in files:
        try:
            stat = path.stat()
            out.append((str(path), stat.st_size, stat.st_mtime_ns))
        except FileNotFoundError:
            out.append((str(path), -1, -1))
    return tuple(out)


def current_fingerprint() -> str:
    """
    fingerprint(), but read the files only when their sizes or times changed, or once a
    minute; and look at sizes and times at most every CHECK_EVERY_SECONDS.
    """
    global _last_hash, _last_check
    now = time.monotonic()
    checked = _last_check
    if checked is not None and 0 <= now - checked[0] < CHECK_EVERY_SECONDS:
        return checked[1]
    files = _files()
    seen = _sizes_and_times(files)
    last = _last_hash
    if last is not None and last[0] == seen and now - last[2] < REHASH_EVERY_SECONDS:
        current = last[1]
    else:
        current = _hash(files)
        _last_hash = (seen, current, now)
    _last_check = (now, current)
    return current


def load_current() -> bool:
    """Reload the game's modules if their files changed since they were loaded. True if it reloaded."""
    current = current_fingerprint()
    with _lock:
        loaded = sys.modules.get(PACKAGES[0])
        if loaded is not None and getattr(loaded, "code_fingerprint", None) == current:
            return False
        stale = loaded is not None
        for name in [n for n in sys.modules if n.split(".")[0] in PACKAGES]:
            del sys.modules[name]
        importlib.invalidate_caches()
        importlib.import_module(PACKAGES[0]).code_fingerprint = current
        return stale


def mark_current() -> None:
    """Record that the loaded modules match the files on disk.

    For tests that import and patch the game's modules before running the app:
    without this, the app's first run would load fresh copies and skip the patches.
    """
    importlib.import_module(PACKAGES[0]).code_fingerprint = fingerprint()
