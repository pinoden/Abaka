# Project Library

Repository guidance and the project's working log for owner requests, current
status, and past decisions. Update the Backlog, Status and Decision log
whenever work is done.

Two coding agents work on this project, Codex and Claude Code. AGENTS.md says
how they share it (branches, pull requests, this log); both read it, and both
keep this file. Claude Code loads the two through CLAUDE.md.

- **Repository:** https://github.com/pinoden/Abaka (git remote `origin`). Finished
  work goes there. `main` is protected: every change goes in through a pull
  request, and GitHub merges one only when both CI jobs passed on a branch
  that is up to date with `main` (required checks, also for admins).
- **Live app:** https://mipt-abaka.streamlit.app/, deployed by the owner on
  Streamlit Community Cloud from `main` (main file `abaka_ui.py`). Merging into
  `main` updates it automatically, within a few minutes. Cloud reloads the code
  in the running server instead of restarting it (see Online play).

## Commands

```bash
pip install -r requirements.txt                       # streamlit 1.67.0 (pinned; needs Python 3.11+), psycopg 3.3.6
ABAKA_TEST_DATABASE_URL=postgresql://... python -m unittest tests.test_postgres   # database tests (else skipped)
streamlit run abaka_ui.py                             # the app (port 8501, all interfaces)
streamlit run abaka_server.py                         # the app and the API for apps (Streamlit 1.67+; docs/API.md)
python -m abaka                                       # CLI version
python -m unittest discover -s tests -p "test_*.py"   # all tests
python -m unittest tests.test_rooms -v                # one test module
python tools/simulate.py 200 40                       # random complete games with rule checks (2-3 min)
python tools/loadtest.py --clients 100 --interval 1   # simulated pages polling every second: CPU, latency
python tools/loadtest.py --clients 100 --interval 1 --set runner.postScriptGC=true   # compare a Streamlit option
python tools/loadtest.py --baseline --record docs/LOADTEST.md   # the release baseline (about 1 min): adds a row, flags a slowdown
python tools/pr.py status                             # open pull requests and their branches
python tools/pr.py ship --title "..." --body-file notes.md   # push, open the PR, wait for CI, merge
                                                      # (if main moved: brings it in, waits for CI again)
```

### Notes for this machine

