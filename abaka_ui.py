"""
Abaka — Streamlit app.

Screens:
  * Home: start a game on this device, create an online game, or join by code.
  * Invite (?room=CODE): join or rejoin an online game.
  * Waiting room: share the invite link until the second player joins.
  * Game: shared by both modes (ui_components/main_ui.py).

Online games live in a shared room inside this server process (abaka/rooms.py);
browsers send moves to it and poll it, so both players see every roll and score
as it happens.
"""

import logging
import os
import socket
import sys
import tempfile
import threading
import time
from html import escape
from pathlib import Path
from typing import Optional
from urllib.parse import urlsplit

import streamlit as st

import code_version

# Before importing the game's modules: make sure they match the files on disk (a
# commit pulled while nobody had the app open would otherwise leave old ones loaded).
code_version.load_current()

from abaka.rooms import (  # noqa: E402
    MAX_PLAYERS, MIN_PLAYERS, RoomEngine, RoomError, RoomStore, normalize_code, within_limit)
from ui_components.actions import forget_action_error  # noqa: E402
from ui_components.i18n import LANGUAGES, error, md, players_count, set_language, t  # noqa: E402
from ui_components.main_ui import (  # noqa: E402
    initialize_session_state, render_game, render_language_switch, render_top_bar, reset_turn_selection)
from ui_components.rules import rules_md  # noqa: E402
from ui_components.style import brand_html, chip, inject_global_css  # noqa: E402

# How often a page checks its room for changes (other players' moves):
POLL_FAST = 1.0    # someone else is acting, or players are joining
POLL_CALM = 3.0    # your own turn (nobody else can move), or the game is over
POLL_IDLE = 10.0   # a same-device game (only a second device could change it)
GAMES_PER_SESSION = 10              # a browser may start this many games...
GAMES_PER_SESSION_WINDOW = 10 * 60  # ...in this many seconds (a guard against scripts)
MY_GAMES_KEPT = 10   # games a browser remembers for "Continue a game"...
MY_GAMES_SHOWN = 4   # ...and how many unfinished ones it shows
STATS_EVERY_SECONDS = 60  # the store logs a stats line this often while pages are open


def _log_to_stderr() -> None:
    """Send the game's log ("abaka": stats line, failed saves) to stderr, which Streamlit
    Cloud shows under Manage app. Once per process: this script runs on every rerun."""
    logger = logging.getLogger("abaka")
    if logger.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)
    logger.propagate = False


_log_to_stderr()


def _save_dir() -> Optional[Path]:
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


@st.cache_resource
def _store_registry() -> dict:
    # Do not edit this function: its source is its cache key. An edit would start a
    # second registry after the next code update and leave the previous store running.
    return {"lock": threading.Lock(), "store": None}


def _running_current_code() -> bool:
    """False in pages still running code from before an update (their once-a-second poll)."""
    rooms_module = sys.modules.get("abaka.rooms")
    return rooms_module is not None and getattr(rooms_module, "RoomStore", None) is RoomStore


def get_store() -> RoomStore:
    """
    The one RoomStore shared by every browser session of this server.

    Streamlit Community Cloud applies a commit by reloading the app's modules, but
    cached objects survive, and a store made by the old code breaks the new code
    (after PR #13, "Create game" failed with a TypeError on the live app). So when
    the new code first asks for the store, the old one is retired (its rooms are
    freed; writes under way finish) and a new one loads the saved games from disk.
    Pages still running the old code get the new store too, so nobody keeps polling
    a store that no longer changes, and old stores never pile up in memory.
    """
    registry = _store_registry()
    with registry["lock"]:
        store = registry["store"]
        if store is None or (type(store) is not RoomStore and _running_current_code()):
            if store is not None:
                store.retire()
            folder = _save_dir()
            store = registry["store"] = RoomStore(save_dir=folder, report_every=STATS_EVERY_SECONDS)
            logging.getLogger("abaka").info("store started; games are saved in %s", folder or "memory only")
        return store


def main():
    st.set_page_config(page_title="Abaka", page_icon="\U0001F3B2", layout="wide",
                       initial_sidebar_state="collapsed")
    inject_global_css()
    initialize_session_state()
    ss = st.session_state
    ss.setdefault("room_code", None)   # room (online or same-device game) this browser is in
    ss.setdefault("seat_token", None)  # proves which seat this browser controls
    ss.setdefault("lobby_notice", None)
    ss.setdefault("lobby_info", None)
    ss.setdefault("my_games", [])      # codes of games this browser played, newest first
    set_language(_pick_language())

    store = get_store()
    invited_code = normalize_code(st.query_params.get("room", ""))

    if ss.room_code:
        try:
            _render_online(store)
        except RoomError as e:
            # The room vanished mid-render (expired, or the server restarted).
            _leave_room(notice=error(str(e)))
            st.rerun()
    elif invited_code:
        _render_invite(store, invited_code)
    else:
        _render_home(store)


