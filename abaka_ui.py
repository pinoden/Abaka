"""
Abaka — Streamlit app.

Screens:
  * Home: start a game on this device, create an online game, or join by code.
  * Invite (?room=CODE-KEY, the game's full code): join or rejoin an online game. The code
    alone opens nothing (Backlog item 31).
  * Waiting room: share the invite link until the second player joins.
  * Game: shared by both modes (ui_components/main_ui.py).

Online games live in a shared room inside this server process (abaka/rooms.py);
browsers send moves to it and poll it, so both players see every roll and score
as it happens.
"""

import importlib
import socket
import sys
import threading
import time
from html import escape
from typing import List, Optional
from urllib.parse import urlsplit

import streamlit as st

import code_version

if "server" not in code_version.PACKAGES:  # a code_version loaded before server/ existed (an update
    code_version = importlib.reload(code_version)  # pulled while no page was open): it would not reload server/

# Before importing the game's modules: make sure they match the files on disk (a
# commit pulled while nobody had the app open would otherwise leave old ones loaded).
code_version.load_current()

from abaka.rooms import (  # noqa: E402
    COMPUTER_LEVELS, MAX_PLAYERS, MIN_PLAYERS, RoomEngine, RoomError, RoomStore, clean_name, full_code,
    normalize_code, split_code, within_limit)
from abaka.seats import requests_for  # noqa: E402
from abaka.bot import SUGGESTED_LEVEL, computer_names, level_name  # noqa: E402
from abaka.clubs import MAX_CLUB_NAME_LENGTH, ClubError, ClubStore, is_club_code, member_key  # noqa: E402
from ui_components.actions import forget_action_error  # noqa: E402
from ui_components.chat import render_chat  # noqa: E402
from ui_components.device import device_to_keep, device_wait, keep_device, device as _device  # noqa: E402
from ui_components.effects import render_events, render_reaction_bar  # noqa: E402
from abaka.i18n import LANGUAGES, error, md, players_count, set_language, t  # noqa: E402
from ui_components.main_ui import (  # noqa: E402
    initialize_session_state, render_game, render_language_switch, render_top_bar, reset_turn_selection)
from ui_components.rules import rules_md  # noqa: E402
from ui_components.style import brand_html, chip, inject_global_css  # noqa: E402
from server import stores  # noqa: E402

# How often a page checks its room for changes (other players' moves):
POLL_FAST = 1.0    # someone else is acting, or players are joining
POLL_CALM = 3.0    # your own turn (nobody else can move), or the game is over
POLL_IDLE = 10.0   # a same-device game (only a second device could change it)
POLL_COMPUTER = 0.5  # the computer's turn: each check may make its next step (rooms.py)
GAMES_PER_SESSION = 10              # a browser may start this many games...
GAMES_PER_SESSION_WINDOW = 10 * 60  # ...in this many seconds (a guard against scripts)
MY_GAMES_KEPT = 10   # games a browser remembers for "Continue a game"...
MY_GAMES_SHOWN = 4   # ...and how many unfinished ones it shows
MY_CLUBS_KEPT = 6    # clubs a browser remembers for the home page
CLUB_GAMES_SHOWN = 10  # recent games on a club's page
POLL_ASK = 2.0       # a device waiting to be let in to a seat asks about the answer this often

