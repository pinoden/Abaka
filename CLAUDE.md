# CLAUDE.md

Guidance for Claude Code in this repository, plus a running log of decisions
and progress. Keep the log at the bottom up to date when work is done.

Repository: https://github.com/pinoden/Abaka (remote `origin`). Finished work
goes there.

## Commands

```bash
pip install -r requirements.txt                       # streamlit, Pillow
streamlit run abaka_ui.py                             # the app (port 8501, all interfaces)
python -m abaka                                       # CLI version
python -m unittest discover -s tests -p "test_*.py"   # tests
python -m unittest tests.test_rooms -v                # one test module
```

Notes for this machine: the base `python3` is Anaconda 3.8 without Streamlit.
The conda env at `~/opt/anaconda3/envs/Python39` has Streamlit 1.48 and
Pillow; use `~/opt/anaconda3/envs/Python39/bin/python -m streamlit run abaka_ui.py`.
`gh` is not installed.

## Architecture

Abaka is a dice game (4 white dice + 1 joker; 15 rows x 3 slots per player:
School 1-6 and nine combinations). Python + Streamlit.

| Path | Purpose |
|---|---|
| `abaka/engine.py` | `GameEngine`: turn flow (`start_turn`, `reroll`, `record_score`, `record_cross`) |
| `abaka/player.py` | `PlayerState`: score table, school balance, final score |
| `abaka/scoring.py`, `school.py`, `bonus.py` | Scoring rules, school balance, row/column bonuses |
| `abaka/rooms.py` | Online play: `RoomStore` (shared rooms) and `RoomEngine` (engine-shaped proxy). No Streamlit imports |
| `abaka_ui.py` | Streamlit entry point: mode switch, online lobby, waiting room, polling |
| `ui_components/` | `main_ui.py` (turn flow), `scoreboard.py`, `dice.py`, `move_selection.py`, `sidebar.py` |
| `tests/` | `unittest` tests |

### Turn state lives in the engine

`engine.dice == []` means the current player has not rolled yet.
`record_score` / `record_cross` end the turn through `GameEngine._end_turn()`,
which clears the dice and advances `current`. The UI derives the phase from
the engine; there are no `awaiting_turn` / `dice_rolled` session flags any more.

### Online play (two browsers, one game)

- One Streamlit server process serves every browser. `abaka_ui.get_store()`
  (`st.cache_resource`) returns the single `RoomStore` for that process.
- A room has a 5-character code, up to two seats (name + secret token) and
  one `GameEngine`. The game is created when the second player joins.
- Browsers never hold game state. Each render takes `store.view(code)` (a deep
  copy) and wraps it in `RoomEngine`, so the existing UI components work
  unchanged. `RoomEngine` forwards `start_turn`, `reroll`, `record_score`,
  `record_cross` to the store.
- `RoomStore._act` holds a lock, checks the token owns the seat whose turn it
  is, applies the move to a copy of the engine, and swaps it in only if the
  move succeeded. Every change bumps `room.version`.
- Live updates: `_watch_room` is an `st.fragment(run_every=1.0)` that compares
  `store.version(code)` with the version the page was drawn from and calls
  `st.rerun()` when it differs.
- The URL carries only `?room=CODE` (safe to share). The seat token stays in
  `st.session_state`. After a refresh the player opens the link and clicks
  their name; `store.reclaim` issues a new token and the old tab loses control.
- Rooms idle for 12 hours are dropped when a new room is created.

## Rules for changes

- Engine code must keep working on Python 3.8 (no `X | None` at runtime).
- Player names reach the other player's browser. `scoreboard.py` builds raw
  HTML, so names must go through `html.escape` there.
- Any new online action goes through `RoomStore._act` so it gets the turn
  check, the lock and the version bump.
- Game rules in this repo are the owner's own; do not copy rule changes from
  the upstream `abaka_cc` repo unless asked.

## Decision log

**2026-11-14/15: live two-player mode**

- Looked at https://github.com/alexeylavrov/abaka_cc (FastAPI WebSocket
  backend + React frontend, 2-6 players, different rule details). Decided not
  to port it: it is a full rewrite in another stack. Took its core idea
  instead: the server owns the game, clients send actions and render what the
  server has.
- Why the previous online mode (Firebase / "mock" client in `abaka/online.py`)
  did not work live: the turn phase was stored per browser in
  `st.session_state`, so the waiting player never saw the opponent's dice; a
  `dice` property on `OnlineGameEngine` shadowed the synced value; the guest
  was always seat 1 with no join handshake; a refresh lost the seat; and
  Firebase mode made both players paste API keys.
- Chose in-process shared rooms over Firebase or a separate server: no
  credentials, no extra service, works on Streamlit Community Cloud and on a
  home network. Cost: games live in memory, so both players must use the same
  running app and games are lost on restart. Accepted.
- Chose polling with a 1-second fragment over WebSockets: Streamlit has no
  server push API for app code; measured delay in a real browser was under a
  second.
- Removed `abaka/online.py` and the Firebase/mock modes (still in git history).
- Rejoin is by clicking your name, with no password. Fine between two friends;
  anyone holding the invite link could take a seat.
- Pre-roll move selection was removed: a player must roll before scoring or
  crossing (the room enforces it too).

## Status

Done and verified (2026-11-15):
- `abaka/rooms.py`, new `abaka_ui.py`, simplified `ui_components/main_ui.py`.
- 14 room tests in `tests/test_rooms.py`, including a full two-player game
  and rematch. All pass, as do the 11 older rule tests.
- Two headless Chromium browsers played against a real Streamlit server:
  create, join by link, live dice on both screens, reroll, score, turn
  passing, refresh and rejoin.

Known issues:
- `tests/test_abaka_engine.py` fails to import (`abaka_engine` no longer
  exists). With the import fixed, 4 of its 15 tests fail because they encode
  older straight and first-roll rules. Left alone; needs the owner's call on
  which rules are right.
- Not yet tested on Streamlit Community Cloud itself.
- `abaka/ui_components/requirements.txt` is a stray leftover file.

Ideas not started:
- Show the active player's selected dice to the opponent.
- Persist rooms (file or database) so games survive a restart.
- More than two players (the engine supports it; `rooms.MAX_PLAYERS` and the
  lobby do not).
