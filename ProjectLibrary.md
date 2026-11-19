# Project Library

Repository guidance and the project's working log for owner requests, current
status, and past decisions. Update the Backlog, Status and Decision log
whenever work is done.

Two coding agents work on this project, Codex and Claude Code. AGENTS.md says
how they share it (branches, pull requests, this log); both read it, and both
keep this file. Claude Code loads the two through CLAUDE.md.

- **Repository:** https://github.com/pinoden/Abaka (git remote `origin`). Finished
  work goes there. `main` is protected: every change goes in through a pull
  request.
- **Live app:** https://mipt-abaka.streamlit.app/, deployed by the owner on
  Streamlit Community Cloud from `main` (main file `abaka_ui.py`). Merging into
  `main` updates it automatically, within a few minutes. Cloud reloads the code
  in the running server instead of restarting it (see Online play).

## Commands

```bash
pip install -r requirements.txt                       # streamlit 1.67.0 (pinned; needs Python 3.11+), psycopg 3.3.6
ABAKA_TEST_DATABASE_URL=postgresql://... python -m unittest tests.test_postgres   # database tests (else skipped)
streamlit run abaka_ui.py                             # the app (port 8501, all interfaces)
python -m abaka                                       # CLI version
python -m unittest discover -s tests -p "test_*.py"   # all tests
python -m unittest tests.test_rooms -v                # one test module
python tools/simulate.py 200 40                       # random complete games with rule checks (2-3 min)
python tools/loadtest.py --clients 100 --interval 1   # simulated pages polling every second: CPU, latency
python tools/loadtest.py --clients 100 --interval 1 --set runner.postScriptGC=true   # compare a Streamlit option
python tools/pr.py status                             # open pull requests and their branches
python tools/pr.py ship --title "..." --body-file notes.md   # push, open the PR, wait for CI, merge
```

### Notes for this machine

- The base `python3` is Anaconda 3.8 without Streamlit. The conda env
  `~/opt/anaconda3/envs/Python39` has Streamlit 1.48:
  `~/opt/anaconda3/envs/Python39/bin/python -m streamlit run abaka_ui.py`.
  - That is older than the pinned 1.67, which needs Python 3.11+, and no
    newer Python is installed here.
- Neon: the repository is linked to the owner's Neon project "Abaka"
  (`restless-haze-52228918`, branch `production`, us-east-1) with the Neon
  CLI (`neon init`, `neon deploy`). `neon.ts` declares Postgres only;
  `package.json` holds its two config packages (no app code is JavaScript,
  so there is no `npm run build`). `neon deploy` writes `DATABASE_URL`
  (pooled, for the app) and `DATABASE_URL_UNPOOLED` to `.env.local`, which
  is gitignored, like `.neon` and `node_modules/`. The app does not read
  `.env.local` or `DATABASE_URL`: it is the production database, so only
  `ABAKA_DATABASE_URL` (set on purpose) reaches it. To run against it
  locally, pass that variable from `.env.local` without printing it.
- No Postgres is installed here. For the database tests, a throwaway one:
  `pip install pgserver "psycopg[binary]"` in a scratch venv (psycopg 3.2 on
  Python 3.9), then its bundled `initdb -D <dir> -U abaka --auth=trust` and
  `pg_ctl -D <dir> -o "-p 55432 -k '' -c listen_addresses=127.0.0.1" -w start`.
  `-k ''` is needed because the scratch path is too long for a Unix socket.
  - Local runs check 1.48; CI (`.github/workflows/tests.yml`) checks 1.67 on
    Python 3.13, as on Cloud. The app works on both.
- Streamlit 1.48 runs on Tornado. 1.67 runs on Starlette and uvicorn, with
  the `websockets` package. `tools/loadtest.py` uses whichever websocket
  client is installed.
- `gh` is not installed. `tools/pr.py` opens, checks and merges pull
  requests through the GitHub REST API, with the credential git already
  stores in the macOS keychain (`git credential fill`). Pushes and pull
  requests therefore come from the owner's GitHub account.
- Headless Chromium for browser checks is cached in
  `~/Library/Caches/ms-playwright`. Use it through `playwright-core` installed
  in a scratch folder, never in the repo.
- Streamlit Cloud runs Python 3.13 and the pinned Streamlit 1.67.0. The
  first message of a page's session (`NewSession.initialize.environment_info`)
  names both; read it with headless Chromium to see what Cloud runs.
  - There, segmented controls and pills are `role="radio"` buttons, so
    browser checks should find them by text, not by role.
  - On Cloud the app runs inside an iframe (`iframe[title="streamlitApp"]`,
    path `/~/+/`).

## Architecture

Abaka is a dice game: 4 white dice + 1 joker; each player has 15 rows x 3
cells (School 1-6 and nine combinations) plus a bonus cell per row.
Python + Streamlit.

| Path | Purpose |
|---|---|
| `abaka/engine.py` | `GameEngine`: turn flow (`start_turn`, `reroll`, `record_score`, `record_cross`) |
| `abaka/player.py` | `PlayerState`: score table, school balance, final score |
| `abaka/scoring.py`, `school.py`, `bonus.py` | Combination scoring, school balance, row and column bonuses |
| `abaka/rooms.py` | Every game: `RoomStore` (online and same-device rooms, saved to disk, stats line) and `RoomEngine` (engine-shaped proxy). No Streamlit imports |
| `abaka/saving.py` | `GameEngine` <-> plain JSON data (`engine_to_data`, `engine_from_data`) for saved games |
| `abaka/repository.py` | Where rooms are kept between runs: the repository methods; `FileRepository` (one JSON file per room), `PostgresRepository` (one row per room; Neon on the live app) and `MirroredRepository` (both). No Streamlit |
| `abaka_ui.py` | Streamlit entry point and screens: home, invite, waiting room; online polling |
| `code_version.py` | Called first on every run: reloads `abaka`/`ui_components` if their files changed since they were loaded |
| `ui_components/main_ui.py` | Game screen for both modes: top bar and menu, play panel, scoreboard, results |
| `ui_components/moves.py` | Possible moves with exact score previews (tries each on a copy of the engine). No Streamlit |
| `ui_components/actions.py` | `on_click` callbacks of the game buttons: make the move, keep a refusal to show once |
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
  returns the single `RoomStore` for that process, kept in a registry
  (`_store_registry`, an `st.cache_resource` that survives code updates; do not
  edit that function, its source is its cache key).
  - When a commit is applied, Streamlit reloads the app's modules, but cached
    objects survive.
  - The first run of the new code retires the old store (`retire()`: its
    rooms are freed, writes under way finish) and makes a new one, which loads
    the saved games from disk. So updates no longer end games.
  - Pages still running the old code (their once-a-second poll) get the new
    store too (`_running_current_code`), so nobody keeps polling a store that
    no longer changes, and old stores never pile up.
  - Do not go back to a plain cached `RoomStore()`: an old store reached the
    new code and broke the live app (Decision log, 2026-11-16).