stores.log_to_stderr()  # the game's log to stderr (Streamlit Cloud: Manage app); where games are saved: server/stores.py


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

    A server started from abaka_server.py also serves the API for apps; its pages
    then share the API's stores (server/stores.py, the same rules).
    """
    if stores.serving_api():
        return stores.get_store()
    registry = _store_registry()
    with registry["lock"]:
        store = registry["store"]
        if store is None or (type(store) is not RoomStore and _running_current_code()):
            if store is not None:
                store.retire()
            store, registry["clubs"] = stores.make_stores()  # the clubs come with the store
            registry["store"] = store
        return store


def get_clubs() -> ClubStore:
    """The ClubStore made together with the current RoomStore (see get_store)."""
    if stores.serving_api():
        return stores.get_clubs()
    get_store()
    registry = _store_registry()
    with registry["lock"]:
        if registry.get("clubs") is None:  # a store made by code from before clubs
            registry["clubs"] = ClubStore(repository=stores.repository("abaka_clubs", "clubs"))
        return registry["clubs"]


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
    ss.setdefault("my_clubs", [])      # codes of clubs this browser opened, newest first
    set_language(_pick_language())
    keep_device()  # which browser this is: it holds its seats (Backlog item 37, ui_components/device.py)

    store = get_store()
    # ?room= holds a game's full code (code and key): its code alone opens nothing (Backlog item 31).
    invited_code, invited_key = split_code(st.query_params.get("room", ""))
    club_code = normalize_code(st.query_params.get("club", ""))

    if ss.room_code:
        try:
            _render_online(store)
        except RoomError as e:
            # The room vanished mid-render (expired, or the server restarted).
            _leave_room(notice=error(str(e)))
            st.rerun()
    elif invited_code:
        _render_invite(store, invited_code, invited_key)
    elif club_code:
        _render_club(store, get_clubs(), club_code)
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
            _card_header("\U0001F465", t("Same device"),
                         t("Take turns on this screen, or play against the computer."))
            count = _player_count("local_count")
            # The computer plays the last seats (abaka/bot.py, Backlog item 33).
            computers = _computer_count(count)
            level = _computer_level() if computers else None
            people = count - computers
            with st.form("local_game", border=False):
                typed = [st.text_input(t("Player {i}", i=i), placeholder=t("Name"), max_chars=20, key=f"local_p{i}")
                         for i in range(1, people + 1)]
                seats = list(range(people, count))
                names = computer_names([""] * count, seats)
                if computers:
                    st.html('<div class="ab-computers">' + "".join(
                        f'<span>&#129302; {escape(names[i])}</span>' for i in seats) + "</div>")
                if st.form_submit_button(t("Start game"), type="primary", icon=":material/play_arrow:",
                                         use_container_width=True):
                    # Saved like an online game: it gets a code and can be continued from its link.
                    names = [name.strip() or t("Player {i}", i=i) for i, name in enumerate(typed, 1)] + names[people:]
                    _start_game(lambda: store.create_local(names, computers=seats, level=level))

    with online_col:
        with st.container(border=True, key="card-online"):
            _card_header("\U0001F310", t("Online"), t("Each player on their own device. Invite friends with a link."))
            players = _player_count("online_count")
            with st.form("create_game", border=False):
                name = st.text_input(t("Your name"), placeholder=t("Name"), max_chars=20, key="create_name")
                if st.form_submit_button(t("Create game"), type="primary", icon=":material/add_link:",
                                         use_container_width=True):
                    _start_game(lambda: store.create(name.strip() or t("Player {i}", i=1), players, device=device_to_keep()))
            st.html(f'<div class="ab-or">{t("or open a game by its code")}</div>')
            with st.form("find_game", border=False):
                typed = st.text_input(t("Game code"), placeholder=t("e.g. Q47CH-8XJ4PN2R"), max_chars=300,
                                      key="find_code", help=t("The full code, or the game's link. Join a friend's "
                                                              "game, or continue a saved game."))
                if st.form_submit_button(t("Open game"), icon=":material/login:", use_container_width=True):
                    code, key = split_code(typed)
                    if key and store.opens(code, key):
                        st.query_params["room"] = full_code(code, key)
                        st.rerun()
                    elif not key:
                        st.error(t("That is only the first part of a game's code. The full code looks like "
                                   "Q47CH-8XJ4PN2R: ask a player of the game for it."))
                    else:
                        st.error(t("No game with that code. Check it and try again."))

    _render_clubs_card(get_clubs())

    _, mid, _ = st.columns([0.4, 10, 0.4])
    with mid:
        with st.expander(t("How to play"), icon=":material/help:"):
            st.markdown(rules_md())
        st.caption(_storage_note(store))


def _storage_note(store: RoomStore) -> str:
    """One line at the foot of the home page: where games are saved (no address or password)."""
    storage = store.storage()
    if storage == "database":
        return t("Games are saved in the database.")
    if storage in ("files", "memory"):
        return t("Games are saved on this server only.")
    why = {
        "database:password": t("the database refused the password"),
        "database:unreachable": t("the database cannot be reached"),
        "database:not connected yet": t("the database is not connected yet"),
    }.get(storage, t("the database reported an error"))
    return t("Games are saved on this server only: {why}.", why=why)


def _render_clubs_card(clubs: ClubStore) -> None:
    """Home page: create a club, open one by its code, or go back to a club this browser knows."""
    ss = st.session_state
    _, mid, _ = st.columns([0.4, 10, 0.4])
    with mid:
        with st.container(border=True, key="card-clubs"):
            _card_header("\U0001F3C6", t("Clubs"),
                         t("A leaderboard for your group of friends. Games started from a club count for its table."))
            known = [(code, clubs.name(code)) for code in ss.get("my_clubs", [])]
            known = [(code, name) for code, name in known if name is not None]
            ss.my_clubs = [code for code, _ in known]
            if known:
                with st.container(horizontal=True, key="my-clubs-row"):
                    for code, name in known:
                        if st.button(md(name), key=f"club-{code}", icon=":material/leaderboard:"):
                            _open_club(code)
            create_col, open_col = st.columns(2, gap="medium")
            with create_col:
                with st.form("create_club", border=False):
                    name = st.text_input(t("Club name"), placeholder=t("e.g. Friday dice"), max_chars=30,
                                         key="club_name")
                    if st.form_submit_button(t("Create club"), icon=":material/add:", use_container_width=True):
                        # Clubs count with new games in the per-browser limit, as the API counts them
                        # per client (server/http.py): a club is kept for a year.
                        if not clean_name(name, "", MAX_CLUB_NAME_LENGTH):
                            st.error(error("Give the club a name."))
                        elif not _may_start_a_game():
                            st.error(t("You started a lot of games just now. Please wait a few minutes."))
                        else:
                            try:
                                _open_club(clubs.create(name))
                            except ClubError as e:
                                st.error(error(str(e)))
            with open_col:
                with st.form("find_club", border=False):
                    typed = st.text_input(t("Club code"), placeholder=t("e.g. K7PX2M"), max_chars=8,
                                          key="find_club_code")
                    if st.form_submit_button(t("Open club"), icon=":material/login:", use_container_width=True):
                        code = normalize_code(typed)
                        if is_club_code(code) and clubs.exists(code):
                            _open_club(code)
                        else:
                            st.error(t("No club with that code. Check it and try again."))


def _open_club(code: str) -> None:
    st.query_params["club"] = code
    st.rerun()


def _render_club(store: RoomStore, clubs: ClubStore, code: str) -> None:
    """A club's page: its table, a link to share, new club games, and the latest results."""
    ss = st.session_state
    _language_row("lang-club")
    _show_lobby_notice()
    club = clubs.get(code)
    if club is None:
        with _centered():
            st.error(t("No club with that code. Check it and try again."))
            _club_home_button()
        return
    ss.my_clubs = ([code] + [c for c in ss.get("my_clubs", []) if c != code])[:MY_CLUBS_KEPT]

    _, mid, _ = st.columns([0.4, 10, 0.4])
    with mid:
        _club_home_button()
        st.html(f'<div class="ab-club-head"><div class="ab-card-icon">&#127942;</div>'
                f'<div class="ab-card-title">{escape(club["name"])}</div>'
                f'<div class="ab-card-sub">{t("Club code")} <b>{code}</b> · '
                f'{t("Games started on this page count for the table.")}</div></div>')
        board, play = st.columns([7, 5], gap="large")
        with board:
            with st.container(border=True, key="card-club-table"):
                st.html(_club_table_html(club))
            if club["games"]:
                with st.container(border=True, key="card-club-games"):
                    st.html(_club_games_html(club))
        with play:
            with st.container(border=True, key="card-club-play"):
                known = clubs.member_names(code)
                _card_header("\U0001F3B2", t("New club game"),
                             t("Pick the club's players, or type a new name.") if known else
                             t("Type the names the same way each time; capital letters do not matter."))
                local_tab, online_tab = st.tabs([t("Same device"), t("Online")])
                with local_tab:
                    count = _player_count("club_local_count")
                    with st.form("club_local_game", border=False):
                        typed = [_name_field(t("Player {i}", i=i), f"club_p{i}", known)
                                 for i in range(1, count + 1)]
                        if st.form_submit_button(t("Start game"), type="primary", icon=":material/play_arrow:",
                                                 use_container_width=True):
                            names = [name.strip() or t("Player {i}", i=i) for i, name in enumerate(typed, 1)]
                            if len({member_key(n) for n in names}) < len(names):
                                st.error(t("Each player needs a different name."))
                            else:
                                _start_game(lambda: store.create_local(names, club=code))
                with online_tab:
                    players = _player_count("club_online_count")
                    with st.form("club_online_game", border=False):
                        name = _name_field(t("Your name"), "club_host", known)
                        if st.form_submit_button(t("Create game"), type="primary", icon=":material/add_link:",
                                                 use_container_width=True):
                            _start_game(lambda: store.create(name.strip() or t("Player {i}", i=1), players,
                                                             club=code, device=device_to_keep()))
            with st.container(border=True, key="card-club-share"):
                st.html(f'<div class="ab-card-sub">{t("Invite friends to the club with this link:")}</div>')
                link, _ = _invite_link(code, "club")
                if link:
                    st.code(link, language=None, wrap_lines=True)


