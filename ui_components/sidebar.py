"""
Sidebar component for Abaka game interface.
Handles new game functionality and sidebar styling.
"""

import streamlit as st
from abaka.engine import GameEngine


def render_sidebar() -> None:
    """Render the sidebar with new game functionality."""
    with st.sidebar:
        st.header("New game")
        names = st.text_input("Players (comma-separated)", "P1,P2")
        
        # Custom CSS for blue start new game button
        st.markdown("""
        <style>
        .sidebar div[data-testid="stButton"] button {
            background-color: #4a90e2 !important;
            color: white !important;
            border: none !important;
        }
        .sidebar div[data-testid="stButton"] button:hover {
            background-color: #357abd !important;
        }
        </style>
        """, unsafe_allow_html=True)
        
        if st.button("Start new game"):
            players = [n.strip() for n in names.split(",") if n.strip()] or ["P1", "P2"]
            st.session_state.engine = GameEngine(players)
            st.session_state.awaiting_turn = True
            st.rerun()
