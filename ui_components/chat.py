"""
The chat of an online game (owner, 2026-11-19): a small card under the play panel with
the game's messages (latest at the bottom) and a box to write one.

Messages are kept by the room (abaka.rooms: RoomStore.say, RoomView.chat), in memory
only, and the move that ends the game deletes them. Players typed them, so they reach
the page escaped: html.escape in the card, i18n.md() in the toast that tells a player
about a new message.
"""

from html import escape
from typing import Callable, List

import streamlit as st

from abaka.rooms import MAX_MESSAGE_LENGTH
from ui_components.i18n import error, md, t

_TEXT_KEY = "chat-text"
_NOTE_KEY = "chat_note"


def render_chat(code: str, chat, names: List[str], me: int, say: Callable[[str], None]) -> None:
    """The chat card for the seated player `me`. `say(text)` sends a message."""
    ss = st.session_state
    note = ss.pop(_NOTE_KEY, None)
    if note:
        st.toast(error(note), icon="\U0001F4AC")
    _announce_new_messages(code, chat, names, me)
    with st.container(border=True, key="card-chat"):
        if chat:
            rows = "".join(
                f'<div class="ab-msg{" mine" if m["seat"] == me else ""}">'
                f'<b>{t("You") if m["seat"] == me else escape(_name(names, m["seat"]))}</b>'
                f'<span>{escape(m["text"])}</span></div>'
                for m in reversed(chat))  # the box lists them bottom up, so it opens at the latest
            body = f'<div class="ab-chat">{rows}</div>'
        else:
            body = f'<div class="ab-chat-empty">{t("No messages yet. Say hi!")}</div>'
        st.html(f'<div class="ab-chat-head">{t("Chat")}'
                f'<span>{t("Deleted when the game ends")}</span></div>{body}')
        with st.form("chat-form", clear_on_submit=True, border=False):
            with st.container(horizontal=True, key="chat-row", vertical_alignment="bottom"):
                st.text_input(t("Message"), placeholder=t("Message"), max_chars=MAX_MESSAGE_LENGTH,
                              key=_TEXT_KEY, label_visibility="collapsed")
                st.form_submit_button(t("Send"), icon=":material/send:", on_click=_send, args=(say,))


def _send(say) -> None:
    """on_click of Send: the form's text is in the session; the form clears it afterwards."""
    text = st.session_state.get(_TEXT_KEY) or ""
    try:
        say(text)
    except (ValueError, RuntimeError) as e:  # too fast (TooFast), or the game has just ended
        st.session_state[_NOTE_KEY] = str(e)


def _announce_new_messages(code: str, chat, names: List[str], me: int) -> None:
    """A toast for each message another player sent since this page last drew the chat, so a
    phone that shows the dice still hears about it. Nothing for older messages on opening."""
    ss = st.session_state
    latest = chat[-1]["id"] if chat else 0
    before = ss.get("chat_seen")
    ss.chat_seen = (code, latest)
    if before is None or before[0] != code:
        return
    new = [m for m in chat if m["id"] > before[1] and m["seat"] != me]
    for m in new[-3:]:
        text = m["text"] if len(m["text"]) <= 80 else m["text"][:79] + "…"
        st.toast(f"**{md(_name(names, m['seat']))}:** {md(text)}", icon="\U0001F4AC")


def _name(names: List[str], seat: int) -> str:
    return names[seat] if 0 <= seat < len(names) else "?"
