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
| `abaka/rooms.py` | Every game: `RoomStore` (online and same-device rooms, saved to disk) and `RoomEngine` (engine-shaped proxy). No Streamlit imports |
| `abaka/saving.py` | `GameEngine` <-> plain JSON data (`engine_to_data`, `engine_from_data`) for saved games |
| `abaka_ui.py` | Streamlit entry point and screens: home, invite, waiting room; online polling |
| `code_version.py` | Called first on every run: reloads `abaka`/`ui_components` if their files changed since they were loaded |
| `ui_components/main_ui.py` | Game screen for both modes: top bar and menu, play panel, scoreboard, results |
| `ui_components/moves.py` | Possible moves with exact score previews (tries each on a copy of the engine). No Streamlit |
| `ui_components/dice.py`, `move_selection.py`, `scoreboard.py`, `rules.py` | Dice, move picker, score table, rules text |
| `ui_components/style.py`, `.streamlit/config.toml` | CSS and dice SVGs; theme colours |
| `ui_components/i18n.py` | Interface text in English and Russian: `t("...")`, plurals, error messages. No Streamlit |
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
- Streamlit re-reads `abaka_ui.py` on every run, but imported modules stay
  loaded, and its file watcher unloads them only while a browser session is
  open. So `abaka_ui` first calls `code_version.load_current()`. It hashes the
  `.py` files of `abaka/` and `ui_components/` and, if they differ from the
  loaded code (`abaka.code_fingerprint`), drops those modules so they are
  imported again from disk. Tests that patch modules before running the app
  call `code_version.mark_current()` first.
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
- Same-device games are rooms too (`store.create_local`, `room.local`): every
  seat belongs to one token, the turn check is skipped, and nobody can join.
  They get a code and `?room=CODE` like online games. Opening that link (a
  reload, a dropped session, another device) or typing the code on the home
  page continues the game at once (`store.resume_local`, no seat to pick).
- Saving: the app's store (`RoomStore(save_dir=...)`) writes each room to
  `<save_dir>/<CODE>.json` after every change (atomic replace) and loads all
  saved rooms when it is created. That happens at startup and after every
  code update, so updates and restarts no longer end games. `save_dir` is
  `$ABAKA_SAVE_DIR` (empty: no saving; tests use this) or `~/.abaka/games`
  (or a temp folder). A failed write is printed and play goes on.
- Rooms nobody touched for 7 days are dropped (from disk too) the next time
  a room is created.
- `.streamlit/config.toml` keeps a disconnected session for 6 hours
  (`server.disconnectedSessionTTL = 21600`, Streamlit's default is 2
  minutes), so a phone that was locked for a while comes back to the same
  page.
- Leaving the waiting room (`store.leave`, before the game starts) frees the
  seat. Later players move up one seat, so if the creator leaves, the next
  player becomes the creator and can press "Start now"; an empty room is
  closed. The others see "<name> left." (`_announce_departures`). Once the
  game has started, leaving keeps the seat so the player can rejoin.

### UI conventions

- `abaka_ui.main()` picks the screen: seated in a room -> the game (online or
  same device, `_render_local_game`) or the waiting room; `?room=` in the URL
  -> the invite page (which continues a same-device game at once); otherwise
  -> home. There is no sidebar.
- Languages: English and Russian. Code is written with English text wrapped in
  `t("...")`; `i18n.RU` holds the Russian versions, with the same
  `{placeholders}`.
  - The language is set at the start of every run (`set_language`, per
    thread): the EN/RU switch (`render_language_switch`, at the top of the home
    and invite pages and in the game menu) keeps it in `ss.lang` and `?lang=`;
    otherwise it follows the browser (`st.context.locale`, Russian -> ru).
  - Each player of an online game sees their own language. Player names
    typed in are kept as typed; blank names get "Player 2" / "Игрок 2" in
    the language of the browser that created the seat.
  - Errors from the engine and rooms are shown through `i18n.error()`.
  - Widget values stay English (the Score / Cross out switch, keys); only
    their labels are translated.
