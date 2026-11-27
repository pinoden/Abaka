"""
Whose seat is whose, in words (owner, Backlog item 37): a seat of an online game belongs to the
device that took it, and another device has to be let in (rooms.py: ask, asked, answer). Here:
which requests a seated player may answer, and what they say, for the web page and for apps.

No Streamlit.
"""

from typing import List, Optional, Sequence

from .i18n import t


def requests_for(asks: Sequence[dict], names: List[str], me: Optional[int]) -> List[dict]:
    """
    The requests to be let in that the player in seat `me` may answer now, with their words
    in the current language: each {"seat", "name", "yours", "title", "text"}. A request for
    the player's own seat is always theirs to answer; one for another seat only once that
    seat's device is not here (`open`). The texts are plain: escape them for HTML or Markdown.
    """
    if me is None:
        return []
    found = []
    for ask in asks:
        seat = ask["seat"]
        if not 0 <= seat < len(names) or not (seat == me or ask["open"]):
            continue
        name = names[seat]
        if seat == me:
            title = t("Is this you on another device?")
            text = t("Someone opened this game on another device and asks to play as you. Let them in only "
                     "if it is you: this device will then stop playing.")
        else:
            title = t("{name} asks to come back", name=name)
            text = t("Someone on another device asks to play as {name}. Let them in only if you know it "
                     "is {name}.", name=name)
        found.append({"seat": seat, "name": name, "yours": seat == me, "title": title, "text": text})
    return found
