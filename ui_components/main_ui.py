"""
Main UI orchestrator for Abaka game interface.
Coordinates all components and handles the main game flow.
"""

import streamlit as st
from abaka.engine import GameEngine
from ui_components.scoreboard import render_scoreboard
from ui_components.dice import render_dice_section
from ui_components.move_selection import render_move_selection


def render_main_ui(engine: GameEngine) -> None:
    """Render the main game interface."""
    # Game title
    st.title("Abaka")
    
    # Scoreboard
    render_scoreboard(engine)
    
    # Current player / turn controls
    player = engine.players[engine.current]
    st.subheader(f"Turn: {player.name}")

    if st.session_state.awaiting_turn:
        if st.button("Start turn"):
            engine.start_turn()
            st.session_state.awaiting_turn = False
            st.rerun()
    else:
        # Dice section
        render_dice_section(engine)
        
        # Move selection
        render_move_selection(engine)


def initialize_session_state() -> None:
    """Initialize the session state variables."""
    if "engine" not in st.session_state:
        st.session_state.engine = None
        st.session_state.awaiting_turn = True  # waiting to start the current player's turn

    if "selected_dice" not in st.session_state:
        st.session_state.selected_dice = set()


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
            st.session_state.awaiting_turn = True
            st.rerun()
    st.stop()
