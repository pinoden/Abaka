"""
Main UI orchestrator for Abaka game interface.
Coordinates all components and handles the main game flow.

The same screen serves both modes. `engine` is either a local GameEngine
(hotseat) or a RoomEngine backed by a shared online room; the turn phase is
read from the engine itself (no dice yet = waiting for the first roll), so
both players of an online game always see the same thing.
"""

from typing import Callable, Optional

import streamlit as st
from abaka.engine import GameEngine
from ui_components.scoreboard import render_scoreboard
from ui_components.dice import render_dice_section
from ui_components.move_selection import render_move_selection


def render_main_ui(engine: GameEngine, read_only: bool = False,
                   on_new_game: Optional[Callable[[], None]] = None) -> None:
    """
    Render the main game interface.

    Args:
        engine: A GameEngine, or anything shaped like one (see abaka.rooms.RoomEngine).
        read_only: True while it is the other player's turn in an online game.
        on_new_game: Called when "Play again" is clicked on the game-over screen.
    """
    st.title("Abaka")

    render_scoreboard(engine)

    if engine.is_game_over():
        _render_game_over(engine, on_new_game)
        return

    player = engine.players[engine.current]
    st.subheader(f"Turn: {player.name}")

    if not engine.dice:
        # The turn has not been rolled yet.
        if read_only:
            st.info(f"{player.name} is about to roll...")
        elif st.button("Roll Dice", type="primary"):
            try:
                engine.start_turn()
            except ValueError as e:
                st.error(str(e))
            else:
                reset_turn_selection()
                st.rerun()
        return

    render_dice_section(engine, read_only=read_only)
    if not read_only:
        render_move_selection(engine)


def _render_game_over(engine: GameEngine, on_new_game: Optional[Callable[[], None]]) -> None:
    st.success("🎉 Game Over! 🎉")
    final_scores = engine.calculate_final_scores()
    best = max(final_scores.values())
    st.subheader("Final Scores:")
    for player_name, score in final_scores.items():
        trophy = " 🏆" if score == best else ""
        st.write(f"**{player_name}**: {score}{trophy}")

    if on_new_game is not None and st.button("Play again", type="primary"):
        reset_turn_selection()
        on_new_game()
        st.rerun()


def reset_turn_selection() -> None:
    """Forget dice/move picks left over from an earlier turn."""
    st.session_state.selected_dice = set()
    st.session_state.selected_move = None


def initialize_session_state() -> None:
    """Initialize the session state variables."""
    if "engine" not in st.session_state:
        st.session_state.engine = None  # local hotseat game, if any

    if "selected_dice" not in st.session_state:
        st.session_state.selected_dice = set()

    if "selected_move" not in st.session_state:
        st.session_state.selected_move = None


def render_new_game_setup() -> None:
    """Render the new game setup form."""
    st.title("Abaka — New game")
    with st.form("name_setup"):
        p1 = st.text_input("Player 1 name", "P1")
        p2 = st.text_input("Player 2 name", "P2")
        submitted = st.form_submit_button("Start game")
        if submitted:
            players = [p1.strip() or "P1", p2.strip() or "P2"]
            st.session_state.engine = GameEngine(players)
            reset_turn_selection()
            st.rerun()
    st.stop()