def _pick_language() -> str:
    """The page's language: the EN/RU switch (kept in the session and in ?lang=), else the browser's."""
    ss = st.session_state
    asked = st.query_params.get("lang")
    if asked in LANGUAGES:
        ss.lang = asked
    if ss.get("lang") not in LANGUAGES:
        try:
            browser = (st.context.locale or "").lower()
        except Exception:  # older Streamlit, or no browser (tests)
            browser = ""
        ss.lang = "ru" if browser.startswith("ru") else "en"
    return ss.lang


def _language_row(key: str) -> None:
    with st.container(horizontal=True, horizontal_alignment="right", key=f"{key}-row"):
        render_language_switch(key)


# ------------------------------------------------------------------ home ----

def _render_home(store: RoomStore) -> None:
    _language_row("lang-home")
    st.html(f'<div class="ab-hero">{brand_html(56)}'
            f"<p>{t('The dice game of combinations. Play with friends on one screen or online.')}</p></div>")
    _show_lobby_notice()
    _render_my_games(store)

    _, local_col, online_col, _ = st.columns([0.4, 5, 5, 0.4], gap="large")
    with local_col:
        with st.container(border=True, key="card-local"):
            _card_header("\U0001F465", t("Same device"), t("Take turns on this screen."))
            count = _player_count("local_count")
            with st.form("local_game", border=False):
                typed = [st.text_input(t("Player {i}", i=i), placeholder=t("Name"), max_chars=20, key=f"local_p{i}")
                         for i in range(1, count + 1)]
                if st.form_submit_button(t("Start game"), type="primary", icon=":material/play_arrow:",
                                         use_container_width=True):
                    # Saved like an online game: it gets a code and can be continued from its link.
                    names = [name.strip() or t("Player {i}", i=i) for i, name in enumerate(typed, 1)]
                    _start_game(lambda: store.create_local(names))

    with online_col:
        with st.container(border=True, key="card-online"):
            _card_header("\U0001F310", t("Online"), t("Each player on their own device. Invite friends with a link."))
            players = _player_count("online_count")
            with st.form("create_game", border=False):
                name = st.text_input(t("Your name"), placeholder=t("Name"), max_chars=20, key="create_name")
                if st.form_submit_button(t("Create game"), type="primary", icon=":material/add_link:",
                                         use_container_width=True):
                    _start_game(lambda: store.create(name.strip() or t("Player {i}", i=1), players))
            st.html(f'<div class="ab-or">{t("or open a game by its code")}</div>')
            with st.form("find_game", border=False):
                typed = st.text_input(t("Game code"), placeholder=t("e.g. Q47CH"), max_chars=8, key="find_code",
                                      help=t("Join a friend's game, or continue a saved game."))
                if st.form_submit_button(t("Open game"), icon=":material/login:", use_container_width=True):
                    code = normalize_code(typed)
                    if store.exists(code):
                        st.query_params["room"] = code
                        st.rerun()
                    else:
                        st.error(t("No game with that code. Check it and try again."))

    _, mid, _ = st.columns([0.4, 10, 0.4])
    with mid:
        with st.expander(t("How to play"), icon=":material/help:"):
            st.markdown(rules_md())


def _start_game(create) -> None:
    """Create a game (online or same-device) and go to it, within the per-browser limit."""
    if not _may_start_a_game():
        st.error(t("You started a lot of games just now. Please wait a few minutes."))
        return
    try:
        code, token = create()
    except RoomError as e:
        st.error(error(str(e)))
        return
    _enter_room(code, token)
    st.rerun()


def _may_start_a_game() -> bool:
    ss = st.session_state
    allowed, ss.games_started = within_limit(ss.get("games_started", []), time.time(),
                                             GAMES_PER_SESSION, GAMES_PER_SESSION_WINDOW)
    return allowed


def _player_count(key: str) -> int:
    """Pick 2-5 players. Clicking the chosen option again would clear it, so keep the last choice."""
    ss = st.session_state
    last_key = key + "_last"

    def keep() -> None:
        if ss.get(key) is None:
            ss[key] = ss.get(last_key, MIN_PLAYERS)
        ss[last_key] = ss[key]

    value = st.segmented_control(t("Players"), list(range(MIN_PLAYERS, MAX_PLAYERS + 1)), default=MIN_PLAYERS,
                                 key=key, on_change=keep)
    return value or ss.get(last_key, MIN_PLAYERS)


