from __future__ import annotations
from typing import List
from .models import Category
from .constants import ROW_W, COL_W, SCHOOL_CATS, COMBO_CATS

def label_for(cat: Category) -> str:
    if cat.name.startswith("SCHOOL_"):
        return cat.name.split('_')[1]
    return {
        Category.PAIR: 'D',  Category.TWO_PAIRS: 'DD', Category.TRIPS: 'T',
        Category.SMALL_STRAIGHT: 'LS', Category.LARGE_STRAIGHT: 'BS',
        Category.FULL: 'F',  Category.KARE: 'C',     Category.ABAKA: 'A',
        Category.SUM: 'Σ',
    }[cat]

def _fmt_cell(v) -> str:
    if v is None: return ' . '
    if v == 'X': return ' X '
    return f"{int(v):>3}"

def render_scoreboard(engine) -> List[str]:
    """Return scoreboard lines (no printing)."""
    header = f"{'Row':>{ROW_W}} " + ''.join(f"| {p.name:^{COL_W}} " for p in engine.players)
    sep = '-' * len(header)
    lines: List[str] = ["", header, sep]

    def row(cat: Category) -> None:
        label = label_for(cat)
        line = f"{label:>{ROW_W}} "
        for p in engine.players:
            cells = ' '.join(_fmt_cell(v) for v in p.table[cat])  # 4 cells
            line += f"| {cells:<{COL_W}} "
        lines.append(line)

    for cat in SCHOOL_CATS: row(cat)
    lines.append(sep)
    for cat in COMBO_CATS: row(cat)

    # separator before bonus row
    lines.append(sep)
    # column bonuses row (B)
    line = f"{'B':>{ROW_W}} "
    for p in engine.players:
        cells3 = ' '.join(_fmt_cell(v) for v in p.column_bonus)
        cells = f"{cells3} {' . ':>3}"  # pad to 4 cells
        line += f"| {cells:<{COL_W}} "
    lines.append(line)
    # separator after bonus row
    lines.append(sep)

    total = f"{'TOT':>{ROW_W}} " + ''.join(f"| {p.calculate_score():>{COL_W}} " for p in engine.players)
    lines.append(total)
    return lines
