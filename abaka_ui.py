# Streamlit front-end for Abaka (works with your split package)
import io
from contextlib import redirect_stdout

import streamlit as st
import re
from PIL import Image, ImageDraw
from PIL import ImageOps
from streamlit_image_select import image_select

from abaka.engine import GameEngine
from abaka.models import Category

GOLD = (255, 215, 0, 255)

# ---------- helpers ----------
def label_for(cat: Category) -> str:
    if cat.name.startswith("SCHOOL_"):
        return cat.name.split("_")[1]  # "1".."6"
    return {
        Category.PAIR: "D",
        Category.TWO_PAIRS: "DD",
        Category.TRIPS: "T",
        Category.SMALL_STRAIGHT: "LS",
        Category.LARGE_STRAIGHT: "BS",
        Category.FULL: "F",
        Category.KARE: "C",
        Category.ABAKA: "A",
        Category.SUM: "Σ",
    }[cat]

def available_rows(engine: GameEngine, player):
    # first three cells editable; bonus cell (index 3) is engine-managed
    return [cat for cat, slots in player.table.items() if any(v is None for v in slots[:3])]

def render_scoreboard(engine: GameEngine) -> str:
    buf = io.StringIO()
    with redirect_stdout(buf):
        engine.print_scoreboard()
    return buf.getvalue()

def _parse_die(d) -> tuple[int, bool]:
    """Return (face 1..6, is_joker) from whatever GameEngine puts in g.dice."""
    # Try attributes first
    v = getattr(d, "value", None)
    is_joker = bool(getattr(d, "is_joker", getattr(d, "joker", False)))
    if v is None:
        s = repr(d)
        m = re.match(r"J\((\d)\)", s)
        if m:
            v = int(m.group(1)); is_joker = True
        else:
            m2 = re.match(r"(\d)", s)
            v = int(m2.group(1)) if m2 else 1
    return int(v), bool(is_joker)
# --- configurable joker colors ---
JOKER_FILL_COLOR    = (59, 130, 128, 255)
JOKER_OUTLINE_COLOR = (96, 165, 250, 255)
JOKER_BAND_COLOR    = (250, 204,  21, 220)  # amber stripe
PIP_COLOR           = (20, 20, 20, 255)

def _make_die_image(value: int, is_joker: bool, size: int = 96, style: str = "fill") -> Image.Image:
    """
    style: 'fill' | 'outline' | 'band'
    """
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # base visuals
    fill = (255, 255, 255, 255)
    outline = (30, 30, 30, 255)

    if is_joker:
        if style == "fill":
            fill, outline = JOKER_FILL_COLOR, JOKER_OUTLINE_COLOR
        elif style == "outline":
            outline = JOKER_OUTLINE_COLOR
        elif style == "band":
            # draw base first; band later
            pass

    # body
    rect = (6, 6, size - 6, size - 6)
    d.rounded_rectangle(rect, radius=16, fill=fill, outline=outline, width=6)

    # optional diagonal band for joker
    if is_joker and style == "band":
        pad = 10
        band = [
            (pad,            size*0.35),
            (size*0.35,      pad),
            (size-pad,       size*0.65),
            (size*0.65,      size-pad),
        ]
        d.polygon(band, fill=JOKER_BAND_COLOR)

    # pips
    grid = [
        (size*0.25, size*0.25), (size*0.5, size*0.25), (size*0.75, size*0.25),
        (size*0.25, size*0.5 ), (size*0.5, size*0.5 ), (size*0.75, size*0.5 ),
        (size*0.25, size*0.75), (size*0.5, size*0.75), (size*0.75, size*0.75),
    ]
    faces = {1:[4], 2:[0,8], 3:[0,4,8], 4:[0,2,6,8], 5:[0,2,4,6,8], 6:[0,2,3,5,6,8]}
    r = int(size * 0.09)
    for idx in faces[int(value)]:
        cx, cy = grid[idx]
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=PIP_COLOR)

    return img

def _with_gold_border(img: Image.Image, selected: bool, thickness: int = 6) -> Image.Image:
    if not selected:
        return img
    # add transparent pad, then draw a rounded gold frame
    pad = thickness + 2
    canvas = Image.new("RGBA", (img.width + pad*2, img.height + pad*2), (0,0,0,0))
    canvas.paste(img, (pad, pad))
    # simple square frame (rounded rect is more code; this is clean & clear)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle([2, 2, canvas.width-3, canvas.height-3], outline=GOLD, width=thickness)
    return canvas

# ---------- session boot ----------
if "engine" not in st.session_state:
    st.session_state.engine = None
    st.session_state.awaiting_turn = True  # waiting to start the current player's turn

if "selected_dice" not in st.session_state:
    st.session_state.selected_dice = set()


# ---------- first-run: ask for player names ----------
if st.session_state.engine is None:
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

# ---------- sidebar: new game ----------
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

