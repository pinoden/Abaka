"""
Move selection component for Abaka game interface.
Handles the move selection interface with radio buttons and execution.
"""

import streamlit as st
from abaka.engine import GameEngine
from abaka.models import Category
from abaka.scoring import score_category


def render_move_selection(engine: GameEngine, read_only: bool = False):
    """Render the move selection interface."""
    st.markdown('<div style="font-size: 1.5em;">Select move category:</div>', unsafe_allow_html=True)
    
    # CSS for Visibility and Contrast
    st.markdown("""
    <style>
    /* Radio Button Style */
    .stRadio > div {
        background-color: #34495e;
        border-radius: 8px;
        padding: 10px;
        color: white;
    }
    
    /* Primary Buttons (Selected Options & Action) */
    div[data-testid="stButton"] button[kind="primary"] {
        background-color: #3498db !important; /* Bright Blue */
        color: white !important;
        font-weight: bold !important;
        border: none !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:hover {
        background-color: #2980b9 !important;
    }
    div[data-testid="stButton"] button[kind="primary"]:disabled {
        background-color: #95a5a6 !important;
        color: #ecf0f1 !important;
    }
    
    /* Secondary Buttons (Unselected Options) */
    div[data-testid="stButton"] button[kind="secondary"] {
        background-color: #ffffff !important;
        color: #2c3e50 !important;
        border: 2px solid #bdc3c7 !important;
        font-weight: bold !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        border-color: #3498db !important;
        background-color: #ecf0f1 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Add action selection radio buttons
    action = st.radio(
        "Action:",
        ["Score", "Cross"],
        horizontal=True,
        key="action_radio",
        disabled=read_only
    )
    
    st.session_state.action = action
    st.markdown("<br>", unsafe_allow_html=True)
    
    # Get available rows for the current player
    avail = _get_available_rows(engine, engine.players[engine.current])
    
    if avail:
        # Filter available categories based on action and current dice
        filtered_cats = _filter_available_categories(engine, avail, action)
        
        if not filtered_cats:
            if not read_only:
                if action == "Score":
                    st.info("No valid scoring options available with current dice. Consider crossing out a category instead.")
                else:
                    st.info("No categories available to cross out.")
            return
        
        label_to_cat = {_get_descriptive_label(c): c for c in filtered_cats}
        
        # Grid for move selection
        cols = st.columns(3)
        
        for i, cat in enumerate(filtered_cats):
            label = _get_descriptive_label(cat)
            col_idx = i % 3
            
            with cols[col_idx]:
                button_key = f"move_btn_{i}"
                is_selected = st.session_state.get('selected_move') == label
                
                # If selected, show as Primary (Blue). If not, Secondary (White).
                if is_selected:
                    if st.button(label, key=button_key, type="primary", disabled=read_only):
                        # Already selected, clicking again does nothing (or could deselect)
                        st.session_state.selected_move = label
                        st.rerun()
                else:
                    if st.button(label, key=button_key, type="secondary", disabled=read_only):
                        st.session_state.selected_move = label
                        st.rerun()
        
        # Execute Action Button
        st.markdown(f'<div style="font-size: 1.5em; margin-top: 20px;">Execute Move: {action}</div>', unsafe_allow_html=True)
        
        # We use a container to visually separate the execute action
        with st.container():
            # Use columns to make the button look distinct (wider/centered) or just placed well
            c1, c2, c3 = st.columns([1, 2, 1])
            with c2:
                # This button also uses 'primary' style (Blue), which is consistent with "Active Action"
                if st.button(f"CONFIRM {action.upper()}", type="primary", disabled=(read_only or not st.session_state.selected_move)):
                    if st.session_state.selected_move:
                        cat = label_to_cat[st.session_state.selected_move]
                        try:
                            slot = engine.leftmost_slot(engine.players[engine.current], cat)
                            if action == "Score":
                                engine.record_score(cat, slot)
                            else:
                                engine.record_cross(cat, slot)
                            
                            st.session_state.selected_move = None
                            st.session_state.awaiting_turn = True
                            st.session_state.dice_rolled = False
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
            if cat.name.startswith("SCHOOL_"):
                continue
            filtered.append(cat)
        else:  # Score
            if not engine.dice:
                filtered.append(cat)
            else:
                if cat.name.startswith("SCHOOL_"):
                    try:
                        school_number = int(cat.name.split('_')[1])
                        can_score = any(d.value == school_number for d in engine.dice)
                        if can_score:
                            filtered.append(cat)
                    except:
                        continue
                else:
                    try:
                        score = score_category(engine.dice, cat, first_roll=engine.first_roll)
                        if score > 0:
                            filtered.append(cat)
                    except:
                        continue
    return filtered


def _get_available_rows(engine: GameEngine, player) -> list:
    return [cat for cat, slots in player.table.items() if any(v is None for v in slots[:3])]


def _get_descriptive_label(cat: Category) -> str:
    if cat.name.startswith("SCHOOL_"):
        return f"School {cat.name.split('_')[1]}"
    
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