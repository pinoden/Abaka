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
from ui_components.actions import run_action, show_action_error
from ui_components.dice import render_dice, render_dice_placeholder, render_reroll, rolls_html
from abaka.i18n import LANGUAGES, and_join, md, picked_dice_note, rerolled_dice_note, t
from ui_components.move_selection import render_move_picker
from ui_components.races import render_races
from ui_components.rules import rules_dialog
from ui_components.scoreboard import render_scoreboard
from ui_components.style import brand_html, chip, die_uri


def initialize_session_state() -> None:
    ss = st.session_state
    ss.setdefault("engine", None)        # local (same device) game, if any
    ss.setdefault("selected_dice", set())


def reset_turn_selection() -> None:
    """Forget dice picks left over from an earlier turn."""
    st.session_state.selected_dice = set()


def _language_picked(key: str) -> None:
    choice = st.session_state.get(key)
    if choice in LANGUAGES:
        st.session_state.lang = choice
        st.query_params["lang"] = choice  # a reload keeps the language


def render_language_switch(key: str) -> None:
    """EN / RU. Another switch may have changed the language, so show the current one first."""
    ss = st.session_state
    ss[key] = ss.get("lang", "en")
    st.segmented_control(t("Language"), list(LANGUAGES), format_func=str.upper, key=key,
                         label_visibility="collapsed", on_change=_language_picked, args=(key,))


def render_top_bar(status_html: str, on_leave: Optional[Callable[[], None]] = None,
                   leave_label: str = "Leave game") -> None:
    with st.container(horizontal=True, vertical_alignment="center", key="topbar"):
        st.html(f'<div class="ab-topbar">{brand_html()}{status_html}</div>')
        with st.popover(t("Menu"), icon=":material/menu:", width="content"):
            render_language_switch("lang-menu")
            if st.button(t("How to play"), icon=":material/help:", key="menu-rules", use_container_width=True):
                rules_dialog()
            if on_leave is not None and st.button(leave_label, icon=":material/logout:", key="menu-leave",
                                                  use_container_width=True):
                on_leave()
                st.rerun()


def render_game(engine: GameEngine, *, me: Optional[int] = None, status_html: str = "",
                on_play_again: Callable[[], None], on_leave: Callable[[], None],
                leave_label: str, board_note_html: str = "", results_note_html: str = "",
                after_results: Optional[Callable[[], None]] = None,
                below_play: Optional[Callable[[], None]] = None,
                after_play_card: Optional[Callable[[], None]] = None) -> None:
    """
    Args:
        engine: A GameEngine, or anything shaped like one (see abaka.rooms.RoomEngine).
        me: This browser's seat in an online game; None when everyone shares this screen.
        board_note_html: shown under the scoreboard (the running score at this table).
        results_note_html: shown on the results screen under the scores (a club game's ratings).
        after_results: draws more buttons on the results screen, under "Play again".
        below_play: draws more at the foot of the play card (the reactions of an online game).
        after_play_card: draws a card under the play card (the chat of an online game).
    """
    render_top_bar(status_html, on_leave, leave_label)
    # Up to 4 players fit the usual layout; with 5 the scoreboard gets more room and the dice shrink a little.
    # With 3 players the two cards stack on screens up to 1000px wide, with 4 or 5 up to 1180px
    # (style.py), so the scoreboard does not scroll sideways there.
    n = len(engine.players)
    wide_board = n >= 5
    with st.container(key="game-many" if n >= 4 else ("game-three" if n == 3 else "game")):
        left, right = st.columns([4, 8] if wide_board else [5, 7], gap="large")
        with left:
            with st.container(border=True, key="card-play"):
                if engine.is_game_over():
                    _render_results(engine, me, on_play_again, on_leave, leave_label, results_note_html,
                                    after_results)
                    target = None
                else:
                    target = _render_play_panel(engine, me)
                    render_races(engine, me)
                if below_play is not None:
                    below_play()
            if after_play_card is not None:
                after_play_card()
        with right:
            with st.container(border=True, key="card-board"):
                render_scoreboard(engine, me=me, target=target)
                if board_note_html:
                    st.html(board_note_html)


def _render_play_panel(engine: GameEngine, me: Optional[int]):
    show_action_error()
    if getattr(engine, "choosing_first_player", False):
        _render_starting_throw(engine, me)
        return None

    player = engine.players[engine.current]
    name = escape(player.name)
    can_act = me is None or engine.current == me

    if me is not None and can_act:
        title = f'<div class="ab-turn-title mine">{t("Your turn")}</div>'
    else:
        title = f'<div class="ab-turn-title">{t("{name}’s turn", name=name)}</div>'
    if engine.dice:
        roll_no = 3 - engine.rolls_left
        sub = f"{rolls_html(engine)} {t('Roll {n} of 3', n=roll_no)}"
        if engine.first_roll:
            sub += " " + chip(t("First roll: combinations score double"), "gold")
    elif can_act:
        sub = t("Roll the dice to start the turn.")
    else:
        sub = t("Waiting for {name} to roll…", name=name)
    st.html(f'{title}<div class="ab-turn-sub">{sub}</div>{_starter_summary(engine, me)}')

    if not engine.dice:
        render_dice_placeholder()
        if can_act:
            st.button(t("Roll dice"), key="roll", type="primary", icon=":material/casino:",
                      use_container_width=True, on_click=run_action, args=(engine.start_turn,))
        return None

    render_dice(engine, interactive=can_act)
    if not can_act:
        picked = len(getattr(engine, "picked", ()) or ()) if engine.rolls_left > 0 else 0
        rerolled = len(getattr(engine, "rerolled", ()) or ())
        if picked:
            note = picked_dice_note(md(player.name), picked)
        elif rerolled:
            note = rerolled_dice_note(md(player.name), rerolled)
        else:
            note = t("{name} is choosing a move. You will see it here as it happens.", name=md(player.name))
        st.caption(note)
        return None
    render_reroll(engine)
    return render_move_picker(engine)


