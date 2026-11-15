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
  display: flex; align-items: center; gap: .75rem; color: #9AA0B5; font-size: .8rem;
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
.ab-chip.gold { background: #FFF4DB; color: #9A6700; }
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
.ab-section-label { font-size: .72rem; font-weight: 700; color: #9AA0B5; text-transform: uppercase;
  letter-spacing: .08em; margin: .3rem 0 -.2rem; }

/* ---------- dice ---------- */
[class*="st-key-die-"] button {
  width: var(--ab-die) !important; height: var(--ab-die); min-height: var(--ab-die); padding: 0;
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
  font-weight: 700; letter-spacing: .08em; text-transform: uppercase; color: #B7791F; white-space: nowrap;
  margin: 6px -20px 0; /* wider than the die so the label never pushes neighbours apart */ }
[class*="st-key-card-play"] { --ab-die: 60px; --ab-die-gap: .6rem; }
[class*="st-key-dice-row"] { flex-wrap: nowrap !important; gap: var(--ab-die-gap) !important; padding-top: 10px; }
[class*="st-key-dice-row"] > * { flex: 0 0 auto !important; width: auto !important; min-width: 0 !important; }
.ab-dice-ph { display: flex; gap: var(--ab-die-gap); padding: 10px 0 22px; flex-wrap: nowrap; }
@media (max-width: 640px) {
  [class*="st-key-card-play"] { --ab-die: 50px; --ab-die-gap: .45rem; padding: 1.1rem 1rem 1rem !important; }
}
.ab-dice-ph div { width: var(--ab-die); height: var(--ab-die); flex: 0 0 auto; border-radius: 14px; border: 2px dashed #D5D9E5;
  display: flex; align-items: center; justify-content: center; color: #B8BDCC; font-size: 1.4rem; font-weight: 700; }
@keyframes ab-roll-a { 0% { transform: rotate(-25deg) scale(.6); opacity: .2; } 70% { transform: rotate(6deg) scale(1.05); } 100% { transform: none; opacity: 1; } }
@keyframes ab-roll-b { 0% { transform: rotate(25deg) scale(.6); opacity: .2; } 70% { transform: rotate(-6deg) scale(1.05); } 100% { transform: none; opacity: 1; } }
.ab-rolls { display: inline-flex; gap: 5px; align-items: center; }
.ab-rolls i { width: 9px; height: 9px; border-radius: 50%; background: #4F46E5; display: inline-block; }
.ab-rolls i.used { background: #D5D9E5; }

/* ---------- big buttons ---------- */
[class*="st-key-roll"] button, [class*="st-key-confirm"] button, [class*="st-key-big-"] button {
  min-height: 3rem; font-size: 1.02rem; font-weight: 600;
}
[class*="st-key-confirm"] button p, [class*="st-key-roll"] button p, [class*="st-key-big-"] button p { font-weight: 600; }

/* ---------- scoreboard ---------- */
.ab-board-wrap { overflow-x: auto; }
.ab-board { width: 100%; border-collapse: separate; border-spacing: 0; font-size: .92rem;
  font-variant-numeric: tabular-nums; color: #1C2033; }
.ab-board th, .ab-board td { padding: 6px 4px; text-align: center; border-bottom: 1px solid #F0F1F6; }
.ab-board .ab-row { text-align: left; font-weight: 500; color: #3A3F55; white-space: nowrap; padding: 6px 12px 6px 2px; }
.ab-board .ab-row img { width: 17px; height: 17px; vertical-align: -3px; margin-right: 7px; }
.ab-board .ab-gap { width: 10px; padding: 0; border-bottom: none; }
.ab-board .ab-player { font-size: 1rem; font-weight: 700; padding: 10px 4px 8px; border-bottom: none;
  border-radius: 12px 12px 0 0; }
.ab-board .ab-pmeta { font-size: .75rem; font-weight: 500; color: #7A8099; margin-top: 2px; }
.ab-board .ab-you { display: inline-block; font-size: .65rem; font-weight: 700; text-transform: uppercase;
  letter-spacing: .06em; background: #EEF0FF; color: #4F46E5; border-radius: 999px; padding: 1px 7px;
  margin-left: 6px; vertical-align: 2px; }
.ab-board .ab-dot { display: inline-block; width: 8px; height: 8px; border-radius: 50%; background: #4F46E5;
  margin-right: 6px; vertical-align: 1px; }
.ab-board .ab-active { background: #F3F4FF; }
.ab-board .ab-player.ab-active { color: #4F46E5; }
.ab-board .ab-sub th { font-size: .68rem; font-weight: 700; color: #A0A6BA; text-transform: uppercase; letter-spacing: .06em; }
.ab-board .ab-section td { text-align: left; font-size: .68rem; font-weight: 700; letter-spacing: .09em;
  text-transform: uppercase; color: #A0A6BA; padding: 16px 2px 4px; border-bottom: 1px solid #E6E8F0; }
.ab-board .ab-bonus { background: #FFF9EE; }
.ab-board .ab-bonus.ab-active { background: #ECE9FA; }
.ab-board .ab-num { font-weight: 600; }
.ab-board .ab-neg { color: #E5484D; font-weight: 600; }
.ab-board .ab-x { color: #E5484D; opacity: .7; font-weight: 700; }
.ab-board .ab-ok { color: #30A46C; font-weight: 700; }
.ab-board .ab-none { color: #CBCFDA; }
.ab-board .ab-bval { color: #B7791F; font-weight: 700; }
.ab-board td.ab-target { box-shadow: inset 0 0 0 2px #4F46E5; background: #E3E5FF !important; color: #4F46E5;
  font-weight: 800; border-radius: 8px; }
.ab-board .ab-total th, .ab-board .ab-total td { font-size: 1.2rem; font-weight: 800; border-bottom: none; padding-top: 14px; }
.ab-board .ab-total td.ab-active { border-radius: 0 0 12px 12px; }

/* ---------- results ---------- */
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
.ab-wait { display: flex; align-items: center; gap: .6rem; justify-content: center; color: #6B7089; margin: 1rem 0 .4rem; }
.ab-wait i { width: 10px; height: 10px; border-radius: 50%; background: #4F46E5; animation: ab-pulse 1.4s ease-in-out infinite; }
@keyframes ab-pulse { 0%, 100% { opacity: .25; transform: scale(.8); } 50% { opacity: 1; transform: scale(1.1); } }
"""
