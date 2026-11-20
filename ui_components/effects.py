"""
Reactions and celebrations (owner, 2026-11-19).

Reactions: in an online game every seated player can send the table a short reaction
("Lucky! 🍀", "GG 🤝", ...), to everyone or, with 3+ players, aimed at one player. Each
screen shows it as a bubble for a few seconds.

Celebrations (owner, 2026-11-19), as the dice land, whatever the player then writes:
bigger fireworks for Abaka or the royal full house (1-1-1-2-2) on the first roll, fireworks
for either after a reroll, and sparkles for a straight, a full house or four of a kind on
the first roll. Sparkles also when a move earns a row or column bonus. Every screen of the
game shows them, the mover's own included, online and on one device. The rules of what
earns which are in abaka.rooms._celebration.

Both come from the room's recent events (abaka.rooms: `RoomView.events`, kept in memory
only). A page shows an event once: from the moment it first draws it, for the event's
length. The animation continues across redraws (a negative animation delay), so a redraw
in the middle neither restarts it nor shows it again. Events from before this browser
opened the game, or older than STALE_SECONDS when first seen, are not shown.
"""

import time
from html import escape
from typing import Callable, List, Optional, Tuple

import streamlit as st

from abaka.models import Category
from abaka.rooms import FIREWORKS, GRAND_FIREWORKS, SPARKLES, TooFast
from abaka.i18n import t
from abaka.moves import row_name

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

SECONDS = {"reaction": 3.5, GRAND_FIREWORKS: 6.0, FIREWORKS: 4.5, SPARKLES: 2.8}  # how long each is on screen
LEAD_IN_SECONDS = 0.45  # a throw's effect waits for the dice to land (their spin in dice.py takes .45s)
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

# Effect -> CSS class, and its bursts: (left %, top %, delay in s). Bigger fireworks come in
# three waves over the whole screen, with a flash and a rain of sparkles.
_LOOKS = {
    GRAND_FIREWORKS: ("grand", 24, 220, [
        (50, 40, 0.0), (20, 28, 0.15), (80, 26, 0.3),
        (32, 58, 1.0), (68, 55, 1.2), (50, 20, 1.4), (12, 50, 1.6), (88, 48, 1.6),
        (26, 34, 2.2), (74, 36, 2.4), (50, 62, 2.7), (40, 18, 3.0), (60, 30, 3.2)]),
    FIREWORKS: ("big", 18, 160, [(20, 30, 0.0), (78, 24, 0.35), (50, 18, 0.8), (30, 55, 1.3), (70, 52, 1.7),
                                 (50, 38, 2.2)]),
    SPARKLES: ("small", 12, 80, [(35, 26, 0.0), (65, 22, 0.3)]),
}
_COLUMNS = ("I", "II", "III")
_STARS = 28  # the rain of sparkles in the bigger fireworks


def _effect_html(event: dict, names: List[str], me: Optional[int]) -> str:
    who = t("You") if _is_me(event, me) else escape(_name(names, event["seat"]))
    kind, spokes, reach, bursts = _LOOKS.get(event["effect"], _LOOKS[SPARKLES])
    title, sub = _effect_text(event, who)
    layers = []
    for b, (x, y, delay) in enumerate(bursts):
        dots = "".join(
            f'<i style="--a:{round(360 * k / spokes)}deg;--c:{_COLORS[(b + k) % len(_COLORS)]}"></i>'
            for k in range(spokes))
        layers.append(f'<div class="ab-burst" style="left:{x}%;top:{y}%;--bd:{delay}s;--r:{reach}px">{dots}</div>')
    if kind == "grand":
        layers.insert(0, '<div class="ab-flash"></div>')
        layers.extend(
            f'<b class="ab-star" style="left:{(k * 37 + 5) % 100}%;--bd:{0.3 + (k * 0.41) % 3.2:.2f}s;'
            f'--s:{12 + (k * 7) % 12}px;--c:{_COLORS[k % len(_COLORS)]}">✦</b>' for k in range(_STARS))
    return (f'<div class="ab-fx-{kind}">{"".join(layers)}'
            f'<div class="ab-fx-banner"><div class="ab-fx-title">{title}</div><div class="ab-fx-sub">{sub}</div></div>'
            "</div>")


def _effect_text(event: dict, who: str) -> Tuple[str, str]:
    """The banner: title and the line under it. `who` is already escaped."""
    what = event.get("what") or event.get("category") or ""
    if what == "BONUS":
        parts = [t("{row} row +{points}", row=escape(_row(name)), points=int(points))
                 for name, points in event.get("rows", ())]
        parts += [t("column {n} +{points}", n=_COLUMNS[col] if 0 <= col < 3 else "?", points=int(points))
                  for col, points in event.get("columns", ())]
        return (t("Bonus!") if len(parts) == 1 else t("Bonuses!")), " · ".join([who] + parts)
    if what == "ABAKA":
        title = t("Abaka!")
    elif what == "ROYAL":
        title = t("Royal full house!")
    else:
        title = escape(_row(what)) + "!"
    return title, who + (f" · {t('first roll')}" if event.get("first") else "")


def _row(name: str) -> str:
    try:
        return row_name(Category[name])
    except KeyError:
        return name


def _lead_in(event: dict) -> float:
    """A throw's effect starts as the dice land; a bonus at once (the move clears the dice)."""
    return LEAD_IN_SECONDS if event["kind"] == "effect" and event.get("what") != "BONUS" else 0.0


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
        ss.fx_state = {"room": code, "after": latest, "starts": {}}
        return
    # When each event starts on this page. An effect waits for the one before it to finish, so
    # two never overlap (a full house thrown and, a second later, the bonus it earned).
    known, starts, layers = state.get("starts", {}), {}, []
    effects_end = 0.0
    for event in events:
        if event["id"] <= state["after"]:
            continue
        kind = event["effect"] if event["kind"] == "effect" else "reaction"
        length = SECONDS.get(kind, 3.0)
        start = known.get(event["id"])
        if start is None:
            if now - event["at"] > STALE_SECONDS:
                continue  # this page was away; old news
            start = now + _lead_in(event)
            if kind != "reaction":
                start = max(start, effects_end)
        if kind != "reaction":
            effects_end = max(effects_end, start + length)
        starts[event["id"]] = start
        if now - start >= length:
            continue
        html = _reaction_html(event, names, me) if kind == "reaction" else _effect_html(event, names, me)
        # --d is the animation delay: the wait still ahead, or minus the time already shown.
        layers.append((kind, f'<div class="ab-fx-item" style="--d:{start - now:.2f}s">{html}</div>'))
    state["starts"] = starts
    if not layers:
        return
    effects = "".join(h for kind, h in layers if kind != "reaction")
    bubbles = "".join(h for kind, h in layers if kind == "reaction")
    st.html(f'<div class="ab-fx" aria-live="polite">{effects}'
            f'<div class="ab-bubbles">{bubbles}</div></div>')
