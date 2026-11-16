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
"""

import hashlib
import importlib
import pathlib
import sys
import threading

APP_DIR = pathlib.Path(__file__).resolve().parent
PACKAGES = ("abaka", "ui_components")
_lock = threading.Lock()


def fingerprint() -> str:
    """Changes whenever any .py file of the game's packages changes."""
    digest = hashlib.sha1()
    for package in PACKAGES:
        for path in sorted((APP_DIR / package).rglob("*.py")):
            digest.update(path.relative_to(APP_DIR).as_posix().encode() + b"\0")
            digest.update(path.read_bytes())
    return digest.hexdigest()


def load_current() -> bool:
    """Reload the game's modules if their files changed since they were loaded. True if it reloaded."""
    current = fingerprint()
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
