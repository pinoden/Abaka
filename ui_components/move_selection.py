"""
Move selection component for Abaka game interface.
Handles the move selection interface with radio buttons and execution.
"""

import streamlit as st
from abaka.engine import GameEngine
from abaka.models import Category
from abaka.scoring import score_category


def render_move_selection(engine: GameEngine):
    """Render the move selection interface."""
    st.markdown('<div style="font-size: 1.5em;">Select move category:</div>', unsafe_allow_html=True)
    
    # Add custom CSS for radio button styling
    st.markdown("""
    <style>
    /* Custom styling for radio buttons */
    .stRadio > div {
        background-color: #2c3e50;
        border-radius: 8px;
        padding: 10px;
        margin: 10px 0;
    }
    .stRadio > div > label {
        color: white !important;
        font-weight: bold !important;
        font-size: 1.1em !important;
    }
    .stRadio > div > div > label {
        color: white !important;
        font-weight: bold !important;
        font-size: 1.1em !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add action selection radio buttons
    action = st.radio(
        "Action:",
        ["Score", "Cross"],
        horizontal=True,
        key="action_radio"
    )
    
    # Store the selected action in session state
    st.session_state.action = action
    
    # Add spacing
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Get available rows for the current player
    avail = _get_available_rows(engine, engine.players[engine.current])
    
    if avail:
        # Filter available categories based on action and current dice
        filtered_cats = _filter_available_categories(engine, avail, action)
        
        if not filtered_cats:
            if action == "Score":
                st.info("No valid scoring options available with current dice. Consider crossing out a category instead.")
            else:
                st.info("No categories available to cross out.")
            return
        
        # Create a mapping from descriptive labels to categories
        label_to_cat = {_get_descriptive_label(c): c for c in filtered_cats}
        
        # Get current action from session state
        action = st.session_state.get('action', 'Score')
        
        # Apply CSS for selected button styling (blue)
        st.markdown("""
        <style>
        /* Make selected move category buttons navy blue */
        /* Use a simpler selector that should work */
        div[data-testid="stButton"] button[kind="primary"] {
            background-color: #2c3e50 !important;
            color: white !important;
        }
        div[data-testid="stButton"] button[kind="primary"]:hover {
            background-color: #1a252f !important;
        }
        /* But keep the execute button green */
        div[data-testid="stButton"] button[kind="primary"]:last-child {
            background-color: #27ae60 !important;
        }
        div[data-testid="stButton"] button[kind="primary"]:last-child:hover {
            background-color: #229954 !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        # Create a 3x5 grid for move selection
        cols = st.columns(3)
        
        for i, cat in enumerate(filtered_cats):
            label = _get_descriptive_label(cat)
            col_idx = i % 3
            
            with cols[col_idx]:
                button_key = f"move_btn_{i}"
                is_selected = st.session_state.get('selected_move') == label
                
                if is_selected:
                    # Blue button for selected action
                    if st.button(label, key=button_key, type="primary"):
                        st.session_state.selected_move = label
                        st.rerun()
                else:
                    # Dark button for unselected
                    if st.button(label, key=button_key, type="secondary"):
                        st.session_state.selected_move = label
                        st.rerun()
        
        # Action button with green color and larger font
        st.markdown('<div style="font-size: 1.5em;">Execute Move:</div>', unsafe_allow_html=True)
        
        # Custom CSS for calming green button
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
                    st.session_state.dice_rolled = False  # reset dice state for next player
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.info("Please select a move category.")
    else:
        st.info("No available moves - all rows are filled!")


def _filter_available_categories(engine: GameEngine, available_categories: list, action: str) -> list:
    """Filter available categories based on action and current dice."""
    filtered = []
    
    for cat in available_categories:
        if action == "Cross":
            # For crossing out, exclude school categories
            if cat.name.startswith("SCHOOL_"):
                continue
            filtered.append(cat)
        else:  # Score action
            if not engine.dice:  # No dice rolled yet
                # Show all categories for scoring when dice haven't been rolled
                filtered.append(cat)
            else:
                # For scoring with dice, check if the category can actually be scored
                if cat.name.startswith("SCHOOL_"):
                    # For school categories, check if the current dice can score in this category
                    try:
                        # Extract the school number from category name (e.g., SCHOOL_1 -> 1)
                        school_number = int(cat.name.split('_')[1])
                        # Check if any die shows this number
                        can_score = any(d.value == school_number for d in engine.dice)
                        if can_score:
                            filtered.append(cat)
                    except:
                        # If we can't determine, don't include this category
                        continue
                else:
                    # For non-school categories, only include if they would score > 0
                    try:
                        score = score_category(engine.dice, cat, first_roll=engine.first_roll)
                        if score > 0:
                            filtered.append(cat)
                    except:
                        # If scoring fails, don't include this category
                        continue
    
    return filtered


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
