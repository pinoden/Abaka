"""
Dice: tap a die to mark it for a reroll, then press Reroll.

Each die is a Streamlit button (key `die-<i>`) drawn as a die face with CSS,
so it stays clickable and keyboard-accessible.
"""

import streamlit as st

from abaka.engine import GameEngine
from ui_components.style import ACCENT, die_uri

MAX_ROLLS = 3


def _toggle_die(i: int) -> None:
    picked = st.session_state.selected_dice
    if i in picked:
        picked.remove(i)
    else:
        picked.add(i)


def render_dice(engine: GameEngine, interactive: bool) -> None:
    """The five dice on the table. Only the player whose turn it is can pick them."""
    ss = st.session_state
    picked = ss.selected_dice if interactive else set()
    dice = list(engine.dice)

    css = []
    for i, d in enumerate(dice):
        rule = f'.st-key-die-{i} button {{ background-image: url("{die_uri(d.value, d.is_joker)}") !important;'
        if i in picked:
            rule += (f" transform: translateY(-8px); box-shadow: 0 0 0 3px {ACCENT},"
                     " 0 12px 22px rgba(79,70,229,.28) !important;")
        css.append(rule + " }")
        if i in picked:
            css.append(
                f'.st-key-die-{i} button::after {{ content: "\\21BB"; position: absolute; top: -10px; right: -10px;'
                f" width: 24px; height: 24px; border-radius: 50%; background: {ACCENT}; color: #fff;"
                " font-size: 15px; line-height: 24px; text-align: center; font-weight: 700; }"
            )
        if d.is_joker:
            css.append(f'.st-key-die-{i}::after {{ content: "{"wild joker" if d.value == 1 else "joker"}"; }}')
    css.extend(_roll_animation(dice))
    st.html("<style>" + "\n".join(css) + "</style>")

    with st.container(horizontal=True, key="dice-row"):
        for i, d in enumerate(dice):
            label = f"{d.value} (joker)" if d.is_joker else str(d.value)
            st.button(label, key=f"die-{i}", disabled=not interactive,
                      on_click=_toggle_die, args=(i,))


def _roll_animation(dice) -> list:
    """Spin the dice whose faces changed since this browser last drew them."""
    ss = st.session_state
    now = [(d.value, d.is_joker) for d in dice]
    before = ss.get("shown_dice")
    ss.shown_dice = now
    if before is not None and len(before) == len(now):
        changed = [i for i in range(len(now)) if now[i] != before[i]]
    else:
        changed = list(range(len(now)))
    if not changed:
        return []
    # Alternate between two identical animations so a die that changes twice in a row spins again.
    ss.roll_anim = "b" if ss.get("roll_anim") == "a" else "a"
    return [f".st-key-die-{i} button {{ animation: ab-roll-{ss.roll_anim} .45s ease-out; }}" for i in changed]


def render_dice_placeholder() -> None:
    st.session_state.shown_dice = None
    st.html('<div class="ab-dice-ph">' + "<div>?</div>" * 5 + "</div>")


def rolls_html(engine: GameEngine) -> str:
    used = MAX_ROLLS - engine.rolls_left if engine.dice else 0
    dots = "".join('<i class="used"></i>' if n < used else "<i></i>" for n in range(MAX_ROLLS))
    return f'<span class="ab-rolls" title="Rolls used">{dots}</span>'


def render_reroll(engine: GameEngine) -> None:
    """Hint plus the Reroll button for the player whose turn it is."""
    ss = st.session_state
    n = len(ss.selected_dice)
    if engine.rolls_left <= 0:
        st.caption("No rerolls left. Choose where to write this roll.")
        return
    left = "1 reroll" if engine.rolls_left == 1 else f"{engine.rolls_left} rerolls"
    if n == 0:
        st.caption(f"Tap the dice you want to roll again ({left} left), or choose a move below.")
    label = "Pick dice to reroll" if n == 0 else f"Reroll {n} {'die' if n == 1 else 'dice'}"
    if st.button(label, key="reroll", icon=":material/refresh:", disabled=n == 0,
                 type="primary" if n else "secondary", use_container_width=True):
        try:
            engine.reroll(sorted(ss.selected_dice))
        except (ValueError, RuntimeError, IndexError) as e:
            st.error(str(e))
        else:
            ss.selected_dice = set()
            st.rerun()
