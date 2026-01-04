"""
Dice display component for Abaka game interface.
Handles rendering of dice, selection, and reroll functionality.
"""

import streamlit as st
from PIL import Image, ImageDraw
from abaka.engine import GameEngine
from abaka.models import Category


def render_dice_section(engine: GameEngine, read_only: bool = False) -> None:
    """Render the dice section with selection and reroll functionality."""
    # Dice display
    dice_cols = st.columns(len(engine.dice))
    for i, c in enumerate(dice_cols):
        with c:
            face, is_joker = _parse_die(engine.dice[i])
            img = _make_die_image(face, is_joker, size=96, style="fill")

            selected = i in st.session_state.selected_dice
            # add a calming yellow border if selected, soft gray if not
            border = (255, 223, 0, 255) if selected else (180, 180, 180, 255)
            draw = ImageDraw.Draw(img)
            draw.rectangle([2, 2, img.width-3, img.height-3], outline=border, width=6)

            # Disable dice clicking if read_only
            if st.button(f"🎲", key=f"die_btn_{i}", disabled=read_only):
                if selected:
                    st.session_state.selected_dice.remove(i)
                else:
                    st.session_state.selected_dice.add(i)
                st.rerun()

            st.image(img, width=96, caption=f"{i}:{repr(engine.dice[i])}")

    # Game info and reroll
    _render_game_info(engine)
    _render_reroll_section(engine, read_only)


def _render_game_info(engine: GameEngine) -> None:
    """Render game information (rolls left, first roll, player)."""
    cols = st.columns(3)
    cols[0].write(f"Rolls left: **{engine.rolls_left}**")
    cols[1].write(f"First roll: **{engine.first_roll}**")
    cols[2].write(f"Player: **{engine.players[engine.current].name}**")


def _render_reroll_section(engine: GameEngine, read_only: bool) -> None:
    """Render the reroll button section."""
    st.divider()
    
    # Updated CSS for visibility without aggressive overrides
    st.markdown("""
    <style>
    div[data-testid="stButton"] button[kind="secondary"] {
        border: 2px solid #ccc !important;
    }
    div[data-testid="stButton"] button[kind="secondary"]:hover {
        border-color: #f1c40f !important;
        background-color: #fef9e7 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Disable reroll if read_only, no rolls left, or no dice selected
    should_disable = (
        read_only or 
        engine.rolls_left <= 0 or 
        not st.session_state.selected_dice
    )
    
    if st.button("Reroll selected", 
                 disabled=should_disable, 
                 key="reroll_btn", 
                 type="secondary"):
        engine.reroll(sorted(st.session_state.selected_dice))
        st.session_state.selected_dice.clear()
        st.rerun()


def _parse_die(d) -> tuple[int, bool]:
    """Return (face 1..6, is_joker) from whatever GameEngine puts in g.dice."""
    v = getattr(d, "value", None)
    is_joker = bool(getattr(d, "is_joker", getattr(d, "joker", False)))
    if v is None:
        import re
        s = repr(d)
        m = re.match(r"J\((\d)\)", s)
        if m:
            v = int(m.group(1)); is_joker = True
        else:
            m2 = re.match(r"(\d)", s)
            v = int(m2.group(1)) if m2 else 1
    return int(v), bool(is_joker)


def _make_die_image(value: int, is_joker: bool, size: int = 96, style: str = "fill") -> Image.Image:
    """Create a die image with the specified value and joker status."""
    JOKER_FILL_COLOR = (59, 130, 128, 255)
    JOKER_OUTLINE_COLOR = (96, 165, 250, 255)
    JOKER_BAND_COLOR = (250, 204, 21, 220)
    PIP_COLOR = (20, 20, 20, 255)
    
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    fill = (255, 255, 255, 255)
    outline = (30, 30, 30, 255)

    if is_joker:
        if style == "fill":
            fill, outline = JOKER_FILL_COLOR, JOKER_OUTLINE_COLOR
        elif style == "outline":
            outline = JOKER_OUTLINE_COLOR

    rect = (6, 6, size - 6, size - 6)
    d.rounded_rectangle(rect, radius=16, fill=fill, outline=outline, width=6)

    if is_joker and style == "band":
        pad = 10
        band = [
            (pad,            size*0.35),
            (size*0.35,      pad),
            (size-pad,       size*0.65),
            (size*0.65,      size-pad),
        ]
        d.polygon(band, fill=JOKER_BAND_COLOR)

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