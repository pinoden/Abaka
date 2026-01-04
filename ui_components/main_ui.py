"""
Main UI orchestrator for Abaka game interface.
Coordinates all components and handles the main game flow.
"""

import streamlit as st
from abaka.engine import GameEngine
from abaka.models import roll_dice
from ui_components.scoreboard import render_scoreboard
from ui_components.dice import render_dice_section
from ui_components.move_selection import render_move_selection


def render_main_ui(engine: GameEngine, read_only: bool = False) -> None:
    """
    Render the main game interface.
    
    Args:
        engine: The GameEngine instance.
        read_only: If True, all interactive controls will be disabled.
    """
    # Game title
    st.title("Abaka")
    
    # Scoreboard
    render_scoreboard(engine)
    
    # Check if game is over
    if engine.is_game_over():
        st.success("🎉 Game Over! 🎉")
        final_scores = engine.calculate_final_scores()
        st.subheader("Final Scores:")
        for player_name, score in final_scores.items():
            st.write(f"**{player_name}**: {score}")
        
        # Reset game state for new game
        if st.button("Start New Game"):
            st.session_state.awaiting_turn = True
            st.session_state.dice_rolled = False
            st.session_state.selected_dice.clear()
            st.session_state.selected_move = None
            st.rerun()
        return
    
    # Current player / turn controls
    player = engine.players[engine.current]
    st.subheader(f"Turn: {player.name}")

    if st.session_state.awaiting_turn:
        # Automatically start the turn and load everything except dice
        
        # If we are the active player (not read_only), we trigger the start turn logic
        if not read_only:
            engine.start_turn()
            # Explicitly set turn defaults
            engine.dice = []  # Clear dice so they're not shown
            engine.rolls_left = 2
            engine.first_roll = True
            
            # CRITICAL FIX: Save these manual state changes to the cloud!
            # The OnlineGameEngine wrapper only auto-saves on method calls, not attribute assignments.
            if hasattr(engine, 'save'):
                engine.save()
                
            st.session_state.awaiting_turn = False
            st.session_state.dice_rolled = False
            st.rerun()
        else:
            # If read_only, we just show "Waiting for [Player] to start turn..."
            st.info(f"Waiting for {player.name} to start their turn...")
            
    elif not st.session_state.get("dice_rolled", False):
        # Show "Roll Dice" button for first roll
        if st.button("Roll Dice", type="primary", disabled=read_only):
            # Actually roll the dice now
            engine.dice = roll_dice()
            # Note: assigning to engine.dice triggers a save in OnlineGameEngine because I added a property setter for it.
            
            st.session_state.dice_rolled = True
            st.rerun()
        else:
            if read_only:
                st.info(f"{player.name} is about to roll...")
            else:
                # Show placeholder for dice area
                st.info("Click 'Roll Dice' to start your turn")
            
            # Show move selection even before dice are rolled (but disabled if read_only)
            render_move_selection(engine, read_only=read_only)
    else:
        # Dice section
        render_dice_section(engine, read_only=read_only)
        
        # Move selection
        render_move_selection(engine, read_only=read_only)


def initialize_session_state() -> None:
    """Initialize the session state variables."""
    if "engine" not in st.session_state:
        st.session_state.engine = None
        st.session_state.awaiting_turn = True  # waiting to start the current player's turn

    if "selected_dice" not in st.session_state:
        st.session_state.selected_dice = set()
    
    if "dice_rolled" not in st.session_state:
        st.session_state.dice_rolled = False


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
            st.session_state.dice_rolled = False
            st.rerun()
    st.stop()