# Abaka UI components

The Streamlit interface. `abaka_ui.py` (project root) picks the screen; these
modules draw it.

What the web page shares with the apps for phones lives in the game package:
- `abaka/moves.py` works out which rows can be written and what each would
  score, by trying the move on a copy of the game;
- `abaka/i18n.py` holds the texts in English and Russian: `t("...")`, plurals,
  error messages, and `md()` for names in Markdown;
- `abaka/api.py` gives the game to apps as JSON (`docs/API.md`).

| Module | What it does |
|---|---|
| `main_ui.py` | Game screen for both modes: top bar with menu, play panel (left), scoreboard (right), the starting throw, results |
| `dice.py` | The five dice as tappable buttons drawn with CSS, the roll animation and the two Reroll buttons |
| `move_selection.py` | Score / Cross out switch, the list of possible rows with their scores, the confirm button |
| `actions.py` | What the game buttons do when clicked (`on_click` callbacks): make the move, keep a refusal to show once |
| `scoreboard.py` | The score table, including the preview of the picked move |
| `rules.py` | "How to play" text and dialog, in English and Russian |
| `style.py` | Page CSS, dice artwork (SVG), small HTML helpers |

## How styling works

- Colours, corner radius and fonts of Streamlit's own widgets come from
  `.streamlit/config.toml` (`[theme]`).
- Everything else is plain CSS in `style.py`, injected once per page.
- Widgets are targeted by key: Streamlit adds the class `st-key-<key>` to any
  element created with `key=...`. For example, the dice are buttons with keys
  `die-0` to `die-4`, and `dice.py` sets each one's face with
  `.st-key-die-0 button { background-image: ... }`. Some keys carry a suffix
  that changes with the game (`reroll-all-2`), so CSS matches keys with
  `[class*="st-key-..."]`.
- Containers whose key starts with `card` get the white card look.

## Player names

Names reach other players' browsers, so they are never trusted:

- inside HTML they always go through `html.escape`;
- in captions, toasts and button labels, which Streamlit renders as Markdown,
  they go through `i18n.md()`.

## Requirements

Streamlit 1.67, pinned in `requirements.txt` (horizontal containers,
`st.pills`, `st.segmented_control`, keyed containers). The code also runs on
Streamlit 1.48.
