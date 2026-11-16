# CLAUDE.md

Guidance for Claude Code in this repository and the project's working log:
the owner's open requests, current status, and the decisions made so far.
Update the Backlog, Status and Decision log whenever work is done.

- **Repository:** https://github.com/pinoden/Abaka (git remote `origin`). Finished
  work goes there. `main` is protected: every change goes in through a pull
  request.
- **Live app:** https://mipt-abaka.streamlit.app/, deployed by the owner on
  Streamlit Community Cloud from `main` (main file `abaka_ui.py`). Merging into
  `main` updates it automatically, within a few minutes. Cloud reloads the code
  in the running server instead of restarting it (see Online play).

## Commands

```bash
pip install -r requirements.txt                       # streamlit >= 1.48
streamlit run abaka_ui.py                             # the app (port 8501, all interfaces)
python -m abaka                                       # CLI version
python -m unittest discover -s tests -p "test_*.py"   # all tests
python -m unittest tests.test_rooms -v                # one test module
```

### Notes for this machine

- The base `python3` is Anaconda 3.8 without Streamlit. The conda env
  `~/opt/anaconda3/envs/Python39` has Streamlit 1.48:
  `~/opt/anaconda3/envs/Python39/bin/python -m streamlit run abaka_ui.py`.
- `gh` is not installed. Pull requests are created and merged through the
  GitHub REST API with the credential git already stores in the macOS keychain
  (`git credential fill`).
- Headless Chromium for browser checks is cached in
  `~/Library/Caches/ms-playwright`. Use it through `playwright-core` installed
  in a scratch folder, never in the repo.
- Streamlit Cloud installs the newest Streamlit (requirements say
  `streamlit>=1.48`), which is newer than the local 1.48. There, segmented
  controls and pills are `role="radio"` buttons, so browser checks should
  find them by text, not by role. On Cloud the app runs inside an iframe
  (`iframe[title="streamlitApp"]`, path `/~/+/`).

## Architecture

Abaka is a dice game: 4 white dice + 1 joker; each player has 15 rows x 3
cells (School 1-6 and nine combinations) plus a bonus cell per row.
Python + Streamlit.

| Path | Purpose |
|---|---|
| `abaka/engine.py` | `GameEngine`: turn flow (`start_turn`, `reroll`, `record_score`, `record_cross`) |
| `abaka/player.py` | `PlayerState`: score table, school balance, final score |
| `abaka/scoring.py`, `school.py`, `bonus.py` | Combination scoring, school balance, row and column bonuses |
| `abaka/rooms.py` | Online play: `RoomStore` (shared rooms) and `RoomEngine` (engine-shaped proxy). No Streamlit imports |
| `abaka_ui.py` | Streamlit entry point and screens: home, invite, waiting room; online polling |
| `ui_components/main_ui.py` | Game screen for both modes: top bar and menu, play panel, scoreboard, results |
| `ui_components/moves.py` | Possible moves with exact score previews (tries each on a copy of the engine). No Streamlit |
| `ui_components/dice.py`, `move_selection.py`, `scoreboard.py`, `rules.py` | Dice, move picker, score table, rules text |
| `ui_components/style.py`, `.streamlit/config.toml` | CSS and dice SVGs; theme colours |
| `tests/` | `unittest` tests |

### Turn state lives in the engine

`engine.dice == []` means the current player has not rolled yet.
`record_score` and `record_cross` end the turn through `GameEngine._end_turn()`,
which clears the dice and moves `current` to the next player. The UI reads the
turn phase from the engine; there are no per-browser turn flags.
`engine.last_move` is `(player index, category, slot)` of the cell written by
the most recent move (None before the first move); the scoreboard highlights
it. A game has 2 to 5 players; turns go round in seat order.

Every game in the app (same device, online, CLI) opens with the starting
throw: `GameEngine(names, starting_throw=True)`. While
`engine.choosing_first_player` is true, `current` is the player whose
throw is next and `throw_round` lists the players throwing in this round
(after a tie, only the tied players). `throw_for_start()` records the throw
in `starting_throws` (dice, total, round). When the round ends, the lowest
total becomes `first_player` and `current`. `start_turn()` is refused until
then. The default `starting_throw=False` exists for tests; `RoomStore` uses
`starting_throw=True` unless told otherwise (old room tests pass `False`).

### Online play

