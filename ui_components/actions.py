"""
Game buttons run their move in an on_click callback, before the page is drawn.

With `if st.button(...): move(); st.rerun()` every move cost two full script runs for
the player who made it; a callback makes it one.

A callback makes the move the page showed when it was drawn. If the game has
changed since (a double tap, another player's move not drawn yet), the room
refuses it (OutdatedPage) and nothing is shown: the page is redrawn with the game
as it is now. Any other refusal is kept in the session and shown by the next
drawing of the play panel (show_action_error).
"""

import streamlit as st

from abaka.rooms import OutdatedPage
from abaka.i18n import error

_ERROR_KEY = "action_error"


def run_action(action, *args) -> None:
    """on_click callback: make the move; on success forget the picked dice."""
    try:
        action(*args)
    except OutdatedPage:
        # The page is redrawn with the game as it is now; dice picked on the old page may
        # no longer be the same dice.
        st.session_state.selected_dice = set()
        st.session_state.pop(_ERROR_KEY, None)
    except (ValueError, RuntimeError, IndexError) as e:
        st.session_state[_ERROR_KEY] = str(e)
    else:
        st.session_state.selected_dice = set()
        st.session_state.pop(_ERROR_KEY, None)


def reroll_picked(engine) -> None:
    run_action(engine.reroll, sorted(st.session_state.get("selected_dice", set())))


def reroll_all(engine) -> None:
    run_action(engine.reroll, list(range(len(engine.dice))))


def show_action_error() -> None:
    """Show (once) why the last move was refused."""
    message = st.session_state.pop(_ERROR_KEY, None)
    if message:
        st.error(error(message))


def forget_action_error() -> None:
    st.session_state.pop(_ERROR_KEY, None)
