"""
Reactions and celebrations (owner, 2026-11-19).

Reactions: in an online game every seated player can send the table a short reaction
("Lucky! 🍀", "GG 🤝", ...), to everyone or, with 3+ players, aimed at one player. Each
screen shows it as a bubble for a few seconds.

Celebrations: fireworks when someone scores Abaka, sparkles for a straight, four of a kind
or the royal full house (1-1-1-2-2) scored on the first roll. Every screen of the game
shows them, the mover's own included, online and on one device.

Both come from the room's recent events (abaka.rooms: `RoomView.events`, kept in memory
only). A page shows an event once: from the moment it first draws it, for the event's
length. The animation continues across redraws (a negative animation delay), so a redraw
in the middle neither restarts it nor shows it again. Events from before this browser
opened the game, or older than STALE_SECONDS when first seen, are not shown.
"""

import time
from html import escape
from typing import Callable, List, Optional

import streamlit as st

from abaka.models import Category
from abaka.rooms import FIREWORKS, TooFast
from ui_components.i18n import t
from ui_components.moves import row_name

# Reaction key (abaka.rooms.REACTIONS) -> emoji and label. Labels go through t() when shown.
REACTIONS = {
    "lucky": ("\U0001F340", "Lucky!"),
    "nice": ("\U0001F44F", "Nice!"),
    "wow": ("\U0001F62E", "Wow!"),
    "ouch": ("\U0001F62C", "Ouch"),
    "hurry": ("⏳", "Hurry up"),
    "gg": ("\U0001F91D", "GG"),
    "haha": ("\U0001F602", "Haha"),
    "fire": ("\U0001F525", "On fire!"),
}

SECONDS = {"reaction": 3.5, FIREWORKS: 4.5, "sparkles": 2.8}  # how long each is on screen
STALE_SECONDS = 15.0   # an event first seen later than this after it happened is skipped
EVERYONE = -1          # the "to" picker's value for the whole table
_NOTE_KEY = "reaction_note"
_COLORS = ("#F59E0B", "#EF4444", "#10B981", "#3B82F6", "#A855F7", "#EC4899", "#FBBF24")


# ------------------------------------------------------------------ reactions ----

def render_reaction_bar(names: List[str], me: int, react: Callable[[str, Optional[int]], None]) -> None:
    """The row of reaction buttons, for a seated player of an online game. `react(key, to)` sends one."""
    ss = st.session_state
    note = ss.pop(_NOTE_KEY, None)
    if note:
        st.toast(t(note), icon="⏳")
    others = [i for i in range(len(names)) if i != me]
    with st.container(key="react-box"):
        if len(others) >= 2:
            st.segmented_control(
                t("Send to"), [EVERYONE] + others, default=EVERYONE, key="react-to",
                format_func=lambda i: t("Everyone") if i == EVERYONE else names[i],
                label_visibility="collapsed")
        with st.container(horizontal=True, key="react-row"):
            for key, (emoji, label) in REACTIONS.items():
                st.button(f"{emoji} {t(label)}", key=f"react-{key}", on_click=_send, args=(react, key))


def _send(react, key: str) -> None:
    """on_click: send the reaction. Too soon after the last one: a gentle note, nothing sent."""
    to = st.session_state.get("react-to")
    try:
        react(key, None if to in (None, EVERYONE) else to)
    except TooFast:
        st.session_state[_NOTE_KEY] = "One reaction every two seconds, please."
    except (ValueError, RuntimeError):
        pass  # the game is gone or changed; the page is redrawn as it is now


def _reaction_html(event: dict, names: List[str], me: Optional[int]) -> str:
    emoji, label = REACTIONS.get(event["reaction"], ("", event["reaction"]))
    seat, to = event["seat"], event.get("to")
    who = t("You") if seat == me else escape(_name(names, seat))
    if to is not None:
        who = t("{name} → you", name=who) if to == me else f"{who} → {escape(_name(names, to))}"
    mine = " mine" if to is not None and to == me else ""
    return (f'<div class="ab-bubble{mine}"><span class="ab-bubble-emoji">{emoji}</span>'
            f'<span class="ab-bubble-text"><b>{who}</b>{escape(t(label))}</span></div>')


def _name(names: List[str], seat: int) -> str:
    return names[seat] if 0 <= seat < len(names) else "?"


# ------------------------------------------------------------------ effects ----

def _effect_html(event: dict, names: List[str], me: Optional[int]) -> str:
    who = t("You") if _is_me(event, me) else escape(_name(names, event["seat"]))
    try:
        category = Category[event["category"]]
    except KeyError:
        category = None
    if event["effect"] == FIREWORKS:
        bursts = [(20, 30, 0.0), (78, 24, 0.35), (50, 18, 0.8), (30, 55, 1.3), (70, 52, 1.7), (50, 38, 2.2)]
        title, kind, spokes, reach = t("Abaka!"), "big", 18, 160
    else:
        bursts = [(35, 26, 0.0), (65, 22, 0.3)]
        if category == Category.FULL:
            title = t("Royal full house!")
        else:
            title = row_name(category) + "!" if category is not None else ""
        kind, spokes, reach = "small", 12, 80
    sparks = []
    for b, (x, y, delay) in enumerate(bursts):
        dots = "".join(
            f'<i style="--a:{round(360 * k / spokes)}deg;--c:{_COLORS[(b + k) % len(_COLORS)]}"></i>'
            for k in range(spokes))
        sparks.append(f'<div class="ab-burst" style="left:{x}%;top:{y}%;--bd:{delay}s;--r:{reach}px">{dots}</div>')
    sub = f"{who} · +{int(event['score'])}"
    if event["effect"] != FIREWORKS:
        sub += f" · {t('first roll')}"
    return (f'<div class="ab-fx-{kind}">{"".join(sparks)}'
            f'<div class="ab-fx-banner"><div class="ab-fx-title">{title}</div><div class="ab-fx-sub">{sub}</div></div>'
            "</div>")


def _is_me(event: dict, me: Optional[int]) -> bool:
    return me is not None and event.get("seat") == me


# ------------------------------------------------------------------ on screen ----

def render_events(code: str, events, names: List[str], me: Optional[int]) -> None:
    """
    Show the room's new reactions and effects on this page (see the module docstring).
    `me` is this browser's seat online, None on one device.
    """
    ss = st.session_state
    now = time.time()
    state = ss.get("fx_state")
    latest = events[-1]["id"] if events else 0
    if state is None or state["room"] != code:
        # This page has just opened the game: what happened before is not news.
        ss.fx_state = {"room": code, "after": latest, "first_seen": {}}
        return
    first_seen, layers = {}, []
    for event in events:
        if event["id"] <= state["after"]:
            continue
        seen_at = state["first_seen"].get(event["id"])
        if seen_at is None:
            if now - event["at"] > STALE_SECONDS:
                continue  # this page was away; old news
            seen_at = now
        first_seen[event["id"]] = seen_at
        kind = event["effect"] if event["kind"] == "effect" else "reaction"
        age = now - seen_at
        if age >= SECONDS.get(kind, 3.0):
            continue
        html = _reaction_html(event, names, me) if kind == "reaction" else _effect_html(event, names, me)
        layers.append((kind, f'<div class="ab-fx-item" style="--d:-{age:.2f}s">{html}</div>'))
    state["first_seen"] = first_seen
    if not layers:
        return
    effects = "".join(h for kind, h in layers if kind != "reaction")
    bubbles = "".join(h for kind, h in layers if kind == "reaction")
    st.html(f'<div class="ab-fx" aria-live="polite">{effects}'
            f'<div class="ab-bubbles">{bubbles}</div></div>')
