"""
Scoreboard component for Abaka game interface.
Handles rendering of the game scoreboard with proper styling and layout.
"""

import streamlit as st
from abaka.engine import GameEngine
from abaka.models import Category


def render_scoreboard(engine: GameEngine) -> None:
    """Render the complete Abaka scoreboard."""
    st.subheader("Scoreboard")
    
    # Custom CSS for the scoreboard table
    _render_scoreboard_css()
    
    # Create and display the scoreboard
    html_table = _build_scoreboard_html(engine)
    st.markdown(html_table, unsafe_allow_html=True)


def _render_scoreboard_css() -> None:
    """Render the CSS styling for the scoreboard."""
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


def _build_scoreboard_html(engine: GameEngine) -> str:
    """Build the complete HTML table for the scoreboard."""
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
    
    # Add school categories
    html_table += _build_school_section(engine)
    
    # Add combo categories
    html_table += _build_combo_section(engine)
    
    # Add column bonuses
    html_table += _build_bonus_section(engine)
    
    # Add totals
    html_table += _build_totals_section(engine)
    
    html_table += "</tbody></table>"
    return html_table


def _build_school_section(engine: GameEngine) -> str:
    """Build the school categories section of the scoreboard."""
    html = ""
    for i in range(1, 7):
        html += f"<tr><td class='row-header'>{i}</td>"
        for player_idx, player in enumerate(engine.players):
            slots = player.table[getattr(Category, f'SCHOOL_{i}')]
            # 3 score slots
            for j in range(3):
                if slots[j] is None:
                    html += '<td class="empty-slot">—</td>'
                elif slots[j] == "X":
                    html += '<td class="crossed-slot">❌</td>'
                else:
                    html += f'<td class="score-slot">{slots[j]}</td>'
            # 1 bonus slot with special styling
            bonus_class = "bonus-column"
            if player_idx == 0:  # First player
                bonus_class += " player-separator"
            
            if slots[3] is None:
                html += f'<td class="{bonus_class} empty-slot">—</td>'
            elif slots[3] == "X":
                html += f'<td class="{bonus_class} crossed-slot">❌</td>'
            else:
                html += f'<td class="{bonus_class} bonus-slot">{slots[3]}</td>'
        html += "</tr>"
    return html


def _build_combo_section(engine: GameEngine) -> str:
    """Build the combination categories section of the scoreboard."""
    html = ""
    # Section divider
    html += '<tr><td colspan="' + str(len(engine.players) * 4 + 1) + '" class="section-divider"></td></tr>'
    
    combo_labels = ["D", "DD", "T", "LS", "BS", "F", "C", "A", "Σ"]
    combo_cats = [Category.PAIR, Category.TWO_PAIRS, Category.TRIPS, 
                  Category.SMALL_STRAIGHT, Category.LARGE_STRAIGHT, 
                  Category.FULL, Category.KARE, Category.ABAKA, Category.SUM]
    
    for i, (label, cat) in enumerate(zip(combo_labels, combo_cats)):
        html += f"<tr><td class='row-header'>{label}</td>"
        for player_idx, player in enumerate(engine.players):
            slots = player.table[cat]
            # 3 score slots
            for j in range(3):
                if slots[j] is None:
                    html += '<td class="empty-slot">—</td>'
                elif slots[j] == "X":
                    html += '<td class="crossed-slot">❌</td>'
                else:
                    html += f'<td class="score-slot">{slots[j]}</td>'
            # 1 bonus slot with special styling
            bonus_class = "bonus-column"
            if player_idx == 0:  # First player
                bonus_class += " player-separator"
            
            if slots[3] is None:
                html += f'<td class="{bonus_class} empty-slot">—</td>'
            elif slots[3] == "X":
                html += f'<td class="{bonus_class} crossed-slot">❌</td>'
            else:
                html += f'<td class="{bonus_class} bonus-slot">{slots[3]}</td>'
        html += "</tr>"
    return html


def _build_bonus_section(engine: GameEngine) -> str:
    """Build the column bonuses section of the scoreboard."""
    html = ""
    # Section divider
    html += '<tr><td colspan="' + str(len(engine.players) * 4 + 1) + '" class="section-divider"></td></tr>'
    
    # Column bonuses row (B)
    html += "<tr><td class='row-header'>B</td>"
    for player_idx, player in enumerate(engine.players):
        col_bonuses = player.column_bonus
        # 3 column bonuses
        for bonus in col_bonuses:
            if bonus is None:
                html += '<td class="empty-slot">—</td>'
            elif bonus == "X":
                html += '<td class="crossed-slot">❌</td>'
            else:
                html += f'<td class="score-slot">{bonus}</td>'
        # 1 filler cell with special styling
        bonus_class = "bonus-column"
        if player_idx == 0:  # First player
            bonus_class += " player-separator"
        html += f'<td class="{bonus_class} empty-slot">—</td>'
    html += "</tr>"
    return html


def _build_totals_section(engine: GameEngine) -> str:
    """Build the totals section of the scoreboard."""
    html = ""
    # Section divider
    html += '<tr><td colspan="' + str(len(engine.players) * 4 + 1) + '" class="section-divider"></td></tr>'
    
    # Totals row
    html += "<tr><td class='row-header'>TOT</td>"
    for player in engine.players:
        total_score = player.calculate_score()
        html += f'<td colspan="4" class="score-slot"><strong>{total_score}</strong></td>'
    html += "</tr>"
    return html