- One Streamlit server process serves every browser. `abaka_ui.get_store()`
  returns the single `RoomStore` for that process. It is cached with
  `st.cache_resource` per `RoomStore` class (`_store_for_code(id(RoomStore))`).
  When a commit is applied, Streamlit reloads all of the app's modules, but
  cached objects survive. Keying by class gives the new code a new store, so
  games in progress end on every update, as on a restart. Do not go back to a
  plain cached `RoomStore()`: an old store reached the new code and broke the
  live app (Decision log, 2026-11-16).
- A room has a 5-character code, a `capacity` of 2 to 5 players chosen by the
  creator (`rooms.MIN_PLAYERS`..`MAX_PLAYERS`), seats in join order (each a
  name plus a secret token; seat 0 is the creator) and one `GameEngine`,
  created when the last seat is taken or when the creator calls
  `store.start_now` with at least two players seated. Names are made distinct
  ("Ann (2)").
- Browsers never hold game state. Each page render takes `store.view(code)`
  (a deep copy) and wraps it in `RoomEngine`, so the UI components work the
  same as in a local game. `RoomEngine` forwards `start_turn`, `reroll`,
  `record_score` and `record_cross` to the store.
- `RoomStore._act` holds a lock, checks that the token owns the seat whose turn
  it is, applies the move to a copy of the engine, and swaps the copy in only
  if the move succeeded. Every change bumps `room.version`.
- Live updates: `_watch_room` is an `st.fragment(run_every=1.0)` that compares
  `store.version(code)` with the version the page was drawn from, and calls
  `st.rerun()` when they differ.
- The URL carries only `?room=CODE`, so it is safe to share. The seat token
  stays in `st.session_state`. After a refresh, the player opens the link and
  clicks their name; `store.reclaim` issues a new token and the old tab loses
  control.
- Rooms idle for 12 hours are dropped the next time a room is created.
- Leaving the waiting room (`store.leave`, before the game starts) frees the
  seat. Later players move up one seat, so if the creator leaves, the next
  player becomes the creator and can press "Start now"; an empty room is
  closed. The others see "<name> left." (`_announce_departures`). Once the
  game has started, leaving keeps the seat so the player can rejoin.

### UI conventions

- `abaka_ui.main()` picks the screen: seated in a room -> online game or
  waiting room; a local engine -> same-device game; `?room=` in the URL ->
  invite page; otherwise -> home. There is no sidebar.
- Widgets are styled through the `st-key-<key>` class Streamlit adds to keyed
  elements. Dice are buttons keyed `die-0` to `die-4`; containers keyed
  `card-*` get the card look. Per-render CSS (die faces, picked dice, roll
  animation) is injected with `st.html("<style>...")`.
- Move-picker widget keys include a turn signature (player, rolls left, dice),
  so a pick never carries over to a reroll or a new turn.
- Dice size: at most `--ab-die` (60px) and shrinks so all five fit the play
  card. The card is a CSS size container and the size is
  `min(--ab-die, (100cqw - 4 gaps) / 5)`, so it adapts to any layout.
- Layout: play panel and scoreboard split 5:7; with 5 players 4:8 so the
  scoreboard fits on desktop. With 3+ players the table uses the compact
  `ab-many` style; on narrow screens it scrolls sideways inside its card with
  the row names pinned.
- Online notifications: "<friend> joined" / "Everyone's here." when this
  browser was on the waiting screen (`was_waiting`); "Your turn!" when
  `was_my_turn` changes from False to True ("Your throw!" during the
  starting throw).
- Starting throw screen: `main_ui._render_starting_throw` shows "Who goes
  first?", each player's latest throw (small dice + total) and the
  `start-throw` button. On the same device the button names the player
  ("Throw for Ann"); online only the thrower's screen has it ("Throw the
  dice"). Until the first move, `_starter_note` shows "Ann threw the lowest
  (9) and goes first."

## Rules for changes

- Engine code must keep working on Python 3.8 (no `X | None` at runtime).
- Player names reach other players' browsers. `scoreboard.py` and other
  modules build raw HTML, so names must go through `html.escape`.
- Every new online action goes through `RoomStore._act`, so it gets the turn
  check, the lock and the version bump.
- The game rules are the owner's own. Do not change them, or copy rule details
  from the upstream `abaka_cc` repo, unless the owner asks.

## Backlog

