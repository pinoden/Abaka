"""
Clean, modular Abaka UI application with Online Multiplayer support and Deep Linking.
"""

import streamlit as st
import time
import socket
from abaka.engine import GameEngine
from abaka.online import FirestoreClient, MockFirestoreClient, OnlineGameEngine, deserialize_game_state
from ui_components.main_ui import (
    render_main_ui, 
    initialize_session_state, 
    render_new_game_setup
)
from ui_components.sidebar import render_sidebar

# --- Helper: Local IP ---
def get_local_ip():
    """Try to determine the local IP address of the machine."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Doesn't actually connect to Google, just determines the route/interface
        s.connect(("8.8.8.8", 80)) 
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "YOUR_IP_ADDRESS"

# --- Helper: Restricted Engine ---
class RestrictedOnlineGameEngine(OnlineGameEngine):
    """
    An OnlineGameEngine that enforces turn-based restrictions locally.
    It prevents state-changing methods from executing if it's not the local player's turn.
    """
    def __init__(self, base_engine, client, game_id, local_player_idx):
        super().__init__(base_engine, client, game_id)
        self.local_player_idx = local_player_idx

    def _is_my_turn(self):
        return self.current == self.local_player_idx

    def start_turn(self):
        if not self._is_my_turn():
            st.toast(f"🚫 Not your turn! Waiting for {self.players[self.current].name}.", icon="🛑")
            return
        super().start_turn()

    def reroll(self, indices):
        if not self._is_my_turn():
            st.toast(f"🚫 Not your turn! Waiting for {self.players[self.current].name}.", icon="🛑")
            return
        super().reroll(indices)

    def record_score(self, category, slot_index):
        if not self._is_my_turn():
            st.toast(f"🚫 Not your turn! Waiting for {self.players[self.current].name}.", icon="🛑")
            return
        super().record_score(category, slot_index)

    def record_cross(self, category, slot_index):
        if not self._is_my_turn():
            st.toast(f"🚫 Not your turn! Waiting for {self.players[self.current].name}.", icon="🛑")
            return
        super().record_cross(category, slot_index)

    def next_player(self):
        if not self._is_my_turn():
            st.toast(f"🚫 Not your turn!", icon="🛑")
            return
        super().next_player()


# --- Main App ---
def main():
    """Main application entry point."""
    st.set_page_config(page_title="Abaka", page_icon="🎲", layout="wide")
    
    # Initialize session state
    initialize_session_state()
    
    if "local_player_idx" not in st.session_state:
        st.session_state.local_player_idx = None # 0 for Host, 1 for Guest
    
    # --- Deep Linking Logic ---
    if "qp_checked" not in st.session_state:
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
        
        radio_index = 0
        if st.session_state.get("online_mode"):
            radio_index = 1 

        mode = st.radio(
            "Select Mode", 
            ["Local Hotseat", "Online Demo (Mock)", "Online Multiplayer (Real)"],
            index=radio_index
        )
        
        if mode == "Local Hotseat":
            st.session_state.online_mode = False
            render_sidebar()
        
        elif mode == "Online Demo (Mock)":
            st.session_state.online_mode = True
            st.divider()
            st.subheader("Mock Online Setup")
            st.info("Simulates online play in-memory. \n\n**To play with a friend:**\nEnsure you are on the same WiFi/Network.")
            
            client = MockFirestoreClient()
            _render_online_lobby(client)
            
        else: # Real Online
            st.session_state.online_mode = True
            st.divider()
            st.subheader("Firebase Setup")
            
            project_id = st.text_input("Firebase Project ID", key="fb_pid")
            api_key = st.text_input("Firebase Web API Key", type="password", key="fb_key")
            
            if project_id and api_key:
                client = FirestoreClient(project_id, api_key)
                _render_online_lobby(client)
            else:
                st.warning("Enter credentials to connect.")

    # --- Main Game Logic ---
    
    # 1. Check for Online Sync (BEFORE Rendering)
    if st.session_state.online_mode and st.session_state.engine:
        if hasattr(st.session_state.engine, 'sync'):
            try:
                st.session_state.engine.sync()
            except Exception as e:
                pass

    # 2. Render UI
    if st.session_state.engine is None:
        if st.session_state.online_mode:
            st.title("Abaka Online Lobby")
            
            if st.session_state.get("url_game_id") and not st.session_state.game_id:
                st.info(f"You have been invited to join Game ID: **{st.session_state.url_game_id}**")
                st.write("Go to the sidebar to set your name and join!")
            else:
                st.info("👈 Please Create or Join a game in the sidebar.")
        else:
            render_new_game_setup()
    else:
        # --- GAME ACTIVE UI ---
        
        # Turn Status Banner & Read-Only Logic
        engine = st.session_state.engine
        local_idx = st.session_state.local_player_idx
        current_idx = engine.current
        
        read_only = False
        if st.session_state.online_mode and local_idx is not None:
            is_my_turn = (current_idx == local_idx)
            read_only = not is_my_turn
            current_player_name = engine.players[current_idx].name
            
            if is_my_turn:
                st.success(f"🟢 **YOUR TURN!** ({current_player_name})")
            else:
                st.error(f"🔴 **WAITING FOR OPPONENT...** ({current_player_name}'s turn)")
        else:
            is_my_turn = True 

        # Render main game interface with read_only flag
        render_main_ui(st.session_state.engine, read_only=read_only)
        
        # 3. Smart Auto-refresh loop (AFTER Rendering)
        if st.session_state.online_mode:
            if not is_my_turn:
                with st.empty():
                    st.caption(f"Waiting for {current_player_name} to move...")
                    time.sleep(2)
                st.rerun()


def _render_online_lobby(client):
    """Render the Create/Join UI for any compatible client (Mock or Real)."""
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
                    
                    st.session_state.local_player_idx = 0
                    st.session_state.engine = RestrictedOnlineGameEngine(base_engine, client, gid, 0)
                    st.session_state.awaiting_turn = True
                    
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
                        
                        st.session_state.local_player_idx = 1
                        st.session_state.engine = RestrictedOnlineGameEngine(base_engine, client, join_id, 1)
                        
                        st.query_params["game_id"] = join_id
                        
                        st.success("Joined successfully!")
                        st.rerun()
                    else:
                        st.error("Game not found.")
                except Exception as e:
                    st.error(f"Error: {e}")
                
    if st.session_state.game_id:
        st.divider()
        st.subheader("Game Active")
        st.markdown(f"**Game ID:** `{st.session_state.game_id}`")
        
        if isinstance(client, MockFirestoreClient):
            local_ip = get_local_ip()
            game_url = f"http://{local_ip}:8501/?game_id={st.session_state.game_id}"
            
            st.warning(f"""
            **How to invite a friend (Mock Mode):**
            1.  Ensure your friend is on the **same WiFi network**.
            2.  Share this specific URL with them (not localhost):
            **`{game_url}`**
            """)
        else:
            st.info(f"""
            **How to invite a friend (Real Mode):**
            * Share the Game ID: `{st.session_state.game_id}` 
            """)
        
        st.divider()
        if st.button("Manual Sync"):
            if st.session_state.engine and hasattr(st.session_state.engine, 'sync'):
                st.session_state.engine.sync()
                st.rerun()


if __name__ == "__main__":
    main()