def _show_lobby_notice() -> None:
    """Say once why this browser left its game (on the home or the invite page, wherever it lands)."""
    ss = st.session_state
    if ss.lobby_notice:
        st.warning(ss.lobby_notice)
        ss.lobby_notice = None
    if ss.get("lobby_info"):
        st.info(ss.lobby_info, icon=":material/save:")
        ss.lobby_info = None


def _render_my_games(store: RoomStore) -> None:
    """Unfinished games this browser played: one tap to continue (they are saved after every move)."""
    ss = st.session_state
    games, kept = [], []
    for code in ss.my_games:
        if len(games) == MY_GAMES_SHOWN:
            kept.append(code)  # not opened now: each look can load a game from disk
            continue
        try:
            view = store.view(code)
        except RoomError:
            continue  # the game is gone: forget it
        kept.append(code)  # a finished game is kept: someone may start the next one
        if not (view.started and view.engine.is_game_over()):
            games.append(view)
    ss.my_games = kept
    if not games:
        return
    _, mid, _ = st.columns([0.4, 10, 0.4])
    with mid:
        with st.container(border=True, key="card-my-games"):
            st.html(f'<div class="ab-card-title">{t("Continue a game")}</div>'
                    f'<div class="ab-card-sub">{t("Your games are saved after every move.")}</div>')
            with st.container(horizontal=True, key="my-games-row"):
                for view in games:
                    kind = t("Same device") if view.local else t("Online")
                    label = t("{code} · {kind} · {names}", code=view.code, kind=kind,
                              names=", ".join(md(n) for n in view.names))
                    if st.button(label, key=f"continue-{view.code}", icon=":material/play_arrow:"):
                        st.query_params["room"] = view.code
                        st.rerun()


def _card_header(icon: str, title: str, subtitle: str) -> None:
    st.html(f'<div class="ab-card-icon">{icon}</div><div class="ab-card-title">{escape(title)}</div>'
            f'<div class="ab-card-sub">{escape(subtitle)}</div>')


def _centered():
    return st.columns([1, 1.5, 1])[1]


# ------------------------------------------------------------------ online ----

def _render_online(store: RoomStore) -> None:
    ss = st.session_state
    code, token = ss.room_code, ss.seat_token
    seat = store.seat_of(code, token)
    if seat is None:
        if store.exists(code):
            notice = t("This game was opened in another tab or device, so this tab no longer controls it.")
        else:
            notice = t("That game is no longer available.")
        _leave_room(notice=notice, keep_link=store.exists(code))
        st.rerun()

    view = store.view(code)
    if view.local:
        _render_local_game(store, view, token)
        _watch_room(code, view.version, POLL_IDLE)  # in step if the game is open on two devices
        return
    status = chip(t("Online · {code}", code=code), "accent")

    if not view.started:
        def leave_waiting_room() -> None:
            store.leave(code, token)  # frees the seat; the next player takes over if this was the creator
            _leave_room()

        _announce_departures(view, seat)
        render_top_bar(status, leave_waiting_room, t("Leave game"))
        _render_waiting_room(store, view, seat, token, leave_waiting_room)
        ss.was_waiting = True
    else:
        engine = RoomEngine(get_store, code, token, view.engine, view.version)
        my_turn = not view.engine.is_game_over() and view.engine.current == seat
        # Before the first round it is a turn to throw for who goes first.
        your_turn = t("Your throw!") if view.engine.choosing_first_player else t("Your turn!")
        if ss.get("was_waiting"):
            # The game just started; this browser was on the waiting screen.
            others = [n for i, n in enumerate(view.names) if i != seat]
            joined = t("{name} joined.", name=md(others[0])) if len(others) == 1 else t("Everyone's here.")
            st.toast(f"{joined} {your_turn}" if my_turn else joined, icon="\U0001F3B2")
        elif my_turn and ss.get("was_my_turn") is False:
            st.toast(your_turn, icon="\U0001F3B2")
        ss.was_waiting = False
        ss.was_my_turn = my_turn

        def rematch() -> None:
            try:
                store.rematch(code, token)
            except RoomError:
                pass  # the other player already started the next game

        render_game(engine, me=seat, status_html=status, on_play_again=rematch,
                    on_leave=_leave_room, leave_label=t("Leave game"))

    # Check often only while someone else can change the room: players joining, or another
    # player's turn. On your own turn, or once the game is over, nobody else moves.
    others_can_act = not view.started or not (my_turn or view.engine.is_game_over())
    _watch_room(code, view.version, POLL_FAST if others_can_act else POLL_CALM)