Nothing open. Requests 1-4 came from the owner after deploying (2026-11-15)
and were merged in PR #13; request 5 (2026-11-16) is in PR #18.

1. **Highlight the last move.** Done. The cell written by the most recent
   move, by any player, is outlined in orange, with a "Last move: ..." line
   under the scoreboard. It returns to normal when the next move is made.
   > "mark the last move with other color. when there's a new last move turn it to normal color"

2. **"Reroll all" button.** Done. "Reroll all" sits next to the button that
   rerolls only the picked dice ("Reroll picked" / "Reroll 2 dice").
   > "add button "reroll all""

3. **School row bonus after paying from the balance.** Done. Before, writing a
   School row with fewer than three dice of its number was paid from the
   school balance (one die short costs 1 in School 1 ... 6 in School 6) and
   the row's bonus was crossed out for that player at once.
   **Decided by the owner:** any payment from the balance keeps the row bonus
   available, whatever the amount, including endgame writes that take the
   balance below zero. Crossing out a combination still cancels its bonus.
   (`school_minus_used` was removed from the engine.)
   > "when I apply "-1", ... "-6" to school, I can't get a bonus for that line anymore"

4. **Games for 3, 4 and 5 players.** Done. Before, a game always had exactly
   two players.
   **Decided by the owner:** both modes support 2 to 5 players. On the same
   device you pick the number and enter the names. Online, the creator picks
   the number when creating the game; it starts by itself once that many have
   joined, and the creator can press "Start now" with at least two.
   > "add options for 3, 4 and 5 multiplayers"

5. **Starting throw: the lowest total goes first.** Done. Before the first
   round, each player throws all five dice, and the lowest total starts.
   This replaced the rotation of who starts from one game to the next.
   Details the owner did not specify; I chose them because the owner said
   "don't ask anymore":
   - players who tie for the lowest throw again, until one is lowest;
   - dice count their face value (the joker's wild 1 is for combinations
     only);
   - every game opens with it, including "Play again" and online rematches;
   - play then goes round the table from the starter;
   - it applies in every mode: same device, online (each player throws on
     their own screen) and the CLI.
   > "Before the first round, each player throws all five dice and the one with the minimal sum starts first"

## Status (2026-11-16)

- **Live two-player online mode:** merged in PR #11.
- **Modern UI:** merged in PR #12 (home screen, tappable dice, move previews,
  new scoreboard, phone layout).
- **Deployed:** the owner deployed `main` on Streamlit Community Cloud and
  reports that it works.
- **Owner requests (last move, Reroll all, School bonus, 2-5 players):**
  merged in PR #13.
- **Starting throw (owner request 5):** PR #18.
- **Tests:** 60 pass: 23 room tests (`test_rooms.py`: a full two-player game,
  rematch, 3-5 player rooms, starting early, leaving the waiting room),
  13 move-preview tests (`test_moves.py`), 5 tests for the owner's requests
  (`test_owner_requests.py`), 6 starting-throw tests
  (`test_starting_throw.py`: lowest starts, ties, joker at face value,
  rooms, rematch), 11 older rule tests, and 2 app tests
  (`test_ui_notices.py`, `test_ui_store.py`). The app tests run the real app
  script with Streamlit's AppTest and are skipped where Streamlit is not
  installed, such as the base Python 3.8.
- **Test round fixes:** the lost-seat notice, merged in PR #14; Leave in the
  waiting room frees the seat, merged in PR #15; online play on the live app
  (stale room store after updates), merged in PR #16.
- **Live app check (2026-11-16):** the home screen loaded, and same-device
  play was not affected. "Create game" failed with a TypeError, so online
  play had been broken on the live app since PR #13 was merged. PR #16 was
  live within minutes, and then the full check passed in headless Chromium
  on a desktop and a phone:
  - Online game: the invite link is
    `https://mipt-abaka.streamlit.app/?room=CODE` and opens the invite page.
    The creator's screen switched to "Your turn" within a second of the join.
  - Moves: dice reached the other player within about a second. "Reroll
    all", scoring and crossing out worked, and the "Your turn!" toast and
    last-move highlight appeared on both screens.
  - Rejoin: rejoining from a second device showed the old tab the
    "opened in another tab" notice.
  - Leaving: Menu > Leave game worked. When the creator left a 3-player
    waiting room, the guest was told they were now the host; their Cancel
    then closed the room.
  - Phone layout: a same-device game for 5 players had dice on one row and no
    sideways page scrolling.
  - Test games used "Test ..." names and were cancelled or left.