- Home: "Continue a game" lists the unfinished games this browser played
  (`ss.my_games`). "Open game" takes a code for both joining and continuing.
  Leaving a same-device game shows "Game CODE is saved..." (`ss.lobby_info`).
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
- Bonus cells: "✕" when the player gave the bonus up themselves, "–" when
  the bonus went to or was decided by another player.
  - Row bonus: a School row paid from the balance, or a crossed-out
    combination cell (`engine.row_bonus_blocked`).
  - Column bonus: a crossed-out combination cell in that column.
  - When the picked move gives a bonus up, the confirm button says so
    (`Move.bonus_lost`, `Move.column_bonus_lost`). For example: ", lose the
    row bonus)" for a School payment, or "Cross out Abaka (lose the row and
    column bonuses)". The scoreboard previews those bonus cells as crossed
    out.

## Rules for changes

- Engine code must keep working on Python 3.8 (no `X | None` at runtime).
- Every new text shown to players goes through `t("...")` and gets a Russian
  version in `ui_components/i18n.py`; `tests/test_i18n.py` fails otherwise.
- Player names reach other players' browsers. `scoreboard.py` and other
  modules build raw HTML, so names must go through `html.escape`.
- Every new online action goes through `RoomStore._act`, so it gets the turn
  check, the lock and the version bump.
- The game rules are the owner's own. Do not change them, or copy rule details
  from the upstream `abaka_cc` repo, unless the owner asks.

## Backlog

Nothing open. Requests 1-4 came from the owner after deploying (2026-11-15)
and were merged in PR #13; request 5 (2026-11-16) was merged in PR #18 and
went live with PR #19; request 6 (2026-11-16, reversing request 3) was
merged in PR #20; requests 7 and 8 (2026-11-16) were merged in PR #21;
request 9 (2026-11-16) was merged in PR #22; request 10 (2026-11-16) is in
PR #24.

1. **Highlight the last move.** Done. The cell written by the most recent
   move, by any player, is outlined in orange, with a "Last move: ..." line
   under the scoreboard. It returns to normal when the next move is made.
   > "mark the last move with other color. when there's a new last move turn it to normal color"

2. **"Reroll all" button.** Done. "Reroll all" sits next to the button that
   rerolls only the picked dice ("Reroll picked" / "Reroll 2 dice").
   > "add button "reroll all""

3. **School row bonus after paying from the balance.** Reversed on
   2026-11-16 by request 6: paying crosses out the row bonus again. Before, writing a
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

6. **Paying from the balance in School crosses out the row bonus.** Done.
   This reverses request 3 and restores the rule the code had before PR #13.
   - Any payment ("minus", fewer than three dice of the number, including
     endgame writes below zero) crosses out that row's bonus cell for the
     player at once: `school.py` puts X in the cell and sets
     `engine.row_bonus_blocked[(player, row)]`.
   - Exactly three or extra dice keep the bonus.
   - If the player who paid is the first to complete the row, nobody gets
     that row's bonus, the same as a crossed-out combination ("the first
     player to complete a row decides its bonus").
   - The confirm button warns ("…, lose the row bonus"), the scoreboard
     previews the crossed-out bonus, and the cell shows "✕".
   > "if you use "minus" for school - you loosing the chance to get a bonus for that line - so you need to cross the bonus section right away"

7. **A game disappears after a short pause (from a tester).** Fixed in PR #21:
   games are saved and come back from their link or code (Decision log).
   > "Комментарий от живого тестировщика: При небольшой паузе игра тоже пропадает, возвращаешься на исходную страницу"

8. **Save the game so it is not lost if you stop midway.** Done in PR #21:
   every game is saved after every move. "Continue a game" on the home page,
   the game's link, or its code bring it back (also after a code update or a
   restart; see Known issues for Cloud reboots).
   > "возможность сохранять игру чтобы она не пропадала если остановился посередине"

