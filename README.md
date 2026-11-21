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
streamlit run abaka_server.py   # the app and the API for apps (docs/API.md) on one port
python -m abaka             # the same game in the terminal (python main.py does the same)
```

### The app for phones

`mobile/` is the app for Android and iOS: React Native with Expo, in TypeScript. It plays
on the server above (`streamlit run abaka_server.py`), so it needs Node 26 and that server:

```bash
cd mobile && npm ci
npx expo start              # scan the QR code with Expo Go on a phone on the same Wi-Fi, or press w
```

Its guide, with the commands and the rules for changing it, is `mobile/AGENTS.md`.

## Project layout

```
abaka/                 the game itself, no Streamlit
  engine.py            GameEngine: turns, the starting throw, scoring and crossing out
  models.py            dice and categories
  player.py            a player's table, school balance and final score
  scoring.py           what each combination scores
  school.py, bonus.py  School rows and their balance; row and column bonuses
  rooms.py             every game, online and on one device: RoomStore, saved to disk
  clubs.py             clubs and their rating tables
  repository.py        where games are saved: files, Postgres, or both
  saving.py            games to and from JSON
  moves.py             the moves a player can make now, with exact previews
  i18n.py              every text players see, in English and Russian
  api.py               the game as JSON, for apps (Android, iOS): docs/API.md
  cli.py, render.py    the terminal version
ui_components/         the Streamlit interface (see ui_components/README.md)
server/                the server around the game: where its stores save (stores.py),
                       the API over HTTP and a live WebSocket (http.py)
abaka_ui.py            the app: home, invite and waiting screens, online updates
abaka_server.py        the app and the API for apps in one process (Streamlit 1.67+)
code_version.py        reloads the game modules when their files change (app updates)
.streamlit/            server settings and colour theme
mobile/                the app for Android and iOS (React Native with Expo): mobile/AGENTS.md
tests/                 unittest tests
tools/                 simulate.py: random complete games with rule checks;
                       loadtest.py: simulated browsers, server CPU and latency;
                       website_check.py, app_check.py: the website and the app in a real browser;
                       export_texts.py: the app's texts from abaka/i18n.py
docs/                  API.md: the API for apps; LOADTEST.md: load-test rows;
                       ARCHITECTURE_REVIEW.md: review for many games at once
```

## Development

```bash
python -m unittest discover -s tests -p "test_*.py"   # all tests
python tools/simulate.py 200 40                        # random complete games (2-3 min)
python tools/loadtest.py --clients 100 --interval 1    # 100 open pages polling every second
pip install -r requirements-dev.txt && python -m playwright install chromium-headless-shell
python tools/website_check.py                          # the live website in a real browser
python tools/website_check.py --serve abaka_ui.py      # the same check on a local server
```

- The engine (`abaka/`) also runs on Python 3.8. There, the tests that need
  Streamlit are skipped.
- GitHub Actions runs the tests on every pull request and on `main`
  (`.github/workflows/tests.yml`):
  - on Python 3.13 with the pinned Streamlit, as on Streamlit Cloud, including
    the website's main flows in headless Chromium (`tests/test_website.py`);
  - on Python 3.8 without Streamlit;
  - the phone app: typecheck, lint, its API client against a real server, and
    its web build in headless Chromium (`tools/app_check.py`).
- `ProjectLibrary.md` is the project's working log: open requests, status, decisions
  and the conventions for changes.

## Contributing

1. Create a branch
2. Make your changes, with tests
3. Open a pull request (`main` is protected)

## License

This project is open source and available under the [MIT License](LICENSE).