- **Full test round (2026-11-16)** after the owner asked to "test everything".
  It found the lost-seat notice bug and the kept seat after Leave (see the
  Decision log).
  - Simulated play: 1,092 complete random games for 2-5 players
    (171,810 moves), played through the same move lists the UI offers, on
    Python 3.9 and 3.8. Found no turn without a legal move and no offered
    move the engine refused. After every move it checked that the written
    cell, last move, turn order, school balance and totals are right, and at
    game end that row and column bonuses are right, including the School
    bonus after paying from the balance (4,184 games had that case). Many
    online rooms were played at once from several threads while other
    threads kept trying moves out of turn; every such move was refused.
  - The text CLI (`python -m abaka`): a full 3-player game.
  - Every screen through Streamlit's AppTest (the real script, one session
    per player; no browser):
    - a full same-device game (90 turns, all by clicking);
    - a full 2-player online game in two sessions, with results, Play again,
      refresh and rejoin, and a stale tab;
    - 3-5 player games, starting early, Cancel and Leave;
    - join-by-code errors, the rules, and player names containing HTML.
  - Headless Chromium against a real server, after the Leave change: all the
    browser checks below, plus the creator leaving a 4-player waiting room
    (the next player, on a phone, is told they're the host and starts the
    game) and the lost-seat notice on a phone.
- **Browser checks** before merging (headless Chromium against a real server):
  a 2-player online game (desktop + phone) with refresh and rejoin; a 3-player
  online game (turn order, last-move highlight, Reroll all on every screen); a
  5-player game started early with 3; same-device games for 2-5 players at
  1360px, 1024px and 390px wide (dice always fit on one row; no sideways page
  scrolling).

### Known issues

- `tests/test_abaka_engine.py` fails to import: the `abaka_engine` module no
  longer exists. With the import fixed, 4 of its 15 tests fail because they
  expect older straight and first-roll rules. Left alone until the owner says
  which rules are right.
- `abaka/ui_components/requirements.txt` is a leftover file that nothing uses.
- On screens around 1024px wide, a 5-player game has small dice (about 34px),
  and with 4 or 5 players the scoreboard scrolls sideways inside its card.

### Ideas not started

- Dark theme (the scoreboard CSS colours would need to follow the theme).
- Show the opponent which dice the active player has picked.
- Save rooms to a file or database so games survive an app restart.

## Decision log

**2026-11-16: starting throw (owner request 5)**

- The rule lives in the engine (`throw_for_start`), so the same-device game,
  online rooms and the CLI share one implementation. Online it is a turn
  action like the others: `RoomStore.throw_for_start` goes through `_act`,
  so only the player whose throw is next can throw.
- The details the owner left open are listed under Backlog item 5. Ties
  throw again rather than falling back to seat order, so the rule alone
  decides.
- The starting throw is kept out of `engine.dice`: it is not a turn and
  never scores.
- Checked with unit tests and simulated games (every simulated starting
  throw ended with a single lowest total, including tie rounds). Also
  checked through AppTest for every screen, including an online tie, and in
  headless Chromium at 1360, 1024 and 390px wide, on the same device and
  online between a desktop and a phone.

**2026-11-16: full test round**

- Fixed: online play was broken on the live app. "Create game" failed with a
  TypeError at `store.create(name, players)`.
  - Cause: Streamlit Cloud applies each commit by reloading the modules in the
    running server, and `st.cache_resource` objects survive the reload.
    `get_store()`'s source never changed, so the live app still held the
    `RoomStore` made by the PR #12 code, whose `create()` takes no player
    count.
  - Fix: the store is now cached per `RoomStore` class, so new code always
    gets a new store. `validate=` was rejected: Streamlit keeps the first
    validate function it was given, and that function would still compare
    against the old class.
  - Pages that keep running the old code (the 1-second poll) keep the old
    store until the next click, so old and new code never replace each
    other's store.
  - Tested with `tests/test_ui_store.py`, and on a real server by editing
    `abaka/rooms.py` while a game was open.
  - The fix itself changes `get_store()`, so merging it also cleared the
    live app's stale store; no reboot was needed.

