"""
Choosing where to write the roll: Score or Cross out, pick a row, confirm.

Every option shows what it would score, and the confirm button says exactly
what will happen ("Score 46 in Full house").
"""

from typing import Optional

import streamlit as st

from abaka.engine import GameEngine
from ui_components.i18n import error, t
from ui_components.moves import Move, cross_options, score_options

SCORE, CROSS = "Score", "Cross out"  # values of the switch (and in widget keys); shown through t()


def _turn_key(engine: GameEngine) -> str:
    """Changes with every roll, so picks never carry over to different dice."""
    dice = "".join(f"{d.value}{'j' if d.is_joker else ''}" for d in engine.dice)
    return f"{engine.current}-{engine.rolls_left}-{dice}"


def _keep_an_action(key: str) -> None:
    # Clicking the selected segment would clear it; keep one action selected.
    if st.session_state.get(key) is None:
        st.session_state[key] = SCORE


def render_move_picker(engine: GameEngine) -> Optional[Move]:
    """Draw the picker. Returns the highlighted move (for the scoreboard preview)."""
    turn = _turn_key(engine)
    action_key = f"action-{turn}"
    st.html(f'<div class="ab-section-label">{t("Write this roll")}</div>')
    action = st.segmented_control(
        "Action", [SCORE, CROSS], default=SCORE, key=action_key, label_visibility="collapsed", format_func=t,
        on_change=_keep_an_action, args=(action_key,),
    ) or SCORE

    moves = score_options(engine) if action == SCORE else cross_options(engine)
    if not moves:
        if action == SCORE:
            st.info(t("Nothing can be scored with these dice. Reroll, or switch to **Cross out**."))
        else:
            st.info(t("There is nothing left to cross out."))
        return None

    pick = st.pills(
        "Row", list(range(len(moves))), format_func=lambda i: moves[i].label,
        key=f"pick-{action}-{turn}", label_visibility="collapsed",
    )
    move = moves[pick] if pick is not None else None

    label = move.action_text if move else (t("Choose a row above") if action == SCORE
                                           else t("Choose a row to cross out"))
    if st.button(label, key="confirm", type="primary", disabled=move is None, use_container_width=True,
                 icon=":material/close:" if action == CROSS else ":material/check:"):
        try:
            if move.cross:
                engine.record_cross(move.category, move.slot)
            else:
                engine.record_score(move.category, move.slot)
        except ValueError as e:
            st.error(error(str(e)))
        else:
            st.session_state.selected_dice = set()
            st.rerun()
    return move