def _name_field(label: str, key: str, known: List[str]) -> str:
    """
    A player's name. In a club that has players, a list of them that also takes a new name
    typed in (so the same player gets the same name every time); otherwise a text box.
    """
    if not known:
        return st.text_input(label, placeholder=t("Name"), max_chars=20, key=key)
    # A different key from the text box: Streamlit keeps a widget's value by key and type.
    picked = st.selectbox(label, known, index=None, key=f"{key}-pick", accept_new_options=True,
                          placeholder=t("Pick a player or type a new name"))
    return picked or ""


def _club_home_button() -> None:
    if st.button(t("Home"), key="club-home", type="tertiary", icon=":material/arrow_back:"):
        if "club" in st.query_params:
            del st.query_params["club"]
        st.rerun()


def _club_table_html(club: dict) -> str:
    members = sorted(club["members"].values(), key=lambda m: (-m["rating"], -m["wins"], m["name"].casefold()))
    if not members:
        return (f'<div class="ab-card-title">{t("Table")}</div>'
                f'<div class="ab-card-sub">{t("No games yet. Start one, and the table fills in when it ends.")}</div>')
    head = "".join(f"<th>{h}</th>" for h in ("#", t("Player"), t("Rating"), t("Games"), t("Wins"),
                                              t("Average"), t("Best")))
    rows = []
    for rank, m in enumerate(members, 1):
        medal = {1: "&#129351;", 2: "&#129352;", 3: "&#129353;"}.get(rank, str(rank))
        average = round(m["points"] / m["games"]) if m["games"] else 0
        rows.append(f'<tr><td class="ab-rank">{medal}</td><td class="ab-name">{escape(m["name"])}</td>'
                    f'<td class="ab-rating"><b>{round(m["rating"])}</b> {_change_html(m["change"])}</td>'
                    f'<td>{m["games"]}</td><td>{m["wins"]}</td><td class="ab-wide">{average}</td>'
                    f'<td class="ab-wide">{m["best"]}</td></tr>')
    return (f'<div class="ab-card-title">{t("Table")}</div>'
            f'<div class="ab-card-sub">{t("Everyone starts at 1000. Beating a stronger player earns more.")}</div>'
            f'<table class="ab-club-table"><thead><tr>{head}</tr></thead><tbody>{"".join(rows)}</tbody></table>')


