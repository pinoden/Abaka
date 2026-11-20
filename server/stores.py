"""
The games of one server process: its RoomStore and ClubStore, and where they are saved.

Every page and every app request of a process must use the same two stores, so that
a game started in an app can be joined from the web. Where they live depends on how
the server runs:

- Streamlit Community Cloud runs abaka_ui.py alone. Its pages keep the stores in
  abaka_ui's registry (an st.cache_resource; see get_store there), as before the API.
- abaka_server.py serves the pages and the API for apps together (Backlog item 25).
  It calls serve_api() first, and from then on the pages and the API's routes both
  use get_store() and get_clubs() here.

The registry here lives in a module made at run time, with no file (_registry), so
neither Streamlit's file watcher nor code_version ever unloads it. Like the
st.cache_resource registry, it survives code updates. Unlike it, the API's routes
reach it outside any page's script run.
"""

import logging
import os
import sys
import tempfile
import threading
import types
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st

from abaka import clubs as club_module
from abaka import rooms
from abaka.repository import FileRepository, MirroredRepository, PostgresRepository

STATS_EVERY_SECONDS = 60  # the store logs a stats line this often while pages are open
_REGISTRY = "_abaka_process"  # the name of the run-time module that holds the registry

log = logging.getLogger("abaka")


def log_to_stderr() -> None:
    """Send the game's log ("abaka": stats line, failed saves) to stderr, which Streamlit
    Cloud shows under Manage app. Once per process: the pages call it on every run."""
    logger = logging.getLogger("abaka")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


def save_dir() -> Optional[Path]:
    """
    Where games are saved: $ABAKA_SAVE_DIR if set (empty: do not save), else
    ~/.abaka/games, or a temporary folder if the home folder is not writable.
    """
    configured = os.environ.get("ABAKA_SAVE_DIR")
    if configured is not None:
        return Path(configured) if configured.strip() else None
    for folder in (Path.home() / ".abaka" / "games", Path(tempfile.gettempdir()) / "abaka-games"):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            return folder
        except OSError:
            continue
    return None


def database_url() -> Optional[str]:
    """
    The Postgres URL (Neon on the live app): $ABAKA_DATABASE_URL if set (empty: no
    database), else the ABAKA_DATABASE_URL or DATABASE_URL secret (Streamlit Cloud: the
    app's Settings, then Secrets; DATABASE_URL is the name Neon gives it). None: games are
    saved in files only.

    A DATABASE_URL environment variable is not used: it names the production database in
    Neon's .env.local, and tests and local runs must never reach it unless asked to.
    """
    url = os.environ.get("ABAKA_DATABASE_URL")
    if url is None:
        try:
            url = st.secrets.get("ABAKA_DATABASE_URL") or st.secrets.get("DATABASE_URL")
        except Exception:  # noqa: BLE001 - no secrets file at all
            url = None
    url = str(url or "").strip()
    return url or None


def repository(table: str = "abaka_rooms", subfolder: Optional[str] = None):
    """
    Where a store keeps its data: the database (with a copy in files) if there is one,
    else files. Games use the table abaka_rooms and the save folder; clubs use
    abaka_clubs and its clubs/ subfolder.
    """
    folder = save_dir()
    if folder is not None and subfolder:
        folder = folder / subfolder
    files = FileRepository(folder) if folder is not None else None
    url = database_url()
    if url is None:
        return files
    database = PostgresRepository(url, table=table)
    # The database is written in the background: a move waits for the file, not the network.
    return MirroredRepository(database, files, background=True) if files is not None else database


def make_stores() -> "Tuple[rooms.RoomStore, club_module.ClubStore]":
    """
    A new RoomStore and ClubStore for this process, saving where the settings say. The
    clubs come first, so the store reports finished club games to them.
    """
    log_to_stderr()
    club_repository = repository("abaka_clubs", "clubs")
    clubs = club_module.ClubStore(repository=club_repository)
    games = repository()
    store = rooms.RoomStore(repository=games, report_every=STATS_EVERY_SECONDS, on_game_over=clubs.record)
    where = games.describe() if hasattr(games, "describe") else getattr(games, "folder", None) or "memory only"
    log.info("store started; games are saved in %s", where)
    for saved in (games, club_repository):
        if isinstance(saved, MirroredRepository):
            # Saved in files before the database (or while it was unreachable).
            threading.Thread(target=saved.import_files, name="abaka-import", daemon=True).start()
    return store, clubs


# ----------------------------------------------- the registry of abaka_server.py ----

def _registry() -> dict:
    """This process's registry: whether it serves the API, and its stores (see the module's notes)."""
    holder = sys.modules.get(_REGISTRY)
    if holder is None:
        holder = sys.modules.setdefault(_REGISTRY, types.ModuleType(_REGISTRY))
    registry = getattr(holder, "registry", None)
    if registry is None:
        registry = holder.__dict__.setdefault(
            "registry", {"lock": threading.Lock(), "api": False, "store": None, "clubs": None})
    return registry


def serve_api(on: bool = True) -> None:
    """abaka_server.py: the pages share their stores with the API for apps, through get_store() here."""
    _registry()["api"] = on


def serving_api() -> bool:
    return _registry()["api"]


def get_store() -> "rooms.RoomStore":
    """
    The process's one RoomStore, for the pages and the API alike. After a code update the
    new code retires the old store (its rooms are freed, writes under way finish) and makes
    a new one, which loads the saved games again. Code still running from before the update
    (a page's poll, an open live connection) gets the new store too.
    """
    registry = _registry()
    with registry["lock"]:
        store = registry["store"]
        if store is None or (type(store) is not rooms.RoomStore and _running_current_code()):
            if store is not None:
                store.retire()
            store, registry["clubs"] = make_stores()
            registry["store"] = store
        return store


def get_clubs() -> "club_module.ClubStore":
    """The ClubStore made together with the current RoomStore."""
    get_store()
    return _registry()["clubs"]


def _running_current_code() -> bool:
    """False in this module as loaded before a code update (old code must not replace the new store)."""
    return sys.modules.get("abaka.rooms") is rooms
