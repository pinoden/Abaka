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

import socket
from html import escape
from urllib.parse import urlsplit

import streamlit as st

from abaka.engine import GameEngine
from abaka.rooms import MAX_PLAYERS, MIN_PLAYERS, RoomEngine, RoomError, RoomStore, normalize_code
from ui_components.main_ui import initialize_session_state, render_game, render_top_bar, reset_turn_selection
from ui_components.rules import RULES_MD
from ui_components.style import brand_html, chip, inject_global_css

POLL_SECONDS = 1.0  # how often a browser checks the room for the other player's moves


@st.cache_resource
def _store_for_code(code_id: int) -> RoomStore:
    return RoomStore()


def get_store() -> RoomStore:
    """
    The one RoomStore shared by every browser session of this server.

    It is kept per version of the code. Streamlit Community Cloud applies a new
    commit by reloading the app's modules, but cached objects survive the reload,
    and a store made by the old code breaks the new code (after PR #13, "Create
    game" failed with a TypeError on the live app). So new code gets a new store;
    pages still running the old code keep the old one until they reload. Games in
    progress are lost on an update, as on a restart.
    """
    return _store_for_code(id(RoomStore))


def main():
    st.set_page_config(page_title="Abaka", page_icon="\U0001F3B2", layout="wide",
                       initial_sidebar_state="collapsed")
    inject_global_css()
    initialize_session_state()
    ss = st.session_state
    ss.setdefault("room_code", None)   # online room this browser is seated in
    ss.setdefault("seat_token", None)  # proves which seat this browser controls
    ss.setdefault("lobby_notice", None)

    store = get_store()
    invited_code = normalize_code(st.query_params.get("room", ""))

    if ss.room_code:
        try:
            _render_online(store)
        except RoomError as e:
            # The room vanished mid-render (expired, or the server restarted).
            _leave_room(notice=str(e))
            st.rerun()
    elif ss.engine is not None:
        render_game(ss.engine, status_html=chip("Same device"), on_play_again=_restart_local_game,
                    on_leave=_end_local_game, leave_label="End game")
    elif invited_code:
        _render_invite(store, invited_code)
    else:
        _render_home(store)


# ------------------------------------------------------------------ home ----

def _render_home(store: RoomStore) -> None:
    st.html(f'<div class="ab-hero">{brand_html(56)}'
            "<p>The dice game of combinations. Play with friends on one screen or online.</p></div>")
    _show_lobby_notice()

    _, local_col, online_col, _ = st.columns([0.4, 5, 5, 0.4], gap="large")
    with local_col:
        with st.container(border=True, key="card-local"):
            _card_header("\U0001F465", "Same device", "Take turns on this screen.")
            count = _player_count("local_count")
            with st.form("local_game", border=False):
                typed = [st.text_input(f"Player {i}", placeholder="Name", max_chars=20, key=f"local_p{i}")
                         for i in range(1, count + 1)]
                if st.form_submit_button("Start game", type="primary", icon=":material/play_arrow:",
                                         use_container_width=True):
                    _new_local_game([t.strip() or f"Player {i}" for i, t in enumerate(typed, 1)])
                    st.rerun()

    with online_col:
        with st.container(border=True, key="card-online"):
            _card_header("\U0001F310", "Online", "Each player on their own device. Invite friends with a link.")
            players = _player_count("online_count")
            with st.form("create_game", border=False):
                name = st.text_input("Your name", placeholder="Name", max_chars=20, key="create_name")
                if st.form_submit_button("Create game", type="primary", icon=":material/add_link:",
                                         use_container_width=True):
                    code, token = store.create(name, players)
                    _enter_room(code, token)
                    st.rerun()
            st.html('<div class="ab-or">or join with a code</div>')
            with st.form("find_game", border=False):
                typed = st.text_input("Game code", placeholder="e.g. Q47CH", max_chars=8, key="find_code")
                if st.form_submit_button("Join game", icon=":material/login:", use_container_width=True):
                    code = normalize_code(typed)
                    if store.exists(code):
                        st.query_params["room"] = code
                        st.rerun()
                    else:
                        st.error("No game with that code. Check it and try again.")

    _, mid, _ = st.columns([0.4, 10, 0.4])
    with mid:
        with st.expander("How to play", icon=":material/help:"):
            st.markdown(RULES_MD)


