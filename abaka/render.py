from __future__ import annotations
from typing import List
from .models import Category
from .constants import ROW_W, COL_W, SCHOOL_CATS, COMBO_CATS

def label_for(cat: Category) -> str:
    if cat.name.startswith("SCHOOL_"):
        return cat.name.split("_")[1]
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

def _fmt_cell(v) -> str:
    if v is None: return " . "
    if v == "X": return " X "
    return f"{int(v):>3}"

def _fmt_player_cells(slots: List[object]) -> str:
    """
    Render one player's 4 cells with a vertical bar before the bonus cell:
    'c0 c1 c2 | bonus'
    """
    core = " ".join(_fmt_cell(v) for v in slots[:3])
    bonus = _fmt_cell(slots[3])
    return f"{core} | {bonus}"

def render_scoreboard(engine) -> List[str]:
    """Return scoreboard lines (no printing)."""
    # Header with double bar between players
    parts: List[str] = [f"{'Row':>{ROW_W}} "]
    for i, p in enumerate(engine.players):
        sep = "|" if i == 0 else "||"
        parts.append(f"{sep} {p.name:^{COL_W}} ")
    header = "".join(parts)
    sep_line = "-" * len(header)

    lines: List[str] = ["", header, sep_line]

    # Body rows
    def add_row(cat: Category) -> None:
        line_parts: List[str] = [f"{label_for(cat):>{ROW_W}} "]
        for i, pl in enumerate(engine.players):
            sep = "|" if i == 0 else "||"
            cells = _fmt_player_cells(pl.table[cat])
            line_parts.append(f"{sep} {cells:<{COL_W}} ")
        lines.append("".join(line_parts))

    # School
    for cat in SCHOOL_CATS:
        add_row(cat)
    lines.append(sep_line)

    # Combos
    for cat in COMBO_CATS:
        add_row(cat)

    # Separator before bonus row
    lines.append(sep_line)

    # Column bonuses row (B) — show 3 column bonuses and a bar before the filler "bonus" cell
    bonus_parts: List[str] = [f"{'B':>{ROW_W}} "]
    for i, p in enumerate(engine.players):
        sep = "|" if i == 0 else "||"
        three = " ".join(_fmt_cell(v) for v in p.column_bonus)
        # pad to 4th cell with a visual bar before it
        cells = f"{three} | {' . ':>3}"
        bonus_parts.append(f"{sep} {cells:<{COL_W}} ")
    lines.append("".join(bonus_parts))

    # Separator after bonus row
    lines.append(sep_line)

    # Totals line with double bar between players
    tot_parts: List[str] = [f"{'TOT':>{ROW_W}} "]
    for i, p in enumerate(engine.players):
        sep = "|" if i == 0 else "||"
        tot_parts.append(f"{sep} {p.calculate_score():>{COL_W}} ")
    lines.append("".join(tot_parts))

    return lines
