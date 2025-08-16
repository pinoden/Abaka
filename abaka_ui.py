"""
Clean, modular Abaka UI application.
This file orchestrates the game interface using separate component modules.
"""

import streamlit as st
from ui_components.main_ui import (
    render_main_ui, 
    initialize_session_state, 
    render_new_game_setup
)
from ui_components.sidebar import render_sidebar


def main():
    """Main application entry point."""
    # Initialize session state
    initialize_session_state()
    
    # Render sidebar
    render_sidebar()
    
    # Check if game exists, if not show setup
    if st.session_state.engine is None:
        render_new_game_setup()
    
    # Render main game interface
    render_main_ui(st.session_state.engine)


if __name__ == "__main__":
    main()