def _player_count(key: str) -> int:
    """Pick 2-5 players. Clicking the chosen option again would clear it, so keep the last choice."""
    ss = st.session_state
    last_key = key + "_last"

    def keep() -> None:
        if ss.get(key) is None:
            ss[key] = ss.get(last_key, MIN_PLAYERS)
        ss[last_key] = ss[key]

    value = st.segmented_control("Players", list(range(MIN_PLAYERS, MAX_PLAYERS + 1)), default=MIN_PLAYERS,
                                 key=key, on_change=keep)
    return value or ss.get(last_key, MIN_PLAYERS)


def _show_lobby_notice() -> None:
    """Say once why this browser left its game (on the home or the invite page, wherever it lands)."""
    ss = st.session_state
    if ss.lobby_notice:
        st.warning(ss.lobby_notice)
        ss.lobby_notice = None


def _card_header(icon: str, title: str, subtitle: str) -> None:
    st.html(f'<div class="ab-card-icon">{icon}</div><div class="ab-card-title">{escape(title)}</div>'
            f'<div class="ab-card-sub">{escape(subtitle)}</div>')


def _centered():
    return st.columns([1, 1.5, 1])[1]


# ------------------------------------------------------------- same device ----

def _start_local_game(names) -> None:
    st.session_state.engine = GameEngine(names)
    reset_turn_selection()


def _new_local_game(names) -> None:
    st.session_state.local_games = 0
    _start_local_game(names)


def _restart_local_game() -> None:
    ss = st.session_state
    names = [p.name for p in ss.engine.players]
    _start_local_game(names)
    # The next player in turn starts each new game.
    ss.local_games = ss.get("local_games", 0) + 1
    ss.engine.current = ss.local_games % len(names)


def _end_local_game() -> None:
    st.session_state.engine = None


# ------------------------------------------------------------------ online ----

def _render_online(store: RoomStore) -> None:
    ss = st.session_state
    code, token = ss.room_code, ss.seat_token
    seat = store.seat_of(code, token)
    if seat is None:
        if store.exists(code):
            notice = "This game was opened in another tab or device, so this tab no longer controls it."
        else:
            notice = "That game is no longer available."
        _leave_room(notice=notice, keep_link=store.exists(code))
        st.rerun()

    view = store.view(code)
    status = chip(f"Online · {code}", "accent")

    if not view.started:
        def leave_waiting_room() -> None:
            store.leave(code, token)  # frees the seat; the next player takes over if this was the creator
            _leave_room()

        _announce_departures(view, seat)
        render_top_bar(status, leave_waiting_room, "Leave game")
        _render_waiting_room(store, view, seat, token, leave_waiting_room)
        ss.was_waiting = True
    else:
        engine = RoomEngine(store, code, token, view.engine)
        my_turn = not view.engine.is_game_over() and view.engine.current == seat
        if ss.get("was_waiting"):
            # The game just started; this browser was on the waiting screen.
            others = [n for i, n in enumerate(view.names) if i != seat]
            joined = f"{others[0]} joined." if len(others) == 1 else "Everyone's here."
            st.toast(f"{joined} Your turn!" if my_turn else joined, icon="\U0001F3B2")
        elif my_turn and ss.get("was_my_turn") is False:
            st.toast("Your turn!", icon="\U0001F3B2")
        ss.was_waiting = False
        ss.was_my_turn = my_turn

        def rematch() -> None:
            try:
                store.rematch(code, token)
            except RoomError:
                pass  # the other player already started the next game

        render_game(engine, me=seat, status_html=status, on_play_again=rematch,
                    on_leave=_leave_room, leave_label="Leave game")

    _watch_room(code, view.version)


@st.fragment(run_every=POLL_SECONDS)
def _watch_room(code: str, seen_version: int) -> None:
    """Re-draw the page as soon as the shared room changes (the other player moved)."""
    if get_store().version(code) != seen_version:
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
    message = f"{', '.join(gone)} left."
    if seat == 0 and before[0] != view.names[0]:
        message += " You're the host now."
    st.toast(message, icon="\U0001F44B")