def _render_local_game(store: RoomStore, view, token: str) -> None:
    """A same-device game. It is saved like an online game, so leaving it keeps it."""
    code = view.code

    def rematch() -> None:
        try:
            store.rematch(code, token)
        except RoomError:
            pass  # already restarted (the game is open on another device too)

    def leave() -> None:
        unfinished = not view.engine.is_game_over()
        _leave_room(info=t("Game {code} is saved. To continue it, open it from this page or enter the code {code}.",
                           code=code) if unfinished else None)

    render_game(RoomEngine(get_store, code, token, view.engine, view.version), me=None,
                status_html=chip(t("Same device · {code}", code=code)), on_play_again=rematch,
                on_leave=leave, leave_label=t("Leave game"))


def _watch_room(code: str, seen_version: int, every: float) -> None:
    """Re-draw the page as soon as the shared room changes, checking every `every` seconds."""
    {POLL_FAST: _watch_fast, POLL_CALM: _watch_calm, POLL_IDLE: _watch_idle}[every](code, seen_version)


def _check_room(code: str, seen_version: int) -> None:
    if get_store().version(code) != seen_version:
        st.rerun()


@st.fragment(run_every=POLL_FAST)
def _watch_fast(code: str, seen_version: int) -> None:
    _check_room(code, seen_version)


@st.fragment(run_every=POLL_CALM)
def _watch_calm(code: str, seen_version: int) -> None:
    _check_room(code, seen_version)


@st.fragment(run_every=POLL_IDLE)
def _watch_idle(code: str, seen_version: int) -> None:
    _check_room(code, seen_version)


def _announce_departures(view, seat: int) -> None:
    """In the waiting room: say who left since this page was last drawn, and who is the creator now."""
    ss = st.session_state
    before = ss.get("waiting_names")
    ss.waiting_names = list(view.names)
    if not before:
        return
    gone = [n for n in before if n not in view.names]
    if not gone:
        return
    message = t("{names} left.", names=", ".join(md(n) for n in gone))
    if seat == 0 and before[0] != view.names[0]:
        message += t(" You're the host now.")
    st.toast(message, icon="\U0001F44B")


def _render_waiting_room(store: RoomStore, view, seat: int, token: str, leave) -> None:
    code = view.code
    joined, capacity = len(view.names), view.capacity
    missing = capacity - joined
    host = view.names[0]
    with _centered():
        with st.container(border=True, key="card-wait"):
            if seat == 0:
                title = t("Invite a friend") if capacity == 2 else t("Invite your friends")
                sub = (t("Send them this link. The game starts as soon as they join.") if capacity == 2 else
                       t("Send them this link. The game starts when all {n} players have joined.", n=capacity))
                _card_header("\u2709\ufe0f", title, sub)
            else:
                _card_header("\u2705", t("You're in!"),
                             t("The game starts when all {capacity} players have joined, or when {host} starts it. "
                               "You can invite people with this link too.", capacity=capacity, host=host))
            link, same_network_only = _invite_link(code)
            if link:
                st.code(link, language=None, wrap_lines=True)
                if same_network_only:
                    st.caption(t("This link works for devices on the same Wi-Fi. To play over the internet, deploy the app "
                                 "(see DEPLOYMENT_GUIDE.md)."))
            seats = "".join(f'<span class="in">{escape(n)}</span>' for n in view.names)
            seats += f'<span>{t("Waiting…")}</span>' * missing
            waiting = (t("Waiting for your friend to join…") if capacity == 2 else
                       t("{joined} of {capacity} players are here. Waiting for {missing} more…",
                         joined=joined, capacity=capacity, missing=missing))
            st.html(f'<div class="ab-or">{t("or share the game code")}</div><div class="ab-code">'
                    + "".join(f"<span>{escape(c)}</span>" for c in code) + "</div>"
                    + (f'<div class="ab-seats">{seats}</div>' if capacity > 2 else "")
                    + f'<div class="ab-wait"><i></i>{waiting}</div>')
            if seat == 0 and capacity > 2 and joined >= 2:
                if st.button(t("Start now with {players}", players=players_count(joined)), key="big-start-now",
                             type="primary", icon=":material/play_arrow:", use_container_width=True):
                    try:
                        store.start_now(code, token)
                    except RoomError as e:
                        st.error(error(str(e)))
                    else:
                        st.rerun()
            # Leaving gives up the seat. "Cancel" when the creator is alone: the game is closed.
            if st.button(t("Cancel") if joined == 1 else t("Leave"), key="wait-cancel", type="tertiary",
                         icon=":material/close:", use_container_width=True):
                leave()
                st.rerun()


