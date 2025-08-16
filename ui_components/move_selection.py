"""
Move selection component for Abaka game interface.
Handles the move selection interface with radio buttons and execution.
"""

import streamlit as st
from abaka.engine import GameEngine
from abaka.models import Category


def render_move_selection(engine: GameEngine) -> None:
    """Render the move selection interface."""
    st.divider()
    
    # Score / Cross - Radio button selection
    avail = _get_available_rows(engine, engine.players[engine.current])
    
    if avail:
        st.markdown("**Choose your move:**", help="Select your action and move category")
        
        # First radio button group: Score or Cross
        st.markdown('<div style="font-size: 1.5em;">Action:</div>', unsafe_allow_html=True)
        action = st.radio("Action:", ["Score", "Cross"], horizontal=True, label_visibility="collapsed")
        
        # Initialize selected_move in session state if not exists
        if "selected_move" not in st.session_state:
            st.session_state.selected_move = None
        
        # Second radio button group: Available move categories in 3x5 grid
        st.markdown('<div style="font-size: 1.5em;">Select move category:</div>', unsafe_allow_html=True)
        
        # Create descriptive labels for each category
        labels = [_get_descriptive_label(c) for c in avail]
        label_to_cat = {_get_descriptive_label(c): c for c in avail}
        
        # Organize in 3x5 grid layout
        num_cols = 3
        num_rows = (len(labels) + num_cols - 1) // num_cols  # Ceiling division
        
        # Create grid columns
        grid_cols = st.columns(num_cols)
        
        # Place options in grid
        for i, label in enumerate(labels):
            col_idx = i % num_cols
            row_idx = i // num_cols
            
            with grid_cols[col_idx]:
                # Use radio button to select the move
                if st.radio(f"Move {i+1}:", [label], key=f"move_{i}", 
                           label_visibility="collapsed", 
                           index=0 if st.session_state.selected_move == label else None):
                    st.session_state.selected_move = label
        
        # Action button with green color and larger font
        st.markdown('<div style="font-size: 1.5em;">Execute Move:</div>', unsafe_allow_html=True)
        
        # Custom CSS for calming green button - target the specific button
        st.markdown("""
        <style>
        div[data-testid="stButton"] button[kind="primary"] {
            background-color: #27ae60 !important;
            color: white !important;
            font-size: 1.5em !important;
            padding: 10px 20px !important;
            border: none !important;
            border-radius: 8px !important;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover {
            background-color: #229954 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        if st.button(f"{action} selected move", type="primary"):
            if st.session_state.selected_move:
                cat = label_to_cat[st.session_state.selected_move]
                try:
                    slot = engine.leftmost_slot(engine.players[engine.current], cat)
                    if action == "Score":
                        engine.record_score(cat, slot)
                    else:
                        engine.record_cross(cat, slot)
                    # Reset the selected move after successful execution
                    st.session_state.selected_move = None
                    st.session_state.awaiting_turn = True  # next player's turn
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.info("Please select a move category.")
    else:
        st.info("No available moves - all rows are filled!")


def _get_available_rows(engine: GameEngine, player) -> list:
    """Get available rows for the current player."""
    # first three cells editable; bonus cell (index 3) is engine-managed
    return [cat for cat, slots in player.table.items() if any(v is None for v in slots[:3])]


def _get_descriptive_label(cat: Category) -> str:
    """Get a descriptive label for a category."""
    if cat.name.startswith("SCHOOL_"):
        return f"School {cat.name.split('_')[1]}"
    
    # Use a more robust lookup that handles enum values properly
    category_labels = {
        "PAIR": "Pair",
        "TWO_PAIRS": "Two Pairs", 
        "TRIPS": "Three of a Kind",
        "SMALL_STRAIGHT": "Small Straight",
        "LARGE_STRAIGHT": "Large Straight",
        "FULL": "Full House",
        "KARE": "Kare",
        "ABAKA": "Abaka",
        "SUM": "Sum",
    }
    
    return category_labels.get(cat.name, str(cat))