9. **Russian language.** Done in PR #22.
   - Every screen, the rules, the move texts, the scoreboard, toasts and
     error messages are in Russian.
   - A Russian browser starts in Russian; EN/RU switches sit on the home and
     invite pages and in the game menu, and the choice survives a reload.
   - Row names: Пара, Две пары, Тройка, Малый стрит, Большой стрит, Фулл-хаус,
     Каре, Абака, Сумма, Школа 1-6. The owner may want other terms (the
     original code's labels were D, DD, T, LS, BS, F, C, A, Σ).
   > "хочу добавить русский язык"

10. **Crossing out a combination gives up the column bonus, like the row
    bonus.** The engine already did this; now it shows. Done in PR #24:
    - the column bonus cell shows "✕" at once (it showed "–");
    - the confirm button warns ("Cross out Abaka (lose the row and column
      bonuses)");
    - the preview crosses out both bonus cells;
    - the rules say both bonus cells are crossed out at once.
    > "Зачеркивание какой-то комбинации (не из школы) точно так же лишает бонуса по столбцу"

## Status (2026-11-16)

- **Crossed-out combinations show the lost column bonus (owner request 10):**
  PR #24.
- **Russian language (owner request 9):** merged in PR #22, live within
  seconds. Checked on the live app in headless Chromium (desktop with
  `?lang=ru`, phone with a Russian browser language): home, starting throw,
  a turn, the board and the rules.
- **Saved games (owner requests 7 and 8):** merged in PR #21. Every game is saved after
  every move and comes back after a reload, a dropped session, a code update
  or a restart. On the live app, test game ULQZP came back from its link
  after a reload, and was still there unchanged after the PR #22 update. That
  means the new code loaded it from disk, so saving works on Streamlit Cloud
  across updates.
- **Live two-player online mode:** merged in PR #11.
- **Modern UI:** merged in PR #12 (home screen, tappable dice, move previews,
  new scoreboard, phone layout).
- **Deployed:** the owner deployed `main` on Streamlit Community Cloud and
  reports that it works.
- **Owner requests (last move, Reroll all, School bonus, 2-5 players):**
  merged in PR #13.
- **School minus crosses the row bonus (owner request 6):** merged in
  PR #20. Streamlit Cloud had not picked it up 40 minutes after the merge
  (earlier merges were live within a minute); it went live with PR #21.
- **Starting throw (owner request 5):** merged in PR #18. On the live app
  it crashed "Start game" until PR #19, which reloads modules left stale by
  the update (Decision log).
- **Tests:** 92 pass: 6 language tests (`test_i18n.py`: every t() text has a
  Russian version with the same placeholders, room errors, plurals, per-thread
  language), 10 saving tests (`test_saving.py`), 23 room tests (`test_rooms.py`: a full two-player game,
  rematch, 3-5 player rooms, starting early, leaving the waiting room),
  13 move-preview tests (`test_moves.py`), 6 tests for the owner's requests
  (`test_owner_requests.py`), 6 starting-throw tests
  (`test_starting_throw.py`: lowest starts, ties, joker at face value,
  rooms, rematch), 4 module-reload tests (`test_code_version.py`), 11 older
  rule tests, 3 scoreboard tests (`test_scoreboard.py`: crossed bonus cells
  and their preview) and 3 app tests (`test_ui_notices.py`,
  `test_ui_store.py`, `test_ui_saved_games.py`). The app tests run the real app script with
  Streamlit's AppTest. They and the scoreboard tests are skipped where
  Streamlit is not installed, such as the base Python 3.8.
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
- Saved games live on the server's disk. On Streamlit Community Cloud that
  survives code updates (checked on the live app) and restarts of the app
  process, but probably not a
  reboot from the Cloud dashboard or the app going to sleep: the container
  is rebuilt. Keeping games through those needs an external database
  (credentials in Streamlit secrets), which the owner would have to set up.
- Online players coming back in a new session (a reload, or a session
  dropped after more than 6 hours) land on the invite page and tap their
  name. The seat token is kept out of the URL, so a copied address bar
  never hands over a seat.
- Streamlit Cloud sometimes does not pick up a merge for a long time (PR #20,
  2026-11-16). "Reboot app" in the Cloud dashboard pulls the latest `main`.

### Ideas not started

- Dark theme (the scoreboard CSS colours would need to follow the theme).
- Show the opponent which dice the active player has picked.
- Save games in an external database so they also survive Cloud reboots.

## Decision log

**2026-11-16: crossing out shows the lost column bonus (owner request 10)**

- The rule was already in the engine (`record_cross` puts X in the row's
  bonus cell and in the column's bonus at once; a column with a crossed-out
  combination never pays). The owner's message matched the School "minus"
  change, so the display was brought in line instead:
  - "✕" in the column bonus cell;
  - a warning on the confirm button;
  - a preview of both bonus cells.
- The column bonus "✕" is derived from the table (a crossed-out combination
  cell in that column), so it needs no new engine state, and old saved
  games show it too.
- Tests: the engine rule (column bonus crossed at once, never paid, School
  payments leave it alone), the button texts, the board cells and the
  preview. The simulation checks every cross-out; the AppTest scenarios
  check every previewed cross-out.

**2026-11-16: Russian (owner request 9)**