def _club_games_html(club: dict) -> str:
    items = []
    for game in club["games"][:CLUB_GAMES_SHOWN]:
        best = max(p["score"] for p in game["players"])
        players = " · ".join(
            f'<span class="{"win" if p["score"] == best else ""}">{escape(p["name"])} {p["score"]}</span>'
            for p in sorted(game["players"], key=lambda p: -p["score"]))
        when = time.strftime("%d.%m", time.localtime(game["at"]))
        items.append(f'<li><span class="ab-when">{when}</span>{players}</li>')
    return (f'<div class="ab-card-title">{t("Latest games")}</div>'
            f'<ul class="ab-club-games">{"".join(items)}</ul>')


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


def _computer_count(players: int) -> int:
    """How many of a same-device game's seats the computer plays: none to all but one."""
    key = f"local_computers_{players}"  # its options change with the number of players
    value = st.segmented_control(t("Computer players"), list(range(players)), default=0, key=key,
                                 help=t("The computer plays the last seats and makes its moves by itself."))
    return value or 0


def _computer_level() -> str:
    """How well the computer plays in the game being set up (Backlog item 34): Medium unless chosen."""
    value = st.segmented_control(t("Level"), list(COMPUTER_LEVELS), default=SUGGESTED_LEVEL, key="local_level",
                                 format_func=level_name,
                                 help=t("How well the computer plays. Easy makes mistakes, Hard works out every roll."))
    return value or SUGGESTED_LEVEL


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
                        st.query_params["room"] = full_code(view.code, view.key)
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
    if _device():
        store.own(code, token, _device())  # a seat taken before devices were remembered keeps this browser's secret
    seat = store.seat_of(code, token)
    if seat is None:
        if store.exists(code):
            notice = t("This game was opened in another tab or device, so this tab no longer controls it.")
        else:
            notice = t("That game is no longer available.")
        _leave_room(notice=notice, keep_link=store.exists(code))
        st.rerun()

    view = store.view(code)
    if st.query_params.get("room") != full_code(code, view.key):
        st.query_params["room"] = full_code(code, view.key)  # a page drawn before games had keys
    if view.local:
        _render_local_game(store, view, token)
        # In step if the game is open on two devices; often while the computer plays its turn (its
        # steps are made by this page's checks, rooms.py: one every COMPUTER_PACE_SECONDS).
        computer_plays = (view.engine is not None and not view.engine.is_game_over()
                          and view.engine.current in view.computers)
        _watch_room(code, view.seen, POLL_COMPUTER if computer_plays else POLL_IDLE)
        return
    status = chip(t("Online · {code}", code=code), "accent")
    _render_requests(view, seat, token)

    if not view.started:
        def leave_waiting_room() -> None:
            store.leave(code, token)  # frees the seat; the next player takes over if this was the creator
            _leave_room()

        _announce_departures(view, seat)
        render_top_bar(status, leave_waiting_room, t("Leave game"), full_code(code, view.key))
        _render_waiting_room(store, view, seat, token, leave_waiting_room)
        ss.was_waiting = True
    else:
        engine = RoomEngine(get_store, code, token, view.engine, view.version, view.picked, view.rerolled)
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

        def react(reaction: str, to: Optional[int]) -> None:
            get_store().react(code, token, reaction, to)

        render_game(engine, me=seat, status_html=status, on_play_again=rematch,
                    on_leave=_leave_room, leave_label=t("Leave game"), board_note_html=_series_html(view),
                    results_note_html=_club_result_html(view), after_results=lambda: _club_button(view),
                    below_play=lambda: render_reaction_bar(view.names, seat, react),
                    after_play_card=None if view.engine.is_game_over() else
                    lambda: render_chat(code, view.chat, view.names, seat,
                                        lambda text: get_store().say(code, token, text)),
                    full_code=full_code(code, view.key))
        render_events(code, view.events, view.names, seat)

    # Check often only while someone else can change the room: players joining, or another
    # player's turn. On your own turn, or once the game is over, nobody else moves.
    others_can_act = not view.started or not (my_turn or view.engine.is_game_over())
    _watch_room(code, view.seen, POLL_FAST if others_can_act else POLL_CALM, token)