- Streamlit re-reads `abaka_ui.py` on every run, but imported modules stay
  loaded, and its file watcher unloads them only while a browser session is
  open. So `abaka_ui` first calls `code_version.load_current()`. It hashes the
  `.py` files of `abaka/` and `ui_components/` and, if they differ from the
  loaded code (`abaka.code_fingerprint`), drops those modules so they are
  imported again from disk. Tests that patch modules before running the app
  call `code_version.mark_current()` first.
  - The contents decide, but the files are read again only when a size or a
    file time changed, or a minute has passed (`current_fingerprint`): 0.5
    instead of 2.5 ms per full run.
- A room has a 5-character code, a `capacity` of 2 to 5 players chosen by the
  creator (`rooms.MIN_PLAYERS`..`MAX_PLAYERS`), seats in join order (each a
  name plus a secret token; seat 0 is the creator) and one `GameEngine`,
  created when the last seat is taken or when the creator calls
  `store.start_now` with at least two players seated. Names are made distinct
  ("Ann (2)").
- Browsers never hold game state. Each page render takes `store.view(code)`
  and wraps it in `RoomEngine`, so the UI components work the same as in a
  local game. `RoomEngine` forwards `throw_for_start`, `start_turn`, `reroll`,
  `record_score` and `record_cross` to the store.
  - The app gives it `get_store` (a function) rather than the store: a
    button's move runs when the next click arrives, and a code update in
    between replaces the store.
  - It also passes the room version the page was drawn from. If the room has
    changed since (a double tap, a page not redrawn yet), the store refuses
    the move with `OutdatedPage`, and the app only redraws the page.
- Engines are copy-on-write. `RoomStore._act` holds the lock, checks that the
  token owns the seat whose turn it is, applies the move to a clone
  (`GameEngine.clone()`, about 15 times cheaper than `deepcopy`) and installs
  the clone only if the move succeeded. An installed engine is never changed
  again, so `view()` hands it out without copying: the UI must never change
  it (`tests/test_ui_store.py` checks every phase). Every change bumps
  `room.version`.
