# Abaka UI components

The Streamlit interface. `abaka_ui.py` (project root) picks the screen; these
modules draw it.

| Module | What it does |
|---|---|
| `main_ui.py` | Game screen for both modes: top bar with menu, play panel (left), scoreboard (right), results |
| `dice.py` | The five dice as tappable buttons drawn with CSS, the roll animation and the Reroll button |
| `move_selection.py` | Score / Cross out switch, the list of possible rows with their scores, the confirm button |
| `moves.py` | Works out which rows can be written and what each would score, by trying the move on a copy of the game. No Streamlit, unit-tested in `tests/test_moves.py` |
| `scoreboard.py` | The score table, including the preview of the picked move |
| `rules.py` | "How to play" text and dialog |
| `style.py` | Page CSS, dice artwork (SVG), small HTML helpers |

## How styling works

- Colours, corner radius and fonts of Streamlit's own widgets come from
  `.streamlit/config.toml` (`[theme]`).
- Everything else is plain CSS in `style.py`, injected once per page.
- Widgets are targeted by key: Streamlit adds the class `st-key-<key>` to any
  element created with `key=...`. For example, the dice are buttons with keys
  `die-0` to `die-4`, and `dice.py` sets each one's face with
  `.st-key-die-0 button { background-image: ... }`.
- Containers whose key starts with `card` get the white card look.
- Player names are shown inside HTML, so they always go through `html.escape`.

## Requirements

Streamlit 1.48 or newer (horizontal containers, `st.pills`,
`st.segmented_control`, keyed containers).