- English text stays in the code and is wrapped in `t()`, rather than moved
  to message keys, so the code still reads naturally and a missing
  translation falls back to English. A test scans the code for `t()` texts,
  so none is forgotten.
- The language is per browser, not per game: each player of an online game
  sees their own. It is kept per thread, because Streamlit runs every
  session's script in its own thread, and `moves.py` (no Streamlit) needs it
  too.
- Russian wording avoids verbs that change with gender ("Последний ход —
  Аня: 23 в «Сумма»", "{name} в игре"), because names don't tell the
  gender.
- On phones the game's top bar shows only the logo (no "Abaka" word), so the
  longer "Одно устройство · CODE" and the Menu fit on one line.
- Checked: unit tests; the AppTest scenarios (all English ones, plus a game
  in Russian with blank names becoming Игрок 1/2 and the menu switch back to
  English); headless Chromium in Russian on desktop (?lang=ru) and on a
  phone (Russian browser language): home, starting throw, a turn, the board
  and the rules, with no sideways scrolling and the dice on one row.

**2026-11-16: saved games (owner requests 7 and 8)**

- Request 7 (a tester): "after a short pause the game disappears, you are
  back on the start page". Causes found:
  - A same-device game lived only in the browser session, which Streamlit
    drops 2 minutes after the connection goes (a locked phone), and which a
    reload replaces.
  - Every code update ended all online games (stores were kept per code
    version, in memory only).
  - Reproduced with headless Chromium: on `main`, a reload or a server
    restart sends a phone back to the start page with the game gone.
- Request 8: save the game so it is not lost when stopped midway.
- Decisions:
  - Same-device games became rooms, so one mechanism (codes, links, saving)
    serves both modes.
  - Games are autosaved after every move; there is no Save button to forget.
  - One JSON file per room, so a write stays small and a bad file affects
    one game.
  - JSON instead of pickle, so any later version of the code can read old
    saves.
  - Idle games are kept 7 days instead of 12 hours.
  - The session lifetime after a disconnect is 6 hours.
- The online seat token stays out of the URL (see Known issues); rejoining
  is still one tap on your name.
- Checked: unit tests (engine round trips at every stage, a second store
  carrying on every game, bad and old files skipped); AppTest (a game left
  midway comes back from the home page, its link in a new session, its code
  and a restart); and headless Chromium against a real server. A phone kept
  its same-device game through a reload and a server restart; on `main` it
  lost it. An online game continued after a restart, each player tapping
  their name once.

**2026-11-16: School minus crosses the row bonus again (owner request 6)**

- The owner reversed the 2026-11-15 decision (request 3). I restored the
  pre-PR #13 behaviour: the cell is crossed at the moment of payment, and a
  payer who completes the row first decides "no bonus" for everyone. The only
  difference is that the record lives in the existing `row_bonus_blocked`
  instead of the removed `school_minus_used`.
- Added on top, so the cost is visible before confirming: the "lose the row
  bonus" wording on the confirm button, the bonus-cell preview, and "✕" for
  bonuses a player gave up (also after crossing out a combination).
- Checked with unit tests and the game simulation: after every payment the
  bonus cell was X at once, and at game end no player who paid in a row had
  its bonus. Also checked with AppTest screen scenarios (each School payment
  picked showed the preview, then the X) and in a browser at desktop and
  phone widths.

**2026-11-16: stale modules on the live app after PR #18**

- After PR #18 went live, "Start game" failed there with a TypeError. The new
  `abaka_ui.py` called `GameEngine(names, starting_throw=True)` on the old
  `GameEngine`, and the rules text was old too.
- Cause: Streamlit re-reads the main script on every run, but imported
  modules stay in `sys.modules`. Its file watcher, which unloads changed
  modules, belongs to a browser session and runs only while one is open.
  Cloud pulled the commit while nobody had the app open, so nothing unloaded
  the old modules. Reproduced locally (a file changed on disk with no
  session open, server started with `--server.disconnectedSessionTTL 1`): on
  `main` the next visitor got the old code, and with the fix the new code.
- Fix: `code_version.load_current()` runs first on every run and reloads
  `abaka`/`ui_components` when their files changed (hash of the `.py`
  files). Hashing the contents rather than file times avoids depending on
  how Cloud writes the files.
- Merging PR #19 also cleared the stale modules on the live app: the main
  script changed, and the reload check found modules without a fingerprint.

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
