"""
The game screen: top bar, play panel (dice and moves) and scoreboard.

The same screen serves both modes. `engine` is either a local GameEngine
(same device) or a RoomEngine backed by a shared online room; the turn phase
is read from the engine itself (no dice yet = waiting for the first roll), so
both players of an online game always see the same thing.
"""

from html import escape
from typing import Callable, Optional

import streamlit as st

from abaka.engine import GameEngine
from ui_components.dice import render_dice, render_dice_placeholder, render_reroll, rolls_html
from ui_components.move_selection import render_move_picker
from ui_components.rules import rules_dialog
from ui_components.scoreboard import render_scoreboard
from ui_components.style import brand_html, chip


def initialize_session_state() -> None:
    ss = st.session_state
    ss.setdefault("engine", None)        # local (same device) game, if any
    ss.setdefault("selected_dice", set())


def reset_turn_selection() -> None:
    """Forget dice picks left over from an earlier turn."""
    st.session_state.selected_dice = set()


def render_top_bar(status_html: str, on_leave: Optional[Callable[[], None]] = None,
                   leave_label: str = "Leave game") -> None:
    with st.container(horizontal=True, vertical_alignment="center", key="topbar"):
        st.html(f'<div class="ab-topbar">{brand_html()}{status_html}</div>')
        with st.popover("Menu", icon=":material/menu:", width="content"):
            if st.button("How to play", icon=":material/help:", key="menu-rules", use_container_width=True):
                rules_dialog()
            if on_leave is not None and st.button(leave_label, icon=":material/logout:", key="menu-leave",
                                                  use_container_width=True):
                on_leave()
                st.rerun()


def render_game(engine: GameEngine, *, me: Optional[int] = None, status_html: str = "",
                on_play_again: Callable[[], None], on_leave: Callable[[], None],
                leave_label: str) -> None:
    """
    Args:
        engine: A GameEngine, or anything shaped like one (see abaka.rooms.RoomEngine).
        me: This browser's seat in an online game; None when everyone shares this screen.
    """
    render_top_bar(status_html, on_leave, leave_label)
    left, right = st.columns([5, 7], gap="large")
    with left:
        with st.container(border=True, key="card-play"):
            if engine.is_game_over():
                _render_results(engine, me, on_play_again, on_leave, leave_label)
                target = None
            else:
                target = _render_play_panel(engine, me)
    with right:
        with st.container(border=True, key="card-board"):
            render_scoreboard(engine, me=me, target=target)


def _render_play_panel(engine: GameEngine, me: Optional[int]):
    player = engine.players[engine.current]
    name = escape(player.name)
    can_act = me is None or engine.current == me

    if me is not None and can_act:
        title = '<div class="ab-turn-title mine">Your turn</div>'
    else:
        title = f'<div class="ab-turn-title">{name}’s turn</div>'
    if engine.dice:
        roll_no = 3 - engine.rolls_left
        sub = f"{rolls_html(engine)} Roll {roll_no} of 3"
        if engine.first_roll:
            sub += " " + chip("First roll: combinations score double", "gold")
    elif can_act:
        sub = "Roll the dice to start the turn."
    else:
        sub = f"Waiting for {name} to roll…"
    st.html(f'{title}<div class="ab-turn-sub">{sub}</div>')

    if not engine.dice:
        render_dice_placeholder()
        if can_act and st.button("Roll dice", key="roll", type="primary", icon=":material/casino:",
                                 use_container_width=True):
            try:
                engine.start_turn()
            except ValueError as e:
                st.error(str(e))
            else:
                reset_turn_selection()
                st.rerun()
        return None

    render_dice(engine, interactive=can_act)
    if not can_act:
        st.caption(f"{player.name} is choosing a move. You will see it here as it happens.")
        return None
    render_reroll(engine)
    return render_move_picker(engine)


def _render_results(engine: GameEngine, me: Optional[int], on_play_again: Callable[[], None],
                    on_leave: Callable[[], None], leave_label: str) -> None:
    scores = [(p.name, p.calculate_score(), i) for i, p in enumerate(engine.players)]
    best = max(s for _, s, _ in scores)
    winners = [i for _, s, i in scores if s == best]
    if len(winners) > 1:
        headline = "It’s a draw!"
    elif me is not None and winners[0] == me:
        headline = "You win!"
    else:
        headline = f"{escape(engine.players[winners[0]].name)} wins!"

    rows = "".join(
        f'<div class="{"win" if s == best else ""}"><span>{escape(n)}</span><span>{s}</span></div>'
        for n, s, _ in sorted(scores, key=lambda t: -t[1])
    )
    st.html(f'<div class="ab-result"><div class="trophy">\U0001F3C6</div><h2>{headline}</h2>'
            f'<div class="ab-scores">{rows}</div></div>')
    if st.button("Play again", key="big-again", type="primary", icon=":material/replay:",
                 use_container_width=True):
        reset_turn_selection()
        on_play_again()
        st.rerun()
    if st.button(leave_label, key="results-leave", use_container_width=True):
        on_leave()
        st.rerun()