- Live updates: `_watch_room` draws a polling fragment
  (`st.fragment(run_every=...)`) that compares `store.version(code)` with the
  version the page was drawn from, and calls `st.rerun()` when they differ.
  - It checks every second while someone else can change the room (players
    joining, another player's turn), every 3 s on the player's own turn or
    after the game, and every 10 s in a same-device game (`POLL_FAST`,
    `POLL_CALM`, `POLL_IDLE`).
  - Streamlit fixes a fragment's interval where the fragment is defined, so
    there is one fragment function per interval.
- The URL carries only `?room=CODE`, so it is safe to share. The seat token
  stays in `st.session_state`. After a refresh, the player opens the link and
  clicks their name; `store.reclaim` issues a new token and the old tab loses
  control.
- Same-device games are rooms too (`store.create_local`, `room.local`): every
  seat belongs to one token, the turn check is skipped, and nobody can join.
  They get a code and `?room=CODE` like online games. Opening that link (a
  reload, a dropped session, another device) or typing the code on the home
  page continues the game at once (`store.resume_local`, no seat to pick).
- Saving: the store keeps rooms through a repository (`abaka/repository.py`,
  chosen by `abaka_ui._repository()`).
  - Without a database, the app uses `FileRepository`, which writes each room
    to `<save_dir>/<CODE>.json` after every change.
  - With a database URL (`ABAKA_DATABASE_URL`: the environment variable, or
    the Streamlit secret `ABAKA_DATABASE_URL` or `DATABASE_URL`, Neon's name;
    never a `DATABASE_URL` environment variable), it uses
    `MirroredRepository`: every save goes to Postgres
    (`PostgresRepository`, table `abaka_rooms`) and to the files; a load takes
    whichever has the newer version. When the store starts, a background
    thread copies files the database lacks into it (`import_files`).
  - The repository methods are `claim`, `load`, `save(code, version, data)`,
    `delete`, `prune`, `quarantine` and `wait`. `RoomStore` uses nothing
    else (`RoomStore(repository=...)`; `tests/test_repository.py` runs a
    store on an in-memory one, `tests/test_postgres.py` on Postgres).
  - Postgres: one row per room (`code`, `version`, `data` jsonb, `deleted`,
    `saved_at`). A save is one statement that writes only if the stored
    version is older; a deleted room is a row without data until its code is
    claimed again; unusable data moves to `abaka_rooms_quarantine`. The
    tables are created on first use. One connection, made again when it drops
    (Neon closes it when it suspends); no prepared statements, for the
    pooler. An unreachable database never stops a game: saves are logged as
    failed, other calls log a warning, and the files still hold every game.
  - The foot of the home page says where games are saved
    (`RoomStore.storage()`, `abaka_ui._storage_note`): in the database, on
    this server only, or on this server only because the database refused
    the password, cannot be reached, or is not connected yet. It names no
    address, so anyone can check the live app from a browser.
  - Loads happen under the store's lock, so with a database the first look
    at a game not in memory waits for a round trip (longer if Neon has to
    wake up).
  - The data is taken under the lock (`_snapshot`) and saved after it
    (`_write`), so storage never holds up other games.
  - Each file write uses its own temp file and an atomic replace.
  - An older state never replaces a newer one (the repository refuses a
    version that is not newer), and a closed room is never written back.
  - Loading happens at startup and after every code update, so updates and
    restarts no longer end games.
  - `save_dir` is `$ABAKA_SAVE_DIR` (empty: no saving; tests use this) or
    `~/.abaka/games` (or a temp folder). A failed write is logged as a
    warning and play goes on.
- Room lifecycle, with a save folder (`RoomStore._sweep`, at most once a minute
  when a room is created):
  - a room no page has looked at for 30 minutes (a finished game: 10) leaves
    memory, and its file stays;
  - opening it again (`_room`, used by every lookup) loads it from disk;
  - at most 2,000 rooms stay in memory; beyond that the rooms seen least
    recently leave first, but never one seen in the last minute;
  - rooms not changed for 7 days are deleted, files too: at start, when
    opened, and in an hourly sweep by file time;
  - unreadable files move to `quarantine/`;
  - nothing is loaded at start;
  - game codes are checked (`is_valid_code`) before they become file names;
  - a new code is never one that is saved on disk.
  Without a save folder (tests), rooms stay in memory and creation is
  refused past the cap. One browser may start 10 games in 10 minutes
  (`abaka_ui.GAMES_PER_SESSION`, `rooms.within_limit`). All limits are
  constants at the top of `abaka/rooms.py` and `abaka_ui.py`.
- Monitoring: the game logs to the `abaka` logger, and the app sends it to
  stderr (`abaka_ui._log_to_stderr`; on Cloud: Manage app, then the logs).
  - The app's store writes a stats line once a minute while pages poll
    (`RoomStore(report_every=60)`). It gives rooms in memory (being played,
    on one device), polls, page views, moves, new games, rooms loaded from
    disk and leaving memory, saves (count, average and slowest time,
    failures), full garbage collections, and memory (resident on Linux, the
    peak elsewhere).
  - Without `report_every` (tests, tools) there is no stats line. Failed
    saves and unreadable files are warnings.
- `.streamlit/config.toml` keeps a disconnected session for 6 hours
  (`server.disconnectedSessionTTL = 21600`, Streamlit's default is 2
  minutes), so a phone that was locked for a while comes back to the same
  page. Streamlit keeps at most 128 disconnected sessions, though
  (`MemorySessionStorage(maxsize=128)`), so with many players older ones are
  dropped sooner. The game itself is saved either way; the player comes back
  by its link or code.
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
  (`ss.my_games`): it remembers the newest 10 (`MY_GAMES_KEPT`) and shows up
  to 4 (`MY_GAMES_SHOWN`). It opens no game beyond the 4 it shows, since each
  can be a read from disk, and it forgets games that no longer exist. "Open game" takes a code for both joining and continuing.
  Leaving a same-device game shows "Game CODE is saved..." (`ss.lobby_info`).
- Widgets are styled through the `st-key-<key>` class Streamlit adds to keyed
  elements. Dice are buttons keyed `die-0` to `die-4`; containers keyed
  `card-*` get the card look. Per-render CSS (die faces, picked dice, roll
  animation) is injected with `st.html("<style>...")`.
- Move-picker widget keys include a turn signature (player, rolls left, dice),
  so a pick never carries over to a reroll or a new turn.
- Game buttons (Throw, Roll dice, the two Reroll buttons, the confirm button)
  make their move in an `on_click` callback (`ui_components/actions.py`), so a
  move costs one script run instead of two (the second came from
  `st.rerun()`). A refused move is kept in the session and shown once, at the
  top of the play panel.
  - Streamlit tells buttons apart by key and label. A button that kept both
    after its move would hand a fast second tap the next page's move, so
    "Reroll all" has the rerolls left in its key (`reroll-all-2`).
- Dice size: at most `--ab-die` (60px) and shrinks so all five fit the play
  card. The card is a CSS size container and the size is
  `min(--ab-die, (100cqw - 4 gaps) / 5)`, so it adapts to any layout.
- Layout: play panel and scoreboard split 5:7; with 5 players 4:8 so the
  scoreboard fits on desktop. With 3+ players the table uses the compact
  `ab-many` style; on phones it scrolls sideways inside its card with the row
  names pinned. Between 641px and 1000px (3 players) or 1180px (4-5 players)
  the play card stacks above the scoreboard (container keys `game-three` and
  `game-many`, CSS in `style.py`), so the board fits and the dice keep 60px.
- Online notifications: "<friend> joined" / "Everyone's here." when this
  browser was on the waiting screen (`was_waiting`); "Your turn!" when
  `was_my_turn` changes from False to True ("Your throw!" during the
  starting throw).
- Starting throw screen: `main_ui._render_starting_throw` shows "Who goes
  first?", each player's latest throw (small dice + total) and the
  `start-throw` button. On the same device the button names the player
  ("Throw for Ann"); online only the thrower's screen has it ("Throw the
  dice"). Until the first move, `_starter_summary` shows "Ann threw the lowest
  (9) and goes first." and every starting throw, so the last thrower's total
  stays visible after the decision (Backlog item 16).
- Bonus cells show "✕" when the player gives up the bonus or another player
  closes a shared bonus by completing its row or column.
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
- Player names reach other players' browsers. In raw HTML (`st.html`,
  `scoreboard.py`) names go through `html.escape`. In places Streamlit renders
  as Markdown (captions, toasts, button labels) they go through `i18n.md()`:
  backslash escapes, plus a zero-width space after ":", "." and "@" because
  captions and toasts turn bare addresses into links even when escaped.
  `rooms.clean_name` also removes control and invisible format characters.
- Every new online action goes through `RoomStore._act`, so it gets the turn
  check, the lock and the version bump.
- The game rules are the owner's own. Do not change them, or copy rule details
  from the upstream `abaka_cc` repo, unless the owner asks.

## Backlog

Item 11 (the scale-up plan) is in progress. Items 12–15 (2026-11-17) were
merged in PR #37. Item 16 (2026-11-18) is in PR #39. Requests 1-4 came from the
owner after deploying (2026-11-15) and were merged in PR #13; request 5
(2026-11-16) was merged in PR #18 and went live with PR #19; request 6
(2026-11-16, reversing request 3) was merged in PR #20; requests 7 and 8
(2026-11-16) were merged in PR #21; request 9 (2026-11-16) was merged in
PR #22; request 10 (2026-11-16) was merged in PR #24.

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

