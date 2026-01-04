import json
import requests
import time
import random
import string
from typing import Dict, Any, List, Optional, Tuple
from .models import Category, Die
from .engine import GameEngine
from .player import PlayerState

# --- Serialization Helpers ---

def serialize_game_state(engine: GameEngine) -> Dict[str, Any]:
    """Convert the entire GameEngine state to a JSON-serializable dictionary."""
    return {
        "current": engine.current,
        "dice": [{"v": d.value, "j": d.is_joker} for d in engine.dice],
        "rolls_left": engine.rolls_left,
        "first_roll": engine.first_roll,
        "row_bonus_claimed": {k.name: v for k, v in engine.row_bonus_claimed.items()},
        "col_bonus_claimed": engine.col_bonus_claimed,
        "school_minus_used": {f"{k[0]},{k[1].name}": v for k, v in engine.school_minus_used.items()},
        "row_bonus_blocked": {f"{k[0]},{k[1].name}": v for k, v in engine.row_bonus_blocked.items()},
        "players": [_serialize_player(p) for p in engine.players],
        "timestamp": time.time()
    }

def _serialize_player(p: PlayerState) -> Dict[str, Any]:
    return {
        "name": p.name,
        "table": {k.name: v for k, v in p.table.items()},
        "column_bonus": p.column_bonus,
        "school_balance": p.school_balance,
        "school_balance_loc": [p.school_balance_loc[0].name, p.school_balance_loc[1]] if p.school_balance_loc else None
    }

def deserialize_game_state(data: Dict[str, Any]) -> GameEngine:
    """Reconstruct a GameEngine instance from a dictionary."""
    player_data_list = data["players"]
    names = [p["name"] for p in player_data_list]
    engine = GameEngine(names)

    engine.current = data["current"]
    engine.rolls_left = data["rolls_left"]
    engine.first_roll = data["first_roll"]
    
    engine.dice = [Die(d["v"], is_joker=d["j"]) for d in data.get("dice", [])]

    engine.row_bonus_claimed = {Category[k]: v for k, v in data["row_bonus_claimed"].items()}
    engine.col_bonus_claimed = data["col_bonus_claimed"]

    engine.school_minus_used = {}
    for k_str, v in data["school_minus_used"].items():
        idx_str, cat_name = k_str.split(',')
        engine.school_minus_used[(int(idx_str), Category[cat_name])] = v

    engine.row_bonus_blocked = {}
    for k_str, v in data["row_bonus_blocked"].items():
        idx_str, cat_name = k_str.split(',')
        engine.row_bonus_blocked[(int(idx_str), Category[cat_name])] = v

    for i, p_data in enumerate(player_data_list):
        p_state = engine.players[i]
        p_state.school_balance = p_data["school_balance"]
        p_state.column_bonus = p_data["column_bonus"]
        
        for cat_name, slots in p_data["table"].items():
            p_state.table[Category[cat_name]] = slots
            
        if p_data.get("school_balance_loc"):
            cat_name, slot_idx = p_data["school_balance_loc"]
            p_state.school_balance_loc = (Category[cat_name], slot_idx)

    return engine


# --- Clients ---

class FirestoreClient:
    """Real REST client for Firestore."""
    def __init__(self, project_id: str, api_key: str):
        self.project_id = project_id
        self.api_key = api_key
        self.base_url = f"https://firestore.googleapis.com/v1/projects/{project_id}/databases/(default)/documents"
        self.collection = "abaka_games"

    def create_game(self, engine: GameEngine) -> str:
        url = f"{self.base_url}/{self.collection}?key={self.api_key}"
        game_data = serialize_game_state(engine)
        payload = {"fields": {"json_data": {"stringValue": json.dumps(game_data)}}}
        
        resp = requests.post(url, json=payload)
        if resp.status_code != 200:
            raise Exception(f"Error creating game: {resp.text}")
        
        doc_name = resp.json()["name"]
        return doc_name.split("/")[-1]

    def save_game(self, game_id: str, engine: GameEngine):
        url = f"{self.base_url}/{self.collection}/{game_id}?key={self.api_key}"
        game_data = serialize_game_state(engine)
        payload = {"fields": {"json_data": {"stringValue": json.dumps(game_data)}}}
        
        resp = requests.patch(url, json=payload)
        if resp.status_code != 200:
            raise Exception(f"Error saving game: {resp.text}")

    def get_game(self, game_id: str) -> Optional[GameEngine]:
        url = f"{self.base_url}/{self.collection}/{game_id}?key={self.api_key}"
        resp = requests.get(url)
        if resp.status_code != 200:
            return None
        
        data = resp.json()
        if "fields" not in data or "json_data" not in data["fields"]:
            return None
            
        json_str = data["fields"]["json_data"]["stringValue"]
        game_dict = json.loads(json_str)
        return deserialize_game_state(game_dict)


class MockFirestoreClient:
    """
    In-memory simulation of Firestore. 
    Data is stored in a class-level dictionary.
    """
    _storage: Dict[str, Dict] = {}

    def create_game(self, engine: GameEngine) -> str:
        # Generate a random 6-character ID
        game_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        self.save_game(game_id, engine)
        return game_id

    def save_game(self, game_id: str, engine: GameEngine):
        # Serialize and store in memory
        MockFirestoreClient._storage[game_id] = serialize_game_state(engine)

    def get_game(self, game_id: str) -> Optional[GameEngine]:
        data = MockFirestoreClient._storage.get(game_id)
        if not data:
            return None
        return deserialize_game_state(data)


# --- Online Game Engine Wrapper ---

class OnlineGameEngine(GameEngine):
    """
    A wrapper around GameEngine that auto-saves to the client 
    whenever a state-changing method is called.
    """
    def __init__(self, wrapped_engine: GameEngine, client: Any, game_id: str):
        # Copy state from the wrapped engine
        self.__dict__.update(wrapped_engine.__dict__)
        self.client = client
        self.game_id = game_id

    def save(self):
        """Push current state to cloud/mock."""
        self.client.save_game(self.game_id, self)

    def sync(self):
        """Pull latest state from cloud/mock."""
        remote_engine = self.client.get_game(self.game_id)
        if remote_engine:
            self.__dict__.update(remote_engine.__dict__)

    # --- Overrides to trigger saves ---

    def next_player(self) -> None:
        super().next_player()
        self.save()

    def start_turn(self) -> None:
        super().start_turn()
        self.save()

    def reroll(self, indices: List[int]) -> None:
        super().reroll(indices)
        self.save()

    def record_score(self, category: Category, slot_index: int) -> None:
        super().record_score(category, slot_index)
        self.save()

    def record_cross(self, category: Category, slot_index: int) -> None:
        super().record_cross(category, slot_index)
        self.save()
        
    @property
    def dice(self):
        return self._dice
    
    @dice.setter
    def dice(self, value):
        self._dice = value
        self.save()