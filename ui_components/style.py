"""
Look and feel: page-wide CSS, dice artwork and small HTML helpers.

Colours and radii for Streamlit's own widgets come from .streamlit/config.toml;
this file styles what the theme cannot reach (cards, dice, scoreboard).
Widgets are targeted through the `st-key-<key>` class Streamlit adds to any
element created with a `key`.
"""

from functools import lru_cache
from html import escape
from urllib.parse import quote

import streamlit as st

ACCENT = "#4F46E5"

_GRID = [(28, 28), (50, 28), (72, 28), (28, 50), (50, 50), (72, 50), (28, 72), (50, 72), (72, 72)]
_PIPS = {1: [4], 2: [0, 8], 3: [0, 4, 8], 4: [0, 2, 6, 8], 5: [0, 2, 4, 6, 8], 6: [0, 2, 3, 5, 6, 8]}


@lru_cache(maxsize=None)
def die_uri(value: int, joker: bool = False) -> str:
    """A die face as an SVG data URI. The joker is dark with gold pips."""
    if joker:
        face, edge, pip = "#262B45", "#262B45", "#FBBF24"
    else:
        face, edge, pip = "#FFFFFF", "#DADDE8", "#262B45"
    pips = "".join(
        f'<circle cx="{_GRID[i][0]}" cy="{_GRID[i][1]}" r="8.5" fill="{pip}"/>' for i in _PIPS[int(value)]
    )
    svg = (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
        f'<rect x="2" y="2" width="96" height="96" rx="20" fill="{face}" stroke="{edge}" stroke-width="3"/>'
        f"{pips}</svg>"
    )
    return "data:image/svg+xml," + quote(svg)


def brand_html(size: int = 34) -> str:
    return (
        f'<div class="ab-brand"><img src="{die_uri(5)}" width="{size}" height="{size}" alt="">'
        "<span>Abaka</span></div>"
    )


def chip(text: str, kind: str = "") -> str:
    return f'<span class="ab-chip {kind}">{escape(text)}</span>'


def inject_global_css() -> None:
    st.html(f"<style>{_CSS}</style>")


