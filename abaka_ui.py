"""
Abaka — Streamlit app.

Two ways to play:
  * Same screen: two players share one browser (hotseat).
  * Online: each player uses their own browser. The game lives in a shared
    room inside this server process (see abaka/rooms.py); browsers send moves
    to it and poll it, so both players see every roll and score as it happens.
"""

import socket
from urllib.parse import urlsplit

import streamlit as st

from abaka.rooms import RoomEngine, RoomError, RoomStore, normalize_code
from ui_components.main_ui import (
    initialize_session_state,
    render_main_ui,
    render_new_game_setup,
    reset_turn_selection,
)
from ui_components.sidebar import render_sidebar

MODE_LOCAL = "Same screen"
MODE_ONLINE = "Online (2 players)"
POLL_SECONDS = 1.0  # how often a browser checks the room for the other player's moves


@st.cache_resource
def get_store() -> RoomStore:
    """The one RoomStore shared by every browser session of this server."""
    return RoomStore()


def main():
    """Main application entry point."""
    st.set_page_config(page_title="Abaka", page_icon="🎲", layout="wide")

    initialize_session_state()
    ss = st.session_state
    ss.setdefault("room_code", None)   # online room this browser is seated in
    ss.setdefault("seat_token", None)  # proves which seat this browser controls
    ss.setdefault("lobby_notice", None)

    invited_code = normalize_code(st.query_params.get("room", ""))

    with st.sidebar:
        st.header("Game Mode")
        # An invite link (?room=CODE) opens straight into online mode.
        mode = st.radio(
            "Select Mode",
            [MODE_LOCAL, MODE_ONLINE],
            index=1 if (invited_code or ss.room_code) else 0,
            key="game_mode",
        )
        if mode == MODE_LOCAL:
            render_sidebar()

    if mode == MODE_LOCAL:
        if ss.engine is None:
            render_new_game_setup()
        else:
            render_main_ui(ss.engine, on_new_game=_end_local_game)
    else:
        try:
            _render_online(get_store(), invited_code)
        except RoomError as e:
            # The room vanished mid-render (expired, or the server restarted).
            _leave_room(notice=str(e))
            st.rerun()


def _end_local_game() -> None:
    st.session_state.engine = None


# ---------------------------------------------------------------- online ----

def _render_online(store: RoomStore, invited_code: str) -> None:
    ss = st.session_state

    if ss.room_code and store.seat_of(ss.room_code, ss.seat_token) is None:
        if store.exists(ss.room_code):
            notice = ("This game was opened in another tab or device, "
                      "so this tab no longer controls it.")
        else:
            notice = "That game is no longer available."
        _leave_room(notice=notice, keep_link=store.exists(ss.room_code))

    if not ss.room_code:
        _render_lobby(store, invited_code)
        return

    code, token = ss.room_code, ss.seat_token
    view = store.view(code)
    seat = store.seat_of(code, token)

    with st.sidebar:
        st.divider()
        st.subheader("Online game")
        st.markdown(f"Game code: **`{code}`**")
        for i, name in enumerate(view.names):
            st.write(f"{'🟢' if i == seat else '⚪'} {name}{' (you)' if i == seat else ''}")
        if st.button("Leave game"):
            _leave_room()
            st.rerun()

    if not view.started:
        _render_waiting_room(code)
    else:
        engine = RoomEngine(store, code, token, view.engine)
        game_over = view.engine.is_game_over()
        my_turn = (not game_over) and view.engine.current == seat
        if not game_over:
            current_name = view.engine.players[view.engine.current].name
            if my_turn:
                st.success(f"🟢 **YOUR TURN!** ({current_name})")
            else:
                st.error(f"🔴 **WAITING FOR OPPONENT...** ({current_name}'s turn)")

        def rematch() -> None:
            try:
                store.rematch(code, token)
            except RoomError:
                pass  # the other player already started the next game

        render_main_ui(engine, read_only=not my_turn, on_new_game=rematch)

    _watch_room(code, view.version)


@st.fragment(run_every=POLL_SECONDS)
def _watch_room(code: str, seen_version: int) -> None:
    """Re-draw the page as soon as the shared room changes (the other player moved)."""
    if get_store().version(code) != seen_version:
        st.rerun()


def _render_waiting_room(code: str) -> None:
    st.title("Abaka Online")
    st.subheader("Waiting for the second player…")
    st.markdown(f"Game code: **`{code}`**")

    link, same_network_only = _invite_link(code)
    if link:
        st.write("Send this link to your friend:")
        st.code(link, language=None)
        if same_network_only:
            st.caption(
                "You opened the app as localhost, so this link uses your computer's "
                "network address and only works for someone on the same Wi-Fi/network. "
                "To play over the internet, deploy the app (see DEPLOYMENT_GUIDE.md)."
            )
    else:
        st.write("Ask your friend to open this app, choose **Online (2 players)** "
                 "and enter the game code.")
    st.caption("The game starts automatically when they join.")


def _render_lobby(store: RoomStore, invited_code: str) -> None:
    ss = st.session_state
    st.title("Abaka Online")

    if ss.lobby_notice:
        st.warning(ss.lobby_notice)
        ss.lobby_notice = None

    container = st.container()
    if invited_code:
        if store.exists(invited_code):
            _render_invite(store, invited_code)
            # Keep the invite front and centre; other options stay out of the way.
            container = st.expander("Start or find a different game instead")
        else:
            st.warning(
                f"Game **{invited_code}** was not found. It may have ended, "
                "or the server may have restarted. Start a new one below."
            )

    create_col, join_col = container.columns(2)
    with create_col:
        with st.form("create_game"):
            st.markdown("**Create a game**")
            name = st.text_input("Your name", key="create_name", max_chars=20)
            if st.form_submit_button("Create game", type="primary"):
                code, token = store.create(name)
                _enter_room(code, token)
                st.rerun()
    with join_col:
        with st.form("find_game"):
            st.markdown("**Have a game code?**")
            typed = st.text_input("Game code", key="find_code", max_chars=8)
            if st.form_submit_button("Find game"):
                typed_code = normalize_code(typed)
                if store.exists(typed_code):
                    st.query_params["room"] = typed_code
                    st.rerun()
                else:
                    st.error("Game not found. Check the code and try again.")


def _render_invite(store: RoomStore, code: str) -> None:
    """Join (or rejoin) the game named in the invite link."""
    view = store.view(code)

    if not view.started:
        st.subheader(f"{view.names[0]} invited you to play")
        with st.form("join_game"):
            name = st.text_input("Your name", key="join_name", max_chars=20)
            if st.form_submit_button("Join game", type="primary"):
                try:
                    token = store.join(code, name)
                except RoomError as e:
                    st.error(str(e))
                else:
                    _enter_room(code, token)
                    st.rerun()
        rejoin_label = "Created this game and lost the page? Rejoin as:"
    else:
        st.subheader(f"Game {code}: {view.names[0]} vs {view.names[1]}")
        st.write("This game already has two players.")
        rejoin_label = "If you are one of them (page refreshed, new device), rejoin as:"

    st.caption(rejoin_label)
    cols = st.columns(len(view.names) + 2)
    for i, name in enumerate(view.names):
        if cols[i].button(name, key=f"rejoin_{i}"):
            try:
                token = store.reclaim(code, i)
            except RoomError as e:
                st.error(str(e))
            else:
                _enter_room(code, token)
                st.rerun()


def _enter_room(code: str, token: str) -> None:
    ss = st.session_state
    ss.room_code = code
    ss.seat_token = token
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
        parts = urlsplit(st.context.url)  # Streamlit 1.45+
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
