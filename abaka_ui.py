"""
Clean, modular Abaka UI application with Online Multiplayer support and Deep Linking.
"""

import streamlit as st
import time
from abaka.engine import GameEngine
from abaka.online import FirestoreClient, MockFirestoreClient, OnlineGameEngine, deserialize_game_state
from ui_components.main_ui import (
    render_main_ui, 
    initialize_session_state, 
    render_new_game_setup
)
from ui_components.sidebar import render_sidebar

def main():
    """Main application entry point."""
    st.set_page_config(page_title="Abaka", page_icon="🎲", layout="wide")
    
    # Initialize session state
    initialize_session_state()
    
    # --- Deep Linking Logic ---
    # Check for game_id in URL query parameters on first load
    if "qp_checked" not in st.session_state:
        # Use st.query_params (Streamlit >= 1.28)
        qp = st.query_params
        if "game_id" in qp:
            st.session_state.online_mode = True
            st.session_state.url_game_id = qp["game_id"]
        st.session_state.qp_checked = True

    if "online_mode" not in st.session_state:
        st.session_state.online_mode = False
    if "game_id" not in st.session_state:
        st.session_state.game_id = None
    if "auto_refresh" not in st.session_state:
        st.session_state.auto_refresh = False

    # --- Sidebar & Online Setup ---
    with st.sidebar:
        st.header("Game Mode")
        
        # Determine default index for radio button
        radio_index = 0
        if st.session_state.get("online_mode"):
            # Default to Mock if just entering, unless we have real credentials saved (not impl here)
            radio_index = 1 

        mode = st.radio(
            "Select Mode", 
            ["Local Hotseat", "Online Demo (Mock)", "Online Multiplayer (Real)"],
            index=radio_index
        )
        
        if mode == "Local Hotseat":
            st.session_state.online_mode = False
            render_sidebar() # Standard local new game setup
        
        elif mode == "Online Demo (Mock)":
            st.session_state.online_mode = True
            st.divider()
            st.subheader("Mock Online Setup")
            st.info("Simulates online play in-memory. \n\n**To play with a friend:**\n1. Ensure you are on the same WiFi/Network.\n2. Use your computer's IP address instead of 'localhost' in the URL.")
            
            # Use Mock Client
            client = MockFirestoreClient()
            _render_online_lobby(client)
            
        else: # Real Online
            st.session_state.online_mode = True
            st.divider()
            st.subheader("Firebase Setup")
            
            # Credentials
            project_id = st.text_input("Firebase Project ID", key="fb_pid")
            api_key = st.text_input("Firebase Web API Key", type="password", key="fb_key")
            
            if project_id and api_key:
                client = FirestoreClient(project_id, api_key)
                _render_online_lobby(client)
            else:
                st.warning("Enter credentials to connect.")

    # --- Main Game Logic ---
    
    # Check for Online Sync
    if st.session_state.online_mode and st.session_state.engine:
        # If we have an engine and are online, try to sync before rendering
        if hasattr(st.session_state.engine, 'sync'):
            try:
                st.session_state.engine.sync()
            except Exception as e:
                # Silent fail for sync to avoid UI clutter, or small warning
                pass
                
        # Auto-refresh loop
        if st.session_state.auto_refresh:
            time.sleep(2)
            st.rerun()

    # If no engine, show setup (Local only, Online is handled in sidebar)
    if st.session_state.engine is None:
        if st.session_state.online_mode:
            st.title("Abaka Online Lobby")
            
            # If we came from a URL, show a big JOIN button in the main area too
            if st.session_state.get("url_game_id") and not st.session_state.game_id:
                st.info(f"You have been invited to join Game ID: **{st.session_state.url_game_id}**")
                st.write("Go to the sidebar to set your name and join!")
            else:
                st.info("👈 Please Create or Join a game in the sidebar.")
        else:
            render_new_game_setup()
    else:
        # Render main game interface
        render_main_ui(st.session_state.engine)


def _render_online_lobby(client):
    """Render the Create/Join UI for any compatible client (Mock or Real)."""
    
    # Pre-fill join ID if from URL
    default_join_id = st.session_state.get("url_game_id", "")
    
    tab1, tab2 = st.tabs(["Create Game", "Join Game"])
    
    with tab1:
        p1_name = st.text_input("Player 1 Name (You)", "Host", key="create_p1")
        p2_name = st.text_input("Player 2 Name (Opponent)", "Guest", key="create_p2")
        
        if st.button("Create Online Game"):
            with st.spinner("Creating game..."):
                try:
                    base_engine = GameEngine([p1_name, p2_name])
                    gid = client.create_game(base_engine)
                    st.session_state.game_id = gid
                    # Initialize OnlineEngine
                    st.session_state.engine = OnlineGameEngine(base_engine, client, gid)
                    st.session_state.awaiting_turn = True
                    
                    # Set URL param for easy sharing
                    st.query_params["game_id"] = gid
                    
                    st.success(f"Created! ID: {gid}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    with tab2:
        join_id = st.text_input("Enter Game ID", value=default_join_id, key="join_input")
        if st.button("Join Game"):
            with st.spinner("Joining..."):
                try:
                    base_engine = client.get_game(join_id)
                    if base_engine:
                        st.session_state.game_id = join_id
                        st.session_state.engine = OnlineGameEngine(base_engine, client, join_id)
                        
                        # Set URL param
                        st.query_params["game_id"] = join_id
                        
                        st.success("Joined successfully!")
                        st.rerun()
                    else:
                        st.error("Game not found.")
                except Exception as e:
                    st.error(f"Error: {e}")
                
    # Active Game Info
    if st.session_state.game_id:
        st.divider()
        st.subheader("Game Active")
        st.markdown(f"**Game ID:** `{st.session_state.game_id}`")
        
        # --- Context-Aware Sharing Instructions ---
        if isinstance(client, MockFirestoreClient):
            st.warning("""
            **How to invite a friend (Mock Mode):**
            
            This mode runs locally on your network.
            1.  Find your computer's **Local IP Address** (e.g., `192.168.1.5`).
            2.  Share this link with your friend on the **same WiFi**:
                `http://<YOUR_IP_ADDRESS>:8501/?game_id={}`
            
            *(Do not use 'localhost' - that only works on your own machine.)*
            """.format(st.session_state.game_id))
        else:
            st.info("""
            **How to invite a friend (Real Mode):**
            
            The game state is synced via the cloud (Firebase), but the app is running on your computer.
            
            * **If your friend ALSO runs the app on their computer:**
                Share the Game ID: `{}` 
                *(Or send the localhost link if they have the app setup locally.)*
                
            * **If your friend does NOT have the app:**
                You must **Deploy** this app (e.g., to Streamlit Community Cloud) so they can access it via a public URL.
            """.format(st.session_state.game_id))
        
        # Auto-refresh toggle
        st.divider()
        st.caption("Game Sync")
        st.session_state.auto_refresh = st.checkbox("Auto-refresh Game State", value=False)
        if st.button("Manual Refresh"):
            if st.session_state.engine and hasattr(st.session_state.engine, 'sync'):
                st.session_state.engine.sync()
                st.rerun()


if __name__ == "__main__":
    main()