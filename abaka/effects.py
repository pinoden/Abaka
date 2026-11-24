"""
What reactions and effects say, for every client: the web page (ui_components/effects.py
draws them) and the API for apps (abaka/api.py sends these words with each event, so an
app shows them as they are, in its player's language).

The events themselves are made by the rooms (abaka/rooms.py: react, _celebration). Here
are only their words: a reaction's emoji and label, who sent it to whom, and an effect's
banner. All of it is plain text; whoever shows it escapes it for its own page.

No Streamlit here, and Python 3.8 like the rest of the package.
"""

from typing import Dict, List, Optional, Tuple

from .i18n import t
from .models import Category
from .moves import row_name

# Reaction (one of abaka.rooms.REACTIONS) -> its emoji and its label in English. A label
# goes through t() when it is shown.
REACTION_LOOKS: Dict[str, Tuple[str, str]] = {
    "lucky": ("\U0001F340", "Lucky!"),
    "mrlucky": ("\U0001F60E", "Mr. Lucky"),
    "nice": ("\U0001F44F", "Nice!"),
    "wow": ("\U0001F62E", "Wow!"),
    "ouch": ("\U0001F62C", "Ouch"),
    "hurry": ("⏳", "Hurry up"),
    "gg": ("\U0001F91D", "GG"),
    "haha": ("\U0001F602", "Haha"),
    "fire": ("\U0001F525", "On fire!"),
}
COLUMNS = ("I", "II", "III")


def player_name(names: List[str], seat: int) -> str:
    return names[seat] if 0 <= seat < len(names) else "?"


def reaction_words(event: dict, names: List[str], me: Optional[int]) -> dict:
    """
    A reaction as the player in seat `me` reads it (None: no seat of their own, as on one
    device): its `emoji` and `label`, `who` sent it ("Ann", "You", "Ann → Bob", "Ann → you"),
    and `to_you`, whether it was aimed at this player.
    """
    emoji, label = REACTION_LOOKS.get(event["reaction"], ("", event["reaction"]))
    seat, to = event["seat"], event.get("to")
    who = t("You") if seat == me else player_name(names, seat)
    if to is not None:
        who = t("{name} → you", name=who) if to == me else f"{who} → {player_name(names, to)}"
    return {"emoji": emoji, "label": t(label), "who": who, "to_you": to is not None and to == me}


def effect_words(event: dict, names: List[str], me: Optional[int]) -> Tuple[str, str]:
    """An effect's banner as the player in seat `me` reads it: its title, and the line under it."""
    who = t("You") if me is not None and event.get("seat") == me else player_name(names, event["seat"])
    what = event.get("what") or event.get("category") or ""
    if what == "BONUS":
        parts = [t("{row} row +{points}", row=_row(name), points=int(points))
                 for name, points in event.get("rows", ())]
        parts += [t("column {n} +{points}", n=COLUMNS[col] if 0 <= col < 3 else "?", points=int(points))
                  for col, points in event.get("columns", ())]
        return (t("Bonus!") if len(parts) == 1 else t("Bonuses!")), " · ".join([who] + parts)
    if what == "ABAKA":
        title = t("Abaka!")
    elif what == "ROYAL":
        title = t("Royal full house!")
    else:
        title = _row(what) + "!"
    return title, who + (f" · {t('first roll')}" if event.get("first") else "")


def _row(name: str) -> str:
    try:
        return row_name(Category[name])
    except KeyError:
        return name


__all__ = ["COLUMNS", "REACTION_LOOKS", "effect_words", "player_name", "reaction_words"]