def _render_requests(view, seat: int, token: str) -> None:
    """
    Devices asking to be let in to a seat (Backlog item 37), at the top of the page: one for this
    player's own seat always, one for another player's once that player's device is not here.
    """
    ss = st.session_state
    code = view.code
    requests = requests_for(view.asks, view.names, seat)
    told = ss.get("requests_told") or []
    for request in requests:
        if request["seat"] not in told:
            st.toast(md(request["title"]), icon=":material/person_alert:")
    ss.requests_told = [r["seat"] for r in requests]

    def answer(asked_seat: int, let_in: bool) -> None:
        try:
            get_store().answer(code, token, asked_seat, let_in)
        except RoomError:
            pass  # answered meanwhile, or the request lapsed: the page shows what is

    for request in requests:
        with st.container(border=True, key=f"card-ask-{request['seat']}"):
            st.html(f'<div class="ab-ask"><b>{escape(request["title"])}</b>{escape(request["text"])}</div>')
            with st.container(horizontal=True):
                st.button(t("Let in"), key=f"ask-yes-{request['seat']}", type="primary", icon=":material/check:",
                          on_click=answer, args=(request["seat"], True))
                st.button(t("Refuse"), key=f"ask-no-{request['seat']}", icon=":material/block:",
                          on_click=answer, args=(request["seat"], False))


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
        _leave_room(info=t("Game {code} is saved. To continue it, open it from this page or enter its full code "
                           "{full}.", code=code, full=full_code(code, view.key)) if unfinished else None)

    render_game(RoomEngine(get_store, code, token, view.engine, view.version, view.picked, view.rerolled,
                           view.computers, getattr(view, "computer_level", None)),
                me=None,
                status_html=chip(t("Same device · {code}", code=code)), on_play_again=rematch,
                on_leave=leave, leave_label=t("Leave game"), board_note_html=_series_html(view),
                results_note_html=_club_result_html(view), after_results=lambda: _club_button(view),
                full_code=full_code(code, view.key))
    render_events(code, view.events, view.names, None)  # fireworks and sparkles; no reactions here