11. **Scale-up plan: many games in parallel.** In progress.
    - Source: the architecture review of 2026-11-16 (`docs/ARCHITECTURE_REVIEW.md`,
      with measurements and file:line).
    - Work goes stage by stage, one PR per step. Tick a step here when its
      PR is merged, with the PR number.
    - Effort scale: S is up to 2 days, M is 1-2 weeks, L is 3-6 weeks.
    > "я хочу чтобы ты заустил агента в роли senior architect и перебрал весь проект целиком с точки зрения оптимальности и качества сборки для потенциально бОльшего проекта с несколькими партиями люде играющих параллельно"
    >
    > "Add this plan into md file and let's keep going"

    **Stage 0: stabilize (S, no new services or accounts)**

    - [x] 0.1 Config: `[runner] postScriptGC = false` (Streamlit's full
      garbage collection after every run, polls included) and
      `[browser] gatherUsageStats = false`. PR #27. Measured with
      `tools/loadtest.py` (200 saved games, M1):
      - 50 browsers: 86% CPU, 34 of 50 polls/s answered, 942 ms median
        before; 18% CPU, all answered, 6 ms after;
      - 100 browsers: 91% CPU, 17 of 100, 3.1 s before; 33% CPU, all
        answered, 10 ms after;
      - CPU per poll went from 25-53 ms to about 3.5 ms.
    - [x] 0.2 Measurement tools in the repo (opt-in, under Commands). PR #27:
      - `tools/loadtest.py`: simulated browsers over websockets; reports
        server CPU, polls served and poll latency;
      - `tools/simulate.py`: random complete games with invariant checks.
    - [x] 0.3 Cheap reads and trial moves. PR #28.
      - `GameEngine.clone()` replaces `deepcopy` in `_act` and
        `score_options`: 15 instead of 210-270 µs; previews 0.30 instead of
        3.5 ms.
      - `view()` hands out the shared copy-on-write engine.
      - A test proves drawing every phase changes nothing.
      - Caching the move list is not needed at 0.3 ms.
    - [x] 0.4 Saving outside the global lock. PR #28. The data is taken
      under the lock and written after it, with a unique temp file per write;
      an older state never replaces a newer file. Measured with 40 rooms
      played at once from threads while 8 threads polled `version()`, with
      saving:
      - 245 → 1,922 moves/s;
      - poll wait p50 98 ms → ~0, p99 624 ms → ~0.
    - [x] 0.5 Retire old stores after a code update. PR #28. A registry keeps
      one current store.
      - The new code retires the old one: its rooms are freed and its writes
        finish first.
      - Old pages poll the new store.
      - Checked on a real server: a game created before a code change on disk
        was still there afterwards, and the page opened before the change saw
        the second player join without being touched.
    - [x] 0.6 Room lifecycle. PR #30.
      - Finished and idle rooms leave memory and are loaded again on
        demand; nothing is loaded at start.
      - Expired files are deleted, unreadable ones quarantined.
      - At most 2,000 rooms in memory; 10 games per browser per 10 minutes.
      - Codes are validated before they become file names (with rooms now
        read on demand, `?room=../...` would otherwise reach outside the
        save folder).
      - Load test with 5,000 saved games: 100 browsers at 33% CPU, 15 ms
        median poll.
    - [x] 0.7 Fewer reruns. PR #31.
      - Polling adapts: every second only while someone else can change the
        room; every 3 s on your own turn or after the game; every 10 s in a
        same-device game.
      - The game buttons make their move in `on_click` callbacks: one script
        run per click instead of two (counted from the websocket messages in
        headless Chromium, on `main` and on the branch).
      - A click from an outdated page (a double tap, a page not redrawn yet)
        makes no move: the store checks the version the page was drawn from.
      - `server.websocketPingInterval = 30`. That is Streamlit's default with
        Tornado 6.5+ (as on Cloud); with an older Tornado it pings every page
        every second.
      - Measured with `tools/loadtest.py`, which now has `--interval` to
        force a poll rate:
        - 100 same-device pages: 29% CPU before, 5% after (pings every 30 s
          in both);
        - 100 idle pages with Tornado 6.4: 8% CPU for the pings, 0% after;
        - an online game asks for 2 polls a second before, 1.33 after with
          2 players (3 players: 3 and 2.33).
    - [x] 0.8 Player names cannot inject Markdown. PR #29.
      - `i18n.md()` is used in the 7 Markdown places that show names.
      - `clean_name` drops control and invisible characters.
      - Checked in a browser: with names `![i](http://e.vil/a)` and
        `[x](http://e.vil)`, no element on any page links or loads from
        e.vil. Escaping alone was not enough: captions and toasts still
        auto-linked the bare URL.
    - [x] 0.9 Build. PR #32.
      - Streamlit pinned to 1.67.0, the version the live app ran (read from
        its session message), on Python 3.13.
      - GitHub Actions (`.github/workflows/tests.yml`), on every pull request
        and on `main`:
        - all tests plus random games with the scoreboard, on Python 3.13
          with the pinned Streamlit;
        - all tests (the Streamlit ones skip) plus random games, on Python 3.8
          in a `python:3.8-slim` container.
      - `tests/test_abaka_engine.py` imports the `abaka` package. 11 of its 15
        tests run; the 4 that expect older rules are skipped, with the reason.
      - The stray `ui_components/requirements.txt` and
        `abaka/ui_components/requirements.txt` are removed.
      - README.md, README_MULTIPLAYER.md, DEPLOYMENT_GUIDE.md and
        ui_components/README.md describe the app as it is now.
    - [x] 0.10 Monitoring and small costs. PR #33.
      - `logging` (the `abaka` logger, to stderr) and a stats line once a
        minute (see Online play, Monitoring). Checked on a local server: one
        line a minute, with the counts of the browser checks it served.
      - "Continue a game" remembers at most 10 games, and opens only the
        games it shows (it used to look at every game the browser ever
        played, loading each from disk, on every view of the home page).
      - The module-reload check reads the files only when their sizes or
        times changed, or once a minute.
      - Load test, 100 pages polling every second, back to back: 27-29% CPU
        on the branch, 30-31% on `main`.

    **Stage 1: harden the single process (M)**

    - [x] A repository interface, with today's files behind it. PR #35.
      - `abaka/repository.py`: `claim`, `load`, `save(code, version, data)`
        (refuses a version that is not newer, and a deleted room), `delete`,
        `prune`, `quarantine`, `wait`.
      - `FileRepository` holds the file code that was in `RoomStore`.
      - A store runs the same on an in-memory repository (tested), which is
        what a database needs.
    - [ ] Seat protection: personal per-seat rejoin links, with the key
      stored hashed. Tap-to-rejoin only when the seat's holder has gone
      quiet. An optional PIN for same-device games. The owner chooses the
      exact scheme.
    - [ ] Presence (who is online), rate limits, and longer game codes for
      new games.
    - [ ] A load-test baseline recorded for every release.

    **Stage 2: durable shared store (M)**

    - [x] Postgres behind the repository, with a version check on every
      write. PR #42. Neon, chosen by the owner (2026-11-19). Change
      notifications are not needed while one server runs.
    - [x] The JSON files imported, and both written while the database is
      new. PR #42. The app imports files the database lacks when it starts,
      writes every save to both and loads the newer copy.
    - [ ] Stop writing the files once the database has proved itself on the
      live app.
    - Games then survive Cloud sleeping and reboots. Needs the owner's
      database account (Supabase or Neon for Postgres, Upstash for Redis)
      and its URL in Streamlit secrets.

    **Stage 3: scale out (M or L), only if hundreds of games become a target**

    - 3a: several Streamlit replicas on paid hosting, with sticky sessions and
      store notifications; or
    - 3b: a game server (FastAPI + WebSockets, reusing `abaka/` unchanged)
      with a thin client. Both UIs share the store during the migration.

    **Owner decisions still open**

    - The Python policy: keep 3.8 for the engine (today's rule), or move to
      3.10+.
    - Whether the CLI and `main.py` stay.
    - How rejoining is protected.
    - The limits: rooms, creations per session, how long finished games are
      kept.
    - The hosting budget (Stage 3). The database is Neon (2026-11-19).

12. **Cross out a claimed bonus for the other players immediately.** Done in PR #37.
    When a player earns a shared row or column bonus, show a cross in the
    corresponding bonus cell for every other player on the updated scoreboard.

13. **Cross out a shared bonus when the first player completes the row or
    column.** Done in PR #37. Completion closes the bonus for every other player, even
    if the completed row or column contains crossed-out cells and the first
    player earns no bonus.
    - Items 12 and 13 apply to rows and the first two columns. Each player's
      final-column bonus depends only on their own scores and crosses.

14. **Disable dice selection after the third throw.** Done in PR #37. Once the third
    throw of a turn is complete, the active player can no longer select or
    deselect dice.

15. **Hide the trophy from losing players.** Done in PR #37. The trophy appears
    only on the outright online winner's results screen.

16. **Starting throws stay on screen after the first player is decided.** Done in
    PR #39. Before, the last thrower's total vanished as soon as the lowest was
    known: the screen showed only "Ann threw the lowest (9) and goes first.", so
    nobody could tell how much the others threw. Now the note comes with every
    player's starting throw (dice and total) until the first move, and nobody is
    dimmed once the decision is made.
    > "Сыграли сегодня втроём на одном телефоне … если второй выкидывает больше
    > первого, его результат не показывается вообще, сразу сообщается, что первым
    > ходит другой. Это вносит сумятицу и вопросы, сколько же он выбросил"

## Status (2026-11-19)

- **Live app on Neon (owner's secret was named `DATABASE_URL`):** PR #44.
  The app now also accepts the `DATABASE_URL` secret, and the home page says
  where games are saved. Before, after the owner's reboot, the live app
  still saved to its disk only (games 6VPPE, RSXZR and L994A never reached
  Neon, and 6VPPE was gone after the reboot: the disk does not survive it).
- **Neon project linked (owner, Neon's setup steps):** PR #43. `neon init`
  and `neon deploy` linked the repository to the owner's Neon project; the
  13 database tests and the restart check (a game back from Neon after its
  save folder was deleted) passed against it. The test game was removed;
  `abaka_rooms` is empty. The `ABAKA_DATABASE_URL` secret on Streamlit Cloud
  is still the owner's to add (the pooled `DATABASE_URL` value).
- **Games in a database (owner: "I already have an account on Neon, can you
  set it up"):** PR #42. With the `ABAKA_DATABASE_URL` secret, the app saves
  every game to Neon Postgres as well as to files, so games survive Cloud
  reboots and sleep. Without it, nothing changes. Checked on a local server
  against Postgres 16: a game came back after a restart with its save
  folder deleted, and games saved only in files were imported at start.
  The secret on Cloud is the owner's to add.
- **Mid-size screens and LICENSE (owner, "you can work on 4"):** PR #41. With
  3-5 players the cards stack between 641px and 1000/1180px, so the
  scoreboard fits and the dice keep 60px; the MIT LICENSE file is added.
- **Rules confirmed (owner, 2026-11-18):** a first roll doubles score and
  bonus; only exact 1-5 and 2-6 are straights. The engine already did this;
  the original engine tests were corrected in PR #40.
- **Starting throws stay on screen (owner's report, Backlog item 16):** PR #39.
  In a same-device game for three, the last thrower's total no longer vanishes
  when the first player is decided. Checked in headless Chromium on a local
  server at 1300px and 390px, with 3 and 5 players.
- **Gameplay and results requests:** Backlog items 12–15, made with Codex,
  were reviewed and merged in PR #37.
- **Two agents, one repository:** AGENTS.md holds the working agreement
  for Codex and Claude Code (branches `codex/...` and `claude/...`, pull
  requests through `tools/pr.py`, this file as the shared log). CLAUDE.md
  loads AGENTS.md and this file. Merged in PR #38.

- **Architecture review (owner's request, 2026-11-16):** a separate agent, in
  the role of senior architect, reviewed the whole project for running many
  games in parallel. The full report is in `docs/ARCHITECTURE_REVIEW.md`:
  verdict, measurements, findings with file:line, quick wins and a staged
  roadmap. Its plan is Backlog item 11; Stage 0 is done (PR #27 to #33).
  Stages 1-3 wait for the owner's decisions listed there.
- **Repository (Stage 1, first step):** merged in PR #35. Afterwards the live
  smoke test passed, and S6VSZ, saved by the older code, loaded with its
  state through the new `FileRepository`.
- **Build (Stage 0.9):** merged in PR #32.
  - The open page's connection dropped 10 s after the merge: Cloud restarted
    the app to install the pinned packages. It came back on the same
    Streamlit 1.67.0 and Python 3.13.18.
  - A same-device test game saved just before (S6VSZ) came back from its link
    unchanged, with the same dice and turn. So saved games survive that
    restart.
- **Monitoring (Stage 0.10):** merged in PR #33. Afterwards the live smoke
  test passed (polling, one run per click, an online game). The stats line
  goes to the Cloud logs, which only the owner can open.
- **Fewer reruns (Stage 0.7):** merged in PR #31, live 16 s later. Checked on
  the live app in headless Chromium:
  - a same-device page polled twice in 21 s;
  - in an online game the thrower polled 3 times in 9 s and the watcher 9,
    and they swapped after the throw;
  - throw, roll and reroll all each took one script run;
  - the other screen offered the next throw 0.2 s after the click.
- **Crossed-out combinations show the lost column bonus (owner request 10):**
  merged in PR #24, checked on the live app in Russian.
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
- **Tests:** on Python 3.9 with Streamlit 1.48 and a test database, all 177
  pass; on 3.8, 148 pass and 29 are skipped (2 of them test `tools/pr.py`, 9
  need a database or psycopg; the others need Streamlit). CI runs them on 3.13 with
  Streamlit 1.67 and a Postgres service, and on 3.8. The suites: 16 database
  tests (`test_postgres.py`: the Postgres repository's contract, where games are saved, the secret's name, a dropped
  connection, an unreachable database, a store on Postgres, the mirrored
  files and their import), 13 lifecycle tests (`test_lifecycle.py`), 3 name tests (`test_names.py`: Markdown escaping,
  invisible characters, hostile names through the real app), 5 clone tests (`test_clone.py`: same game as
  `deepcopy`, nothing mutable shared, previews identical), 6 language tests (`test_i18n.py`: every t() text has a
  Russian version with the same placeholders, room errors, plurals, per-thread
  language), 15 saving tests (`test_saving.py`, including writes outside the
  lock and a retired store), 26 room tests (`test_rooms.py`: a full two-player game,
  rematch, 3-5 player rooms, starting early, leaving the waiting room, moves
  from outdated pages),
  13 move-preview tests (`test_moves.py`), 6 tests for the owner's requests
  (`test_owner_requests.py`), 6 starting-throw tests
  (`test_starting_throw.py`: lowest starts, ties, joker at face value,
  rooms, rematch), 5 module-reload tests (`test_code_version.py`), 9
  repository tests (`test_repository.py`: the file repository's contract, a
  store on an in-memory repository), 6 monitoring tests (`test_monitoring.py`: the stats line, failed saves, the
  "Continue a game" list), 11 older
  rule tests, the original engine's 15 tests (`test_abaka_engine.py`, with the
  first-roll and straight rules the owner confirmed on 2026-11-18), 3 scoreboard tests (`test_scoreboard.py`: crossed bonus cells
  and their preview) and 7 app tests (`test_ui_notices.py`,
  `test_ui_store.py` with the old store retired and rendering that never
  changes the shared engine, `test_ui_saved_games.py`, `test_ui_reruns.py`:
  one script run per move, a click on an outdated page, poll intervals). The app tests run the real app script with
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

- Until the `ABAKA_DATABASE_URL` secret is set on Cloud, saved games live
  only on the server's disk. That survives code updates and the restart
  after a change to `requirements.txt` (both checked on the live app), but
  probably not a reboot from the Cloud dashboard or the app going to sleep.
  With the secret, games are in Neon too (PR #42).
- Neon's free plan suspends an idle database; the first game opened after
  that waits for it to wake up (about a second, not measured on the live
  app).
- Online players coming back in a new session (a reload, or a session
  dropped after more than 6 hours) land on the invite page and tap their
  name. The seat token is kept out of the URL, so a copied address bar
  never hands over a seat.
- Streamlit Cloud sometimes does not pick up a merge for a long time (PR #20,
  2026-11-16). "Reboot app" in the Cloud dashboard pulls the latest `main`.
- Changes to `.streamlit/config.toml` apply differently:
  - `runner.*` and other run options apply while the app runs (Streamlit
    watches the file);
  - `server.*` options, such as `disconnectedSessionTTL`, apply only when the
    server process starts: on Cloud, after a reboot or a change to
    `requirements.txt`.

From the architecture review (details and file:line in
`docs/ARCHITECTURE_REVIEW.md`):

- **Capacity.** Every open page polls its room through the `_watch_room`
  fragment: every second while another player acts, otherwise every 3 or
  10 s (PR #31).
  - Before stage 0, measured on one M1 core: 50-100 waiting browsers
    saturated the server, about 6-10 actively played 3-player games. Cloud
    is 1.5-3 times slower.
  - Since `postScriptGC = false` (PR #27), 100 pages polling every second
    take about 30% of a core.
- (Fixed in PR #28 and PR #30: memory only grew. Finished games stayed in
  memory for 7 days, and every code update left the previous store behind.)
- (Fixed in PR #28: the global lock was held across deep copies and file
  writes, so every poll and render waited behind any room's save.)
- **Security, "friends only":**
  - anyone with a game's code can take any seat or empty a waiting room;
  - 5-character codes can be guessed;
  - room creation was unlimited (now 10 per browser per 10 minutes, and
    rooms beyond 2,000 leave memory; a script opening new sessions is not
    stopped yet).
  - (Fixed in PR #29: player names reached Markdown unescaped, so a name
    could be a link or an image.)
- (Fixed in PR #32: Streamlit was unpinned and there was no CI. Expired and
  unreadable save files are deleted or quarantined since PR #30.)

### Roadmap

The scale-up plan is Backlog item 11, as a checklist.

Other ideas, not planned:
- a dark theme (the scoreboard CSS colours would need to follow the theme);
- showing the opponent which dice the active player has picked.

## Decision log

**2026-11-19: the `DATABASE_URL` secret, and where games are saved (Claude Code, PR #44)**

- The owner had saved the Streamlit secret as `DATABASE_URL`, the name in
  Neon's `.env.local`, so the app (which read only `ABAKA_DATABASE_URL`)
  kept saving to its disk. The app now reads either name from Streamlit
  secrets. A `DATABASE_URL` environment variable is still ignored, so tests
  and local runs cannot reach the production database by accident.
- Streamlit Community Cloud has no API for secrets or logs, so the agents
  cannot see why the live app does not use the database. The home page now
  says it in one line (database, server only, or why the database is not
  in use), without the address or the server's message.
- The owner's reboot confirmed the Known issue: a game saved only on the
  disk (6VPPE) was gone afterwards.
**2026-11-19: Neon project linked (Claude Code, PR #43)**

- The owner pasted Neon's agent setup steps (install the CLI, `neon init`
  for project `restless-haze-52228918`, `neon deploy`, wire the services,
  `npm run build`, test end to end).
- `neon.ts`, `package.json` and `package-lock.json` are committed so `neon
  deploy` works from the repository; `.env.local`, `.neon` and
  `node_modules/` are gitignored. Streamlit Cloud ignores the npm files.
- The wiring stays as in PR #42. Neon's skill says to keep the existing
  driver (psycopg suits a long-running server) and to use the pooled URL for
  app traffic, which the app supports (no prepared statements).
- The app keeps reading only `ABAKA_DATABASE_URL`, not `DATABASE_URL` or
  `.env.local`: those name the production database, and the app tests run the
  real app script, so a generic name could put test games into it.
- `npm run build` fails with "Missing script": there is no JavaScript to
  build. The proof is the database tests and a real server, both on Neon.
- Measured from this machine: 1.8 s for the first connection (the compute
  waking up), then 38 ms per query.
- The dropped-connection test used to end every session with no application
  name, which on a shared database would include the live app's. Connections
  now carry an application name (`abaka`), and the test ends only its own.
  Through Neon's pooler the name is not visible, so there it ends nothing
  and checks the reconnect after closing the connection itself.
**2026-11-19: games in Neon Postgres (Claude Code, PR #42)**

- The owner asked about free databases and storing games on GitHub, chose
  Neon ("I already have an account on Neon, can you set it up for the
  abaka?"), and decided against moving the app to Vercel, which cannot run a
  Streamlit server.
- Postgres behind the existing repository interface, so `RoomStore` and the
  game did not change. psycopg 3.3.6 (with its binary libpq) is pinned; it
  is imported only by `PostgresRepository`, so the engine still runs on
  Python 3.8 without it.
- The URL comes from the `ABAKA_DATABASE_URL` secret, never from the code or
  the log (the log names only the host). The app works as before without
  it, so the merge and the secret are independent.
- The files stay as a mirror at first, because the database is new: a load
  takes the newer of the two copies, so a game whose database save failed
  still comes back, and a game saved before the database moves into it on
  start (`import_files`) or on its next save. Dropping the mirror is the
  open Stage 2 step.
- The version rule moved into the database: a save writes only if the stored
  version is older, in one statement. A second server could not undo a move
  either.
- One connection behind a lock, made again on demand: a single process
  writes about one row per move, so a pool would add a package for nothing.
  A statement that fails on a dropped connection runs again once; every
  statement is safe to repeat.
- Tested against a real Postgres: locally (Postgres 16 from `pgserver`, as
  no other was installed), and in CI through a Postgres service. Checked
  end to end on a local server in headless Chromium: a game was played,
  the server stopped, its save folder deleted, and a new server with an
  empty folder showed the game unchanged from its link.
**2026-11-18: mid-size screens and the LICENSE file (Claude Code, PR #41)**

- The owner asked for the small polish items ("you can work on 4").
- Measured on a local server: side by side, the scoreboard needs about 1000px
  of screen with 3 players, 1150px with 4 and 1180px with 5. Below that it
  scrolled sideways inside its card, and with 5 players the dice shrank to
  26-39px. (The 3-player case was not in Known issues; it showed up in the
  measurement.)
- Stacking the cards in that range, as on phones, was chosen over shrinking
  the table further: the table is already compact (`ab-many`), and stacking
  keeps the dice at 60px. Above those widths and on phones nothing changes.
- After the change, at 700-1180px the board fits, the dice are 60px and no
  page scrolls sideways (at exactly 641px a 5-player board still scrolls by
  40px inside its card).
- LICENSE: README.md has said MIT from the start, so the file is MIT with the
  owner's name (from the repository's git author) and 2026.

**2026-11-18: first-roll and straight rules confirmed (Claude Code, PR #40)**

- The owner answered the two open rule questions:
  > "Bonus gets doubled as well, for example, abaka on first throw with 6's gets 160 points.
  > There are only 2 straights in this game: 1 2 3 4 5 (small) or 2 3 4 5 6 (large).
  > 4 consecutive numbers don't score anything"
- The engine (`scoring.py`: `(base + bonus) * 2` on a first roll; straights
  exactly `{1..5}` = 15 and `{2..6}` = 20) and the rules text already did
  this, so no game code changed.
- The 4 original engine tests that expected the older rules are corrected and
  run again; nothing is skipped on Python 3.9 any more.

**2026-11-18: starting throws stay on screen (Claude Code, PR #39)**

- The owner's same-device game for three: after the last starting throw, the
  screen moved on at once and showed only the first player's total. A last
  thrower who threw more than the first never saw the result, and nobody could
  tell how much he had thrown (Backlog item 16).
- The note "X threw the lowest (N) and goes first." now comes with every
  player's starting throw (dice and total) until the first move. The totals
  are the ones the round used; no rule changed.
- Players are dimmed ("out") only while the starting throw is still going on
  (a player knocked out of a tie). After the decision, every row shows in full.
- Checked with `tests/test_ui_starting_throws.py` (a three-player game through
  the app script, and the online wording; both fail on `main`), and in
  headless Chromium on a local server at 1300px and 390px with 3 and 5
  players: every total visible, no sideways scrolling. With 5 players on a
  phone the table adds about five rows above the dice; the Roll button stays
  on the first phone screen.

**2026-11-18: two agents, one repository (Claude Code, PR #38)**

- The owner asked for a structure in which Codex and Claude Code can both work
  on the project.
- One shared guide and log (this file), one shared working agreement
  (AGENTS.md), and one loader for Claude Code (CLAUDE.md). AGENTS.md stays
  short: Codex loads at most 32 KiB of it by default, and this file is about
  67 KB.
- Each agent works on its own branch prefix and ships through pull requests,
  because `main` is protected. Codex's earlier commit went to local `main` and
  could not be pushed (PR #37 carried it).
- `tools/pr.py` replaces the private script Claude Code used, so every agent
  (and the owner) opens, checks and merges pull requests the same way, and
  sees the other agent's open pull requests before starting.
- Agents' memories are private, so anything the other agent needs goes into
  this file.

**2026-11-17: scoreboard, dice and results updates (items 12–15)**

- The scoreboard renders stored lost bonuses as crosses as soon as it draws
  the updated game. The engine already closes shared bonuses on completion.
- Dice picking is available while the active player has a reroll left.
- The trophy is reserved for the outright online winner's screen. Draws and
  shared screens show the result and scores without a trophy.

**2026-11-17: final-column bonus (owner clarification)**

- Each player earns or loses their final-column bonus independently. The
  first player to complete that column has no effect on anyone else's bonus.

**2026-11-17: Stage 1, the repository (PR #35)**

- The interface follows what `RoomStore` already did with files, so the
  refactor changes no behaviour (every existing test passed unchanged before
  the new ones were added).
- Saving keeps its version rule: the repository refuses a version that is
  not newer than the one it stored, and a deleted room. A database does the
  same with a conditional write. `claim` frees a deleted room's code for a
  new room.
- The repository gets the room's data as a plain dict and does not look
  inside it. `RoomStore` turns data into rooms, and quarantines data it
  cannot use (a missing field), as the files did before.
- A failed read is no longer quarantined: it may be passing (a disk hiccup).
  Only data that cannot be parsed or used is.
- The in-memory repository is a test double only. A real second backend
  waits for the owner's database account (Stage 2).

**2026-11-17: Stage 0.10, monitoring and small costs (PR #33)**

- The stats line comes from the store, because the store sees every poll,
  view, move and save. It is written by a poll once the minute is up, so it
  needs no timer thread, and a server nobody has open writes nothing.
- Only the app asks for it (`report_every`), and only the app attaches a
  handler: the `abaka` package configures no logging of its own.
- Memory is the resident size from `/proc` on Linux (Cloud). Elsewhere only
  the peak is available without extra packages.
- "Continue a game" keeps finished games in the list (another player may
  start the next game in that room) but forgets games that no longer exist.
- The module-reload check still compares contents, because the first fix
  chose contents over file times (2026-11-16). It reads them again at least
  once a minute, so even a change that kept every size and time is picked up.

**2026-11-16: Stage 0.9, build (PR #32)**

- Pinned to the version the live app already ran, 1.67.0, rather than the
  local 1.48.1. Pinning 1.48 would have downgraded the live app, and every
  live check so far was made on 1.67.
  - 1.67 needs Python 3.11+, so this machine's 3.9 environment cannot install
    it. CI is the check for 1.67; local runs check 1.48.
  - Read from the source of the 1.67 wheel, the settings this app relies on
    still hold there: `postScriptGC` (on by default), the 128-session cap,
    `disconnectedSessionTTL`, and `websocketPingInterval` (30 s by default
    now).
  - Changing `requirements.txt` restarts the Cloud app once, to install the
    same version.
- The Python 3.8 job runs in the `python:3.8-slim` container, so it does not
  depend on GitHub's runner images still offering Python 3.8, which reached
  its end of life in 2024.
- The original engine's tests now run against the `abaka` package instead of
  failing to import. 4 of them expect older rules; they are skipped with the
  reason rather than changed, because the owner decides the rules.
- The AppTest workaround for single-choice button groups only applies where
  AppTest needs it (1.48; 1.67 handles them).
- CI's first run found one more difference, in a test: AppTest 1.67 returns a
  query parameter as a string, 1.48 as a list. The app itself passed every
  test on 1.67.

**2026-11-16: Stage 0.7, fewer reruns (PR #31)**

- Moves in `on_click` callbacks. With `if st.button(...)`, the click makes
  the move halfway through a script run, and `st.rerun()` then draws the page
  again. A callback runs before the script, so the page is drawn once, with
  the move made.
- A callback makes the move its page showed. A second tap that arrives before
  the page is redrawn would make a move nobody saw: on the same device, a
  double tap on "Throw for Ann" would also throw for Bob.
  - So each move carries the version its page was drawn from, and the store
    refuses it if the room has changed (`OutdatedPage`). The app then only
    redraws the page.
  - A reclaim (a player taking their seat back on another device) changes the
    version too, so the player whose turn it is can lose one tap then. Their
    page redraws at once.
- `RoomEngine` takes `get_store` rather than the store, because a code update
  can replace the store between drawing a page and the click.
- Polling uses one fragment function per interval, because Streamlit fixes a
  fragment's `run_every` where it is defined. Checked in headless Chromium
  that the old timer stops when a page switches: 3 polls in 9 s on your own
  turn, 9 while watching, 2 in 21 s on the same device.
- The idle load in the local load test was websocket pings. Streamlit pings
  every second with Tornado below 6.5 (6.4.1 here) and every 30 s with 6.5+
  (Cloud installs the newest). The config now says 30 s, so every setup
  behaves like Cloud.

**2026-11-16: Stage 0.3-0.5, faster store (PR #28)**

- Copy-on-write instead of copies: a move works on `GameEngine.clone()` and
  installs it, so `view()` can share the installed engine. The contract (the
  UI never changes an engine) is tested on every phase of a game.
- Files are written outside the lock, with per-room versions, so a late
  writer can never put an older state back and a closed room never returns.
- Old stores are retired through a registry, not left in a per-class cache.
  Pages still on the old code read the new store, which is safe because its
  `version()` and data come from the same saved files.
- No cache for the move list: with `clone()`, `score_options` costs about
  0.3 ms, about 1% of a page run.

**2026-11-16: architecture review (owner's request)**

- The owner asked for a review by a separate agent in the role of senior
  architect, focused on running many games in parallel. The agent worked
  read-only and measured on a local server with a websocket load driver.
  Its report, unedited apart from a header, is `docs/ARCHITECTURE_REVIEW.md`.
- I checked two of its findings in Streamlit's source, and both correct
  earlier statements in this file and to the owner:
  - `runner.postScriptGC` defaults to True and runs `gc.collect(2)` after
    every script run, polls included;
  - disconnected sessions are capped at 128, so the 6-hour lifetime does not
    hold for everyone.
- The review also found that names reach Markdown unescaped. Nothing was
  changed yet; the Roadmap lists what comes next.

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