def _render_starting_throw(engine: GameEngine, me: Optional[int]) -> None:
    """Before the first round: everyone throws all five dice, and the lowest total goes first."""
    thrower = engine.players[engine.current]
    can_act = me is None or engine.current == me
    if engine.throw_round_no == 1:
        sub = t("Everyone throws all five dice. The lowest total goes first.")
    else:
        tied = and_join(escape(engine.players[p].name) for p in engine.throw_round)
        sub = t("A tie for the lowest total: {names} throw again.", names=tied)
    st.html(f'<div class="ab-turn-title">{t("Who goes first?")}</div><div class="ab-turn-sub">{sub}</div>'
            + _throws_html(engine, me))
    if not can_act:
        st.caption(t("Waiting for {name} to throw…", name=md(thrower.name)))
        return
    label = t("Throw the dice") if me is not None else t("Throw for {name}", name=md(thrower.name))
    st.button(label, key="start-throw", type="primary", icon=":material/casino:", use_container_width=True,
              on_click=run_action, args=(engine.throw_for_start,))


def _throws_html(engine: GameEngine, me: Optional[int]) -> str:
    """One line per player: their latest starting throw and its total, or who throws next."""
    latest = {throw["player"]: throw for throw in engine.starting_throws}
    rows = []
    for i, p in enumerate(engine.players):
        in_round = i in engine.throw_round
        throw = latest.get(i)
        if throw is not None and (throw["round"] == engine.throw_round_no or not in_round):
            faces = "".join(f'<img src="{die_uri(v, j)}" alt="{v}">' for v, j in throw["dice"])
            result = f'<span class="ab-throw-dice">{faces}</span><b>{throw["total"]}</b>'
        else:
            waiting = t("throws next") if i == engine.current else t("waiting")
            result = f'<span class="ab-throw-wait">{waiting}</span>'
        cls = "next" if i == engine.current else ("out" if engine.choosing_first_player and not in_round else "")
        you = f'<span class="ab-you">{t("You")}</span>' if i == me else ""
        rows.append(f'<div class="ab-throw {cls}"><span class="ab-throw-name">{escape(p.name)}{you}</span>'
                    f'<span class="ab-throw-res">{result}</span></div>')
    return f'<div class="ab-throws">{"".join(rows)}</div>'


def _starter_summary(engine: GameEngine, me: Optional[int]) -> str:
    """Until the first move: who won the starting throw, and everyone's starting throws.

    The throws stay on screen after the decision, so every player's total stays visible
    (the last thrower's included) until the game moves on.
    """
    first = getattr(engine, "first_player", None)
    if first is None or engine.last_move is not None:
        return ""
    total = [throw["total"] for throw in engine.starting_throws if throw["player"] == first][-1]
    if first == me:
        note = t("You threw the lowest ({total}) and go first.", total=total)
    else:
        note = t("{name} threw the lowest ({total}) and goes first.", name=escape(engine.players[first].name),
                 total=total)
    return f'<div class="ab-start-note">{note}</div>' + _throws_html(engine, me)


def _render_results(engine: GameEngine, me: Optional[int], on_play_again: Callable[[], None],
                    on_leave: Callable[[], None], leave_label: str, note_html: str = "",
                    after_results: Optional[Callable[[], None]] = None) -> None:
    scores = [(p.name, p.calculate_score(), i) for i, p in enumerate(engine.players)]
    best = max(s for _, s, _ in scores)
    winners = [i for _, s, i in scores if s == best]
    if len(winners) > 1:
        headline = t("It’s a draw!")
    elif me is not None and winners[0] == me:
        headline = t("You win!")
    else:
        headline = t("{name} wins!", name=escape(engine.players[winners[0]].name))

    rows = "".join(
        f'<div class="{"win" if s == best else ""}"><span>{escape(n)}</span><span>{s}</span></div>'
        for n, s, _ in sorted(scores, key=lambda row: -row[1])
    )
    trophy = '<div class="trophy">\U0001F3C6</div>' if len(winners) == 1 and me == winners[0] else ""
    st.html(f'<div class="ab-result">{trophy}<h2>{headline}</h2>'
            f'<div class="ab-scores">{rows}</div></div>{note_html}')
    if st.button(t("Play again"), key="big-again", type="primary", icon=":material/replay:",
                 use_container_width=True):
        reset_turn_selection()
        on_play_again()
        st.rerun()
    if after_results is not None:
        after_results()
    if st.button(leave_label, key="results-leave", use_container_width=True):
        on_leave()
        st.rerun()
