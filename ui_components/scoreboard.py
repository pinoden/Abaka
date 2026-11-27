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
from abaka.i18n import t
from abaka.moves import Move, is_school, row_hint, row_name, school_number
from abaka.turns import what_was_written
from ui_components.style import die_uri

CROSS = "✕"
CHECK = "✓"
EMPTY = "·"


def render_scoreboard(engine: GameEngine, me: Optional[int] = None, target: Optional[Move] = None,
                      differences: Optional[dict] = None) -> None:
    """`me`: this browser's seat in an online game (marks "You"). `target`: move to preview.
    `differences`: abaka.standings.row_differences, drawn as a last column (None: not shown)."""
    st.html(build_scoreboard_html(engine, me, target, differences))


def _diff_cell(value) -> str:
    """One row's difference: +12 in green, −8 in red, 0 in grey, nothing while nobody wrote there."""
    if value is None:
        return '<td class="ab-gap"></td><td class="ab-diff"></td>'
    if value > 0:
        return f'<td class="ab-gap"></td><td class="ab-diff up">+{value}</td>'
    if value < 0:
        return f'<td class="ab-gap"></td><td class="ab-diff down">−{-value}</td>'
    return '<td class="ab-gap"></td><td class="ab-diff">0</td>'


def _bonus_cell(value, classes: str, crossed_tail: str) -> str:
    if value is None:
        return f'<td class="{classes} ab-none">{EMPTY}</td>'
    if value == "X":
        return f'<td class="{classes}{crossed_tail}'
    return f'<td class="{classes} ab-bval">{value}</td>'


