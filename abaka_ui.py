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
from abaka.rooms import RoomEngine, RoomError, RoomStore, normalize_code
from ui_components.main_ui import initialize_session_state, render_game, render_top_bar, reset_turn_selection
from ui_components.rules import RULES_MD
from ui_components.style import brand_html, chip, inject_global_css

POLL_SECONDS = 1.0  # how often a browser checks the room for the other player's moves


@st.cache_resource
def get_store() -> RoomStore:
    """The one RoomStore shared by every browser session of this server."""
    return RoomStore()


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
    ss = st.session_state
    st.html(f'<div class="ab-hero">{brand_html(56)}'
            "<p>The dice game of combinations. Play with a friend on one screen or online.</p></div>")
    if ss.lobby_notice:
        st.warning(ss.lobby_notice)
        ss.lobby_notice = None

    _, local_col, online_col, _ = st.columns([0.4, 5, 5, 0.4], gap="large")
    with local_col:
        with st.container(border=True, key="card-local"):
            _card_header("\U0001F465", "Same device", "Two players take turns on this screen.")
            with st.form("local_game", border=False):
                p1 = st.text_input("Player 1", placeholder="Name", max_chars=20, key="local_p1")
                p2 = st.text_input("Player 2", placeholder="Name", max_chars=20, key="local_p2")
                if st.form_submit_button("Start game", type="primary", icon=":material/play_arrow:",
                                         use_container_width=True):
                    _start_local_game([p1.strip() or "Player 1", p2.strip() or "Player 2"])
                    st.rerun()

    with online_col:
        with st.container(border=True, key="card-online"):
            _card_header("\U0001F310", "Online", "Each player on their own device. Invite a friend with a link.")
            with st.form("create_game", border=False):
                name = st.text_input("Your name", placeholder="Name", max_chars=20, key="create_name")
                if st.form_submit_button("Create game", type="primary", icon=":material/add_link:",
                                         use_container_width=True):
                    code, token = store.create(name)
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


def _card_header(icon: str, title: str, subtitle: str) -> None:
    st.html(f'<div class="ab-card-icon">{icon}</div><div class="ab-card-title">{escape(title)}</div>'
            f'<div class="ab-card-sub">{escape(subtitle)}</div>')


def _centered():
    return st.columns([1, 1.5, 1])[1]


# ------------------------------------------------------------- same device ----

def _start_local_game(names) -> None:
    st.session_state.engine = GameEngine(names)
    reset_turn_selection()


def _restart_local_game() -> None:
    old = st.session_state.engine
    names = [p.name for p in old.players]
    _start_local_game(names)
    # The other player starts the next game.
    st.session_state.engine.current = (old.current + 1) % len(names)


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
        render_top_bar(status, _leave_room, "Cancel game")
        _render_waiting_room(code)
    else:
        engine = RoomEngine(store, code, token, view.engine)
        my_turn = not view.engine.is_game_over() and view.engine.current == seat
        if my_turn and ss.get("was_my_turn") is False:
            st.toast("Your turn!", icon="\U0001F3B2")
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


def _render_waiting_room(code: str) -> None:
    with _centered():
        with st.container(border=True, key="card-wait"):
            _card_header("✉️", "Invite a friend",
                         "Send them this link. The game starts as soon as they join.")
            link, same_network_only = _invite_link(code)
            if link:
                st.code(link, language=None)
                if same_network_only:
                    st.caption("This link works for devices on the same Wi-Fi. To play over the internet, "
                               "deploy the app (see DEPLOYMENT_GUIDE.md).")
            st.html('<div class="ab-or">or share the game code</div><div class="ab-code">'
                    + "".join(f"<span>{escape(c)}</span>" for c in code)
                    + '</div><div class="ab-wait"><i></i>Waiting for your friend to join…</div>')


def _render_invite(store: RoomStore, code: str) -> None:
    """Join (or rejoin) the game named in the invite link."""
    st.html(f'<div class="ab-hero" style="margin-bottom:1.2rem">{brand_html(44)}</div>')
    with _centered():
        with st.container(border=True, key="card-invite"):
            if not store.exists(code):
                _card_header("\U0001F50D", "Game not found",
                             f"Game {code} has ended, or the server restarted. You can start a new one.")
                _home_button("Go to start", primary=True)
                return

            view = store.view(code)
            if not view.started:
                _card_header("\U0001F3B2", f"{view.names[0]} invited you to play",
                             "Enter your name to join. The game starts right away.")
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
                rejoin_text = "Created this game and lost the page? Rejoin as:"
            else:
                _card_header("\U0001F3B2", f"{view.names[0]} vs {view.names[1]}",
                             "This game already has two players.")
                rejoin_text = "Are you one of them? Rejoin as:"

            st.caption(rejoin_text)
            with st.container(horizontal=True):
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
