"""
The turn that has just been played, in words and dice, for every client.

- `what_was_written`: the latest move as players read it ("scored 23 in Full house").
- `last_throw`: the dice the computer's move was written from (owner, Backlog item 35: "you
  should see his final combination first"). The computer writes a second after its last roll,
  so its dice were gone before a person had read them. Now they stay on the table until the
  next player rolls, with what the computer wrote: the player's own "Roll dice" is the one
  button that moves on.

The web page draws both (ui_components/scoreboard.py, main_ui.py), and the API sends
`last_throw` to apps. No Streamlit here, and Python 3.8 like the rest of the package.
"""

from typing import Optional, Sequence

from .i18n import t
from .moves import is_school, row_name


def what_was_written(engine, move) -> str:
    """What the move `(player, row, slot)` wrote: "scored 23 in Full house" and similar."""
    player, cat, slot = move
    value = engine.players[player].table[cat][slot]
    name = row_name(cat)
    if is_school(cat):
        return (t("wrote {name} (exactly three)", name=name) if value == "X"
                else t("wrote {name} (balance now {value})", name=name, value=value))
    if value == "X":
        return t("crossed out {name}", name=name)
    return t("scored {value} in {name}", value=value, name=name)


def last_throw(engine, computers: Sequence[int] = ()) -> Optional[dict]:
    """
    The computer's final dice, while they are still on the table: its move was the latest one
    and the next player has not rolled yet. None otherwise (and once the game is over).

    - `seat`: the computer's seat; `dice`: its dice as (value, is joker);
    - `text`: "Computer’s last throw: scored 46 in Full house", in the viewer's language.
    """
    move = getattr(engine, "last_move", None)
    dice = getattr(engine, "last_dice", ())
    if (move is None or not dice or engine.dice or move[0] not in (computers or ())
            or getattr(engine, "choosing_first_player", False) or engine.is_game_over()):
        return None
    return {
        "seat": move[0],
        "dice": [(value, bool(joker)) for value, joker in dice],
        "text": t("{name}’s last throw: {what}", name=engine.players[move[0]].name,
                  what=what_was_written(engine, move)),
    }