def build_scoreboard_html(engine: GameEngine, me: Optional[int] = None, target: Optional[Move] = None,
                          differences: Optional[dict] = None) -> str:
    """
    The whole table as HTML. It has about 75 cells per player and is drawn on every page
    run, so everything that does not depend on the cell (translated tooltips, each
    player's classes, the highlighted cells) is worked out once, outside the loops.
    """
    players = engine.players
    over = engine.is_game_over()
    active = None if over else engine.current
    diffs = differences
    span = 1 + 5 * len(players) + (2 if diffs else 0)  # row label + (gap + 3 cells + bonus) per player
    last = getattr(engine, "last_move", None)  # (player, category, slot) of the latest move
    last = tuple(last) if last is not None else (None, None, None)
    many = len(players) > 2
    acts = [" ab-active" if i == active else "" for i in range(len(players))]  # header and bonus cells
    plain = [a.strip() for a in acts]                                            # score cells
    scores = [p.calculate_score() for p in players]
    # The end of a crossed-out cell: in School rows an X means "settled" (exactly three, or an
    # old balance cell), elsewhere a crossed-out combination.
    school_x = f' ab-ok" title="{t("Done")}">{CHECK}</td>'
    combo_x = f' ab-x" title="{t("Crossed out")}">{CROSS}</td>'
    bonus_x = f' ab-x" title="{t("Bonus crossed out")}">{CROSS}</td>'
    # The picked move: which cell it fills, and which bonus cells it gives up (previewed as crossed out).
    aim_cat = target.category if target is not None and active is not None else None
    aim_slot = target.slot if aim_cat is not None else None

    h = [f'<div class="ab-board-wrap"><table class="ab-board{" ab-many" if many else ""}{" ab-diffs" if diffs else ""}">'
         '<thead><tr><th></th>']
    for i, p in enumerate(players):
        dot = '<span class="ab-dot"></span>' if i == active else ""
        you = f'<span class="ab-you">{t("You")}</span>' if i == me else ""
        bal = p.school_balance
        bal_txt = f'<span style="color:#E5484D">{bal}</span>' if bal < 0 else str(bal)
        h.append(
            f'<th class="ab-gap"></th><th colspan="4" class="ab-player{acts[i]}">{dot}{escape(p.name)}{you}'
            f'<div class="ab-pmeta"><span class="ab-nw">{t("{score} pts", score=scores[i])}</span>'
            f'{"<br>" if many else " &middot; "}<span class="ab-nw">{t("balance {balance}", balance=bal_txt)}</span>'
            f'</div></th>'
        )
    if diffs:
        h.append(f'<th class="ab-gap"></th><th class="ab-diff ab-diff-head" title="{escape(diffs["hint"])}">'
                 f'{escape(diffs["title"])}</th>')
    h.append('</tr><tr class="ab-sub"><th></th>')
    row_bonus_tip = t("Row bonus")
    for a in acts:
        h.append(f'<th class="ab-gap"></th><th class="{a}">I</th><th class="{a}">II</th>'
                 f'<th class="{a}">III</th><th class="ab-bonus{a}" title="{row_bonus_tip}">★</th>')
    if diffs:
        h.append('<th class="ab-gap"></th><th class="ab-diff"></th>')
    h.append("</tr></thead><tbody>")

    lose_row_tip = t("This move crosses out the row bonus")
    for title, cats in ((t("School"), SCHOOL_CATS), (t("Combinations"), COMBO_CATS)):
        h.append(f'<tr class="ab-section"><td colspan="{span}">{title}</td></tr>')
        for cat in cats:
            school = is_school(cat)
            crossed_tail = school_x if school else combo_x
            icon = f'<img src="{die_uri(school_number(cat))}" alt="">' if school else ""
            h.append(f'<tr><th class="ab-row" title="{escape(row_hint(cat))}">{icon}{escape(row_name(cat))}</th>')
            aimed = cat == aim_cat
            for i, p in enumerate(players):
                cells = p.table[cat]
                h.append('<td class="ab-gap"></td>')
                for slot in range(3):
                    classes = plain[i]
                    if i == last[0] and cat == last[1] and slot == last[2]:
                        classes += " ab-last"
                    if aimed and i == active and slot == aim_slot:
                        h.append(f'<td class="{classes} ab-target">{escape(target.preview)}</td>')
                        continue
                    value = cells[slot]
                    if value is None:
                        h.append(f'<td class="{classes} ab-none">{EMPTY}</td>')
                    elif value == "X":
                        h.append(f'<td class="{classes}{crossed_tail}')
                    else:
                        cls = "ab-neg" if isinstance(value, int) and value < 0 else "ab-num"
                        h.append(f'<td class="{classes} {cls}">{value}</td>')
                if aimed and i == active and getattr(target, "bonus_lost", False):
                    # The picked move pays from the balance: preview the crossed-out bonus.
                    h.append(f'<td class="ab-bonus{acts[i]} ab-target" title="{lose_row_tip}">{CROSS}</td>')
                else:
                    h.append(_bonus_cell(cells[3], "ab-bonus" + acts[i], bonus_x))
            if diffs:
                h.append(_diff_cell(diffs["rows"].get(cat.name)))
            h.append("</tr>")

    h.append(f'<tr class="ab-section"><td colspan="{span}">{escape(t("Bonuses & total"))}</td></tr>')
    h.append(f'<tr><th class="ab-row" title="{t("Complete a column with no crossed-out combinations")}">'
             f'{t("Column bonus")}</th>')
    lose_column = aim_cat is not None and getattr(target, "column_bonus_lost", False)
    lose_column_tip = t("This move crosses out the column bonus")
    for i, p in enumerate(players):
        h.append('<td class="ab-gap"></td>')
        for col, value in enumerate(p.column_bonus):
            if lose_column and i == active and col == aim_slot:
                # The picked move crosses out a combination in this column: preview the crossed-out bonus.
                h.append(f'<td class="{plain[i]} ab-target" title="{lose_column_tip}">{CROSS}</td>')
            else:
                h.append(_bonus_cell(value, plain[i], bonus_x))
        h.append(f'<td class="ab-bonus{acts[i]}"></td>')
    if diffs:
        h.append(_diff_cell(diffs["columns"] if any(v is not None for p in players for v in p.column_bonus)
                            else None))
    h.append(f'</tr><tr class="ab-total"><th class="ab-row">{t("Total")}</th>')
    for i in range(len(players)):
        h.append(f'<td class="ab-gap"></td><td colspan="4" class="{plain[i]}">{scores[i]}</td>')
    if diffs:
        h.append(_diff_cell(diffs["total"]))
    h.append("</tr></tbody></table></div>")
    if last[0] is not None:
        h.append(f'<div class="ab-legend"><span class="ab-swatch"></span>'
                 f'{escape(describe_move(engine, last, me))}</div>')
    return "".join(h)


def describe_move(engine: GameEngine, move, me: Optional[int] = None) -> str:
    """'Last move: Bob scored 23 in Full house' and similar."""
    who = t("You") if move[0] == me else engine.players[move[0]].name
    return t("Last move: {who} {what}", who=who, what=what_was_written(engine, move))