def _series_html(view) -> str:
    """The running score at this table, under the scoreboard, once a game here has finished."""
    if not view.results:
        return ""
    wins, draws = view.series()
    order = sorted(range(len(view.names)), key=lambda i: (-wins[i], i))
    leader = order[0] if wins[order[0]] > 0 and (len(order) == 1 or wins[order[0]] > wins[order[1]]) else None
    people = " · ".join(f'{"&#128081; " if i == leader else ""}{escape(view.names[i])} <b>{wins[i]}</b>'
                        for i in order)
    games = len(view.results)
    head = t("Games at this table: {n}", n=games)
    tail = f' · {t("draws: {n}", n=draws)}' if draws else ""
    club = f'<span class="ab-series-club">&#127942; {t("club game")}</span>' if view.club else ""
    return f'<div class="ab-series"><span class="ab-series-head">{head}</span> {people}{tail}{club}</div>'


def _club_result_html(view) -> str:
    """On the results screen of a club game: how the ratings moved (once the game is recorded)."""
    if not view.club or not (view.engine is not None and view.engine.is_game_over()):
        return ""
    game = get_clubs().game(view.club, view.code, view.games_played)
    if game is None:
        return ""
    rows = [f'<span>{escape(p["name"])} <b>{round(p["rating"])}</b> {_change_html(p["change"])}</span>'
            for p in sorted(game["players"], key=lambda p: -p["score"])]
    return (f'<div class="ab-club-result"><div>{t("Club rating · {name}", name=escape(game["club"]))}</div>'
            f'{"".join(rows)}</div>')


def _club_button(view) -> None:
    """On the results screen of a club game: a way to the club's table."""
    if not view.club:
        return
    if st.button(t("Club table"), key="results-club", icon=":material/leaderboard:", use_container_width=True):
        _leave_room()
        st.query_params["club"] = view.club
        st.rerun()


def _change_html(change: float) -> str:
    n = round(change)
    if n > 0:
        return f'<span class="ab-up">&#9650;{n}</span>'
    if n < 0:
        return f'<span class="ab-down">&#9660;{-n}</span>'
    return '<span class="ab-same">=</span>'


def _watch_room(code: str, seen, every: float, token: Optional[str] = None) -> None:
    """
    Re-draw the page as soon as the shared room changes, or the player whose turn it is picks
    other dice (`seen` is RoomView.seen), checking every `every` seconds. With an online
    seat's `token`, each check also tells the room that this seat's device is here.
    """
    {POLL_FAST: _watch_fast, POLL_CALM: _watch_calm, POLL_IDLE: _watch_idle,
     POLL_COMPUTER: _watch_computer}[every](code, tuple(seen), token)


def _check_room(code: str, seen, token: Optional[str] = None) -> None:
    if get_store().seen(code, token) != seen:
        st.rerun()


