"""
Choosing where to write the roll: Score or Cross out, pick a row, confirm.

Every option shows what it would score, and the confirm button says exactly
what will happen ("Score 46 in Full house"). The option that adds the most to
the player's total is highlighted (bold, in gold: style.py), all of them on a tie.
"""

from typing import Optional

import streamlit as st

from abaka.engine import GameEngine
from ui_components.actions import run_action
from abaka.i18n import t
from abaka.moves import Move, cross_options, most_points, score_options

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

    # Labels are Markdown: the best options are bold, which the CSS also colours (style.py).
    best = set(most_points(moves))
    pick = st.pills(
        "Row", list(range(len(moves))), format_func=lambda i: f"**{moves[i].label}**" if i in best else moves[i].label,
        key=f"pick-{action}-{turn}", label_visibility="collapsed",
    )
    move = moves[pick] if pick is not None else None

    label = move.action_text if move else (t("Choose a row above") if action == SCORE
                                           else t("Choose a row to cross out"))
    # The move runs in an on_click callback (ui_components/actions.py): one script run, not two.
    args = None
    if move is not None:
        args = (engine.record_cross if move.cross else engine.record_score, move.category, move.slot)
    st.button(label, key="confirm", type="primary", disabled=move is None, use_container_width=True,
              icon=":material/close:" if action == CROSS else ":material/check:",
              on_click=run_action if move is not None else None, args=args)
    return move
