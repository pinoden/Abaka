"""
Scoreboard: every player's table, side by side.

Each player has three cells per row (filled left to right) and a bonus cell.
The current player's columns are tinted, and the cell the picked move would
fill is outlined with its preview value.
"""

from html import escape
from typing import Optional

import streamlit as st

from abaka.constants import COMBO_CATS, SCHOOL_CATS
from abaka.engine import GameEngine
from ui_components.moves import Move, is_school, row_hint, row_name, school_number
from ui_components.style import die_uri

CROSS = "✕"
CHECK = "✓"
EMPTY = "·"
NONE = "–"


def render_scoreboard(engine: GameEngine, me: Optional[int] = None, target: Optional[Move] = None) -> None:
    """`me`: this browser's seat in an online game (marks "You"). `target`: move to preview."""
    st.html(build_scoreboard_html(engine, me, target))


def _score_cell(value, category, classes, target_text=None) -> str:
    if target_text is not None:
        return f'<td class="{classes} ab-target">{escape(target_text)}</td>'
    if value is None:
        return f'<td class="{classes} ab-none">{EMPTY}</td>'
    if value == "X":
        # In school rows an X means "settled" (exactly three, or an old balance cell).
        if is_school(category):
            return f'<td class="{classes} ab-ok" title="Done">{CHECK}</td>'
        return f'<td class="{classes} ab-x" title="Crossed out">{CROSS}</td>'
    cls = "ab-neg" if isinstance(value, int) and value < 0 else "ab-num"
    return f'<td class="{classes} {cls}">{value}</td>'


def _bonus_cell(value, classes) -> str:
    if value is None:
        return f'<td class="{classes} ab-none">{EMPTY}</td>'
    if value == "X":
        return f'<td class="{classes} ab-none" title="No bonus">{NONE}</td>'
    return f'<td class="{classes} ab-bval">{value}</td>'


def build_scoreboard_html(engine: GameEngine, me: Optional[int] = None, target: Optional[Move] = None) -> str:
    players = engine.players
    over = engine.is_game_over()
    active = None if over else engine.current
    span = 1 + 5 * len(players)  # row label + (gap + 3 cells + bonus) per player

    def act(i: int) -> str:
        return " ab-active" if i == active else ""

    h = ['<div class="ab-board-wrap"><table class="ab-board"><thead><tr><th></th>']
    for i, p in enumerate(players):
        dot = '<span class="ab-dot"></span>' if i == active else ""
        you = '<span class="ab-you">You</span>' if i == me else ""
        bal = p.school_balance
        bal_txt = f'<span style="color:#E5484D">{bal}</span>' if bal < 0 else str(bal)
        h.append(
            f'<th class="ab-gap"></th><th colspan="4" class="ab-player{act(i)}">{dot}{escape(p.name)}{you}'
            f'<div class="ab-pmeta">{p.calculate_score()} pts · balance {bal_txt}</div></th>'
        )
    h.append('</tr><tr class="ab-sub"><th></th>')
    for i, _ in enumerate(players):
        h.append(f'<th class="ab-gap"></th><th class="{act(i)}">I</th><th class="{act(i)}">II</th>'
                 f'<th class="{act(i)}">III</th><th class="ab-bonus{act(i)}" title="Row bonus">★</th>')
    h.append("</tr></thead><tbody>")

    for title, cats in (("School", SCHOOL_CATS), ("Combinations", COMBO_CATS)):
        h.append(f'<tr class="ab-section"><td colspan="{span}">{title}</td></tr>')
        for cat in cats:
            icon = f'<img src="{die_uri(school_number(cat))}" alt="">' if is_school(cat) else ""
            h.append(f'<tr><th class="ab-row" title="{escape(row_hint(cat))}">{icon}{escape(row_name(cat))}</th>')
            for i, p in enumerate(players):
                h.append('<td class="ab-gap"></td>')
                for slot in range(3):
                    hit = target is not None and i == active and target.category == cat and target.slot == slot
                    h.append(_score_cell(p.table[cat][slot], cat, act(i).strip(), target.preview if hit else None))
                h.append(_bonus_cell(p.table[cat][3], "ab-bonus" + act(i)))
            h.append("</tr>")

    h.append(f'<tr class="ab-section"><td colspan="{span}">Bonuses &amp; total</td></tr>')
    h.append('<tr><th class="ab-row" title="Complete a column with no crossed-out combinations">Column bonus</th>')
    for i, p in enumerate(players):
        h.append('<td class="ab-gap"></td>')
        for value in p.column_bonus:
            h.append(_bonus_cell(value, act(i).strip()))
        h.append(f'<td class="ab-bonus{act(i)}"></td>')
    h.append('</tr><tr class="ab-total"><th class="ab-row">Total</th>')
    for i, p in enumerate(players):
        h.append(f'<td class="ab-gap"></td><td colspan="4" class="{act(i).strip()}">{p.calculate_score()}</td>')
    h.append("</tr></tbody></table></div>")
    return "".join(h)
