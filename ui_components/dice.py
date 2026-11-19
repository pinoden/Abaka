"""
Dice: tap a die to mark it for a reroll, then press Reroll.

Each die is a Streamlit button (key `die-<i>`) drawn as a die face with CSS,
so it stays clickable and keyboard-accessible.

Online, the other players see the picked dice too (RoomStore.pick, polled about once
a second), and after a reroll exactly the dice that were rolled again spin.
"""

import streamlit as st

from abaka.engine import GameEngine
from ui_components.actions import reroll_all, reroll_picked
from ui_components.i18n import reroll_dice, rerolls_left, t
from ui_components.style import ACCENT, die_uri

MAX_ROLLS = 3


def _toggle_die(i: int, engine) -> None:
    picked = st.session_state.selected_dice
    if i in picked:
        picked.remove(i)
    else:
        picked.add(i)
    share = getattr(engine, "pick", None)  # an online game: show the other players
    if share is not None:
        try:
            share(sorted(picked))
        except (ValueError, RuntimeError):
            pass  # only a display; the page is redrawn with the game as it is now


def render_dice(engine: GameEngine, interactive: bool) -> None:
    """
    The active player can pick dice while a reroll remains. The other players of an online
    game see the dice picked so far, marked the same way.
    """
    can_pick = engine.rolls_left > 0
    interactive = interactive and can_pick
    ss = st.session_state
    if interactive:
        picked = ss.selected_dice
    else:
        picked = set(getattr(engine, "picked", ()) or ()) if can_pick else set()
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
            css.append(f'.st-key-die-{i}::after {{ content: "{t("wild joker") if d.value == 1 else t("joker")}"; }}')
    css.extend(_roll_animation(engine, dice))
    st.html("<style>" + "\n".join(css) + "</style>")

    with st.container(horizontal=True, key="dice-row"):
        for i, d in enumerate(dice):
            label = t("{value} (joker)", value=d.value) if d.is_joker else str(d.value)
            st.button(label, key=f"die-{i}", disabled=not interactive,
                      on_click=_toggle_die if interactive else None, args=(i, engine) if interactive else None)


def _roll_animation(engine, dice) -> list:
    """
    Spin the dice that were rolled since this browser last drew them: after a reroll the
    dice rolled again (also those that landed on the same face), otherwise the dice whose
    faces changed.
    """
    ss = st.session_state
    now = [(d.value, d.is_joker) for d in dice]
    roll = (engine.current, engine.rolls_left)
    before, before_roll = ss.get("shown_dice"), ss.get("shown_roll")
    ss.shown_dice, ss.shown_roll = now, roll
    rerolled = [i for i in (getattr(engine, "rerolled", ()) or ()) if i < len(now)]
    if before is not None and len(before) == len(now):
        changed = [i for i in range(len(now)) if now[i] != before[i]]
        if rerolled and roll != before_roll:
            changed = sorted(set(changed) | set(rerolled))
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
    return f'<span class="ab-rolls" title="{t("Rolls used")}">{dots}</span>'


def render_reroll(engine: GameEngine) -> None:
    """Hint plus the Reroll buttons for the player whose turn it is."""
    ss = st.session_state
    n = len(ss.selected_dice)
    if engine.rolls_left <= 0:
        st.caption(t("No rerolls left. Choose where to write this roll."))
        return
    left = rerolls_left(engine.rolls_left)
    if n == 0:
        st.caption(t("Tap the dice you want to roll again ({left} left), or choose a move below.", left=left))

    # The moves run in on_click callbacks (ui_components/actions.py): one script run per move.
    # A button whose label and key stay the same after its move would hand a second, fast tap
    # the next page's move, so "Reroll all" has the rerolls left in its key ("Reroll 2 dice"
    # becomes "Reroll picked" after its reroll anyway).
    with st.container(horizontal=True, key="reroll-row"):
        label = t("Reroll picked") if n == 0 else reroll_dice(n)
        st.button(label, key="reroll", icon=":material/refresh:", disabled=n == 0,
                  type="primary" if n else "secondary", width="stretch", on_click=reroll_picked, args=(engine,))
        st.button(t("Reroll all"), key=f"reroll-all-{engine.rolls_left}", icon=":material/casino:", width="stretch",
                  on_click=reroll_all, args=(engine,))