@st.fragment(run_every=POLL_FAST)
def _watch_fast(code: str, seen, token: Optional[str] = None) -> None:
    _check_room(code, seen, token)


@st.fragment(run_every=POLL_CALM)
def _watch_calm(code: str, seen, token: Optional[str] = None) -> None:
    _check_room(code, seen, token)


@st.fragment(run_every=POLL_IDLE)
def _watch_idle(code: str, seen, token: Optional[str] = None) -> None:
    _check_room(code, seen, token)


@st.fragment(run_every=POLL_COMPUTER)
def _watch_computer(code: str, seen, token: Optional[str] = None) -> None:
    _check_room(code, seen, token)


@st.fragment(run_every=POLL_ASK)
def _watch_request(code: str, key: str, seat: int, ticket: str) -> None:
    """A browser that asked to be let in to a seat: take the seat once someone let it in."""
    ss = st.session_state
    try:
        status, token = get_store().asked(code, seat, key, ticket, device_to_keep())
    except RoomError:
        status, token = "gone", None
    if status == "waiting":
        return
    ss.asking = None
    if status == "in":
        _enter_room(code, token)
    else:
        ss.lobby_notice = (t("The request was refused.") if status == "refused" else
                           t("The request is no longer there. Ask again."))
    st.rerun()


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
            link, same_network_only = _invite_link(full_code(code, view.key))
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
            # The full code: the code alone opens nothing (Backlog item 31). Its key part is smaller.
            st.html(f'<div class="ab-or">{t("or share the game code")}</div><div class="ab-code">'
                    + "".join(f"<span>{escape(c)}</span>" for c in code) + "</div>"
                    + '<div class="ab-code ab-code-key">' + "".join(f"<span>{escape(c)}</span>" for c in view.key)
                    + "</div>"
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


def _render_invite(store: RoomStore, code: str, key: str) -> None:
    """Join (or rejoin) the game named in the invite link: its code and its key."""
    _language_row("lang-invite")
    st.html(f'<div class="ab-hero" style="margin-bottom:1.2rem">{brand_html(44)}</div>')
    with _centered():
        # A tab whose seat was taken over keeps the link, so it lands here: tell it why.
        _show_lobby_notice()
        with st.container(border=True, key="card-invite"):
            if not key:
                # A code alone (an old link, or a code typed into the address): it opens nothing, and
                # the page says the same whether or not there is such a game.
                _card_header("\U0001F512", t("This link is not complete"),
                             t("A game opens only with its full link or code, such as Q47CH-8XJ4PN2R. "
                               "Ask a player of the game to send it again."))
                _home_button(t("Go to start"), primary=True)
                return
            if not store.opens(code, key):
                _card_header("\U0001F50D", t("Game not found"),
                             t("Game {code} has ended, or it is no longer kept. You can start a new one.", code=code))
                _home_button(t("Go to start"), primary=True)
                return
            if store.view(code).local:
                # A saved same-device game (after a reload, or opened by its full code): carry on at once.
                _enter_room(code, store.resume_local(code, key))
                st.rerun()

            view = store.view(code)
            ss = st.session_state
            if _device() is None and view.started and any(view.held) and code not in ss.get("left_rooms", []):
                # A session's first moment: the browser has not said which it is yet. If it holds a
                # seat here, the game opens by itself, so the invite is not shown in between.
                _card_header("\U0001F3B2", t(" vs ").join(view.names), t("Opening the game…"))
                st.html(f'<div class="ab-wait"><i></i>{t("Waiting…")}</div>')
                device_wait()
                return
            device = device_to_keep()
            mine = store.device_seat(code, key, device)  # the seat this browser holds, if any

            def come_back() -> None:
                try:
                    token = store.reclaim(code, mine, key, device)
                except RoomError as e:
                    st.error(error(str(e)))
                else:
                    _enter_room(code, token)
                    st.rerun()

            if mine is not None and view.started and code not in ss.get("left_rooms", []):
                # After a reload or a dropped session: straight back to the seat. Not for a tab that
                # was just told its seat went to another tab, or the two would take it in turns.
                come_back()
            asking = ss.get("asking")
            if asking and (asking["code"] != code or asking["seat"] >= len(view.names)):
                asking = ss.asking = None
            if asking:
                name = view.names[asking["seat"]]
                _card_header("\u23F3", t("Asked to come back as {name}", name=name),
                             t("Waiting to be let in. If the game is open on the device that holds this seat, "
                               "confirm it there. Otherwise another player is asked in a few seconds."))
                st.html(f'<div class="ab-wait"><i></i>{t("Waiting…")}</div>')
                if st.button(t("Cancel"), key="ask-cancel", type="tertiary", icon=":material/close:",
                             use_container_width=True):
                    ss.asking = None
                    st.rerun()
                _watch_request(code, key, asking["seat"], asking["ticket"])
                return
            if not view.started:
                if view.capacity == 2:
                    sub = t("Enter your name to join. The game starts right away.")
                else:
                    sub = t("A game for {n} players; {k} joined so far: {names}. Enter your name to join.",
                            n=view.capacity, k=len(view.names), names=", ".join(view.names))
                _card_header("\U0001F3B2", t("{host} invited you to play", host=view.names[0]), sub)
                # A club game: offer the club's players who are not seated yet.
                seated = {member_key(n) for n in view.names}
                known = [n for n in (get_clubs().member_names(view.club) if view.club else [])
                         if member_key(n) not in seated]
                with st.form("join_game", border=False):
                    name = _name_field(t("Your name"), "join_name", known)
                    if st.form_submit_button(t("Join game"), type="primary", icon=":material/login:",
                                             use_container_width=True):
                        try:
                            token = store.join(code, name.strip() or t("Player {i}", i=len(view.names) + 1), key,
                                               device)
                        except RoomError as e:
                            st.error(error(str(e)))
                        else:
                            _enter_room(code, token)
                            st.rerun()
                rejoin_text = t("Already joined on another device? Ask to come back as:")
            else:
                _card_header("\U0001F3B2", t(" vs ").join(view.names), t("This game is full and already playing."))
                rejoin_text = t("Are you one of the players? Ask to come back as:")

            if mine is not None:
                st.caption(t("This browser holds a seat in this game:"))
                if st.button(t("Continue as {name}", name=md(view.names[mine])), key="come-back", type="primary",
                             icon=":material/login:", use_container_width=True):
                    come_back()
            others = [i for i in range(len(view.names)) if i != mine]
            if others:
                # A seat belongs to the device that took it (Backlog item 37): any other asks to be let in.
                st.caption(rejoin_text, help=t(
                    "A seat belongs to the device that took it. From another device you are let in by your own "
                    "device, if the game is open there, and otherwise by another player."))
                with st.container(horizontal=True, key="rejoin-row"):
                    for i in others:
                        if st.button(md(view.names[i]), key=f"rejoin-{i}", icon=":material/person:"):
                            try:
                                ticket = store.ask(code, i, key, device)
                            except RoomError as e:
                                st.error(error(str(e)))
                            else:
                                ss.asking = {"code": code, "seat": i, "ticket": ticket}
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
    ss.asking = None
    ss.left_rooms = [c for c in ss.get("left_rooms", []) if c != code]
    reset_turn_selection()
    forget_action_error()
    # The game's full code goes in the URL (never the seat's token): the link to share with the
    # players, which also brings the game back after a reload or a dropped session.
    st.query_params["room"] = full_code(code, get_store().view(code).key)
    ss.my_games = ([code] + [c for c in ss.get("my_games", []) if c != code])[:MY_GAMES_KEPT]


def _leave_room(notice: str = None, keep_link: bool = False, info: str = None) -> None:
    ss = st.session_state
    if ss.room_code:  # no going straight back to a seat this session left or lost (_render_invite)
        ss.left_rooms = ([ss.room_code] + [c for c in ss.get("left_rooms", []) if c != ss.room_code])[:20]
    ss.room_code = None
    ss.seat_token = None
    ss.lobby_notice = notice
    ss.lobby_info = info
    reset_turn_selection()
    forget_action_error()
    if not keep_link and "room" in st.query_params:
        del st.query_params["room"]


def _invite_link(code: str, param: str = "room"):
    """Returns (link or None, True if the link only works on the local network). `param`: room or club."""
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
    return f"{parts.scheme}://{netloc}{path}?{param}={code}", same_network_only


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
