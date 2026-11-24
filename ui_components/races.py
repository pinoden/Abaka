"""
The races for the shared bonuses, at the foot of the play card (Backlog item 30): cells left
in column I and II for every player, and the rows where two or more players are one cell from
the bonus. What to say comes from abaka/races.py, which the API sends to apps too; here it is
only drawn. Names are typed by players, so everything is escaped.
"""

from html import escape
from typing import Optional

import streamlit as st

from abaka.races import bonus_races


def render_races(engine, me: Optional[int]) -> None:
    html = races_html(engine, me)
    if html:
        st.html(html)


def races_html(engine, me: Optional[int]) -> str:
    races = bonus_races(engine, me)
    if races is None:
        return ""
    parts = []
    if races["columns"]:
        heads = "".join(f'<th class="ab-race-who{" me" if i == me else ""}" title="{escape(name)}">'
                        f'{escape(name)}</th>' for i, name in enumerate(races["heads"]))
        body = []
        for column in races["columns"]:
            fewest = min(column["left"])
            cells = []
            for left, can_earn in zip(column["left"], column["open"]):
                classes = " ".join(c for c in ("lead" if left == fewest else "", "" if can_earn else "off") if c)
                cross = "" if can_earn else '<span class="ab-race-x">✕</span>'
                cells.append(f'<td class="{classes}">{left}{cross}</td>' if classes else f"<td>{left}</td>")
            body.append(f'<tr><th>{escape(column["label"])}</th>{"".join(cells)}</tr>')
        parts.append(f'<table class="ab-race-table"><thead><tr><th class="ab-race-title">'
                     f'{escape(races["title"])}</th>{heads}</tr></thead><tbody>{"".join(body)}</tbody></table>')
    parts += [f'<div class="ab-race-row">{escape(row["text"])}</div>' for row in races["rows"]]
    if races["note"]:
        parts.append(f'<div class="ab-race-note">{escape(races["note"])}</div>')
    return f'<div class="ab-race">{"".join(parts)}</div>'