def _render_waiting_room(store: RoomStore, view, seat: int, token: str, leave) -> None:
    code = view.code
    joined, capacity = len(view.names), view.capacity
    missing = capacity - joined
    host = view.names[0]
    with _centered():
        with st.container(border=True, key="card-wait"):
            if seat == 0:
                title = "Invite a friend" if capacity == 2 else "Invite your friends"
                sub = ("Send them this link. The game starts as soon as they join." if capacity == 2 else
                       f"Send them this link. The game starts when all {capacity} players have joined.")
                _card_header("\u2709\ufe0f", title, sub)
            else:
                _card_header("\u2705", "You're in!",
                             f"The game starts when all {capacity} players have joined, "
                             f"or when {host} starts it. You can invite people with this link too.")
            link, same_network_only = _invite_link(code)
            if link:
                st.code(link, language=None, wrap_lines=True)
                if same_network_only:
                    st.caption("This link works for devices on the same Wi-Fi. To play over the internet, "
                               "deploy the app (see DEPLOYMENT_GUIDE.md).")
            seats = "".join(f'<span class="in">{escape(n)}</span>' for n in view.names)
            seats += '<span>Waiting\u2026</span>' * missing
            waiting = ("Waiting for your friend to join\u2026" if capacity == 2 else
                       f"{joined} of {capacity} players are here. Waiting for "
                       f"{missing} more\u2026")
            st.html('<div class="ab-or">or share the game code</div><div class="ab-code">'
                    + "".join(f"<span>{escape(c)}</span>" for c in code) + "</div>"
                    + (f'<div class="ab-seats">{seats}</div>' if capacity > 2 else "")
                    + f'<div class="ab-wait"><i></i>{waiting}</div>')
            if seat == 0 and capacity > 2 and joined >= 2:
                if st.button(f"Start now with {joined} players", key="big-start-now", type="primary",
                             icon=":material/play_arrow:", use_container_width=True):
                    try:
                        store.start_now(code, token)
                    except RoomError as e:
                        st.error(str(e))
                    else:
                        st.rerun()
            # Leaving gives up the seat. "Cancel" when the creator is alone: the game is closed.
            if st.button("Cancel" if joined == 1 else "Leave", key="wait-cancel", type="tertiary",
                         icon=":material/close:", use_container_width=True):
                leave()
                st.rerun()


def _render_invite(store: RoomStore, code: str) -> None:
    """Join (or rejoin) the game named in the invite link."""
    st.html(f'<div class="ab-hero" style="margin-bottom:1.2rem">{brand_html(44)}</div>')
    with _centered():
        # A tab whose seat was taken over keeps the link, so it lands here: tell it why.
        _show_lobby_notice()
        with st.container(border=True, key="card-invite"):
            if not store.exists(code):
                _card_header("\U0001F50D", "Game not found",
                             f"Game {code} has ended, or the server restarted. You can start a new one.")
                _home_button("Go to start", primary=True)
                return

            view = store.view(code)
            if not view.started:
                if view.capacity == 2:
                    sub = "Enter your name to join. The game starts right away."
                else:
                    sub = (f"A game for {view.capacity} players; {len(view.names)} joined so far: "
                           f"{', '.join(view.names)}. Enter your name to join.")
                _card_header("\U0001F3B2", f"{view.names[0]} invited you to play", sub)
                with st.form("join_game", border=False):
                    name = st.text_input("Your name", placeholder="Name", max_chars=20, key="join_name")
                    if st.form_submit_button("Join game", type="primary", icon=":material/login:",
                                             use_container_width=True):
                        try:
                            token = store.join(code, name)
                        except RoomError as e:
                            st.error(str(e))
                        else:
                            _enter_room(code, token)
                            st.rerun()
                rejoin_text = "Already joined and lost the page? Rejoin as:"
            else:
                _card_header("\U0001F3B2", " vs ".join(view.names), "This game is full and already playing.")
                rejoin_text = "Are you one of the players? Rejoin as:"

            st.caption(rejoin_text)
            with st.container(horizontal=True, key="rejoin-row"):
                for i, name in enumerate(view.names):
                    if st.button(name, key=f"rejoin-{i}", icon=":material/person:"):
                        try:
                            token = store.reclaim(code, i)
                        except RoomError as e:
                            st.error(str(e))
                        else:
                            _enter_room(code, token)
                            st.rerun()
            _home_button("Start your own game instead")


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
    # Only the room code goes in the URL, so it is always safe to share.
    st.query_params["room"] = code


def _leave_room(notice: str = None, keep_link: bool = False) -> None:
    ss = st.session_state
    ss.room_code = None
    ss.seat_token = None
    ss.lobby_notice = notice
    reset_turn_selection()
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