_CSS = """
/* ---------- page ---------- */
header[data-testid="stHeader"] { display: none; }
[data-testid="stMainBlockContainer"] { padding-top: 1.25rem; padding-bottom: 4rem; max-width: 1220px; }
h1, h2, h3 { letter-spacing: -0.02em; }

/* ---------- cards ---------- */
[class*="st-key-card"] {
  background: #FFFFFF;
  border-radius: 20px !important;
  box-shadow: 0 1px 2px rgba(20, 24, 40, .04), 0 10px 30px rgba(20, 24, 40, .06);
  padding: 1.4rem 1.4rem 1.2rem !important;
}
.ab-card-title { font-size: 1.25rem; font-weight: 700; color: #1C2033; margin: 0; }
.ab-card-sub { color: #6B7089; font-size: .95rem; margin-top: .2rem; }
.ab-card-icon {
  width: 42px; height: 42px; border-radius: 12px; display: inline-flex; align-items: center;
  justify-content: center; font-size: 22px; background: #EEF0FF; margin-bottom: .6rem;
}
.ab-or {
  display: flex; align-items: center; gap: .75rem; color: #666C88; font-size: .8rem;
  text-transform: uppercase; letter-spacing: .08em; margin: .4rem 0 .2rem;
}
.ab-or::before, .ab-or::after { content: ""; flex: 1; height: 1px; background: #E6E8F0; }

/* ---------- top bar ---------- */
.ab-brand { display: inline-flex; align-items: center; gap: .55rem; font-weight: 800; font-size: 1.45rem;
  letter-spacing: -0.03em; color: #1C2033; }
.ab-brand img { border-radius: 9px; box-shadow: 0 3px 10px rgba(20, 24, 40, .12); }
.ab-topbar { display: flex; align-items: center; gap: .9rem; flex-wrap: wrap; }
.ab-chip { display: inline-block; padding: .22rem .7rem; border-radius: 999px; font-size: .8rem; font-weight: 600;
  background: #ECEEF6; color: #4A4F68; white-space: nowrap; }
.ab-chip.accent { background: #EEF0FF; color: #4F46E5; }
.ab-chip.gold { background: #FFF4DB; color: #8A5B00; }
.ab-chip.green { background: #E6F6EC; color: #1F7A4A; }

/* ---------- hero ---------- */
.ab-hero { text-align: center; margin: 1.5rem 0 1.8rem; }
.ab-hero .ab-brand { font-size: 2.6rem; }
.ab-hero .ab-brand img { width: 56px; height: 56px; border-radius: 14px; }
.ab-hero p { color: #6B7089; font-size: 1.1rem; margin: .5rem 0 0; }

/* ---------- turn header ---------- */
.ab-turn-title { font-size: 1.6rem; font-weight: 800; letter-spacing: -0.03em; color: #1C2033; line-height: 1.2; }
.ab-turn-title.mine { color: #4F46E5; }
.ab-turn-sub { margin-top: .35rem; color: #6B7089; font-size: .92rem; display: flex; gap: .5rem;
  align-items: center; flex-wrap: wrap; }
.ab-section-label { font-size: .72rem; font-weight: 700; color: #666C88; text-transform: uppercase;
  letter-spacing: .08em; margin: .3rem 0 -.2rem; }

/* ---------- dice ---------- */
[class*="st-key-die-"] button {
  width: var(--ab-size) !important; height: var(--ab-size); min-height: var(--ab-size); padding: 0;
  border: none !important; border-radius: 15px;
  background-color: transparent !important; background-size: 100% 100%; background-repeat: no-repeat;
  color: transparent !important;
  box-shadow: 0 2px 0 rgba(20, 24, 40, .05), 0 8px 18px rgba(20, 24, 40, .12);
  transition: transform .15s ease, box-shadow .15s ease;
  position: relative; overflow: visible;
}
[class*="st-key-die-"] button p { color: transparent !important; }
[class*="st-key-die-"] button:hover:not(:disabled) { transform: translateY(-3px); }
[class*="st-key-die-"] button:disabled { opacity: 1 !important; cursor: default; }
[class*="st-key-die-"]::after { content: "\\00a0"; display: block; text-align: center; font-size: .66rem;
  font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #8A5B00; white-space: nowrap;
  margin: 6px -20px 0; /* wider than the die so the label never pushes neighbours apart */ }
/* Dice are at most --ab-die wide and shrink so all five always fit the play card (cqw = card width). */
[class*="st-key-card-play"] { --ab-die: 60px; --ab-die-gap: .6rem; container-type: inline-size; }
[class*="st-key-dice-row"], .ab-dice-ph { --ab-size: min(var(--ab-die), calc((100cqw - 4 * var(--ab-die-gap)) / 5)); }
[class*="st-key-dice-row"] { flex-wrap: nowrap !important; gap: var(--ab-die-gap) !important; padding-top: 10px; }
[class*="st-key-dice-row"] > * { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
.ab-dice-ph { display: flex; gap: var(--ab-die-gap); padding: 10px 0 22px; flex-wrap: nowrap; }
@media (max-width: 640px) {
  [class*="st-key-card-play"] { --ab-die: 50px; --ab-die-gap: .45rem; padding: 1.1rem 1rem 1rem !important; }
}
.ab-dice-ph div { width: var(--ab-size); height: var(--ab-size); flex: 0 0 auto; border-radius: 14px; border: 2px dashed #D5D9E5;
  display: flex; align-items: center; justify-content: center; color: #B8BDCC; font-size: 1.4rem; font-weight: 700; }
@keyframes ab-roll-a { 0% { transform: rotate(-25deg) scale(.6); opacity: .2; } 70% { transform: rotate(6deg) scale(1.05); } 100% { transform: none; opacity: 1; } }
@keyframes ab-roll-b { 0% { transform: rotate(25deg) scale(.6); opacity: .2; } 70% { transform: rotate(-6deg) scale(1.05); } 100% { transform: none; opacity: 1; } }
/* the computer's final dice, left on the table until the next player rolls (Backlog item 35) */
.ab-last-throw { margin-top: .7rem; font-size: .88rem; font-weight: 600; color: #4B5069; line-height: 1.35; }
.st-key-last-throw [class*="st-key-die-"] button, .st-key-last-throw [class*="st-key-die-"] button:disabled {
  opacity: .5 !important; box-shadow: none !important; }
.ab-rolls { display: inline-flex; gap: 5px; align-items: center; }
.ab-rolls i { width: 9px; height: 9px; border-radius: 50%; background: #4F46E5; display: inline-block; }
.ab-rolls i.used { background: #D5D9E5; }

/* ---------- starting throw (who goes first) ---------- */
.ab-throws { display: flex; flex-direction: column; gap: .45rem; margin: 1rem 0 .9rem; }
.ab-throw { display: flex; align-items: center; justify-content: space-between; gap: .6rem;
  padding: .5rem .75rem; min-height: 2.75rem; border-radius: 12px; background: #F5F6FA; border: 1px solid #E3E6EF; }
.ab-throw.next { background: #EEF0FF; border-color: #4F46E5; }
.ab-throw.out { opacity: .45; }
.ab-throw-name { font-weight: 600; color: #1C2033; min-width: 0; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
.ab-throw-name .ab-you { display: inline-block; margin-left: .4rem; font-size: .62rem; font-weight: 700;
  text-transform: uppercase; letter-spacing: .06em; color: #4F46E5; background: #E4E7FF; border-radius: 6px;
  padding: 1px 5px; vertical-align: middle; }
.ab-throw-res { display: inline-flex; align-items: center; gap: .55rem; flex: 0 0 auto; }
.ab-throw-dice { display: inline-flex; gap: 3px; }
.ab-throw-dice img { width: 22px; height: 22px; display: block; }
.ab-throw-res b { font-size: 1.05rem; min-width: 1.5rem; text-align: right; color: #1C2033; }
.ab-throw-wait { color: #8A8FA8; font-size: .85rem; }
.ab-throw.next .ab-throw-wait { color: #4F46E5; font-weight: 600; }
.ab-start-note { margin-top: .55rem; display: inline-block; padding: .3rem .65rem; border-radius: 999px;
  background: #EEF0FF; color: #3730A3; font-size: .85rem; font-weight: 600; }

/* ---------- big buttons ---------- */
[class*="st-key-roll"] button, [class*="st-key-confirm"] button, [class*="st-key-big-"] button {
  min-height: 3rem; font-size: 1.02rem; font-weight: 600;
}
[class*="st-key-confirm"] button p, [class*="st-key-roll"] button p, [class*="st-key-big-"] button p { font-weight: 600; }

/* ---------- move picker: the option with the most points (bold label, move_selection.py) ----------
   Gold unless picked. A picked pill is data-testid="stBaseButton-pillsActive" in Streamlit 1.48 and
   aria-checked="true" in 1.67 (where pills are role="radio" buttons with no data-testid). */
[class*="st-key-pick-"] button:has(strong):not([data-testid="stBaseButton-pillsActive"]):not([aria-checked="true"]) {
  background: #FFF4DB; border-color: #F2C14E; color: #8A5B00; }
[class*="st-key-pick-"] button:has(strong):not([data-testid="stBaseButton-pillsActive"]):not([aria-checked="true"]):hover {
  background: #FFEBC2; border-color: #E0A82E; color: #7A5200; }

/* ---------- scoreboard ---------- */
.ab-board-wrap { overflow-x: auto; }
/* The difference row by row (a tester, 2026-11-26): the viewer's points minus the opponent's. */
.ab-board .ab-diff { font-size: .8rem; font-weight: 700; color: #666C88; text-align: right; padding: 6px 4px 6px 2px;
  width: 3em; min-width: 2.6em; white-space: nowrap; }
.ab-board .ab-diff.up { color: #15803D; }
.ab-board .ab-diff.down { color: #CF2F36; }
@media (max-width: 640px) { .ab-board.ab-diffs .ab-gap { width: 3px; }
  .ab-board.ab-diffs td, .ab-board.ab-diffs .ab-sub th { padding-left: 2px; padding-right: 2px; }
  .ab-board.ab-diffs:not(.ab-many) { font-size: .84rem; } .ab-board.ab-diffs .ab-row { padding-right: 6px; }
  .ab-board.ab-diffs .ab-diff { min-width: 2.3em; width: 2.3em; padding-left: 0; } }
.ab-board th.ab-diff-head { font-size: 1rem; color: #4A4F68; border-bottom: none; cursor: help; }
/* Scores by move (chart.py): a line per player. */
.ab-chart { margin-top: .9rem; padding-top: .7rem; border-top: 1px solid #F0F1F6; }
.ab-chart-title { font-size: .8rem; font-weight: 700; color: #6B7089; text-transform: uppercase;
  letter-spacing: .04em; margin-bottom: .3rem; }
.ab-chart-plot { position: relative; height: 150px; margin-left: 42px; }
.ab-chart-plot img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; display: block; }
.ab-chart-y { position: absolute; left: -42px; width: 36px; text-align: right; transform: translateY(-50%);
  font-size: .72rem; color: #666C88; }
.ab-chart-x { display: flex; justify-content: space-between; margin-left: 42px; font-size: .72rem; color: #666C88;
  margin-top: .15rem; }
.ab-chart-keys { display: flex; flex-wrap: wrap; gap: .3rem .9rem; font-size: .8rem; color: #3A3F55; margin-top: .3rem; }
.ab-chart-keys span { display: inline-flex; align-items: center; gap: .35rem; min-width: 0; }
.ab-chart-keys i { width: 14px; height: 3px; border-radius: 2px; background: var(--c); flex: none; }
.ab-chart-keys b { font-weight: 700; }
.ab-board { width: 100%; border-collapse: separate; border-spacing: 0; font-size: .92rem;
  font-variant-numeric: tabular-nums; color: #1C2033; }
.ab-board th, .ab-board td { padding: 6px 4px; text-align: center; border-bottom: 1px solid #F0F1F6; }
.ab-board .ab-row { text-align: left; font-weight: 500; color: #3A3F55; white-space: nowrap; padding: 6px 12px 6px 2px; }
.ab-board .ab-row img { width: 17px; height: 17px; vertical-align: -3px; margin-right: 7px; }
.ab-board .ab-gap { width: 10px; padding: 0; border-bottom: none; }
.ab-board .ab-player { font-size: 1rem; font-weight: 700; padding: 10px 4px 8px; border-bottom: none;
  border-radius: 12px 12px 0 0; }
.ab-board .ab-pmeta { font-size: .75rem; font-weight: 500; color: #666C88; margin-top: 2px; }
.ab-board .ab-you { display: inline-block; font-size: .65rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; background: #EEF0FF; color: #4F46E5; border-radius: 999px; padding: 1px 7px;
  margin-left: 6px; vertical-align: 2px; }
.ab-board .ab-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #4F46E5;
  margin-right: 6px; vertical-align: 1px; }
.ab-board .ab-active { background: #F3F4FF; }
.ab-board .ab-player.ab-active { color: #4F46E5; }
.ab-board .ab-sub th { font-size: .68rem; font-weight: 700; color: #666C88; text-transform: uppercase; letter-spacing: .06em; }
.ab-board .ab-section td { text-align: left; font-size: .68rem; font-weight: 700; letter-spacing: .09em;
  text-transform: uppercase; color: #666C88; padding: 16px 2px 4px; border-bottom: 1px solid #E6E8F0; }
.ab-board .ab-bonus { background: #FFF9EE; }
.ab-board .ab-bonus.ab-active { background: #ECE9FA; }
.ab-board .ab-num { font-weight: 600; }
.ab-board .ab-neg { color: #CF2F36; font-weight: 600; }
.ab-board .ab-x { color: #E5484D; opacity: .7; font-weight: 700; }
.ab-board .ab-ok { color: #30A46C; font-weight: 700; }
.ab-board .ab-none { color: #CBCFDA; }
.ab-board .ab-bval { color: #8A5B00; font-weight: 700; }
.ab-board td.ab-target { box-shadow: inset 0 0 0 2px #4F46E5; background: #E3E5FF !important; color: #4F46E5;
  font-weight: 800; border-radius: 8px; }
.ab-board td.ab-last { background: #FFE8D1 !important; color: #A04A08 !important; font-weight: 800;
  box-shadow: inset 0 0 0 2px #F59E0B; border-radius: 8px; opacity: 1; }
.ab-legend { display: flex; align-items: center; gap: .5rem; margin-top: .8rem; font-size: .85rem; color: #6B7089; }
.ab-swatch { width: 14px; height: 14px; border-radius: 4px; background: #FFE8D1; box-shadow: inset 0 0 0 2px #F59E0B;
  flex: 0 0 auto; }
/* Row names stay visible when a wide table scrolls sideways. */
.ab-board .ab-row, .ab-board thead tr th:first-child { position: sticky; left: 0; background: #FFFFFF; z-index: 1; }
/* 3 to 5 players: tighter table. */
.ab-board.ab-many { font-size: .82rem; }
.ab-board.ab-many th, .ab-board.ab-many td { padding: 5px 2px; min-width: 24px; }
.ab-board.ab-many .ab-row { padding: 5px 8px 5px 2px; }
.ab-board.ab-many .ab-player { font-size: .88rem; }
.ab-board.ab-many .ab-pmeta { font-size: .68rem; line-height: 1.3; }
.ab-board.ab-many .ab-gap { width: 6px; min-width: 6px; padding: 0; }
.ab-board.ab-many .ab-total th, .ab-board.ab-many .ab-total td { font-size: 1.05rem; }
.ab-board .ab-total th, .ab-board .ab-total td { font-size: 1.2rem; font-weight: 800; border-bottom: none; padding-top: 14px; }
.ab-board .ab-total td.ab-active { border-radius: 0 0 12px 12px; }

/* ---------- results ---------- */
/* ---------- running score and clubs ---------- */
.ab-series { margin-top: .7rem; padding: .55rem .8rem; border-radius: 12px; background: #F6F7FB; color: #4A4F68;
  font-size: .88rem; display: flex; flex-wrap: wrap; gap: .25rem .6rem; align-items: center; }
.ab-series-head { color: #666C88; font-size: .75rem; font-weight: 700; text-transform: uppercase; letter-spacing: .06em; }
.ab-series b { color: #1C2033; }
.ab-series-club { margin-left: auto; color: #8A5B00; font-weight: 600; font-size: .8rem; }
/* ---------- the races for shared bonuses (races.py), at the foot of the play card ---------- */
.ab-race { margin-top: .8rem; padding: .55rem .7rem; border-radius: 12px; background: #F6F7FB; color: #4A4F68;
  font-size: .85rem; display: flex; flex-direction: column; gap: .4rem; }
.ab-race-table { width: 100%; border-collapse: collapse; table-layout: fixed; margin: 0; }
.ab-race-table th, .ab-race-table td { padding: .1rem .25rem; border: none; background: none; text-align: center;
  font-size: .85rem; line-height: 1.35; }
.ab-race-table th:first-child { text-align: left; width: 40%; padding-left: 0; color: #4A4F68; font-weight: 600; }
.ab-race-table thead th { font-size: .72rem; font-weight: 700; color: #6B7089; vertical-align: bottom; }
.ab-race-table thead th.ab-race-title { color: #666C88; text-transform: uppercase; letter-spacing: .06em; }
.ab-race-table tbody th.ab-race-who { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.ab-race-table tbody th.me { color: #4F46E5; }
.ab-race-table td { color: #1C2033; font-variant-numeric: tabular-nums; }
.ab-race-table td.lead { font-weight: 800; }
.ab-race-table td.off { color: #666C88; }
.ab-race-x { margin-left: .2rem; font-size: .8em; }
.ab-race-row { padding: .35rem .55rem; border-radius: 9px; background: #FFF4DB; color: #8A5A00; font-weight: 600; }
.ab-race-note { font-size: .75rem; color: #666C88; line-height: 1.35; }
.ab-club-result { display: flex; flex-wrap: wrap; gap: .3rem .9rem; justify-content: center; margin: -.4rem 0 1rem;
  padding: .6rem .8rem; border-radius: 12px; background: #EEF0FF; color: #4A4F68; font-size: .9rem; }
.ab-club-result > div { width: 100%; text-align: center; font-size: .75rem; font-weight: 700; color: #4F46E5;
  text-transform: uppercase; letter-spacing: .06em; }
.ab-up { color: #1F7A4A; font-weight: 700; font-size: .8em; }
.ab-down { color: #C2410C; font-weight: 700; font-size: .8em; }
.ab-same { color: #666C88; font-size: .8em; }
.ab-club-head { margin: .2rem 0 1rem; }
.ab-club-table { width: 100%; border-collapse: collapse; margin-top: .8rem; font-size: .95rem; }
.ab-club-table th { text-align: left; font-size: .72rem; font-weight: 700; color: #666C88; text-transform: uppercase;
  letter-spacing: .06em; padding: 0 .5rem .4rem; border-bottom: 1px solid #E6E8F0; }
.ab-club-table td { padding: .55rem .5rem; border-bottom: 1px solid #F0F1F6; color: #4A4F68; }
.ab-club-table tbody tr:first-child td { background: #FFF8E6; }
.ab-club-table .ab-rank { width: 2rem; text-align: center; }
.ab-club-table .ab-name { color: #1C2033; font-weight: 600; overflow-wrap: anywhere; }
.ab-club-table .ab-rating { white-space: nowrap; }
.ab-club-games { list-style: none; padding: 0; margin: .6rem 0 0; display: flex; flex-direction: column; gap: .35rem; }
.ab-club-games li { display: flex; flex-wrap: wrap; gap: .2rem .6rem; font-size: .9rem; color: #6B7089;
  padding: .4rem 0; border-bottom: 1px solid #F0F1F6; }
.ab-club-games .win { color: #1C2033; font-weight: 700; }
.ab-club-games .ab-when { color: #666C88; font-variant-numeric: tabular-nums; min-width: 2.8rem; }
@media (max-width: 640px) {
  .ab-club-table { font-size: .88rem; }
  .ab-club-table .ab-wide, .ab-club-table th:nth-child(6), .ab-club-table th:nth-child(7) { display: none; }
  .ab-club-table td, .ab-club-table th { padding-left: .3rem; padding-right: .3rem; }
}

.ab-result { text-align: center; padding: .5rem 0 1rem; }
.ab-result .trophy { font-size: 3rem; line-height: 1; }
.ab-result h2 { margin: .4rem 0 .2rem; font-size: 1.8rem; }
.ab-scores { display: flex; flex-direction: column; gap: .4rem; margin: .8rem 0 1.2rem; }
.ab-scores div { display: flex; justify-content: space-between; padding: .6rem .9rem; border-radius: 12px;
  background: #F5F6FA; font-weight: 600; }
.ab-scores div.win { background: #FFF4DB; color: #7A5200; }

/* ---------- waiting room ---------- */
.ab-code { display: flex; gap: .4rem; justify-content: center; margin: .6rem 0 .2rem; }
.ab-code span { width: 46px; height: 56px; border-radius: 12px; background: #F1F2FA; display: flex;
  align-items: center; justify-content: center; font-size: 1.7rem; font-weight: 800; color: #1C2033; }
/* the game's key, under its code: 8 smaller boxes that fit a 360px phone (Backlog item 31) */
.ab-code-key { gap: .3rem; margin-top: .35rem; }
.ab-code-key span { width: 32px; height: 40px; border-radius: 9px; font-size: 1.2rem; font-weight: 700; color: #4F46E5; }
.ab-seats { display: flex; flex-wrap: wrap; gap: .4rem; justify-content: center; margin: .9rem 0 0; }
.ab-seats span { padding: .3rem .75rem; border-radius: 999px; font-size: .85rem; font-weight: 600;
  border: 1.5px dashed #D5D9E5; color: #666C88; }
.ab-seats span.in { border: 1.5px solid #C7CBF5; background: #EEF0FF; color: #4F46E5; }
/* the computer's seats in the same-device card (Backlog item 33) */
.ab-computers { display: flex; flex-wrap: wrap; gap: .4rem; margin: .1rem 0 .6rem; }
.ab-computers span { padding: .3rem .75rem; border-radius: 999px; font-size: .85rem; font-weight: 600;
  border: 1.5px solid #C7CBF5; background: #EEF0FF; color: #4F46E5; }
[class*="st-key-rejoin-row"] { flex-wrap: wrap !important; }
/* A device asking to be let in to a seat (abaka_ui._render_requests), and the script that keeps the browser's secret. */
[class*="st-key-card-ask-"] { border-color: #D97706 !important; background: #FFFBEB; margin-bottom: .6rem; }
.ab-ask { color: #1F2333; line-height: 1.45; }
.ab-ask b { display: block; margin-bottom: .2rem; }
.st-key-device-keeper, [data-testid="stElementContainer"]:has(> .st-key-device-keeper) { display: none !important; }
.ab-wait { display: flex; align-items: center; gap: .6rem; justify-content: center; color: #6B7089; margin: 1rem 0 .4rem; }
.ab-wait i { width: 10px; height: 10px; border-radius: 50%; background: #4F46E5; animation: ab-pulse 1.4s ease-in-out infinite; }
@keyframes ab-pulse { 0%, 100% { opacity: .25; transform: scale(.8); } 50% { opacity: 1; transform: scale(1.1); } }

/* ---------- reactions and celebrations (effects.py) ---------- */
.st-key-react-box { border-top: 1px solid #F0F1F6; padding-top: .7rem; margin-top: .2rem; }
[class*="st-key-react-row"] { flex-wrap: wrap !important; gap: .35rem !important; }
[class*="st-key-react-row"] > * { width: auto !important; flex: 0 0 auto !important; }
[class*="st-key-react-"] button { min-height: 0; padding: .2rem .65rem; border-radius: 999px; }
[class*="st-key-react-"] button p { font-size: .85rem; }
/* Over the page, never in the way of a tap. --d is minus the time already shown, so a redraw
   in the middle carries on instead of starting again. */
.ab-fx { position: fixed; inset: 0; pointer-events: none; z-index: 999990; overflow: hidden; }
.ab-bubbles { position: absolute; top: 4.2rem; left: 0; right: 0; display: flex; flex-direction: column;
  align-items: center; gap: .45rem; padding: 0 16px; }
.ab-bubble { display: inline-flex; align-items: center; gap: .6rem; max-width: 100%; padding: .5rem 1rem .5rem .6rem;
  border-radius: 999px; background: #FFFFFF; color: #1C2033; font-size: 1rem;
  box-shadow: 0 2px 4px rgba(20, 24, 40, .06), 0 14px 34px rgba(20, 24, 40, .18); border: 1px solid #E6E8F0;
  opacity: 0; animation: ab-bubble 3.5s ease-out var(--d) both; }
.ab-bubble.mine { border-color: #C7CBF5; background: #EEF0FF; }
.ab-bubble-emoji { font-size: 1.9rem; line-height: 1; }
.ab-bubble-text { display: flex; flex-direction: column; line-height: 1.2; min-width: 0; }
.ab-bubble-text b { font-size: .78rem; color: #6B7089; font-weight: 600; overflow: hidden; text-overflow: ellipsis;
  white-space: nowrap; }
@keyframes ab-bubble { 0% { opacity: 0; transform: translateY(-14px) scale(.7); }
  8% { opacity: 1; transform: translateY(0) scale(1.06); } 14% { transform: scale(1); }
  80% { opacity: 1; transform: translateY(0); } 100% { opacity: 0; transform: translateY(-18px); } }
.ab-fx-grand, .ab-fx-big, .ab-fx-small { position: absolute; inset: 0; }
.ab-burst { position: absolute; width: 0; height: 0; }
.ab-burst i { position: absolute; left: -4px; top: -4px; width: 8px; height: 8px; border-radius: 50%;
  background: var(--c); box-shadow: 0 0 8px 1px var(--c); opacity: 0;
  animation: ab-spark 1.3s cubic-bezier(.15, .7, .3, 1) calc(var(--d) + var(--bd)) forwards; }
/* forwards, not both: a burst still waiting for its turn stays hidden (opacity 0), not a dot. */
.ab-fx-big .ab-burst i { left: -5px; top: -5px; width: 10px; height: 10px; }
.ab-fx-small .ab-burst i { left: -3px; top: -3px; width: 6px; height: 6px; animation-duration: 1.1s; }
.ab-fx-grand .ab-burst i { left: -6px; top: -6px; width: 12px; height: 12px; animation-duration: 1.6s; }
/* Bigger fireworks: a golden flash first, then a rain of sparkles over the bursts. */
.ab-flash { position: absolute; inset: 0; opacity: 0;
  background: radial-gradient(circle at 50% 42%, rgba(255, 205, 80, .5), rgba(255, 205, 80, 0) 70%);
  animation: ab-flash 1.6s ease-out var(--d) both; }
@keyframes ab-flash { 0% { opacity: 0; } 12% { opacity: 1; } 100% { opacity: 0; } }
.ab-star { position: absolute; top: -30px; font-size: var(--s); line-height: 1; color: var(--c); opacity: 0;
  text-shadow: 0 0 8px var(--c); animation: ab-fall 2.6s linear calc(var(--d) + var(--bd)) both; }
@keyframes ab-fall { 0% { opacity: 0; transform: translateY(0) rotate(0deg); } 10% { opacity: 1; }
  75% { opacity: 1; } 100% { opacity: 0; transform: translateY(75vh) rotate(220deg); } }
@keyframes ab-spark { 0% { opacity: 1; transform: rotate(var(--a)) translateY(0) scale(1.3); }
  70% { opacity: 1; } 100% { opacity: 0; transform: rotate(var(--a)) translateY(calc(-1 * var(--r))) scale(.4); } }
/* Low on the screen: effects come as the dice land, and the banner must not hide them (on phones
   the dice are in the upper half). As wide as its text, up to the screen. */
.ab-fx-banner { position: absolute; left: 50%; top: 76%; transform: translate(-50%, -50%); text-align: center;
  width: max-content; max-width: calc(100% - 32px);
  padding: .9rem 1.6rem; border-radius: 22px; background: rgba(255, 255, 255, .94);
  box-shadow: 0 20px 50px rgba(20, 24, 40, .25); opacity: 0;
  animation: ab-banner 4.5s ease-out calc(var(--d) + .1s) both; }
.ab-fx-small .ab-fx-banner { padding: .6rem 1.2rem; animation-name: ab-banner-small;
  animation-duration: 2.8s; }
.ab-fx-title { font-size: 2.6rem; font-weight: 800; letter-spacing: -0.03em; color: #8A5B00; line-height: 1.1; }
.ab-fx-small .ab-fx-title { font-size: 1.5rem; color: #4F46E5; }
.ab-fx-grand .ab-fx-banner { padding: 1.1rem 2.1rem; border: 2px solid #F6C453; animation-duration: 6s;
  box-shadow: 0 0 0 8px rgba(246, 196, 83, .22), 0 24px 60px rgba(20, 24, 40, .3); }
.ab-fx-grand .ab-fx-title { font-size: 3.6rem; text-shadow: 0 2px 14px rgba(246, 196, 83, .55); }
.ab-fx-grand .ab-fx-sub { font-size: 1.1rem; }
.ab-fx-sub { font-size: 1rem; font-weight: 600; color: #4A4F68; margin-top: .2rem; }
@keyframes ab-banner { 0% { opacity: 0; transform: translate(-50%, -50%) scale(.5); }
  10% { opacity: 1; transform: translate(-50%, -50%) scale(1.08); } 16% { transform: translate(-50%, -50%) scale(1); }
  82% { opacity: 1; } 100% { opacity: 0; transform: translate(-50%, -60%) scale(1); } }
@keyframes ab-banner-small { 0% { opacity: 0; transform: translate(-50%, -50%) scale(.6); }
  14% { opacity: 1; transform: translate(-50%, -50%) scale(1); } 78% { opacity: 1; }
  100% { opacity: 0; transform: translate(-50%, -70%); } }
/* Tears: Abaka or the royal full house thrown with its row already full. A grey-blue gloom
   and a rain of drops instead of fireworks. */
.ab-fx-tears { position: absolute; inset: 0; }
.ab-gloom { position: absolute; inset: 0; opacity: 0;
  background: radial-gradient(circle at 50% 45%, rgba(90, 110, 150, .28), rgba(90, 110, 150, 0) 75%);
  animation: ab-gloom 4.5s ease-out var(--d) both; }
@keyframes ab-gloom { 0% { opacity: 0; } 15% { opacity: 1; } 80% { opacity: 1; } 100% { opacity: 0; } }
.ab-tear { position: absolute; top: -30px; font-size: var(--s); line-height: 1; opacity: 0;
  animation: ab-drip 1.9s cubic-bezier(.5, 0, .9, .6) calc(var(--d) + var(--bd)) both; }
@keyframes ab-drip { 0% { opacity: 0; transform: translateY(0); } 12% { opacity: .9; }
  85% { opacity: .9; } 100% { opacity: 0; transform: translateY(80vh); } }
.ab-fx-tears .ab-fx-banner { border: 2px solid #A9BCE0; }
.ab-fx-tears .ab-fx-title { font-size: 1.9rem; color: #3B5E9C; }
@media (prefers-reduced-motion: reduce) { .ab-burst, .ab-star, .ab-tear { display: none; } }
@media (max-width: 640px) { .ab-fx-title { font-size: 2rem; } .ab-fx-grand .ab-fx-title { font-size: 2.6rem; }
  .ab-fx-tears .ab-fx-title { font-size: 1.45rem; }
  .ab-bubbles { top: 3.6rem; } }

/* ---------- chat (chat.py) ---------- */
.st-key-card-chat { margin-top: .4rem; padding: 1rem 1.1rem .9rem !important; }
.ab-chat-head { font-weight: 700; color: #1C2033; display: flex; align-items: baseline; gap: .6rem; flex-wrap: wrap; }
.ab-chat-head span { font-weight: 400; font-size: .78rem; color: #666C88; }
/* Listed newest first and shown bottom up, so the box opens scrolled to the latest message. */
.ab-chat { display: flex; flex-direction: column-reverse; gap: .3rem; max-height: 190px; overflow-y: auto;
  margin-top: .5rem; padding-right: .2rem; overflow-wrap: anywhere; }
.ab-msg { align-self: flex-start; max-width: 88%; padding: .35rem .7rem; border-radius: 14px 14px 14px 4px;
  background: #F1F2FA; color: #1C2033; font-size: .9rem; line-height: 1.3; }
.ab-msg b { display: block; font-size: .72rem; color: #6B7089; font-weight: 600; }
.ab-msg.mine { align-self: flex-end; background: #EEF0FF; border-radius: 14px 14px 4px 14px; }
.ab-msg.mine b { color: #4F46E5; }
.ab-chat-empty { color: #666C88; font-size: .88rem; margin-top: .4rem; }
[class*="st-key-chat-row"] { flex-wrap: nowrap !important; gap: .4rem !important; }
.st-key-card-chat [data-testid="InputInstructions"] { display: none; }
[class*="st-key-chat-row"] > *:first-child { flex: 1 1 auto !important; min-width: 0 !important; }
[class*="st-key-chat-row"] > *:last-child { flex: 0 0 auto !important; width: auto !important; }

/* ---------- notifications: bottom of the screen, clear of the turn title and scoreboard ---------- */
[data-testid="stToastContainer"] { top: auto !important; bottom: 1.25rem !important; }

/* ---------- tablets and small laptops, 3-5 players ----------
   Side by side, the scoreboard needs about 1000px of screen with 3 players, 1150px with 4 and 1180px
   with 5; below that it scrolled sideways and the dice shrank (26-39px with 5 players). There the
   play panel stacks above the scoreboard instead, as on phones (main_ui.render_game sets the key). */
@media (min-width: 641px) and (max-width: 1180px) {
  .st-key-game-many [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-card-board) {
    flex-wrap: wrap; gap: 1rem !important; }
  .st-key-game-many [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-card-board)
    > [data-testid="stColumn"] { flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important; }
  .st-key-game-many .st-key-card-play, .st-key-game-many .st-key-card-chat { max-width: 640px; margin: 0 auto; }
}
@media (min-width: 641px) and (max-width: 1000px) {
  .st-key-game-three [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-card-board) {
    flex-wrap: wrap; gap: 1rem !important; }
  .st-key-game-three [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"] .st-key-card-board)
    > [data-testid="stColumn"] { flex: 1 1 100% !important; width: 100% !important; min-width: 100% !important; }
  .st-key-game-three .st-key-card-play, .st-key-game-three .st-key-card-chat { max-width: 640px; margin: 0 auto; }
}

/* ---------- phones ---------- */
@media (max-width: 640px) {
  /* Columns stack on phones; keep the stacked cards close together. */
  [data-testid="stHorizontalBlock"]:has(> [data-testid="stColumn"]) { gap: 1rem !important; }
  .ab-hero { margin: .5rem 0 1rem; }
  .ab-hero .ab-brand { font-size: 2.1rem; }
  .ab-hero p { font-size: 1rem; }
  [data-testid="stDialog"] table { font-size: .82rem; }
  [data-testid="stDialog"] th, [data-testid="stDialog"] td { padding: .35rem .4rem !important; }
  /* The logo alone in the game's top bar, so the game code and the Menu stay on one line. */
  .ab-topbar .ab-brand span { display: none; }
}
.ab-pmeta .ab-nw { white-space: nowrap; }
/* Streamlit's captions are the text colour faded to 60% (#777985, 4.3:1 on white): the faint text's colour, not faded. */
[data-testid="stCaptionContainer"] { color: #666C88 !important; opacity: 1 !important; }
[data-testid="stCaptionContainer"] p { color: inherit !important; opacity: 1 !important; }
/* Phones: the choices that are small buttons (players, level, Score / Cross out, the options to
   write a roll, EN / RU, "Send to") are 32px high in Streamlit; 40px is easier to hit with a thumb. */
@media (max-width: 640px) {
  [data-testid="stButtonGroup"] button { min-height: 40px; }
}
/* A phone 360 wide: two players' columns fit the board without scrolling (they were 12px too wide). */
@media (max-width: 380px) {
  .ab-board th, .ab-board td { padding-left: 3px; padding-right: 3px; }
  .ab-board .ab-row { padding-right: 4px; }
  .ab-board .ab-row img { margin-right: 4px; }
  .ab-board .ab-gap { width: 6px; }
}
"""
