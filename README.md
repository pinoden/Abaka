# Abaka

A dice game of combinations for 2 to 5 players, built in Python and Streamlit.
Play on one screen, or online with each player on their own device.

Live app: https://mipt-abaka.streamlit.app/

## Features

- **Two ways to play**, for 2 to 5 players: on one screen, or online with an
  invite link or a game code (see `README_MULTIPLAYER.md`)
- **Starting throw**: before the first round everyone throws all five dice, and
  the lowest total goes first
- **Tap-to-pick dice**: tap the dice to reroll, or reroll all five; the joker is
  marked
- **Moves with previews**: every option shows its score ("Full house · 46"), the
  target cell lights up on the scoreboard, and the button says exactly what
  happens, including a bonus the move gives up
- **Clear scoreboard**: full row names, totals and school balance in each
  player's header; the last move is outlined in orange until the next one
- **Saved games**: every game is saved after every move and comes back from its
  link, its code or "Continue a game" on the home page
- **English and Russian**: a Russian browser starts in Russian; the EN/RU switch
  is on the home page and in the game menu
- **Works on phones**: the layout stacks on narrow screens
- **How to play**: the rules are on the home page and in the game menu

## Quick start

Needs Python 3.11 or newer (for the pinned Streamlit 1.67).

```bash
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

streamlit run abaka_ui.py   # the app, on port 8501, reachable from your local network
python -m abaka             # the same game in the terminal (python main.py does the same)
```

## Project layout

```
abaka/                 the game itself, no Streamlit
  engine.py            GameEngine: turns, the starting throw, scoring and crossing out
  models.py            dice and categories
  player.py            a player's table, school balance and final score
  scoring.py           what each combination scores
  school.py, bonus.py  School rows and their balance; row and column bonuses
  rooms.py             every game, online and on one device: RoomStore, saved to disk
  saving.py            games to and from JSON
  cli.py, render.py    the terminal version
ui_components/         the Streamlit interface (see ui_components/README.md)
abaka_ui.py            the app: home, invite and waiting screens, online updates
code_version.py        reloads the game modules when their files change (app updates)
.streamlit/            server settings and colour theme
tests/                 unittest tests
tools/                 simulate.py: random complete games with rule checks;
                       loadtest.py: simulated browsers, server CPU and latency
docs/                  ARCHITECTURE_REVIEW.md: review for many games at once
```

## Development

```bash
python -m unittest discover -s tests -p "test_*.py"   # all tests
python tools/simulate.py 200 40                        # random complete games (2-3 min)
python tools/loadtest.py --clients 100 --interval 1    # 100 open pages polling every second
```

- The engine (`abaka/`) also runs on Python 3.8. There, the tests that need
  Streamlit are skipped.
- GitHub Actions runs the tests on every pull request and on `main`
  (`.github/workflows/tests.yml`):
  - on Python 3.13 with the pinned Streamlit, as on Streamlit Cloud;
  - on Python 3.8 without Streamlit.
- `CLAUDE.md` is the project's working log: open requests, status, decisions
  and the conventions for changes.

## Contributing

1. Create a branch
2. Make your changes, with tests
3. Open a pull request (`main` is protected)

## License

This project is open source and available under the [MIT License](LICENSE).