- The base `python3` is Anaconda 3.8 without Streamlit. The conda env
  `~/opt/anaconda3/envs/Python39` has Streamlit 1.48:
  `~/opt/anaconda3/envs/Python39/bin/python -m streamlit run abaka_ui.py`.
  - That is older than the pinned 1.67, which needs Python 3.11+, and no
    newer Python is installed here.
  - To run the tests on Python 3.13 with Streamlit 1.67, as CI and Cloud do,
    make a throwaway one with uv, all in a scratch folder `$S`:
    `python3 -m venv $S/uvenv`, `$S/uvenv/bin/pip install -U pip uv`, then
    `UV_CACHE_DIR=$S/uvcache UV_PYTHON_INSTALL_DIR=$S/pythons
    UV_PYTHON_BIN_DIR=$S/bin $S/uvenv/bin/uv python install 3.13`,
    `uv venv -p 3.13 $S/venv313` and
    `uv pip install -p $S/venv313/bin/python -r requirements.txt`.
    Without `UV_PYTHON_BIN_DIR`, uv also links `python3.13` into
    `~/.local/bin`. The base Python's own pip (20.1) cannot install uv;
    upgrade it first.
  - `abaka_server.py` (the app with the API) needs Streamlit 1.67, so it runs
    from that scratch Python: `ABAKA_DATABASE_URL= $S/venv313/bin/python -m
    streamlit run abaka_server.py`. Its network tests are skipped on 1.48.
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
    - Pills there have `data-variant="pills"` and no `data-testid`, and the
      picked one has `aria-checked="true"`. In 1.48 they are
      `data-testid="stBaseButton-pills"` (picked: `stBaseButton-pillsActive`).
      CSS for them must match both.
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
| `abaka/clubs.py` | Clubs: `ClubStore` (a club's table, saved through a repository), the multiplayer Elo `rating_changes`, `member_key`. No Streamlit |
| `abaka/saving.py` | `GameEngine` <-> plain JSON data (`engine_to_data`, `engine_from_data`) for saved games |
| `abaka/repository.py` | Where rooms are kept between runs: the repository methods; `FileRepository` (one JSON file per room), `PostgresRepository` (one row per room; Neon on the live app) and `MirroredRepository` (both). No Streamlit |
| `abaka/moves.py` | Possible moves with exact score previews (tries each on a copy of the engine), and the option with the most points. No Streamlit |
| `abaka/i18n.py` | Every text players see, in English and Russian: `t("...")`, plurals, error messages, `md()`. No Streamlit |
| `abaka/api.py` | The game as JSON for apps (Android, iOS) and any other client: `handle(request, store, clubs)`, protocol 1, described in `docs/API.md`. No Streamlit |
| `abaka_ui.py` | Streamlit entry point and screens: home, invite, waiting room; online polling |
| `abaka_server.py` | The app and the API for apps in one process (`streamlit run abaka_server.py`, Streamlit 1.67's `st.App` with two routes) |
| `server/stores.py` | The process's `RoomStore` and `ClubStore` and where they save (files, Neon); the registry the pages and the API share under `abaka_server.py` |
| `server/http.py` | The API over HTTP (`POST /api/v1`) and a live WebSocket (`/api/v1/live`) that pushes a watched game's state. Starlette |
| `code_version.py` | Called first on every run: reloads `abaka`/`ui_components`/`server` if their files changed since they were loaded |
| `ui_components/main_ui.py` | Game screen for both modes: top bar and menu, play panel, scoreboard, results |
| `ui_components/actions.py` | `on_click` callbacks of the game buttons: make the move, keep a refusal to show once |
| `ui_components/chat.py` | The chat card of an online game: messages (escaped), the box to write one, a toast for new ones |
| `ui_components/effects.py` | Reactions (buttons, bubbles) and celebrations (fireworks, sparkles), drawn from the room's recent events |
| `ui_components/dice.py`, `move_selection.py`, `scoreboard.py`, `rules.py` | Dice, move picker, score table, rules text |
| `ui_components/style.py`, `.streamlit/config.toml` | CSS and dice SVGs; theme colours |
| `tests/` | `unittest` tests |

`abaka/` is the game without its web page: the rules, the rooms, the clubs,
saving, the move previews, the texts and the API. Everything in it runs on
Python 3.8 without Streamlit. `abaka_ui.py` and `ui_components/` are the web
app, one client of it; the apps for phones will be another (Backlog item 25).
Code that both need goes in `abaka/`. `server/` is the server around the game:
where its stores save, and the API over the network.

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
  - The stores themselves are made by `server/stores.py` (`make_stores`),
    which also says where they save.
  - Under `abaka_server.py` the pages use another registry,
    `server/stores.py`'s (`serve_api()` switches them). The API's routes run
    outside any page's script run, and that registry is the one both reach.
    It lives in a module made at run time (`_abaka_process`), which neither
    Streamlit's file watcher nor `code_version` ever unloads. The same rules
    apply there: the new code retires the old store, and old code gets the
    new one.
- Streamlit re-reads `abaka_ui.py` on every run, but imported modules stay
  loaded, and its file watcher unloads them only while a browser session is
  open. So `abaka_ui` first calls `code_version.load_current()`. It hashes the
  `.py` files of `abaka/`, `ui_components/` and `server/` and, if they differ
  from the loaded code (`abaka.code_fingerprint`), drops those modules so they
  are imported again from disk. Tests that patch modules before running the
  app call `code_version.mark_current()` first.
  - `code_version` itself stays loaded across updates. If the loaded one does
    not list `server` yet (an update pulled while no page was open),
    `abaka_ui` reloads it first.
  - The contents decide, but the files are read again only when a size or a
    file time changed, or a minute has passed (`current_fingerprint`). Sizes
    and times are looked at at most every 2 s (`CHECK_EVERY_SECONDS`): the
    check costs about 1 µs per run instead of 0.6 ms.
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
  (`st.fragment(run_every=...)`) that compares `store.seen(code)` with the
  value the page was drawn from (`RoomView.seen`: the room version, a
  count of dice-pick changes and the room's latest event or chat id,
  `room.last_event_id`), and calls `st.rerun()` when they differ.
- Picked dice (Backlog item 18): a tap on a die in an online game also calls
  `store.pick` (`RoomEngine.pick`), which keeps the picks in the room
  (`room.picked`, with `room.picks` counting changes) for the other pages.
  A pick is not a move: it changes neither the game nor `room.version`, so a
  Reroll pressed right after a pick is not refused as outdated, and nothing
  is saved. Only the player whose turn it is can pick, and only while a
  reroll remains. Every move clears the picks; a reroll records its dice in
  `room.rerolled`, which `dice._roll_animation` spins.
- Reactions and celebrations (Backlog item 22, `ui_components/effects.py`):
  the room keeps its last 20 events in memory (`room.events`, never saved,
  cleared by a rematch). Each has an id from the clock in milliseconds, so
  ids keep growing after a room is loaded again.
  - `store.react(code, token, reaction, to=None)`: anyone seated in an
    online game, at any time, one of `rooms.REACTIONS`, to everyone or one
    seat; one per seat every 2 s (`TooFast`). Not a move: no version bump,
    no turn check. Same-device rooms ignore it.
  - `_act` adds an effect after a move that earned one (`_celebration`, the
    owner's rules of Backlog item 23), online and on one device:
    - A throw (`roll`, `reroll`) shows what the dice make, whatever is
      written afterwards. A joker showing 1 is wild, as in scoring.
      - Abaka or the royal full house (1-1-1-2-2, `scoring.is_royal_full`):
        bigger fireworks on the first roll, fireworks after a reroll.
      - A straight, a full house or four of a kind on the first roll:
        sparkles.
    - A move that earns its player a row or column bonus (a bonus cell that
      gets a number): sparkles.
    - The starting throw brings nothing.
  - `effects.render_events` shows each event once per page.
    - Skipped: events from before the page first drew the game, and events
      more than 15 s old when first seen.
    - A throw's effect waits 0.45 s for the dice to land
      (`LEAD_IN_SECONDS`, their spin in `dice.py`).
    - An effect that arrives while another plays waits for it to end, so
      two never overlap.
    - The page keeps when each event starts (`fx_state["starts"]`). A
      redraw continues the animation (a negative CSS animation delay)
      instead of starting it again.
- Chat (Backlog item 22, `ui_components/chat.py`): `store.say(code, token,
  text)` keeps the last 50 messages in `room.chat`, in memory only. Anyone
  seated in an online game may write while it is played; not before it
  starts, not after it ends, not on one device. Text is cleaned like a name
  (`rooms.clean_message`: no control or invisible characters, spaces
  collapsed) and cut to 200 characters; at most 3 messages per seat in 3 s
  (`TooFast`). Not a move: no version bump. The move that ends the game
  deletes the chat (owner's rule), and a rematch starts empty. Ids come from
  the same clock as the events, so new messages change `seen`.
  - The card sits under the play card (`render_game(after_play_card=...)`),
    only while the game is on. Messages are drawn with `html.escape`; a
    message from someone else also shows a toast (`i18n.md()`), so a phone
    scrolled to the dice still hears about it.
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
  - The app's `MirroredRepository` writes the database in the background
    (`background=True`): a save writes the file and returns, and a thread
    (`abaka-db-writer`, stopped after 30 s idle) writes the newest pending
    version of each room. A move waits about 1 ms for storage instead of
    about 40 ms to Neon. `wait()` (used by `retire()`) returns once the
    database has caught up; a delete drops the room's pending write. If the
    file write fails, that save goes to the database at once. Data handed to
    a repository must not change afterwards (`ClubStore` saves a copy).
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

### Clubs and the running score (Backlog item 17)

- Every room remembers its finished games (`room.results`, the last 100:
  game number and scores, saved with the room). `RoomView.series()` gives
  wins per seat and draws; the line under the scoreboard shows it ("Games at
  this table: 3 · 👑 Ann 2 · Bob 1") once a game there has finished.
- `RoomStore(on_game_over=...)` is called once per finished game, after the
  lock, with room, game number, club, names, scores and time. A failing
  listener is logged and never stops the game. The app passes
  `ClubStore.record`.
- A club (`abaka/clubs.py`) has a 6-character code (rooms have 5) and a
  name. Its page is `?club=CODE`: the table, the latest 10 games, forms to
  start a same-device or online game that counts for the club
  (`create_local(names, club=)`, `create(name, players, club=)`), and its
  link. The home page has a Clubs card (create, open by code, clubs this
  browser opened: `ss.my_clubs`).
  - The `?club=` parameter stays in the URL during a game started from the
    club page, so leaving the game returns to the club. The results screen
    of a club game shows how the ratings moved and a "Club table" button.
  - Players are matched by name, ignoring capitals and spaces
    (`member_key`). Anyone who can open a club can add games to it: it is
    for friends, like the game codes.
  - Rating: Elo with every pair of players as a head-to-head match (higher
    score wins, equal draws), K = 32 scaled by 1/(players - 1), start 1000.
    The changes of a game add up to zero.
  - A result is recorded once (id `ROOM:game`). A club keeps its latest 200
    games; members keep games, wins, total and best score, rating and last
    change. A best score starts from the first game, since scores can be
    negative.
  - Saved like rooms but apart: table `abaka_clubs` (and the files in
    `<save_dir>/clubs/`, mirrored). Clubs not changed for a year are deleted.
    `get_clubs()` returns the `ClubStore` made together with the current
    `RoomStore` in `get_store()`.

### The API for apps (Backlog item 25)

- `abaka/api.py` is the game for clients other than the web page, such as the
  Android and iOS apps to come. `handle(request, store, clubs)` takes a
  request as JSON data and returns JSON data, or raises `ApiError`, which
  carries:
  - a code that tells the app what to do (`outdated`: draw the new state;
    `not_seated`: offer to rejoin; and so on);
  - a message in the request's language.
- `docs/API.md` is the protocol: every operation, the fields of a state, the
  errors, and the rules for versions. `tests/test_api.py` checks that it names
  every operation and error code.
- It uses the same `RoomStore` and `ClubStore` as the web app, and every move
  goes through the store's methods (turn check, lock, version). So web and app
  players can share a game.
- The server is the referee. A state lists:
  - the moves of the player whose turn it is, with the previews from
    `abaka/moves.py` (and `best` for the most points);
  - what this player may do now (`can`).
  Apps offer just that and never apply the rules themselves.
- A state is drawn for one seat, the holder of the token. Tokens never appear
  in a state. Without a seat, the state shows only what the invite page shows.
- A move carries the `version` of the state it was chosen on. If the room has
  changed since, it is refused as `outdated`, like the web's buttons.
- Texts come in the request's `lang` (en/ru). The call sets it for its thread
  and puts the thread's language back afterwards.
- Protocol 1. Adding operations or fields keeps it. Changing what apps already
  rely on makes it 2, because apps on phones update slowly.
- Over the network (`server/http.py`), from `streamlit run abaka_server.py`:
  - `POST /api/v1`: one request per call. A refusal comes with an HTTP status
    that matches its code (404 `not_found`, 409 `outdated`, 422 `refused`,
    429 `too_fast`...).
  - `WS /api/v1/live`: requests as messages (with an `id` echoed in the
    answer), plus `watch`. A watched game's state is pushed when its `seen`
    changes, checked every 0.25 s. A push carries only new events and chat
    messages, and a move made over the connection is not pushed back.
  - One process serves the pages and the API (Streamlit 1.67's `st.App`), so
    they share the stores with no messages between servers.
  - Store calls run in worker threads (`run_in_threadpool`). The event loop
    also serves the web pages, and a store call may wait for its lock or for
    the database.
  - A client address may start 10 games and clubs in 10 minutes, as one
    browser may (`may_create`, `ApiError` `too_fast`). Behind a proxy,
    `ABAKA_CLIENT_ADDRESS_HEADER` names the header with the client's address.
  - A request is at most 16 KB.
  - The routes in `abaka_server.py` are made once, when the server starts.
    Each request loads the current code first (`code_version`), and a live
    connection made by older code closes with 1012 so the app reconnects to
    the new code.
  - Streamlit Community Cloud runs `abaka_ui.py` alone, so the live app does
    not serve the API yet (item 25, stage B).

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
- The score option that adds the most to the player's total is highlighted
  (Backlog item 24).
  - `Move.points` is the total's change, from the same trial move as the
    preview: the score or the School balance change, plus any row or column
    bonus the move earns.
  - `moves.most_points` picks the options, all of them on a tie.
  - The picker writes their labels in bold (pill labels are Markdown), and
    `style.py` colours a bold pill gold unless it is picked (`:has(strong)`).
    A picked pill keeps Streamlit's indigo.
    - Streamlit marks a picked pill differently in each version:
      `data-testid="stBaseButton-pillsActive"` in 1.48, `aria-checked="true"`
      in 1.67.
  - An option that earns a bonus says so: "Sum · 11 · bonus +52".
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
  version in `abaka/i18n.py`; `tests/test_i18n.py` fails otherwise.
- Code that is not about drawing the web page goes in `abaka/`, not in
  `ui_components/`, so the apps' API can use it too (Backlog item 25).
- A new thing players can do in the web app also gets an operation in
  `abaka/api.py` and a section in `docs/API.md`, so apps can offer it. Never
  change what an existing field or operation means in protocol 1: add a new
  one instead (`docs/API.md`, Versions). Apps installed on phones cannot be
  updated at once.
- Player names reach other players' browsers. In raw HTML (`st.html`,
  `scoreboard.py`) names go through `html.escape`. In places Streamlit renders
  as Markdown (captions, toasts, button labels) they go through `i18n.md()`:
  backslash escapes, plus a zero-width space after ":", "." and "@" because
  captions and toasts turn bare addresses into links even when escaped.
  `rooms.clean_name` also removes control and invisible format characters.
- A pull request that changes the app's code records a load-test row
  (`python tools/loadtest.py --baseline --record docs/LOADTEST.md`, about a
  minute) and says in its description if the tool flags a slowdown.
- Every new online action goes through `RoomStore._act`, so it gets the turn
  check, the lock and the version bump. (The one exception is `pick`, which
  shows picked dice and is not a move: it takes the lock and the same turn
  check, `_check_turn`, but changes no version. `react` and `say` are not
  moves either: they take the lock and a seat check, no turn check, and
  change no version.)
- The game rules are the owner's own. Do not change them, or copy rule details
  from the upstream `abaka_cc` repo, unless the owner asks.

## Backlog

Item 11 (the scale-up plan) is in progress. Items 12–15 (2026-11-17) were
merged in PR #37. Item 16 (2026-11-18) is in PR #39. Item 17 (2026-11-19) is in PR #45. Item 18 (2026-11-19) is in PR #48. Item 19 (2026-11-19) is in PR #49. Item 20 (2026-11-19) is in PR #50. Item 21 (2026-11-19) is in PR #51. Item 22 (2026-11-19) is in PR #52 and PR #53. Item 23 (2026-11-19) is in PR #55. Item 24 (2026-11-19) is in PR #56 and PR #57. Item 25 (2026-11-20, apps for Android and iOS) is in progress: steps A1 and A2 are in PR #58 and PR #59. Requests 1-4 came from the
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
    - [x] A load-test baseline recorded for every release. PR #47.
      - `tools/loadtest.py --baseline --record docs/LOADTEST.md`: 100 pages
        polling every second, 200 saved games, 20 s. It adds a row (date,
        commit, machine, Python and Streamlit, CPU, polls answered, poll
        latency, CPU per poll, page run, memory) and compares it with the
        latest row from the same machine, versions and load; a number 25%
        worse is flagged.
      - Rule: a pull request that changes the app's code (`abaka/`,
        `ui_components/`, `abaka_ui.py`, `code_version.py`, `.streamlit/`,
        `requirements.txt`) records a row, and says in the pull request if
        it is flagged.
      - First row, `main` at 996d5f5 on the M1 (Python 3.9, Streamlit
        1.48): 31% CPU, 97 of 100 polls/s answered, 8.2 ms median poll.

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

17. **Leaderboards: the running score at a table, and clubs.** Done in PR #45.
    > "Is there a smart fun way to keep leaderboard ?" … "Both" (layers 1 and 2
    > of the proposal: the running score at a table, and clubs with a rating)
    - Every table shows its running score across "Play again".
    - Clubs: a code to share, a rating table (Elo, start 1000), the latest
      games, and club games started from the club page. See "Clubs and the
      running score".
    - Not done (layer 3 of the proposal): records and titles ("Abaka hunter",
      highest score, streaks), and a public hall of fame.

18. **The other players see which dice are picked for a reroll.** Done in
    PR #48.
    > "When one player rerolling , I want the opponent (s )to see which exact dice"
    - Online, each die the player whose turn it is taps is lifted and marked
      (↻) on every other screen too, about a second later (their poll), with
      "Bob picked 2 dice to roll again." under the dice.
    - After the reroll, exactly the dice rolled again spin on every screen,
      also one that landed on the same face, with "Bob rolled 2 dice
      again."
    - Same-device games are unchanged (everyone sees the one screen).

19. **Four of a kind counts as two pairs.** Done in PR #49.
    > "there was an error during my game - I was't able to score two pairs
    > into the last row" (game LWUNK: joker 6, 6, 6, 6, 1 on the third roll;
    > only Sum was offered)
    - **Decided by the owner** (reported as an error): four of a kind holds
      two pairs of the same number, so 6 6 6 6 1 scores 24 in Two pairs.
      Five of a kind scores four of its dice (4 4 4 4 4: 16).
    - Before, Two pairs needed two different numbers (the scoring code from
      2025), so four of a kind scored 0 there and the move was not offered.
    - The rules text says "two pairs (four of a kind counts)" / "две пары
      (каре тоже)". Full house was changed next, by item 20.

20. **Abaka counts as a full house; every combination holds a pair.** Done
    in PR #50.
    > "Also abaka should be able to be written as a full house as well"
    > "an all of above could be a pair"
    - Five of a kind scores in Full house as all five dice (6 6 6 6 6: 30,
      doubled on a first roll). The 1-1-1-2-2 bonus is unchanged; five of a
      kind gets no bonus there.
    - Pair already accepted three, four and five of a kind, two pairs and a
      full house (the highest pair counts); now tested, and the rules text
      says so.
    - Four of a kind is still not a full house.

21. **Pick a club's players by name.** Done in PR #51.
    > "for existing clubs if there were some games played already - I want
    > the options to be provided - so you can type a new name or select of
    > the existing players"
    - Once a club has players, every name field of a club game (same device,
      online host, and someone joining an online club game) is a list of the
      club's players, the most recently played first, that also takes a new
      name typed in ("Add: Zed"). Joiners are offered only players not
      seated yet.
    - A same-device club game with the same player twice is refused ("Each
      player needs a different name."), since both would count as one
      member.
    - A club with no games yet keeps the plain text boxes.

22. **Reactions, fireworks and a chat.** Reactions and effects done in
    PR #52; the chat in PR #53.
    > "I want to create a set of emojies, kind of like on GG poker - where one
    > player can send the other player emojies - for example if one get's
    > lucky - you send send him "lucky", or so on. If someone scores Abaka we
    > can do fireworks in general - so all the players could see it. If good
    > combination from first attempt (straights, care or 11122 full - smaller
    > effect). Also is it hard to add a chat during the game? The chat should
    > be deleted once the game is over"
    - Online, every seated player has eight reaction buttons under the play
      panel: Lucky! 🍀, Nice! 👏, Wow! 😮, Ouch 😬, Hurry up ⏳, GG 🤝,
      Haha 😂, On fire! 🔥. With 3+ players a picker sends one to everyone
      or to one player ("Ann → Bob"; "Ann → you" on Bob's screen). Every
      screen shows a bubble at the top for 3.5 s. One reaction every 2 s
      per player. Same-device games have none.
    - Fireworks with "Abaka! Ann · +160" on every screen when someone
      scores Abaka; sparkles with "Large straight! Ann · +40 · first roll"
      for a straight, four of a kind or the royal full house on the first
      roll. Online and on one device, the mover's screen included, once.
      Item 23 replaced these rules: effects now come with the throw.
    - Chat (online games): a card under the play panel with the game's
      messages (latest at the bottom, the last 50) and a box with Send.
      Messages up to 200 characters, about one a second. A message from
      someone else also pops up as a notification. **The chat is deleted by
      the move that ends the game** and is never saved; the next game starts
      with an empty chat.

23. **Effects as the dice land, bigger fireworks, sparkles for bonuses.**
    Done in PR #55.
    > "I want sparkles on the following combinations if scored from first
    > throw: Small straight, Large straight, Full house (not royal), Four of
    > a kind, Abaka. Fireworks on any abaka and royal full house. Bigger
    > fireworks after abaka and royal full house on the first throw. Those
    > should be right after the throw, not after recodring it. Also I want
    > sparkles after recording any type of bonus."
    - Effects come with the throw, on every screen, as the dice land (after
      their 0.45 s spin), whatever the player then writes:

      | Thrown | First roll | After a reroll |
      |---|---|---|
      | Abaka, royal full house (1-1-1-2-2) | bigger fireworks | fireworks |
      | Small or large straight, full house, four of a kind | sparkles | nothing |

    - Bigger fireworks: three waves of bursts over the whole screen, a golden
      flash, a rain of sparkles and a larger banner, for 6 s ("Abaka! Ann ·
      first roll").
    - Sparkles when a move earns a row bonus (School or combination) or a
      column bonus (I, II or III): "Bonus! Ann · Sum row +52".
    - Writing a combination adds no effect of its own. The +20 and +50
      inside Four of a kind, Abaka and the royal full house are part of
      those rows' scores, celebrated at the throw.
    - Abaka on the first roll gets the bigger fireworks only (they include
      sparkles), not two effects. The starting throw gets nothing.
    - Banners now sit in the lower part of the screen, so they never hide
      the dice.

24. **Highlight the option with the most points.** Done in PR #56; gold on
    the live app since PR #57.
    > "Among the options,, can you highlight the option with the most points
    > potential ?"
    - Among the Score options, the one that adds the most to the player's
      total now is bold and gold. Points are the score (a School row: its
      balance change) plus any row or column bonus the move earns at once.
    - On a tie, every option with the most is highlighted. A full house
      always ties with Sum, and so do both straights.
    - An option that earns a bonus shows it: "Sum · 11 · bonus +52".
    - Nothing is highlighted when crossing out.

25. **Apps for Android and iOS.** In progress: stage A is done (PR #58 and
    PR #59). Stages B to D wait for the owner's decisions below.
    > "Let's start preparing the code base to expand on android/ios"
    >
    > "Go ahead" (step A2)
    - The plan, one PR per step. Tick a step here when its PR is merged.
    - The app is a thin client: the server keeps the game and the rules, and
      the app shows what it is told and sends the player's moves. So the rules
      stay in one place (the owner changes them often), and players on the web
      and in the app can share a table.
    - A native client is the safer path to the App Store than the web page in
      a wrapper: Apple asks apps to do more than repackage a website (App
      Review Guideline 4.2).

    **Stage A: the game as an API (no new services or accounts)**

    - [x] A1. The game as JSON for any client: `abaka/api.py`, protocol 1,
      described in `docs/API.md` (see "The API for apps"). The move previews
      and the texts moved into the game package (`abaka/moves.py`,
      `abaka/i18n.py`), so everything that is not the web page is in
      `abaka/`. PR #58.
    - [x] A2. The API over the network, in the same process as the web app:
      `streamlit run abaka_server.py` (see "The API for apps"). PR #59.
      - `POST /api/v1` for single requests, and `WS /api/v1/live`, which also
        pushes a watched game's state when it changes.
      - The pages and the API share one `RoomStore` through
        `server/stores.py`, so a game made in an app can be joined on the
        web and the other way round.
      - A client address may start 10 games in 10 minutes, as on the web.
      - Streamlit Community Cloud keeps running `abaka_ui.py` alone, with its
        own store registry: the live app does not serve the API before stage B.

    **Stage B: a host for the server (owner decides)**

    - [ ] B1. Streamlit Community Cloud cannot be an app's server:
      - it puts an app to sleep when nobody has used it for a while, and only
        a visit in a browser wakes it, so an app would get a wake-up page
        instead of its data;
      - it runs the app inside its own page, under `/~/+/`;
      - app links (below) need files served at the root of the app's own
        domain.
      So the server, web app and API together, moves to a small paid host
      (for example Fly.io, Render or Railway; check current prices), with
      Neon as it is, and a domain. The web app moves with it, so web and app
      players keep sharing games.

    **Stage C: the app**

    - [ ] C1. The app's technology (owner decides). Recommended: React
      Native with Expo, in TypeScript.
      - One code base for iOS and Android, built in Expo's cloud.
      - Updates to the app's code without a store review.
      - Alternatives: Flutter (also one code base) or two native apps
        (twice the work).
    - [ ] C2. The screens, as on the web:
      - home (new game, open by code, continue, clubs), invite and waiting
        room, the game (dice, moves, scoreboard, reactions, chat), results;
      - English and Russian. The game's texts come from the server (`info`,
        move labels, errors). The app's own texts reuse `abaka/i18n.py`,
        exported when the app is built.
    - [ ] C3. Links: a game's link opens the app when it is installed
      (universal links and app links, served from the domain).

    **Stage D: the stores (the owner's accounts)**

    - [ ] D1. Apple Developer Program (99 USD a year) and Google Play
      Console (25 USD once), in the owner's name. Also needed:
      - the app's name, icon and identifier;
      - a privacy policy page: names and games are stored, and the chat is
        deleted when the game ends;
      - store listings, and test releases first (TestFlight, Play internal
        testing).

    **Stage E: after the first release**

    - [ ] "Your turn!" notifications (Apple's and Google's push services):
      the server keeps each seat's device address.
    - [ ] Seat protection, already open in item 11, matters more for a public
      app. The token on the device is already personal, but anyone with the
      code can still take a seat by its name.
    - [ ] Optional: games on one device without a network, by running the
      rules in the app (a port of the engine, checked against games recorded
      from the Python engine). Until then, every game needs the server.

    **Owner decisions still open**

    - The app's technology (recommended: Expo).
    - The host for the server, its budget, and a domain.
    - The store accounts, the app's name and its identifier.
    - Whether games on one device must work without a network.
    - How seats are protected (also in item 11).

## Status (2026-11-20)

- **The API over the network (owner: "Go ahead", Backlog item 25):** PR #59,
  step A2. `streamlit run abaka_server.py` serves the web app and the API
  together (`POST /api/v1`, `WS /api/v1/live`); the live app is unchanged.
  - Checked on a local server with Streamlit 1.67, in headless Chromium:
    - A game made through the API was joined from a web page. The API's
      live connection got the new state 175 ms after the click.
    - After the app's starting throw, the web page offered the other player
      his throw 1.3 s later (pages check once a second).
    - His throw on the page was pushed to the app.
  - The web app alone (`streamlit run abaka_ui.py`, as on Cloud) was checked
    the same way as before. A game in English and the home page in Russian
    showed no errors, and the store now comes from `server/stores.py`.
  - 9 new tests (`tests/test_server.py`):
    - a real server, for the HTTP statuses, the limit on new games, a
      server fault, pushes and what they carry, and the closing on a code
      update;
    - `streamlit run abaka_server.py` itself;
    - a page joining a game made through the API.
  - The network tests run on Python 3.13 with Streamlit 1.67 (CI, and the
    scratch Python here).
  - Load-test row: no slowdown (26% CPU, 7.1 ms median poll).
  - Next: the owner's decisions in item 25 (the host, the app's technology,
    the store accounts).

- **Preparing for apps on Android and iOS (owner, Backlog item 25):**
  PR #58, step A1 of the plan.
  - `abaka/api.py` gives apps the whole game as JSON (protocol 1,
    `docs/API.md`), over the same rooms as the web app.
  - The move previews and the texts moved from `ui_components/` to
    `abaka/`; the web app is unchanged.
  - 18 new tests (`tests/test_api.py`). They include complete games for 2
    and 5 players online, and on one device, played only through the API.
    Every offered move was accepted, and its preview matched the cell and the
    points it got.
  - All tests also pass on Python 3.13 with Streamlit 1.67 on this machine,
    as on Cloud (a scratch install; see Notes for this machine).
  - Load-test row: no slowdown (25% CPU, 6.9 ms median poll; `main` just
    before it: 26%, 8.0 ms). A first run was flagged while Spotlight indexed
    the machine; it was not kept.
  - Next: A2, the server that carries the API, and the owner's decisions in
    item 25.

- **The option with the most points (owner, Backlog item 24):** PR #56 and
  PR #57.
  - On the live app after PR #56 the best option was bold, but not gold:
    Streamlit 1.67 marks pills differently (Decision log). PR #57 fixed the
    style. Before merging, the new rule was checked against the live page's
    markup in a headless browser (the best option gold, the others grey) and
    on 1.48 locally.
  - Checked in headless Chromium on a local server with steered dice, at
    1300px and 390px:
    - with four 2s on a first roll, only "Four of a kind · 56" was gold;
    - picked, it turned Streamlit's indigo;
    - with a full house, "Full house · 46" and "Sum · 46" were both gold.
  - No sideways scrolling.
  - The load-test row was flagged against the previous one (25% → 33% CPU,
    6.8 → 8.6 ms median poll). `main` and this branch measured back to back
    gave the same (33% and 34%, 8.7 and 8.9 ms), so the previous row was low.
    The poll path did not change.

- **Effects as the dice land (owner, Backlog item 23):** PR #55.
  - Checked in headless Chromium on a local server with steered dice (a
    scratch launcher), at 1300px and 390px:
    - bigger fireworks for Abaka on the first roll;
    - fireworks for Abaka after a reroll;
    - sparkles for a large straight;
    - "Bonus! … Sum row +52" when the Sum row was completed.
  - Each banner appeared about 0.67 s after the click (the dice land first),
    below the dice. No page scrolled sideways.
  - Online, a phone showed the desktop player's bigger fireworks 1.2 s after
    the throw.
  - Load-test row: no slowdown (25% CPU, 6.8 ms median poll).

- **CI required for merging (owner: "I think we need to enforce checks to
  pass before the merge"):** set on GitHub on 2026-11-19 and documented in
  PR #54. `main` takes a pull request only when both CI jobs passed on a
  branch up to date with `main`; this applies to admins too, so also to
  merges from the GitHub website. `tools/pr.py merge` waits for both jobs by
  name and brings a moved `main` into the branch.
- **In-game chat (owner, Backlog item 22):** PR #53. Checked in headless
  Chromium on a local server, a desktop (1300px) and a phone (390px) in one
  online game: a message reached the other screen in 0.3 s, shown as text
  (an `<b>` tag and a Markdown link stayed plain, no link on the page),
  text half typed on the other screen survived its redraw, a burst of 6
  messages sent 3 and showed the "Slow down" note; no sideways scrolling.

- **Reactions and fireworks (owner, Backlog item 22):** PR #52. Checked in
  headless Chromium on a local server, a desktop (1300px) and a phone
  (390px) in one online game: a reaction reached the other screen in under
  2 s, both ways, no sideways scrolling. The fireworks and sparkles were
  checked on a scratch page at both widths (an Abaka cannot be rolled on
  purpose in the app); the AppTest test drives them through the app.
  Load-test row: no slowdown (25% CPU, 6.1 ms median poll). On the live
  app after the merge, a reaction reached the other screen (desktop and
  phone) in 1.3 s.

- **Club player picker (owner, Backlog item 21):** PR #51. Checked in
  headless Chromium on a local server at 1300px and 390px: the club's
  players offered, one picked and one typed in, the game started with both;
  no sideways scrolling.
- **Abaka as a full house (owner, Backlog item 20):** PR #50, with the
  rules text in English and Russian.
- **Two pairs from four of a kind (owner's report, Backlog item 19):** PR #49.
  The owner's game LWUNK had already moved on, so that turn stays as played.
- **Picked dice on the other screens (owner, Backlog item 18):** PR #48.
  Checked in headless Chromium on a local server, a desktop and a phone in
  one online game: the watcher saw the two picked dice lifted 1 s after the
  tap, and after the reroll exactly those two spun. Load-test row: no
  slowdown (30% CPU, 7.1 ms median poll).
- **Load-test baseline (Backlog item 11, Stage 1; owner: "Keep going"):**
  PR #47. `docs/LOADTEST.md` keeps one row per release, written by
  `tools/loadtest.py --baseline --record`, which flags a slowdown against
  the previous comparable row. First row: 31% CPU for 100 pages polling
  every second, 8.2 ms median poll. A load test never reaches the
  production database any more (its server gets an empty database URL).
- **Code review for speed (owner: "review all the code on its optimality"):**
  PR #46. Nothing in the game grows with input size (a table is 15 rows ×
  4 cells, at most 5 players), so the work went to what each click and page
  run costs: moves wait about 1 ms for storage instead of about 40 ms (Neon
  is written in the background), the code-update check costs about 1 µs
  instead of 0.6 ms per run, and the scoreboard is built in about half the
  time, with byte-identical HTML.
- **Leaderboards (owner: "Both"):** PR #45. The running score at a table, and
  clubs with a rating table. Checked with AppTest (a club created through the
  home page form, a game finished, its table and results screen) and in
  headless Chromium on a local server with Postgres at 1300px and 390px: home,
  club page and results, no sideways scrolling; creating a club, starting a
  game from it and leaving it returns to the club.
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
- **Tests:** on Python 3.9 with Streamlit 1.48, all 279 pass but these are
  skipped: one step (a typed-in club name, which AppTest 1.48 cannot send), the
  9 database tests, which need a test database (CI has one), and the 7 network
  tests, which need Streamlit 1.67's packages (CI has them). On 3.8, 227 pass
  and 52 are skipped (9 need a database or psycopg; the others need
  Streamlit). On 3.13 with Streamlit 1.67, all pass but the 9 database
  tests. 9 server tests (`test_server.py`: HTTP statuses for every refusal,
  the limit on new games per client and behind a proxy, a server fault
  answered with `retry` without the token in the log, the live connection's
  pushes (only new chat, no echo of the app's own move), a closed game
  reported once, connections closed with 1012 after a code update, one store
  until the code changes, a page joining a game made through the API, and
  `streamlit run abaka_server.py` serving the page and the API). 18 API tests (`test_api.py`: complete games for 2 and 5
  players online and on one device through the API only, every preview
  matched by the move it describes; what a seat and an outsider see, tokens
  never in a state, outdated and out-of-turn moves, a seat taken back, picks,
  reactions and chat, a web move seen by an app, the shared game never
  changed by drawing a state, club games, malformed requests, languages, and
  `docs/API.md` naming every operation and error). 7 PR tool tests (`test_pr_tool.py`:
  remote URLs, and `merge` with a fake GitHub: a required job not started
  yet, a failing job, a branch behind `main`, a conflict). 24 reaction and
  celebration tests (`test_reactions.py`: a reaction is not a move, aimed
  reactions, the rate limit, never saved, which throws bring which effect
  (wild jokers included), effects at the throw and not at the move, none for
  the starting throw, row, School and column bonuses, a crossed-out bonus,
  rematch, and the screens through the app: bubbles, bigger fireworks shown
  once as the dice land, a bonus banner in Russian queued after the throw's,
  escaped names). 10 chat tests (`test_chat.py`: not a move, anyone seated, cleaned
  and cut, the rate limit, deleted at game over and after a rematch, not
  saved, and two screens through the app with hostile text). 6 picked-dice tests
  (`test_shown_dice.py`: picks are shown but are not a move, only the
  player whose turn it is picks, a reroll right after a pick, the other
  screen through the app). 4 baseline tests
  (`test_loadtest_baseline.py`: rows read back, a slowdown flagged, only
  comparable rows compared). 11 club tests
  (`test_clubs.py`: ratings, the running score, club tables, saving, the
  club pages through the app). CI runs them on 3.13 with
  Streamlit 1.67 and a Postgres service, and on 3.8. The suites: 21 database
  tests (`test_postgres.py`: the Postgres repository's contract, background database writes, where games are saved, the secret's name, a dropped
  connection, an unreachable database, a store on Postgres, the mirrored
  files and their import), 13 lifecycle tests (`test_lifecycle.py`), 3 name tests (`test_names.py`: Markdown escaping,
  invisible characters, hostile names through the real app), 5 clone tests (`test_clone.py`: same game as
  `deepcopy`, nothing mutable shared, previews identical), 6 language tests (`test_i18n.py`: every t() text has a
  Russian version with the same placeholders, room errors, plurals, per-thread
  language), 15 saving tests (`test_saving.py`, including writes outside the
  lock and a retired store), 26 room tests (`test_rooms.py`: a full two-player game,
  rematch, 3-5 player rooms, starting early, leaving the waiting room, moves
  from outdated pages),
  20 move-preview tests (`test_moves.py`, with the most points: the total's
  change, ties, a bonus earned or already closed, and the page drawing the
  best option bold), 10 tests for the owner's requests
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

## Decision log

**2026-11-20: the API over the network (Claude Code, PR #59)**

- The owner said "Go ahead" for step A2 of item 25.
- One process serves the pages and the API (`abaka_server.py`, Streamlit
  1.67's `st.App` with two routes). Separate servers would each hold games in
  memory and would need to tell each other about every move (Stage 3 work).
  In one process they share the `RoomStore` as they are.
- The live app is not switched. Cloud keeps running `abaka_ui.py`, with its
  `st.cache_resource` registry unchanged; only the code that makes the stores
  moved, to `server/stores.py`. The reasons:
  - The registry's key is its function's module and source. Moving it would
    make a second registry at the next update. Old pages would keep the old
    store while new pages used a new one, the failure of 2026-11-16.
  - Cloud cannot serve an app anyway (item 25, stage B).
- Under `abaka_server.py` the registry is a module made at run time, not an
  `st.cache_resource`:
  - the API's routes run outside any script run, where Streamlit warns about
    a missing ScriptRunContext;
  - uvicorn imports the entry file as a module, so a cached function there
    would be keyed apart from the pages' copy;
  - a module without a file is never unloaded by Streamlit's watcher or by
    `code_version`.
- One endpoint for every operation (`POST /api/v1`), rather than a URL per
  operation: the messages are the API's own, and the same ones travel over
  the WebSocket.
- HTTP statuses still follow the codes (404, 409, 422, 429...), so proxies,
  logs and HTTP clients read them correctly.
- Pushes, rather than apps polling `seen`:
  - A phone keeps one connection open instead of asking every second.
  - The server checks `seen` for each watched game four times a second. That
    costs about a microsecond in the store, plus a hop to a worker thread.
  - The store has no change notifications yet. They would replace the check,
    with no change for apps.
- Store calls run in worker threads. In ASGI mode Streamlit serves the pages
  on the same event loop, and a store call can wait for the database (Neon
  waking up takes seconds).
- The routes are made once, at start, so after a code update applied in place
  they would run old code against new stores. Each request therefore loads
  the current code (`code_version`) and imports `server/http.py` again. Live
  connections from older code close with 1012, so apps reconnect to the new
  code. A deploy on a host of our own restarts the process anyway.
- `abaka_ui.py` reloads `code_version` if the loaded one does not list
  `server/`. That module is never reloaded itself. After an update pulled while
  no page was open, it would not notice later changes to `server/stores.py`,
  which the live app now uses.
- The limit on new games is per client address (10 in 10 minutes, as per
  browser on the web). A proxy hides addresses, so
  `ABAKA_CLIENT_ADDRESS_HEADER` names the header to trust; it is only set on a
  host whose proxy writes that header.
- Not done yet: cross-origin requests (CORS; apps do not need them), and
  limits on connections per client.

**2026-11-20: preparing for apps on Android and iOS (Claude Code, PR #58)**

- The owner asked to start preparing the code base for Android and iOS. The
  plan is Backlog item 25; this PR is its first step, which needs no owner
  decision: the game as JSON, for any client.
- A thin client, with the server as the referee, rather than the rules in the
  app.
  - The owner changes the rules often (items 19, 20, 23 in one day). With the
    rules on the server, a change reaches every app at once, with no store
    review.
  - Two copies of the rules, in Python and in the app's language, would drift
    apart.
  - Web and app players can share a table, because both use one `RoomStore`.
- Not the web page in an app wrapper:
  - Apple turns down apps that only repackage a website (App Review
    Guideline 4.2);
  - every tap would still be a Streamlit rerun;
  - Community Cloud's sleep would show in the app.
- `handle(request, store, clubs)` does not know how messages travel. The same
  JSON can go over HTTP or a WebSocket, and the tests play whole games
  without a server.
- The move previews (`moves.py`) and the texts (`i18n.py`) moved from
  `ui_components/` to `abaka/`. The API needs both, and the game package
  should not import the web page's package. Imports changed; the code did not.
- Error codes are few, chosen by what the app does next (`outdated`: draw the
  new state; `not_seated`: offer to rejoin; `refused`: show the message), not
  one per message. The messages are the store's own, translated as on the web.
- A move must name the `version` it was chosen on. In the store that is
  optional, but a double tap on a phone is the usual case, so the API
  requires it.
- A state is drawn for one seat. Someone with only the code sees what the
  invite page shows, as on the web. Tokens never appear in a state.
- A second rematch tap answers with the new game, as the web does, instead
  of an error.
- Left out of protocol 1, because they live in Streamlit modules: the rules
  text and the reaction labels. Adding them later keeps protocol 1.
- Found while planning, from Streamlit 1.67's source:
  - `st.App(script, routes=[...])` serves extra routes next to the app, and
    `streamlit run` picks it up from the main file. So the API can run in the
    web app's process and share its store: step A2.
  - Uvicorn would import the main file as a module, so Streamlit would key
    its `st.cache_resource` registry apart from the script's. The registry
    has to move out of `abaka_ui.py` first; that is part of A2.
- Python 3.13 with Streamlit 1.67 now runs on this machine from a scratch
  folder (Notes for this machine). The full suite passed there before CI ran:
  two of the last three CI failures were 1.67 differences.

**2026-11-19: the gold option on the live app (Claude Code, PR #57)**

- After PR #56 went live, the best option was bold but not gold.
  - In Streamlit 1.67, pills are `role="radio"` buttons with
    `data-variant="pills"` and no `data-testid`.
  - The rule matched only 1.48's `data-testid="stBaseButton-pills"`. The
    `stBaseButton-pills` ids I had found in the 1.67 frontend belong to its
    other buttons, not to the pills.
- The rule now matches any bold pill that is not picked, as each version
  marks it: `data-testid="stBaseButton-pillsActive"` in 1.48,
  `aria-checked="true"` in 1.67.
- Checked before merging. The rule, injected into a headless browser's copy
  of the live page, turned the best option gold and left the others grey;
  nothing changed on the server. It also behaves as before on 1.48.
- PR #56's first CI run failed in its new page test: AppTest 1.67 gives pill
  options as text, 1.48 as protos. The test reads both. The app code was not
  at fault, and nothing was merged until CI passed.

**2026-11-19: the option with the most points (Claude Code, PR #56)**

- "Most points" is what the move adds to the player's total now: the total
  after the trial move the preview already makes, minus the total before.
  - That is the number on the option, except when the move also earns a row
    or column bonus. The highlight is the true best, so those options show
    their bonus ("Sum · 11 · bonus +52"), or a highlighted "Sum · 11" next to
    "Four of a kind · 28" would look wrong.
  - It is points, not strategy. Sum adds every die, so it ties with a full
    house or a straight and beats a pair, two pairs or three of a kind until
    the Sum row is full. Four of a kind, Abaka and the royal full house beat
    it with their +20/+50. A bonus a School payment gives up is not counted:
    the confirm button already warns about it.
- On a tie every option with the most is highlighted, instead of choosing
  between them: which row to keep free is the player's call.
- The pill labels are Markdown in both Streamlit versions, so a bold label
  is the hook for the gold style (`:has(strong)`). No position or label text
  is matched, and the tests still pick options by position.

**2026-11-19: effects as the dice land (Claude Code, PR #55)**

- The owner set new rules for the effects (Backlog item 23).
  - They come at the throw, not when the move is written.
  - Abaka and the royal full house: bigger fireworks on the first roll,
    fireworks after a reroll.
  - A straight, a full house or four of a kind on the first roll: sparkles.
  - Sparkles for any bonus written.
- A throw is judged by what the dice make, read the way scoring reads them
  (a joker showing 1 is wild), not by what the player writes.
  - Where the dice make several, the biggest effect wins. Five of a kind is
    also four of a kind and a full house, so Abaka on the first roll gets
    the bigger fireworks, which include a rain of sparkles, rather than two
    effects at once.
- "Any type of bonus" is read as the bonus cells in the rules' Bonuses
  section: row bonuses (School and combinations) and column bonuses (I, II,
  III).
  - The +20 and +50 inside Four of a kind, Abaka and the royal full house
    are part of those rows' scores, and are celebrated at the throw.
  - A completed row or column whose bonus is crossed out ("✕") earns
    nothing, so it brings no sparkles.
- The effect waits 0.45 s, the dice's spin, so it plays as the dice land
  instead of giving the result away while they still spin.
- Each page queues its effects: one that arrives while another plays starts
  when it ends. For example, a full house thrown and written at once shows
  the sparkles, then the bonus.
- Banners moved from the middle of the screen to its lower part, because at
  the throw the dice are on screen, and on a phone the middle is where they
  are. A banner is now as wide as its text; it used to wrap at half the
  screen.
- Found while checking: bursts waiting for their turn showed as glowing
  dots, because their animation's first frame applied during the delay
  (also before this change). They now stay hidden until they fire
  (`animation-fill-mode: forwards`).
- The starting throw brings nothing: it is not a turn and never scores.

**2026-11-19: CI required for merging (Claude Code, PR #54)**

- The owner asked to enforce passing checks before a merge. Before, only
  `tools/pr.py` waited for CI; GitHub itself would have merged a pull
  request with failing or unfinished CI (for example from its website).
- Branch protection on `main` now requires the two CI jobs, "App on Python
  3.13 (as on Streamlit Cloud)" and "Engine on Python 3.8", from the GitHub
  Actions app (so no other app can report them), and that the branch is up
  to date with `main` ("strict"). "Include administrators" was already on, so
  nobody can bypass it. Every other protection setting was kept (read back
  and compared).
- Strict, because two agents ship on the same day: a pull request tested
  against an older `main` could pass its checks and still break `main` once
  combined. The cost is one more CI run (about 2 minutes) when `main` moved.
- `tools/pr.py merge` does that run itself: it brings `main` into the branch
  on GitHub (`update-branch`, a merge commit, only if the branch is still the
  commit CI tested), waits for CI on the combined code and merges exactly
  that commit. On a conflict it stops and says to rebase (AGENTS.md step 5).
- It also waits for both jobs by name. It used to stop waiting when every
  check run it could see had finished, which could happen before the
  second job had started.
- Renaming a CI job now blocks every merge until the protection names the
  new job; `tests.yml` and AGENTS.md say so.
**2026-11-19: in-game chat (Claude Code, PR #53)**

- The owner asked "is it hard to add a chat during the game? The chat should
  be deleted once the game is over". Not hard: it follows the reactions
  (PR #52), kept in the room's memory and polled through the same value.
- Deleted by the move that ends the game, in the store, so every screen
  loses it at once and no page can keep it. It is never saved, so a server
  restart or a code update also deletes it, mid-game. That fits the
  owner's rule (the chat is not part of the game) and keeps players' words
  out of the database.
- Online only, while the game is played: the waiting room has no chat (the
  game screen has), and a same-device game has no one to write to.
- Messages are drawn as plain text: `html.escape` in the card, `i18n.md()`
  in the toast; cleaned like names, so invisible and right-to-left
  characters cannot disguise them. No other moderation: the game is for
  friends who share a link.
- A small form (text box and Send) instead of `st.chat_input`, which pins
  itself to the bottom of the page and does not sit inside a card.
  The form sends in its `on_click`, so a message costs one page run.
- The load-test row was flagged against the previous one (25% → 28% CPU,
  6.1 → 7.7 ms median poll). `main` measured at the same time gave 32% and
  8.5 ms, and earlier rows were 29-31%, so the previous row was a low
  outlier, not a change from the chat (the poll path is the same).

**2026-11-19: reactions and fireworks (Claude Code, PR #52)**

- The owner asked for poker-style reactions, fireworks for Abaka, a smaller
  effect for a straight, four of a kind or 1-1-1-2-2 on the first roll, and a
  chat that is deleted when the game ends. Reactions and effects are this PR;
  the chat is the next.
- Same pattern as the picked dice (PR #48): events live in the room's memory,
  not in the game and not saved; a reaction changes what pages poll but not
  `room.version`, so it never makes a move look outdated. Pages poll
  `(version, picks, latest event id)`; a page still on the old code polls a
  pair, which never equals the triple, so it redraws once with the new code.
- Effects are worked out by the store in `_act`, from the game before and
  after the move, so every mode (online, same device) gets them with no
  per-browser logic, and they cannot be faked from a page.
- "Smaller effect" for 1-1-1-2-2 is read as the royal full house scored in
  Full house on the first roll, as the owner listed it with first-roll
  combinations. Abaka gets fireworks on any roll. A crossed-out row gets
  nothing.
- Ids come from the clock in milliseconds, not a counter, so a room loaded
  again after leaving memory (events are not saved) cannot reuse an id a page
  has already shown.
- Shown once: a page that opens a game (a reload, a new session) skips what
  happened before; a redraw carries an animation on from where it was
  (negative animation delay) rather than starting it again. The effects are
  CSS only, over the page with `pointer-events: none`, and the sparks are
  hidden for people who ask their system for reduced motion.
- With 3+ players a reaction can be aimed at one player; it is still shown to
  everyone (a table talk, like poker), marked "→ you" for its target.
- On your own turn a page polls every 3 s, so a reaction can take up to 3 s
  to reach the player whose turn it is; the poll rates were not changed.

**2026-11-19: picking a club's players (Claude Code, PR #51)**

- A Streamlit select box that accepts new options (`accept_new_options`,
  available in 1.48 and 1.67) does both things the owner asked in one
  field, so names already in the club are picked with their exact spelling.
- The list comes from `ClubStore.member_names` (no club copy), most recent
  players first, so regulars are at the top.
- The select box has its own key (`<key>-pick`), because Streamlit keeps a
  widget's value by key and would clash with the text box the same field
  shows before the club's first game.
- AppTest 1.48 cannot send a typed-in option, so that step of the app test
  is skipped there and runs on 1.67 in CI; the browser check covered it.
**2026-11-19: Abaka as a full house, pairs in every combination (Claude Code, PR #50)**

- The owner asked for both while PR #49 was going live. Abaka counts in
  Full house as the sum of all five dice, like any full house, without
  the Abaka bonus (+50 stays with the Abaka row) and without the 1-1-1-2-2
  bonus.
- "All of above could be a pair" needed no code change: the Pair rule
  already took the highest number appearing at least twice. Tests now hold
  it for every combination.
**2026-11-19: four of a kind counts as two pairs (Claude Code, PR #49)**

- The owner could not write joker 6, 6, 6, 6, 1 in Two pairs and called it an
  error. The engine was doing what the 2025 scoring code said (two different
  numbers); the rules text, written from that code in PR #12, said "two
  different pairs". The owner's report is taken as the rule: four of a kind
  is two pairs.
- Five of a kind follows the same rule (two pairs out of four of its dice),
  since it holds four of a kind. A Pair already accepted three, four or five
  of a kind, and Three of a kind accepted four or five, so Two pairs now
  matches them.
- Full house was left as it is (exactly three and two; five of a kind is not
  a full house): the owner did not ask, and that is a separate rule.
**2026-11-19: picked dice on the other screens (Claude Code, PR #48)**

- The owner asked that the other players see exactly which dice are rerolled.
  Both moments are shown: the picks as they are made, and the dice that were
  rolled after the reroll. A player who picks and rerolls within a second
  would otherwise show the others nothing between two polls.
- Picks are kept in the room, not in the game: they are not part of the
  rules, and a saved game does not need them.
- A pick does not change the room version, which guards moves against
  outdated pages. If it did, a fast tap on Reroll after picking a die (on a
  phone, before the page is redrawn) would be refused as outdated and the
  picks lost. Pages poll a separate value (`seen`: version and pick count)
  instead.
- A page still on the old code after the update polls with the old version
  number, which never equals the new tuple, so it redraws once with the
  new code.
- After a reroll the spin follows the dice that were rolled, not the faces
  that changed, so a die that lands on the same number spins too, on every
  screen, the player's own included.
**2026-11-19: load-test baseline (Claude Code, PR #47)**

- The owner said "Keep going" after the speed review. The next Stage 1 step
  that needs no owner decision was the load-test baseline; seat protection
  waits for the owner's choice of scheme.
- The baseline is a table in the repository (`docs/LOADTEST.md`), not a CI
  job: CI machines vary from run to run and are much noisier than the
  numbers being compared. Rows are compared only with rows from the same
  machine, Python, Streamlit and load.
- The load is the worst case a page asks for (a poll every second) with 100
  pages, the size Stage 0 measured, so the first row lines up with those
  numbers (PR #27: 33% CPU, 10 ms median; now 31%, 8.2 ms).
- Two runs back to back on the same code gave the same CPU, polls and
  median poll, and page runs 76.9 and 77.6 ms, so a 25% threshold flags real
  changes, not noise.
- "+changes" after the commit means the app's files differed from it; other
  files (tools, docs) do not count.
- Found while doing it: the load test passed its environment to the server,
  so with `ABAKA_DATABASE_URL` set (as for the database tests against Neon)
  its 200 games would have gone to the production database. The server now
  gets an empty URL, which also makes the app ignore any secrets file.
**2026-11-19: code review for speed (Claude Code, PR #46)**

- The owner asked to review all the code for optimality and optimize it.
- Big-O: the engine works on fixed sizes (15 rows × 4 cells per player, at
  most 5 players, 5 dice), so no algorithm there grows with anything. The
  store's per-request work was already constant: a poll costs about 1 µs, a
  page's room read about 2 µs (measured). What remained was constant costs
  repeated on every click or page run, measured on a 5-player game half
  played:
  - a move with Neon: 40 ms (median; p90 47 ms), almost all of it the
    database round trip. Now about 1 ms (median; p90 1.9 ms): the database
    is written in the background, behind the file copy;
  - the code-update check: 588 µs per run, listing and checking every file.
    Now about 1 µs: it looks at most every 2 s;
  - the scoreboard: 844 µs. Now 393 µs: tooltips, classes and the
    highlighted cells are worked out once instead of per cell. Its HTML is
    byte-identical (compared on 10,986 boards: 2-5 players, every phase,
    picked moves, both languages);
  - a club's results screen copied the whole club twice (0.3 ms each with
    200 games); now it copies one game.
- One lookup (`models.SCHOOL_NUMBERS`, `is_school`) replaces seven string
  tests of the row name, in the engine and the UI.
- Not changed, with reasons: move previews (`score_options`, 0.25 ms) try
  each move on a copy of the game, which keeps them exact; a page run's
  remaining time is Streamlit building widgets, not our code; the 17 KB of
  styles sent with every full run are compressed on the websocket, and
  moving them to a static file would depend on how Streamlit Cloud serves
  files.
**2026-11-19: leaderboards (Claude Code, PR #45)**

- The owner asked for "a smart fun way to keep leaderboard" and chose layers
  1 and 2 of the proposal: the running score at a table, and clubs.
- Player names are typed freely, so a global table could not tell people
  apart. Clubs keep the table inside a group of friends, where a name is
  enough; names match ignoring capitals and spaces.
- Elo over every pair of players, rather than points for places, so 3-5
  player games count fairly and beating strong players counts more. K is
  scaled by 1/(players - 1), so a game moves a rating by at most 32 however
  many play. Abaka is luck-heavy, so ratings should move slowly; K can be
  lowered later without losing data (the games are kept).
- The room reports a finished game through a callback (`on_game_over`),
  so `RoomStore` knows nothing about clubs, and a club failure never stops a
  game. Clubs reuse the repository classes in their own table and folder,
  so they are in Neon on the live app with no new setup.
- The running score lives in the room (its results), so it needs no club
  and survives restarts like the game.
- No rules changed. Not done: records, titles and a hall of fame (layer 3).
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