# ---------- main UI ----------
g: GameEngine = st.session_state.engine

st.title("Abaka")

# Scoreboard
st.subheader("Scoreboard")

# Create a clean, professional scoreboard with proper table structure
def render_clean_scoreboard(engine: GameEngine):
    # Custom CSS for the scoreboard table
    st.markdown("""
    <style>
    .scoreboard-table {
        border-collapse: collapse;
        width: 100%;
        font-family: monospace;
        font-size: 14px;
        margin-left: 0;
    }
    .scoreboard-table th, .scoreboard-table td {
        border: 1px solid #444;
        padding: 6px 8px;
        text-align: center;
        min-width: 45px;
    }
    .scoreboard-table th {
        background-color: #2c3e50;
        color: white;
        font-weight: bold;
    }
    .scoreboard-table td {
        background-color: #34495e;
        color: white;
    }
    .scoreboard-table .row-header {
        background-color: #2c3e50;
        font-weight: bold;
        text-align: left;
        min-width: 50px;
        padding-left: 8px;
        padding-right: 8px;
    }
    .scoreboard-table .current-player {
        background-color: #e74c3c;
        color: white;
        font-weight: bold;
    }
    .scoreboard-table .section-divider {
        background-color: #7f8c8d;
        height: 3px;
    }
    .scoreboard-table .empty-slot {
        color: #95a5a6;
    }
    .scoreboard-table .crossed-slot {
        color: #e74c3c;
        font-weight: bold;
    }
    .scoreboard-table .score-slot {
        color: #2ecc71;
        font-weight: bold;
    }
    .scoreboard-table .bonus-slot {
        color: #f39c12;
        font-weight: bold;
    }
    .scoreboard-table .bonus-column {
        border-left: 3px solid #f39c12;
        background-color: #2d3748;
    }
    .scoreboard-table .player-separator {
        border-left: 4px solid #7f8c8d;
        background-color: #2d3748;
    }
    .scoreboard-table .bonus-header {
        background-color: #f39c12;
        color: #2d3748;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Create the scoreboard HTML
    html_table = """
    <table class="scoreboard-table">
        <thead>
            <tr>
                <th class="row-header">Row</th>
    """
    
    # Add player headers with 4 columns each (3 score + 1 bonus)
    for i, player in enumerate(engine.players):
        if player == engine.players[engine.current]:
            html_table += f'<th colspan="4" class="current-player">→ {player.name} 🎯</th>'
        else:
            html_table += f'<th colspan="4">{player.name}</th>'
    
    html_table += "</tr><tr><th class='row-header'></th>"
    
    # Add sub-headers for score slots
    for player in engine.players:
        html_table += '<th>S1</th><th>S2</th><th>S3</th><th class="bonus-header">B</th>'
    
    html_table += "</tr></thead><tbody>"
    
    # School categories (rows 1-6)
    for i in range(1, 7):
        html_table += f"<tr><td class='row-header'>{i}</td>"
        for player_idx, player in enumerate(engine.players):
            slots = player.table[getattr(Category, f'SCHOOL_{i}')]
            # 3 score slots
            for j in range(3):
                if slots[j] is None:
                    html_table += '<td class="empty-slot">—</td>'
                elif slots[j] == "X":
                    html_table += '<td class="crossed-slot">❌</td>'
                else:
                    html_table += f'<td class="score-slot">{slots[j]}</td>'
            # 1 bonus slot with special styling
            bonus_class = "bonus-column"
            if player_idx == 0:  # First player
                bonus_class += " player-separator"
            
            if slots[3] is None:
                html_table += f'<td class="{bonus_class} empty-slot">—</td>'
            elif slots[3] == "X":
                html_table += f'<td class="{bonus_class} crossed-slot">❌</td>'
            else:
                html_table += f'<td class="{bonus_class} bonus-slot">{slots[3]}</td>'
        html_table += "</tr>"
    
    # Section divider
    html_table += '<tr><td colspan="' + str(len(engine.players) * 4 + 1) + '" class="section-divider"></td></tr>'
    
    # Combo categories (rows D, DD, T, LS, BS, F, C, A, Σ)
    combo_labels = ["D", "DD", "T", "LS", "BS", "F", "C", "A", "Σ"]
    combo_cats = [Category.PAIR, Category.TWO_PAIRS, Category.TRIPS, 
                  Category.SMALL_STRAIGHT, Category.LARGE_STRAIGHT, 
                  Category.FULL, Category.KARE, Category.ABAKA, Category.SUM]
    
    for i, (label, cat) in enumerate(zip(combo_labels, combo_cats)):
        html_table += f"<tr><td class='row-header'>{label}</td>"
        for player_idx, player in enumerate(engine.players):
            slots = player.table[cat]
            # 3 score slots
            for j in range(3):
                if slots[j] is None:
                    html_table += '<td class="empty-slot">—</td>'
                elif slots[j] == "X":
                    html_table += '<td class="crossed-slot">❌</td>'
                else:
                    html_table += f'<td class="score-slot">{slots[j]}</td>'
            # 1 bonus slot with special styling
            bonus_class = "bonus-column"
            if player_idx == 0:  # First player
                bonus_class += " player-separator"
            
            if slots[3] is None:
                html_table += f'<td class="{bonus_class} empty-slot">—</td>'
            elif slots[3] == "X":
                html_table += f'<td class="{bonus_class} crossed-slot">❌</td>'
            else:
                html_table += f'<td class="{bonus_class} bonus-slot">{slots[3]}</td>'
        html_table += "</tr>"
    
    # Section divider
    html_table += '<tr><td colspan="' + str(len(engine.players) * 4 + 1) + '" class="section-divider"></td></tr>'
    
    # Column bonuses row (B)
    html_table += "<tr><td class='row-header'>B</td>"
    for player_idx, player in enumerate(engine.players):
        col_bonuses = player.column_bonus
        # 3 column bonuses
        for bonus in col_bonuses:
            if bonus is None:
                html_table += '<td class="empty-slot">—</td>'
            elif bonus == "X":
                html_table += '<td class="crossed-slot">❌</td>'
            else:
                html_table += f'<td class="score-slot">{bonus}</td>'
        # 1 filler cell with special styling
        bonus_class = "bonus-column"
        if player_idx == 0:  # First player
            bonus_class += " player-separator"
        html_table += f'<td class="{bonus_class} empty-slot">—</td>'
    html_table += "</tr>"
    
    # Section divider
    html_table += '<tr><td colspan="' + str(len(engine.players) * 4 + 1) + '" class="section-divider"></td></tr>'
    
    # Totals row
    html_table += "<tr><td class='row-header'>TOT</td>"
    for player in engine.players:
        total_score = player.calculate_score()
        html_table += f'<td colspan="4" class="score-slot"><strong>{total_score}</strong></td>'
    html_table += "</tr>"
    
    html_table += "</tbody></table>"
    
    # Display the HTML table
    st.markdown(html_table, unsafe_allow_html=True)

# Display the clean scoreboard
render_clean_scoreboard(g)

# Current player / turn controls
player = g.players[g.current]
st.subheader(f"Turn: {player.name}")

if st.session_state.awaiting_turn:
    if st.button("Start turn"):
        g.start_turn()
        st.session_state.awaiting_turn = False
        st.rerun()
else:
    dice_cols = st.columns(len(g.dice))
    for i, c in enumerate(dice_cols):
        with c:
            face, is_joker = _parse_die(g.dice[i])
            img = _make_die_image(face, is_joker, size=96, style="fill")

            selected = i in st.session_state.selected_dice
            # add a calming yellow border if selected, soft gray if not
            border = (255, 223, 0, 255) if selected else (180, 180, 180, 255)
            draw = ImageDraw.Draw(img)
            draw.rectangle([2, 2, img.width-3, img.height-3], outline=border, width=6)

            if st.button(f"🎲", key=f"die_btn_{i}"):
                if selected:
                    st.session_state.selected_dice.remove(i)
                else:
                    st.session_state.selected_dice.add(i)
                st.rerun()

            st.image(img, width=96, caption=f"{i}:{repr(g.dice[i])}")

    cols = st.columns(3)
    cols[0].write(f"Rolls left: **{g.rolls_left}**")
    cols[1].write(f"First roll: **{g.first_roll}**")
    cols[2].write(f"Player: **{player.name}**")

    st.divider()

    # --- Reroll button uses selected dice ---
    # Custom CSS for yellow reroll button
    st.markdown("""
    <style>
    div[data-testid="stButton"] button[kind="secondary"] {
        background-color: #f4d03f !important;
        color: #2c3e50 !important;
        border: none !important;
        font-weight: 500 !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        background-color: #f1c40f !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:disabled {
        background-color: #bdc3c7 !important;
        color: #7f8c8d !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    if st.button("Reroll selected", disabled=(g.rolls_left <= 0 or not st.session_state.selected_dice), key="reroll_btn", type="secondary"):
        g.reroll(sorted(st.session_state.selected_dice))
        st.session_state.selected_dice.clear()
        st.rerun()


    st.divider()

    # Score / Cross - Radio button selection
    avail = available_rows(g, player)
    
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
        def get_descriptive_label(cat: Category) -> str:
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
        
        labels = [get_descriptive_label(c) for c in avail]
        label_to_cat = {get_descriptive_label(c): c for c in avail}
        
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
                if st.radio(f"Move {i+1}:", [label], key=f"move_{i}", label_visibility="collapsed", index=0 if st.session_state.selected_move == label else None):
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
                    slot = g.leftmost_slot(player, cat)
                    if action == "Score":
                        g.record_score(cat, slot)
                    else:
                        g.record_cross(cat, slot)
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
