# Streamlit front-end for Abaka (works with your split package)
import io
from contextlib import redirect_stdout

import streamlit as st
import re
from PIL import Image, ImageDraw


from abaka.engine import GameEngine
from abaka.models import Category

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

# ---------- session boot ----------
if "engine" not in st.session_state:
    st.session_state.engine = None
    st.session_state.awaiting_turn = True  # waiting to start the current player's turn

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
st.code(render_scoreboard(g), language="text")

# Current player / turn controls
player = g.players[g.current]
st.subheader(f"Turn: {player.name}")

if st.session_state.awaiting_turn:
    if st.button("Start turn"):
        g.start_turn()
        st.session_state.awaiting_turn = False
        st.rerun()
else:
    # Show dice (images) & turn state
    dice_cols = st.columns(len(g.dice))
    for i, c in enumerate(dice_cols):
        with c:
            face, is_joker = _parse_die(g.dice[i])
            img = _make_die_image(face, is_joker, size=96, style="fill")  # try 'outline' or 'band'
            st.image(img, width=96, caption=f"{i}:{repr(g.dice[i])}")

    cols = st.columns(3)
    cols[0].write(f"Rolls left: **{g.rolls_left}**")
    cols[1].write(f"First roll: **{g.first_roll}**")
    cols[2].write(f"Player: **{player.name}**")

    st.divider()

    # Reroll block
    st.markdown("**Reroll**")
    options = list(range(len(g.dice)))
    show_opt = [f"{i}:{repr(g.dice[i])}" for i in options]
    idxs = st.multiselect("Select dice to reroll", options, default=[], format_func=lambda i: show_opt[i])
    if st.button("Reroll selected", disabled=(g.rolls_left <= 0)):
        try:
            g.reroll(idxs)
            st.rerun()
        except Exception as e:
            st.error(str(e))

    st.divider()

    # Score / Cross
    avail = available_rows(g, player)
    labels = [label_for(c) for c in avail]
    label_to_cat = {label_for(c): c for c in avail}

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**Score row**")
        pick = st.selectbox("Choose a row to score", ["—"] + labels, index=0)
        if st.button("Score selected", type="primary"):
            if pick != "—":
                cat = label_to_cat[pick]
                try:
                    slot = g.leftmost_slot(player, cat)
                    g.record_score(cat, slot)
                    st.session_state.awaiting_turn = True  # next player's turn
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.info("Pick a row to score.")

    with c2:
        st.markdown("**Cross row**")
        pickx = st.selectbox("Choose a row to cross", ["—"] + labels, index=0, key="cross_sel")
        if st.button("Cross selected"):
            if pickx != "—":
                cat = label_to_cat[pickx]
                try:
                    slot = g.leftmost_slot(player, cat)
                    g.record_cross(cat, slot)
                    st.session_state.awaiting_turn = True
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
            else:
                st.info("Pick a row to cross.")
