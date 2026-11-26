"""
The scores by move, under the score table (a tester, 2026-11-26: "like the chart of a chess
game, a curve per player"). The points come from abaka/standings.py, which the API sends to
apps too; here they are drawn as an inline SVG, so nothing is loaded and it costs a page run
about as much as the table's last row. Names are typed by players, so they are escaped.
"""

from html import escape
from typing import List, Optional

import streamlit as st

from abaka.i18n import t
from abaka.standings import score_history

# One colour per seat, the same in the app (mobile/src/components/Chart.tsx).
COLORS = ("#4F46E5", "#F59E0B", "#10B981", "#E5484D", "#A855F7")
# The lines are drawn in a box 1000 x 100 that stretches to the chart's width and height (the
# strokes keep their width); the labels are HTML, so they keep their size on a phone too.
WIDTH, HEIGHT, PAD = 1000, 100, 5


def render_score_chart(engine, me: Optional[int]) -> None:
    html = score_chart_html(engine, me)
    if html:
        st.html(html)


def score_chart_html(engine, me: Optional[int]) -> str:
    """The chart, or "" until there are two points to join."""
    history = score_history(engine)
    if len(history) < 2:
        return ""
    moves = [point["move"] for point in history]
    values = [v for point in history for v in point["totals"]]
    low, high = min(0, min(values)), max(0, max(values))
    if high == low:
        high = low + 1
    first, last = moves[0], moves[-1]

    def x(move: int) -> float:
        return (move - first) * WIDTH / (last - first)

    def y(value: int) -> float:  # from the top, leaving PAD above and below
        return PAD + (high - value) * (HEIGHT - 2 * PAD) / (high - low)

    lines, labels = [], []
    for value in sorted({low, 0, high}):
        dash = "" if value == 0 else ' stroke-dasharray="3 4"'
        lines.append(f'<line x1="0" x2="{WIDTH}" y1="{y(value):.2f}" y2="{y(value):.2f}" stroke="#E2E4EE" '
                     f'vector-effect="non-scaling-stroke"{dash}/>')
        labels.append(f'<span class="ab-chart-y" style="top:{y(value):.2f}%">{value}</span>')
    players = engine.players
    order = [i for i in range(len(players)) if i != me] + ([me] if me is not None else [])  # the viewer on top
    for seat in order:
        points = " ".join(f"{x(point['move']):.1f},{y(point['totals'][seat]):.2f}" for point in history)
        lines.append(f'<polyline points="{points}" fill="none" stroke="{COLORS[seat % len(COLORS)]}" '
                     f'stroke-width="{3 if seat == me else 2}" stroke-linejoin="round" stroke-linecap="round" '
                     f'vector-effect="non-scaling-stroke"/>')
    keys: List[str] = []
    for seat, p in enumerate(players):
        name = t("You") if seat == me else p.name
        keys.append(f'<span><i style="--c:{COLORS[seat % len(COLORS)]}"></i>{escape(name)} '
                    f'<b>{history[-1]["totals"][seat]}</b></span>')
    title = escape(t("Scores by move"))
    return (f'<div class="ab-chart"><div class="ab-chart-title">{title}</div>'
            f'<div class="ab-chart-plot"><svg viewBox="0 0 {WIDTH} {HEIGHT}" preserveAspectRatio="none" '
            f'role="img" aria-label="{title}">{"".join(lines)}</svg>{"".join(labels)}</div>'
            f'<div class="ab-chart-x"><span>{first}</span><span>{escape(t("move {n}", n=last))}</span></div>'
            f'<div class="ab-chart-keys">{"".join(keys)}</div></div>')