- Fixed: when a player's seat was taken over from another tab (refresh and
  rejoin), the old tab was meant to say "This game was opened in another tab
  or device". It kept the `?room=` link, so it landed on the invite page,
  which did not show notices. The message appeared later, out of context, on
  the home screen. The invite page now shows it (`_show_lobby_notice`), and
  `tests/test_ui_notices.py` covers it.
- The test scripts used for the round (game simulation, AppTest screens,
  browser checks) are not in the repo; only the regression tests were added.
- Leave in the waiting room now frees the seat. The test round found that a
  guest who pressed "Leave" kept their seat: the game still counted them and
  started with them, and nobody could remove them. Also, if the creator left,
  the others could not start the game. The owner said "Always allow, don't ask
  anymore", so I chose the behaviour the button's name suggests: leaving
  before the start gives up the seat, the next player in join order becomes
  the creator, and an empty room closes. After the start, seats are kept so
  players can rejoin. The button reads "Cancel" only when the creator is
  alone (the room then closes).
- Tool permissions: the owner allowed all tools without prompts
  (`~/.claude/settings.json`, plus `.claude/settings.local.json`, which is
  not committed).

**2026-11-15: owner requests after deploying**

- Last move is stored in the engine (`last_move`), not per browser, so every
  player of an online game sees the same highlight. Orange was chosen because
  indigo (current player, picked move) and gold (bonuses) were taken.
- School bonus rule changed as the owner decided: paying from the balance no
  longer cancels the row bonus. The old engine tests that expected an `X` in
  the bonus cell were updated.
- 2-5 players: the engine already supported it; rooms got a `capacity` and
  `start_now`. Only 5-player games get the 4:8 layout, because 3 and 4 players
  fit the usual 5:7 one.
- While checking layouts, found that the dice overflowed the play card at
  about 1024px wide (also in the previous release). Fixed by sizing dice to
  the card with CSS container units.

**2026-11-15: modern UI** (owner asked for something "more user-friendly, more
modern, not like a game from the 80s")

- Replaced the sidebar radio buttons with a home screen ("Same device" and
  "Online" cards).
- Two-column game screen, so the dice and the scoreboard are both visible
  without scrolling; the columns stack on phones.
- Dice are buttons drawn as real dice (SVG through CSS) instead of emoji
  buttons above PIL images; Pillow was dropped from the requirements.
- Moves: replaced the radio buttons, button grid and "CONFIRM" button with a
  Score / Cross out switch, options that show their score, and a confirm
  button that states the result. Options come from `moves.py`, which runs the
  real engine on a copy, so only legal moves are offered. The old filter
  offered School rows the engine then rejected.
- Light theme with an indigo accent in `config.toml`; Streamlit's own
  header and toolbar are hidden. Streamlit's default font is kept, so nothing
  is loaded from external font services.
- Streamlit minimum raised to 1.48 (horizontal containers).
- Fixes made after reviewing it, before merging: stacked cards on phones are
  16px apart (were 64px); the invite link wraps; the waiting room has a
  visible Cancel button; the rules table is smaller on phones; notifications
  appear at the bottom of the screen; the game creator is told
  "<friend> joined. Your turn!".

**2026-11-14/15: live two-player mode**

- Looked at https://github.com/alexeylavrov/abaka_cc (FastAPI WebSocket
  backend + React frontend, 2-6 players, different rule details). Did not port
  it, because it is a full rewrite in another stack. Took its core idea
  instead: the server owns the game; clients send actions and draw what the
  server has.
- Why the previous online mode (Firebase / "mock" client in `abaka/online.py`)
  did not work live: the turn phase was stored separately in each browser, so
  the waiting player never saw the opponent's dice; a `dice` property on
  `OnlineGameEngine` hid the synced value; the guest was always seat 1 with no
  join step; a refresh lost the seat; and Firebase mode made both players
  paste API keys.
- Chose shared rooms inside the app's process over Firebase or a separate
  server: no credentials, no extra service, and it works on Streamlit
  Community Cloud and on a home network. Cost: games live in memory, so all
  players must use the same running app, and games are lost on restart.
- Chose polling with a 1-second fragment over WebSockets: Streamlit offers app
  code no way to push to the browser. Measured delay in a real browser was
  under a second.
- Removed `abaka/online.py` and the Firebase/mock modes (still in git
  history).
- Rejoining is by clicking your name, with no password. Fine between friends,
  but anyone holding the invite link could take a seat.
- A player must roll before scoring or crossing out; the room enforces this
  too.
