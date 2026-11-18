"""
Scoreboard: every player's table, side by side.

Each player has three cells per row (filled left to right) and a bonus cell.
The current player's columns are tinted, the cell written by the most recent
move is highlighted in orange (until the next move), and the cell the picked
move would fill is outlined with its preview value.
"""

from html import escape
from typing import Optional

import streamlit as st

from abaka.constants import COMBO_CATS, SCHOOL_CATS
from abaka.engine import GameEngine
from ui_components.i18n import t
from ui_components.moves import Move, is_school, row_hint, row_name, school_number
from ui_components.style import die_uri

CROSS = "✕"
CHECK = "✓"
EMPTY = "·"


def render_scoreboard(engine: GameEngine, me: Optional[int] = None, target: Optional[Move] = None) -> None:
    """`me`: this browser's seat in an online game (marks "You"). `target`: move to preview."""
    st.html(build_scoreboard_html(engine, me, target))


def _score_cell(value, category, classes, target_text=None, last=False) -> str:
    if last:
        classes += " ab-last"
    if target_text is not None:
        return f'<td class="{classes} ab-target">{escape(target_text)}</td>'
    if value is None:
        return f'<td class="{classes} ab-none">{EMPTY}</td>'
    if value == "X":
        # In school rows an X means "settled" (exactly three, or an old balance cell).
        if is_school(category):
            return f'<td class="{classes} ab-ok" title="{t("Done")}">{CHECK}</td>'
        return f'<td class="{classes} ab-x" title="{t("Crossed out")}">{CROSS}</td>'
    cls = "ab-neg" if isinstance(value, int) and value < 0 else "ab-num"
    return f'<td class="{classes} {cls}">{value}</td>'


def _bonus_cell(value, classes) -> str:
    if value is None:
        return f'<td class="{classes} ab-none">{EMPTY}</td>'
    if value == "X":
        return f'<td class="{classes} ab-x" title="{t("Bonus crossed out")}">{CROSS}</td>'
    return f'<td class="{classes} ab-bval">{value}</td>'


def build_scoreboard_html(engine: GameEngine, me: Optional[int] = None, target: Optional[Move] = None) -> str:
    players = engine.players
    over = engine.is_game_over()
    active = None if over else engine.current
    span = 1 + 5 * len(players)  # row label + (gap + 3 cells + bonus) per player
    last = getattr(engine, "last_move", None)  # (player, category, slot) of the latest move
    many = len(players) > 2

    def act(i: int) -> str:
        return " ab-active" if i == active else ""

    h = [f'<div class="ab-board-wrap"><table class="ab-board{" ab-many" if many else ""}"><thead><tr><th></th>']
    for i, p in enumerate(players):
        dot = '<span class="ab-dot"></span>' if i == active else ""
        you = f'<span class="ab-you">{t("You")}</span>' if i == me else ""
        bal = p.school_balance
        bal_txt = f'<span style="color:#E5484D">{bal}</span>' if bal < 0 else str(bal)
        h.append(
            f'<th class="ab-gap"></th><th colspan="4" class="ab-player{act(i)}">{dot}{escape(p.name)}{you}'
            f'<div class="ab-pmeta"><span class="ab-nw">{t("{score} pts", score=p.calculate_score())}</span>'
            f'{"<br>" if many else " &middot; "}<span class="ab-nw">{t("balance {balance}", balance=bal_txt)}</span>'
            f'</div></th>'
        )
    h.append('</tr><tr class="ab-sub"><th></th>')
    for i, _ in enumerate(players):
        h.append(f'<th class="ab-gap"></th><th class="{act(i)}">I</th><th class="{act(i)}">II</th>'
                 f'<th class="{act(i)}">III</th><th class="ab-bonus{act(i)}" title="{t("Row bonus")}">★</th>')
    h.append("</tr></thead><tbody>")

    for title, cats in ((t("School"), SCHOOL_CATS), (t("Combinations"), COMBO_CATS)):
        h.append(f'<tr class="ab-section"><td colspan="{span}">{title}</td></tr>')
        for cat in cats:
            icon = f'<img src="{die_uri(school_number(cat))}" alt="">' if is_school(cat) else ""
            h.append(f'<tr><th class="ab-row" title="{escape(row_hint(cat))}">{icon}{escape(row_name(cat))}</th>')
            for i, p in enumerate(players):
                h.append('<td class="ab-gap"></td>')
                for slot in range(3):
                    hit = target is not None and i == active and target.category == cat and target.slot == slot
                    was_last = last is not None and tuple(last) == (i, cat, slot)
                    h.append(_score_cell(p.table[cat][slot], cat, act(i).strip(), target.preview if hit else None,
                                         last=was_last))
                loses_bonus = (target is not None and i == active and target.category == cat
                               and getattr(target, "bonus_lost", False))
                if loses_bonus:  # the picked move pays from the balance: preview the crossed-out bonus
                    h.append(f'<td class="ab-bonus{act(i)} ab-target" '
                             f'title="{t("This move crosses out the row bonus")}">{CROSS}</td>')
                else:
                    h.append(_bonus_cell(p.table[cat][3], "ab-bonus" + act(i)))
            h.append("</tr>")

    h.append(f'<tr class="ab-section"><td colspan="{span}">{escape(t("Bonuses & total"))}</td></tr>')
    h.append(f'<tr><th class="ab-row" title="{t("Complete a column with no crossed-out combinations")}">'
             f'{t("Column bonus")}</th>')
    for i, p in enumerate(players):
        h.append('<td class="ab-gap"></td>')
        for col, value in enumerate(p.column_bonus):
            if (target is not None and i == active and target.slot == col
                    and getattr(target, "column_bonus_lost", False)):
                # The picked move crosses out a combination in this column: preview the crossed-out bonus.
                h.append(f'<td class="{act(i).strip()} ab-target" '
                         f'title="{t("This move crosses out the column bonus")}">{CROSS}</td>')
            else:
                h.append(_bonus_cell(value, act(i).strip()))
        h.append(f'<td class="ab-bonus{act(i)}"></td>')
    h.append(f'</tr><tr class="ab-total"><th class="ab-row">{t("Total")}</th>')
    for i, p in enumerate(players):
        h.append(f'<td class="ab-gap"></td><td colspan="4" class="{act(i).strip()}">{p.calculate_score()}</td>')
    h.append("</tr></tbody></table></div>")
    if last is not None:
        h.append(f'<div class="ab-legend"><span class="ab-swatch"></span>{escape(describe_move(engine, last, me))}</div>')
    return "".join(h)


def describe_move(engine: GameEngine, move, me: Optional[int] = None) -> str:
    """'Last move: Bob scored 23 in Full house' and similar."""
    player, cat, slot = move
    who = t("You") if player == me else engine.players[player].name
    value = engine.players[player].table[cat][slot]
    name = row_name(cat)
    if is_school(cat):
        what = (t("wrote {name} (exactly three)", name=name) if value == "X"
                else t("wrote {name} (balance now {value})", name=name, value=value))
    elif value == "X":
        what = t("crossed out {name}", name=name)
    else:
        what = t("scored {value} in {name}", value=value, name=name)
    return t("Last move: {who} {what}", who=who, what=what)