def _render_invite(store: RoomStore, code: str) -> None:
    """Join (or rejoin) the game named in the invite link."""
    _language_row("lang-invite")
    st.html(f'<div class="ab-hero" style="margin-bottom:1.2rem">{brand_html(44)}</div>')
    with _centered():
        # A tab whose seat was taken over keeps the link, so it lands here: tell it why.
        _show_lobby_notice()
        with st.container(border=True, key="card-invite"):
            if not store.exists(code):
                _card_header("\U0001F50D", t("Game not found"),
                             t("Game {code} has ended, or it is no longer kept. You can start a new one.", code=code))
                _home_button(t("Go to start"), primary=True)
                return
            if store.view(code).local:
                # A saved same-device game (after a reload, or opened by its code): carry on at once.
                _enter_room(code, store.resume_local(code))
                st.rerun()

            view = store.view(code)
            if not view.started:
                if view.capacity == 2:
                    sub = t("Enter your name to join. The game starts right away.")
                else:
                    sub = t("A game for {n} players; {k} joined so far: {names}. Enter your name to join.",
                            n=view.capacity, k=len(view.names), names=", ".join(view.names))
                _card_header("\U0001F3B2", t("{host} invited you to play", host=view.names[0]), sub)
                with st.form("join_game", border=False):
                    name = st.text_input(t("Your name"), placeholder=t("Name"), max_chars=20, key="join_name")
                    if st.form_submit_button(t("Join game"), type="primary", icon=":material/login:",
                                             use_container_width=True):
                        try:
                            token = store.join(code, name.strip() or t("Player {i}", i=len(view.names) + 1))
                        except RoomError as e:
                            st.error(error(str(e)))
                        else:
                            _enter_room(code, token)
                            st.rerun()
                rejoin_text = t("Already joined and lost the page? Rejoin as:")
            else:
                _card_header("\U0001F3B2", t(" vs ").join(view.names), t("This game is full and already playing."))
                rejoin_text = t("Are you one of the players? Rejoin as:")

            st.caption(rejoin_text)
            with st.container(horizontal=True, key="rejoin-row"):
                for i, name in enumerate(view.names):
                    if st.button(md(name), key=f"rejoin-{i}", icon=":material/person:"):
                        try:
                            token = store.reclaim(code, i)
                        except RoomError as e:
                            st.error(error(str(e)))
                        else:
                            _enter_room(code, token)
                            st.rerun()
            _home_button(t("Start your own game instead"))


def _home_button(label: str, primary: bool = False) -> None:
    if st.button(label, key="go-home", type="primary" if primary else "tertiary", use_container_width=primary,
                 icon=":material/home:" if primary else ":material/arrow_back:"):
        if "room" in st.query_params:
            del st.query_params["room"]
        st.rerun()


def _enter_room(code: str, token: str) -> None:
    ss = st.session_state
    ss.room_code = code
    ss.seat_token = token
    ss.was_my_turn = None
    ss.was_waiting = False
    ss.waiting_names = None
    reset_turn_selection()
    forget_action_error()
    # Only the room code goes in the URL, so it is always safe to share. It also
    # brings the game back after a reload or a dropped session.
    st.query_params["room"] = code
    ss.my_games = ([code] + [c for c in ss.get("my_games", []) if c != code])[:MY_GAMES_KEPT]


def _leave_room(notice: str = None, keep_link: bool = False, info: str = None) -> None:
    ss = st.session_state
    ss.room_code = None
    ss.seat_token = None
    ss.lobby_notice = notice
    ss.lobby_info = info
    reset_turn_selection()
    forget_action_error()
    if not keep_link and "room" in st.query_params:
        del st.query_params["room"]


def _invite_link(code: str):
    """Returns (link or None, True if the link only works on the local network)."""
    try:
        parts = urlsplit(st.context.url)
    except Exception:
        return None, False
    if not parts.scheme or not parts.netloc:
        return None, False

    netloc = parts.netloc
    same_network_only = False
    if parts.hostname in ("localhost", "127.0.0.1", "0.0.0.0"):
        ip = _local_ip()
        if ip is None:
            return None, False
        netloc = f"{ip}:{parts.port}" if parts.port else ip
        same_network_only = True
    path = parts.path if parts.path.endswith("/") else parts.path + "/"
    return f"{parts.scheme}://{netloc}{path}?room={code}", same_network_only


def _local_ip():
    """This machine's address on the local network, if it can be determined."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            s.connect(("8.8.8.8", 80))  # no packet is sent; this only picks the route
            return s.getsockname()[0]
        finally:
            s.close()
    except Exception:
        return None


if __name__ == "__main__":
    main()
