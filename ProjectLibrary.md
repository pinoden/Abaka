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
pip install -r requirements-dev.txt && python -m playwright install chromium-headless-shell   # for the website check
python tools/website_check.py                         # the live website in a real browser (after every merge)
python tools/website_check.py --serve abaka_ui.py     # the same check on a local server (Streamlit 1.67)
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
python tools/export_texts.py                          # the phone app's texts from abaka/i18n.py (mobile/src/texts.json)
```

The phone app (`mobile/`, React Native with Expo; its own guide is `mobile/AGENTS.md`):

```bash
cd mobile && npm ci                                   # its packages (Node 26)
npx expo start                                        # development server: Expo Go on a phone, or w for the web
npx expo start --android                              # the app on Android's emulator (start the emulator first: mobile/AGENTS.md)
npx tsc --noEmit && npx expo lint                     # typecheck and lint
ABAKA_SERVER=http://127.0.0.1:8501 npm test           # its API client against a running abaka_server.py
npm test                                              # only its connection against a scripted server (no game server)
npx expo export --platform web                        # its web build, in mobile/dist (not committed)
python tools/app_check.py --serve                     # (from the repository) the web build in headless Chromium
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
  - The website check (`tools/website_check.py`) runs from it too.
    - Install Playwright with `uv pip install -p $S/venv313/bin/python -r
      requirements-dev.txt`.
    - Playwright 1.65.2 uses Chromium build 1255, already in
      `~/Library/Caches/ms-playwright`.
    - For `--cleanup` on the live app, pass the database URL with
      `$S/neonenv.py`, or any wrapper that reads `.env.local` without
      printing it.
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
- The phone app: Node 26.13 and npm 11 are here (nvm). The app is checked
  through its web build in headless Chromium (`tools/app_check.py`, from the
  scratch Python 3.13; CI runs it), which runs all of the app's code; only the
  drawing underneath differs from a phone's.
  - Google's Android emulator is here (2026-11-21, Backlog item 27), without
    Android Studio. mobile/AGENTS.md ("On Android") has its commands and what
    it shows that the web build cannot.
    - Java 21 (Eclipse Temurin) in `~/Library/Java/JavaVirtualMachines`,
      found by `/usr/libexec/java_home -v 21`. Only the SDK's own tools
      (`sdkmanager`, `avdmanager`) need it, not Expo.
    - The Android SDK in `~/Library/Android/sdk`, where Expo looks without
      `ANDROID_HOME`: the command-line tools, `platform-tools` (adb), the
      emulator, and the image `system-images;android-36;google_apis;arm64-v8a`
      (Android 16 with Google's apps and fonts, no Play Store), 5.7 GB in all.
    - One virtual phone, `Pixel_7_API_36`: 411 x 914 dp, 2 GB of memory, the
      Mac's keyboard types into it. `adb shell wm density 480` makes it a
      phone 360 wide; `adb shell wm density reset` puts it back.
    - To install it again: the command-line tools and Java from their sites
      (checksums checked), then `sdkmanager --licenses`, `sdkmanager
      "platform-tools" "emulator" "<the image>"` and `avdmanager create avd -n
      Pixel_7_API_36 -k "<the image>" -d pixel_7`.
  - Xcode is not here (only its command line tools), so there is no iPhone
    simulator. Xcode comes from the Mac App Store with the owner's Apple ID.
  - The server for the app is `abaka_server.py` on port 8501, from the scratch
    Python 3.13. It listens on every interface, so Expo Go on a phone on the
    same Wi-Fi reaches it, and so does the emulator (`src/lib/server.ts` uses
    the Expo server's host).
  - The server allows 10 new games per address in 10 minutes. Repeated local
    runs of the app's tests hit it (`too_fast`); restart the server.
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
| `abaka/effects.py` | What reactions and effects say, for the web page and for apps: a reaction's emoji and label, who sent it to whom, an effect's banner. No Streamlit |
| `abaka/rules.py` | The rules players read, in English and Russian: Markdown for the web page, blocks for apps (`rules_blocks`). No Streamlit |
| `ui_components/effects.py` | Reactions (buttons, bubbles) and celebrations (fireworks, sparkles), drawn from the room's recent events |
| `abaka/standings.py`, `ui_components/chart.py` | How the players stand, for one viewer: each row's difference from the opponent (the board's column behind the "Row differences" switch) and every total after each move (`engine.score_history`, the chart under the board). For the web page and apps |
| `abaka/races.py`, `ui_components/races.py` | The races for the shared bonuses (cells left in column I and II, rows two players are one cell from), for the web page and apps; and their box under the dice |
| `ui_components/dice.py`, `move_selection.py`, `scoreboard.py`, `rules.py` | Dice, move picker, score table, the rules dialog (its text is `abaka/rules.py`) |
| `ui_components/style.py`, `.streamlit/config.toml` | CSS and dice SVGs; theme colours |
| `tests/` | `unittest` tests |
| `mobile/` | The app for Android and iOS: React Native with Expo, TypeScript. Its own guide: `mobile/AGENTS.md` |
| `tools/export_texts.py` | The app's texts from `abaka/i18n.py`, into `mobile/src/texts.json` (committed) |
| `tools/app_check.py` | The app's web build played in headless Chromium against a real server (CI), and against a server with steered dice for what cannot be thrown on purpose |

`abaka/` is the game without its web page: the rules, the rooms, the clubs,
saving, the move previews, the texts and the API. Everything in it runs on
Python 3.8 without Streamlit. `abaka_ui.py` and `ui_components/` are the web
app, one client of it; the app for phones in `mobile/` is another (Backlog
item 25).
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
      - Only a combination the thrower can still write counts: its row needs
        a free cell (a tester, Backlog item 32). Abaka or the royal full house
        with its row (Abaka, Full house) already full brings tears instead: a
        grey-blue gloom, a rain of 💧 and "Abaka, and nowhere to write it 😭".
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
- A game's code alone opens nothing (owner, Backlog item 31, PR #72). Every
  room also has a secret `key` (8 characters of the code alphabet, saved with
  the room), and players share the full code `CODE-KEY`
  (`rooms.full_code`; "K7M2Q-8XJ4PN2R"):
  - `store.join`, `store.reclaim` and `store.resume_local` take the key, and
    `store.opens(code, key)` checks it. A missing or wrong key gets the same
    "Game not found" as a game that does not exist.
  - The URL carries `?room=CODE-KEY` (`rooms.split_code` reads it, a typed
    full code, or a pasted link). It is the link to share with the players,
    and never holds the seat token. `?room=CODE` alone shows "This link is not
    complete", the same whether or not the game exists.
  - The seat token stays in `st.session_state`. After a refresh, the player
    opens the link and clicks their name; `store.reclaim` issues a new token
    and the old tab loses control. So anyone with the link can still take a
    seat by its name, as before; only the code alone no longer can.
  - The game's code (without the key) is not secret: it shows in the top bar.
    The waiting room shows the link and the full code, the game menu the full
    code, for another device.
  - A game saved before keys gets one the first time it is loaded, saved at
    once (a version bump), so later loads keep it.
- Same-device games are rooms too (`store.create_local`, `room.local`): every
  seat belongs to one token, the turn check is skipped, and nobody can join.
  They get a code and a link like online games. Opening that link (a reload,
  a dropped session, another device) or typing the full code on the home page
  continues the game at once (`store.resume_local`, no seat to pick).
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
- A game's code alone opens nothing (Backlog item 31): `join`, `rejoin`,
  `resume`, and `state` and `seen` without a seat need the game's `key` (as
  `key`, or the full code in `code`), and a wrong one is `not_found`. Every
  state carries the key, since only someone in the game gets a state
  (`api._admit`). The live connection's watch keeps it for its pushes.
- A move carries the `version` of the state it was chosen on. If the room has
  changed since, it is refused as `outdated`, like the web's buttons.
- Texts come in the request's `lang` (en/ru). The call sets it for its thread
  and puts the thread's language back afterwards.
- `rules` gives the rules in the request's language as blocks (`abaka/rules.py`):
  headings, paragraphs with `**bold**` marks and the table of combinations. The
  web page shows the same text as Markdown.
- Reactions and effects come with their words (`abaka/effects.py`), for the
  player the state is drawn for:
  - a reaction's `emoji`, `label` and `who` ("Ann → you");
  - an effect's `title` and `text` ("Abaka!", "You · first roll").
  The web page shows the same words. `info.reaction_list` lists the reaction
  buttons, so an app need not know the reactions.
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
  - A connection the server cannot go on serving (a push that fails) is
    closed with 1011, so the app reconnects. It is never left open without
    news.
  - Answers are written so that they can always be sent (`as_json`): text
    UTF-8 cannot carry goes out as `\u` escapes.
  - Any reply on a live connection that carries the watched game's state for
    the watching seat (a move, a `state` request) counts as sent: only later
    changes are pushed. A client hands such replies to its screen
    (`mobile/src/lib/api.ts`); the first version of that client did not, and
    its screen missed the last moves of a game (Decision log, 2026-11-20).
- The app (`mobile/`) is the first client:
  - It sends every request over the live connection, so its web build needs no
    cross-origin permission from the server.
  - One connection serves every screen and stays open between them. A screen
    that stops watching sends `unwatch` (a request of the live connection,
    like `watch`).
  - It reconnects after a drop and watches its game again.
  - A screen gets its game's states in order. The answer to `watch` is a fresh
    start: after a server restart a game's counts of picks and events begin
    again (they are not saved).
  - A connection can die without closing. When nothing has arrived for 20 s
    the app asks the server whether it is there (`seen`, or `unwatch` when
    nothing is watched). No answer within 8 s, or a request never answered,
    and the connection is replaced.
  - A request that got no answer within 15 s fails as `offline` and is never
    made later.

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
- The foot of the play card shows the races for the shared bonuses while the
  game is played (Backlog item 30). `abaka/races.py` works them out, and the
  API sends the same words to apps (`state.races`):
  - a small table of the cells each player has left in column I and II, while
    that column's bonus is undecided, someone can still earn it, and someone
    has written in it. Each player is a row (the viewer is "You", in indigo)
    and each column a column, so a name has the width of the row with any
    number of players (PR #71). The fewest are bold. A player whose bonus there is
    crossed out is grey, with ✕: completing the column first still closes it
    for the others;
  - a gold line for one move when that move caught up in a row: its player
    came to one cell from the row's bonus where another player already was,
    and one of them can still earn it ("Bob caught up in Sum: one cell to the
    bonus for you and Bob."). It comes from `engine.last_move`, so every
    screen shows it until the next move (Backlog item 32; until then every
    such row stayed listed);
  - column III is each player's own (`bonus.py`), so it is no race.
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
- The website must keep working while the apps are built (owner,
  2026-11-20; AGENTS.md, "The website must keep working"):
  - `tests/test_website.py` checks it in a real browser in CI;
  - `python tools/website_check.py` checks the live app after every merge;
  - a broken live app is reverted at once.
- Code that is not about drawing the web page goes in `abaka/`, not in
  `ui_components/`, so the apps' API can use it too (Backlog item 25).
- The phone app's texts follow the same rule: English in `t("...")`, Russian
  in `abaka/i18n.py`, then `python tools/export_texts.py`
  (`tests/test_mobile_texts.py` fails otherwise).
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
  `rooms.clean_name` also removes control and invisible format characters,
  and halves of surrogate pairs, which UTF-8 cannot carry.
- Text a player types (a name, a chat message, a club's name) reaches a store
  only through `rooms.clean_name` or `rooms.clean_message`. A new kind of
  typed text goes through them too.
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
merged in PR #37. Item 16 (2026-11-18) is in PR #39. Item 17 (2026-11-19) is in PR #45. Item 18 (2026-11-19) is in PR #48. Item 19 (2026-11-19) is in PR #49. Item 20 (2026-11-19) is in PR #50. Item 21 (2026-11-19) is in PR #51. Item 22 (2026-11-19) is in PR #52 and PR #53. Item 23 (2026-11-19) is in PR #55. Item 24 (2026-11-19) is in PR #56 and PR #57. Item 25 (2026-11-20, apps for Android and iOS) is in progress: steps A1 and A2 are in PR #58 and PR #59, where the app's code lives in PR #60, the app's technology and first screens in PR #61, its reactions, effects and chat in PR #64, its clubs in PR #65, and its rules screen in PR #66. Item 26 (2026-11-21, a full test round) is in PR #62 and PR #63. Item 27 (2026-11-21, a phone simulator on this Mac) is in PR #67. Item 28 (2026-11-21, the app's dice) is in PR #68. Item 29 (2026-11-23, a "Mr. Lucky" reaction) is in PR #69. Item 30 (2026-11-23, the races for the shared bonuses, from a tester) is in PR #70 and PR #71. Item 31 (2026-11-25, a game opens only with its key) is in PR #72. Item 32 (2026-11-26, a tester's second round) is in PR #73 and PR #74. Requests 1-4 came from the
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
      - The owner chose the first layer (2026-11-25, Backlog item 31,
        PR #72): a game's link and full code carry a secret key, and its
        code alone opens nothing. Still open: protecting one seat from
        another player who has the link.
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
    PR #59), the app's code lives in `mobile/` in this repository (PR #60), it
    is React Native with Expo (C1), its first screens are in PR #61 (C2,
    first part), reactions, effects and the chat in PR #64 (C2, second
    part), clubs in PR #65 (C2, third part), the rules screen in PR #66
    (C2, fourth part), and what the Android emulator showed in PR #67 (item
    27). Stages B and D wait for the owner's decisions below.
    > "Let's start preparing the code base to expand on android/ios"
    >
    > "Go ahead" (step A2)
    >
    > "React native" (C1)
    >
    > "Make sure that the websites version won't brake while developing the
    > app transform"
    - The website keeps working at every step (AGENTS.md, "The website must
      keep working"):
      - CI checks it in a real browser (`tests/test_website.py`);
      - every merge is checked on the live app (`tools/website_check.py`);
      - a broken live app is reverted at once;
      - app work goes in its own files;
      - the website stays on Streamlit Cloud until the owner moves it.
    - The plan, one PR per step. Tick a step here when its PR is merged.
    - The app is a thin client: the server keeps the game and the rules, and
      the app shows what it is told and sends the player's moves. So the rules
      stay in one place (the owner changes them often), and players on the web
      and in the app can share a table.
    - A native client is the safer path to the App Store than the web page in
      a wrapper: Apple asks apps to do more than repackage a website (App
      Review Guideline 4.2).

    **Where the app's code lives (the owner agreed, 2026-11-20)**

    > "Do we need separate (GitHub) projects for an app folder and a website
    > app?" … "Add to the app plan"

    - In this repository, in `mobile/`, next to the website and the server,
      not in a GitHub project of its own. The reasons are in the Decision log
      (2026-11-20, the phone app in this repository).
      - The folder is made with the app (C2). Its name does not depend on the
        technology (C1).
      - Not `app/`: in this file "the app" usually means the website.
    - `mobile/` holds everything the app needs to build, with its own
      `package.json` and lock file. The root `package.json` stays Neon's
      config, and `.gitignore` already ignores `mobile/node_modules/`.
    - The website never runs it:
      - Streamlit Cloud runs `abaka_ui.py` and installs only
        `requirements.txt`, so a merge that changes only `mobile/` changes
        nothing the website runs. It still gets the website check after the
        merge, like every merge.
      - A server image for the host of stage B leaves `mobile/` out.
    - CI:
      - the two required jobs keep running on every pull request, the app's
        included, so no app change merges with the website broken;
      - the app gets a job of its own (its checks and tests, and its API
        client against a real `abaka_server.py`), required like the other two;
      - no `paths` filters on required jobs: GitHub blocks a merge while a
        required job has not reported, and a workflow a filter skips never
        reports.
    - The app's own texts come from `abaka/i18n.py` (C2). A script exports
      them into `mobile/`, the export is committed, and CI fails when it is
      out of date, so building the app needs no Python.
    - `mobile/AGENTS.md` holds the app's commands and conventions, and
      AGENTS.md points to it, so both agents read it (PR #61).
    - One repository, separate releases. The website changes on every merge;
      the app only when the owner publishes it, and old versions stay on some
      phones for months. So the server keeps answering every app version in
      use: protocol 1 never changes (`docs/API.md`, Versions).

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
      - The owner (2026-11-25): "we need to select host. I also don't mind
        moving away from Streamlit for a web version." The comparison given
        to the owner that day (prices from the hosts' pages and reviews of
        2026-11; check again before paying):

        | Host | A month | For this server |
        |---|---|---|
        | Fly.io | about $3.69 (512 MB, Virginia) | With one machine, a deploy stops the old one before starting the new: never two servers at once. Pay as you go; deploys from GitHub Actions with a token |
        | Railway | $5 (includes $5 of use) | Deploys from GitHub by itself; during a deploy the old copy runs on, and how it treats live connections then is not documented |
        | Render | $7 (512 MB) | Deploys from GitHub by itself; the old copy runs up to 30 s next to the new |
        | Hetzner (US) | about $20 | Prices about tripled in 2026; a server to look after |

      - Recommended: Fly.io in Virginia (`iad`, next to Neon's us-east-1).
        Games live in the server's memory, so two copies at once could each
        take moves (the rule "two servers writing the same games would lose
        moves"); and it costs least. Without Streamlit a plain Python server
        fits 512 MB; Streamlit would want about 1 GB.
      - Recommended for the web version: the phone app's web build (the
        same code as the app, already playing every feature), served by the
        same server. It needs a layout for wide screens.
      - Waiting for the owner: the account (a card) and a domain.
      - The move keeps the website working. The new host first runs next to
        Streamlit Cloud, with its own Neon branch, and passes
        `tools/website_check.py --url <new host>`. Then the owner decides when
        players switch: the new address, and the production database.
      - Streamlit Cloud stays up until then, as the way back.

    **Stage C: the app**

    - [x] C1. The app's technology: React Native with Expo (SDK 58), in
      TypeScript. Decided by the owner ("React native"), PR #61.
      - One code base for iOS and Android, built in Expo's cloud.
      - Updates to the app's code without a store review.
      - Expo is the way React Native's own documentation starts an app; the
        owner had it as the recommendation.
    - [ ] C2. The screens, as on the web. English and Russian: the game's
      texts come from the server (`info`, move labels, errors); the app's own
      texts reuse `abaka/i18n.py`, exported into `mobile/` (see "Where the
      app's code lives"). In parts:
      - [x] First part, PR #61: the app plays a whole game, on one device or
        online.
        - Home: continue a game played on this device, a game on one device,
          an online game, open a game by its code.
        - The invite: join, or take a seat back.
        - The waiting room: the code to share, Start now, Leave.
        - The game: starting throw, dice to pick and roll again, Score and
          Cross out with the server's previews and the best option in gold,
          and the board with the move's preview and the last move.
        - The results, and Play again.
        - The language switch.
        - Checks: its API client plays whole games against a real server,
          and its web build plays in headless Chromium (CI, "Phone app
          (Expo)").
      - [x] Reactions, fireworks and sparkles, and the chat. PR #64.
        - The eight reaction buttons, with "Send to" one player at a table of
          three or more. A reaction is a bubble at the top of every screen.
        - Fireworks, bigger fireworks and sparkles with their banner, as the
          dice land, by the website's rules (Backlog item 23).
        - The chat card, and a bubble for another player's new message.
        - The words come from the server with each event, in the player's
          language (`abaka/effects.py`), so the website and the app say the
          same.
        - Checked in the browser: a website player and an app player at one
          table, and an Abaka on the first roll with steered dice.
      - [x] Clubs: the club page, club games and the player picker. PR #65.
        - Home: the clubs this device opened, create a club, open one by its
          code.
        - A club's screen: its table (medals, rating and its last change,
          games, wins; average and best from 480px), the latest games, a new
          club game on one device or online, and the club's code to share.
        - The club's players as names to tap instead of typing: on one
          device each tap fills the next empty box (or empties the box the
          player is in); online, the host's name; on the invite of a club
          game, the players not at the table yet.
        - The results of a club game: each player's rating and how it moved,
          and a "Club table" button. The running score says "club game".
      - [x] The rules screen. PR #66.
        - The rules text moved from `ui_components/rules.py` to
          `abaka/rules.py`, and the API's new `rules` operation serves it as
          blocks (headings, paragraphs with **bold**, the table of
          combinations). The website's text is unchanged, byte for byte.
        - The app's "How to play" opens from home, and from a game with the
          "?" at the top, which also leads to the language switch there.
      - [x] The app on Android's emulator (Backlog item 27), PR #67: it
        plays there, and what only a phone showed is fixed (the gesture bar,
        the status bar, the keyboard, the board on a phone 360 wide).
      - [ ] The app's own look on a phone: its icon and name (D1), the
        status bar's colours, haptics on a roll, and a check on real phones
        in Expo Go (an iPhone too: no iPhone simulator here).
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
      app. The token on the device is already personal, and since item 31 a
      game's code alone opens nothing, but anyone with the game's link or full
      code can still take a seat by its name.
    - [ ] Optional: games on one device without a network, by running the
      rules in the app (a port of the engine, checked against games recorded
      from the Python engine). Until then, every game needs the server.

    **Owner decisions still open**

    - The host for the server, its budget, and a domain.
    - The store accounts, the app's name and its identifier.
    - Whether games on one device must work without a network.
    - How seats are protected beyond the game's key (also in item 11).

26. **A full test round, with a new model.** Done: the server's side in
    PR #62, the app's side in PR #63.
    > "Keep going, also test everything again while of Fable"
    - Everything was run again, and all the code was read again (Status has
      the list).
    - New kinds of test: malformed and hostile requests thrown at the API, and
      many phones on the live connection at once.
    - Found and fixed in PR #62:
      - half of a broken character in a name or a chat message, sent through
        the API, broke that game for everyone at its table;
      - a connection the server could not go on serving stayed open without
        news;
      - one game the database would not take stopped the import of all the
        saved games after it;
      - the test of a club player's name typed in was skipped on every
        Streamlit version.
    - The website was not at risk: the first two need the API, which the live
      app does not serve yet.
    - Found and fixed in the app, PR #63:
      - "‹ Home" in the waiting room gave up the seat, so a host who went to
        the home page closed the game their friends had the code of;
      - after a server restart, a phone did not show what happened in its game
        until the next move;
      - a connection that died without closing was never replaced;
      - "Continue a game" offered games that had ended or no longer existed;
      - in a tie for the first turn, the throw of a player who was out of the
        next round vanished from the screen.

27. **A phone simulator on this Mac.** Android's emulator: done in PR #67.
    The iPhone simulator needs Xcode, which the owner installs with their
    Apple ID.
    > "Is there a phone simulator for mac?" … "Set up android one"
    - Google's Android emulator with an Android 16 phone (a Pixel 7), without
      Android Studio; Notes for this machine says what is where.
    - The app plays in Expo Go there against the game server on this Mac,
      and mobile/AGENTS.md ("On Android") has the commands.
    - Checked there: a game on one device, an online game with a second
      player through the API (picked dice, a reaction, the chat), the bigger
      fireworks with steered dice, Android's back button, the app in the
      background while the other player moves, the network switched off and
      on, and Russian on a phone 360 wide.
    - Found there and fixed (the web build cannot show them):
      - the end of every page sat under Android's gesture bar (an iPhone's
        home indicator too), and could not be scrolled clear of it;
      - a reaction's bubble was drawn over the status bar (an iPhone's notch
        too);
      - on Android the keyboard covered the box being typed in: the game's
        code at the foot of home, the chat, a name on an invite;
      - on a phone 360 wide (many Android phones) the second player's bonus
        column was cut off the board, with nothing to say the board scrolls.
    - The keyboard's key now does what the form's button does where a form is
      one box and a button (a game's code, a club's code, a club's name,
      joining): the keyboard covers the button on a phone.

28. **The app's dice looked ugly.** Done in PR #68.
    > "Dice look ugly" (a screenshot of the app's dice on the emulator)
    - The pips sat at 20% and 80% of the die, close to its rounded corners,
      where the website puts them at 28% and 72%. And they sat off centre,
      right of and below the middle: a pip placed inside a die is measured
      from inside its border, which the app did not take off (more on a
      picked die, whose border is thicker).
    - The app's dice are now drawn as the website's: the same grid, centred
      with either border. Checked side by side with the website's own dice in
      Chromium, on the same roll as in the owner's screenshot.

29. **A "Mr. Lucky" reaction.** Done in PR #69.
    > "add one more suggested comment "прушник" - "mr lucky" or something like
    > that in English"
    - A ninth reaction button, "😎 Mr. Lucky" ("😎 Прушник" in Russian), right
      after "🍀 Lucky!", on the website and in the app.
    - The app takes its buttons from the server, so an app already on a phone
      shows it too, without an update.

30. **The races for the shared bonuses, next to the dice.** Done in PR #70;
    a row per player since PR #71.
    > (a tester, through the owner) "Чего еще не хватает (но это уже из
    > необязательного) - так это подсказок/ предупреждений в борьбе за премии.
    > Например, при борьбе за столбец - сколько осталось клеток до столбца у
    > тебя и у соперника. Поскольку тут сразу таблицу не видно, надо крутить
    > вниз, считать, то это было бы удобно. Или еще, например, предупреждение,
    > что тебя догнали по строчке, если у тебя осталась одна клеточка до
    > премии"
    - Under the dice, on the website and in the app, while a game is played:
      - "Cells to the bonus": how many cells each player still has to fill in
        column I and in column II, while that bonus is still to be won;
      - a gold line when two or more players are one cell from the same row's
        bonus ("One cell to the bonus for you and Bob: Sum."). Whoever fills
        it first decides that bonus, so this is the warning that you have been
        caught up, or have caught up.
    - Column III is no race: each player earns their own.
    - No rule changed: the box counts what the board shows.
    - Each player is a row of the table (PR #71). With players as columns,
      four or five names were cut to "Test…" or "T…", on a phone and in the
      website's play card on a desktop, so nobody could tell whose count was
      whose.

31. **A game opens only with its key.** Done in PR #72.
    > "For 4 I think it's important to fix it now, the link should be somewhat
    > encrypted, one shouldn't be able to enter a game just knowing the code"
    - Every game has a secret key of 8 characters. Its link and its full code
      carry both: `?room=K7M2Q-8XJ4PN2R`, "K7M2Q-8XJ4PN2R".
    - The code alone (on a screen, said aloud, guessed, an old link) opens
      nothing: no names, no join, no taking a seat. A wrong key is answered as
      a game that does not exist.
    - On the website, in the app and through the API. Games saved before get
      a key when they are next opened; their players' open pages switch to the
      full link by themselves.
    - Still possible, as before: someone who has the link takes a seat by
      tapping its name (item 11's next layer, if the owner wants it).

32. **A tester's second round.** Done: the row warning, tears and the teasing
    reactions in PR #73; the board's row differences and the score chart in
    PR #74.
    > (a tester, through the owner) "Играл в абаку с Пашей, видел нововведения.
    > По строчкам, мне кажется, немного не то, о чем я говорил. Я имел ввиду
    > предупреждение, которое появляется на один ход, когда кто-то догоняет и
    > подвешивает премию. А так получается очень много инфы, которая все время
    > висит и замыливается. Ещё интересно, если бы справа были видны разницы
    > сумм по строчкам, чтобы понимать, сколько проигрываешь в строчке (это уже
    > капризы, конечно). Ещё можно сделать как в шахматах график набора очков
    > по ходам - две (по количеству игроков) кривые. Интересно было бы. И Паша
    > заметил, что все мемы позитивные, ругательных не хватает. И кстати, когда
    > выкидываешь абаку или королевский фулл, а строчка уже вся занята,
    > фейерверки неуместны, или их надо дополнять плачем)"
    - [x] The row warning for one move (PR #73): it shows when a move catches
      up, that is, its player comes to one cell from a row's bonus where
      another player already was, and stays until the next move. Before, every
      row two players were one cell from stayed under the dice all game. The
      column table under the dice is unchanged.
    - [x] Tears instead of fireworks (PR #73): Abaka or the royal full house
      thrown when the thrower's row for it is already full. Sparkles too need
      a free cell in their row.
    - [x] Teasing reactions (PR #73): 🤬 Damn! / Блин!, 🙄 Seriously? /
      Серьёзно?, 😤 Unfair! / Нечестно!, 🤡 Clown / Клоун, after the nine
      there were.
    - [x] The board: each row's difference from the opponent, as a last
      column (PR #74): the player's points in the row (its three cells and its
      bonus) minus the opponent's, or the best of the others' at a table of
      three or more; +12 green, −8 red. Behind a "Row differences" switch above
      the board, off at first. On one device it is read for whose turn it is.
    - [x] A chart of the scores by move under the board (PR #74): a line per
      player, from move 0 to the latest, on the website and in the app.

## Status (2026-11-26)

- **A tester's second round, second part (Backlog item 32):** PR #74.
  - The board's column of row differences, behind a switch, on the website
    and in the app. The chart of scores by move under the board.
  - The engine keeps every player's total after each move
    (`score_history`), saved with the game; the API sends it
    (`game.history`) and each seat's differences (`differences`). Protocol 1:
    fields added.
  - Checked:
    - 13 new Python tests (`tests/test_standings.py`): the differences row by
      row, with two and three players, on one device, and adding up to the
      totals' difference in random whole games; the history after every move,
      saved, shared by a clone, and for a game saved before it; the API; the
      board's HTML (every row as wide as the header); the switch on the page.
    - The app's browser check turns the switch on and off and finds the chart.
    - Headless Chromium, the website's board with the column and the chart,
      English at 1300px and Russian at 390px: two players fit at 390 (the
      board's font and gaps narrow on a phone while the column is on); three
      or more scroll inside the card, as before. The app at 390: the board
      scrolls so the column shows when it is switched on.
    - Every Python test on 3.13 (345; the 8 database tests skipped, no
      Postgres here), 3.9 (343) and 3.8 (343); the app's 47 tests, typecheck,
      lint and all seven browser flows.
    - The website check now also finds the chart and switches the column on;
      with the chart left out on purpose it failed, on both widths.
  - Load-test row: no slowdown (26% CPU, 6.8 ms median poll, page run 97 ms
    against 91).

- **A tester's second round, first part (Backlog item 32):** PR #73.
  - The row warning now comes for the one move that caught up, on the website
    and in the app (the server sends it: the app needs no update). In random
    whole games it was shown 65 times, each time for the move just made.
  - Abaka or the royal full house with its row already full: tears instead of
    fireworks, on every screen and in the app; sparkles only for a
    combination its row has room for.
  - Four teasing reactions: 13 buttons, five rows on a 390px phone, four on a
    desktop, no sideways scrolling (English and Russian, headless Chromium).
  - Checked:
    - 7 new Python tests, 1 new app test; the row tests rewritten for the new
      rule. With the free-row check switched off, three of them failed, and so
      did the app's browser check.
    - The app's browser check now throws Abaka with both players' Abaka rows
      full (steered dice): tears on both phones, "Абака, а записать некуда 😭"
      on the Russian one, no fireworks.
    - The website's tears in headless Chromium at 390px and 1300px.
    - Every Python test on 3.13 (332; the 8 database tests skipped, no
      Postgres here), 3.9 (330) and 3.8 (330); the app's 47 tests, typecheck,
      lint and all seven browser flows; 60 random games.
  - Load-test row: no slowdown (29% CPU, 7.2 ms median poll).


- **A game opens only with its key (owner: "one shouldn't be able to enter a
  game just knowing the code", Backlog item 31):** PR #72.
  - Every game has a secret 8-character key, saved with it. Its link
    (`?room=CODE-KEY`) and its full code carry it; the code alone opens
    nothing, and a wrong key is refused exactly as a game that does not exist.
  - The website: the invite page needs the full link ("This link is not
    complete" for a code alone, whether or not the game exists); "Open game"
    takes a full code or a pasted link; the waiting room shows the key under
    the code; the game menu shows the full code, for another device; a seated
    page puts the full link in the address bar.
  - The API: `join`, `rejoin`, `resume`, and `state`, `seen` and `watch`
    without a seat need the key; every state carries it (docs/API.md).
  - The app: the home page opens a game by its full code or link only; the
    waiting room shows and shares the full code; the device keeps each game's
    key with its token.
  - Checked:
    - 16 new tests (`tests/test_game_keys.py`), and the app's test of the
      full code (`mobile/tests/codes.test.ts`). With the key check switched
      off, 27 of them failed.
    - The website check opens an online game by its code alone (nothing of
      the game shows), then by the full link. The app's browser check types
      the code alone (refused), then the full code; and the website's full
      code into the app.
    - At 360px, English and Russian: the waiting room's code and key, the
      page for a code alone, the menu's full code. No sideways scrolling.
    - Every Python test on 3.13 (327; the 8 database tests skipped, no
      Postgres here), 3.9 (325) and 3.8 (325); the app's 46 tests, typecheck,
      lint and all seven browser flows; 60 random games.
  - No load-test row: the machine was busy (load average 5 to 10). Main and
    the branch measured in turn, two rounds each: median poll 27.5 and 279.7
    ms on main, 15.3 and 15.4 on the branch; page runs alike (164 to 189 ms).
    The poll path did not change.
  - Also that day: the hosts compared for Backlog item 25, B1 (Fly.io
    recommended); waiting for the owner's account and domain.


- **The race box, a row per player (owner: "Run it", the emulator check of
  Backlog item 30):** PR #71.
  - Checked on Android's emulator (Pixel 7, Android 16), in Russian, against
    `abaka_server.py` on this Mac, with the other player through the API:
    - an online game in which both players were one cell from the Sum bonus:
      the counts and the gold line under the dice; the phone wrote Sum, the
      line went and the bonus banner played; the other player crossed out a
      cell of column I, and within 3 s the phone showed his count grey with ✕
      and the note;
    - "😎 Прушник" among the reactions (PR #69);
    - a phone 360 wide: the box fits, its title on two lines.
  - Found there: **with five players the names were cut** to "Test…",
    "Ale…", "Test…", "Test…", "Test…" (each name had a fifth of 60% of the
    box). The website's play card cut them too, to "T…" on a desktop, where
    five players leave the play card a third of the screen.
  - Now each player is a row, with "Column I" and "Column II" as the columns.
    A name has 40% of the box whatever the number of players, so "Александра"
    fits on a 360px phone. The box has a line per player instead of one per
    column: two players racing for both columns take the three lines they
    took before, five take three more. The server's data did not change: the
    website and the app only lay it out the other way.
  - Checked:
    - a new page test: five players, each a row with the whole name, the
      viewer marked, the fewest bold, a crossed-out bonus grey. It fails on
      the old layout;
    - the app's browser check measures a long name ("Александра") in the
      box on its 360px phone, in Russian. With the name cell squeezed to 15%
      it failed: "cut short by 50px";
    - on the emulator at 360 wide, with five players and with two, and in
      headless Chromium (website, 390px and 1300px, English and Russian): no
      name cut, no sideways scrolling;
    - every Python test on 3.13 (311; the 8 database tests skipped, no
      Postgres here), 3.9 (309) and 3.8 (309); the app's 45 tests, typecheck,
      lint and all seven browser flows.
  - Load-test row, the first since PR #68 on a quiet machine: no slowdown
    (29% CPU, 7.4 ms median poll).


- **The races for the shared bonuses (a tester, through the owner; Backlog
  item 30):** PR #70.
  - Under the dice while a game is played, on the website and in the app: the
    cells each player has left in column I and II, and a gold warning for rows
    where two or more players are one cell from the bonus.
  - `abaka/races.py` works it out, in the viewer's language. The website draws
    it (`ui_components/races.py`). The API sends it with every state (`races`;
    protocol 1 kept, a field added), so the app shows the same words.
  - Checked:
    - 14 new tests (`tests/test_races.py`). Among them, random whole games in
      which every race shown matches the board, and a row race shown is
      decided by the next completion of that row (58 times in those games).
    - Five deliberate breakages of the logic: four failed the tests. The
      fifth (ignoring that a column was already decided) changes nothing
      anyone sees, since nobody can still earn a decided column.
    - The website check looks for the box after the first move, and on the
      other screen of the online game. With the box switched off, it failed.
    - The app's browser check (all seven flows) looks for it too, and on the
      other phone reads 14 cells left in column I for the player who moved.
      The app's client tests check every move's counts against the board.
    - In headless Chromium at 390px and 1300px, in English and Russian, the
      website and the app's web build: no sideways scrolling.
  - No load-test row: another project's tests kept the machine busy (72 to 90
    of 100 polls answered, where a quiet machine answers 97 to 100). Main and
    the branch, measured in turn from two equal copies, three rounds each,
    gave the same: 27% and 26% CPU, median poll 9.6 and 8.2 ms, page run 130
    and 112 ms. The box itself costs about 0.3 ms of a page run with five
    players, and polls never draw it.
  - Not checked on the emulator, which was not running. The web build runs
    the same code. (Checked there afterwards, in PR #71, which found the
    names cut with five players.)

- **A "Mr. Lucky" reaction (owner, Backlog item 29):** PR #69.
  - "😎 Mr. Lucky" / "😎 Прушник", the ninth reaction, after "Lucky!".
  - Checked on a local server in headless Chromium, in English and Russian:
    the nine buttons wrap onto three rows on a 390px phone and on a desktop,
    no page scrolls sideways, and the bubble reached the other screen.
  - No load-test row: another project's browser tests kept the machine
    busy. The change adds a name to two lists, which no poll or page run
    loops over more than once.

- **The app's dice (owner: "Dice look ugly", Backlog item 28):** PR #68.
  - The pips crowded the dice's rounded corners (20% and 80% of the die; the
    website uses 28% and 72%), and sat off centre: about 1.5 dp right of and
    below the middle, 3 dp on a picked die. Both came from `Dice.tsx`.
  - The pips' places are now worked out in `src/lib/dice.ts` from the
    website's grid (`ui_components/style.py`), with the die's border taken
    off. A new test checks every face is centred with either border; it fails
    without that correction.
  - Checked on the emulator on the owner's roll (6, 1, 1, 6 and the joker's
    4), with a die picked, next to the website's dice drawn by Chromium: the
    same.
  - The app's 45 tests, typecheck, lint and the seven browser flows pass. The
    website is unchanged.

- **A phone simulator on this Mac: Android's emulator (owner: "Set up android
  one", Backlog item 27):** PR #67.
  - Installed without Android Studio: Java 21, Google's command-line tools,
    the emulator and an Android 16 phone (Notes for this machine). Downloads
    checked against their published checksums.
  - The app plays there in Expo Go, against `abaka_server.py` on this Mac.
    Driven through adb (taps, typing, uiautomator's view of the screen), with
    a second player through the API:
    - a game on one device: names typed with the phone's keyboard, the
      starting throws, a roll, two dice picked and rolled again, the best
      option in gold, a row crossed out (the button warns of both bonuses),
      the rules and back, Android's back button home;
    - an online game: the other player's picked dice lifted on the phone
      about a second later, a reaction and a chat message as bubbles (the
      emoji in Android's own colours), an answer written in the chat;
    - the bigger fireworks for an Abaka on the first roll (steered dice):
      bursts, sparkles and "Abaka! You · first roll", gone when they end;
    - the app in the background for 45 s while the other player moved and
      wrote: back through the app switcher, the move and the message were on
      the screen within about 3 s;
    - Wi-Fi and mobile data off for 40 s: "Connecting…" within 3 s, and 10 s
      after they came back the other player's move and message were there;
    - Russian on a phone 360 wide: home, the game, the rules.
  - Found there, and fixed (all in `mobile/`; the website is unchanged):
    - **The end of every page sat under Android's gesture bar** (an iPhone's
      home indicator too): the "Last move" line and "How to play" could not
      be scrolled clear of it. A page now ends the bar's height higher.
    - **A reaction's bubble was drawn over the status bar** (on an iPhone it
      would sit behind the notch). Bubbles and fireworks now keep to the safe
      area.
    - **On Android the keyboard covered the box being typed in**: the game's
      code at the foot of home was typed blind, and the chat box hid behind
      the keyboard. Android 15 and later no longer shrink an app's window
      for the keyboard, and the setting the app had for it works on iOS
      only. The page now shrinks to the space above the keyboard, and
      Android scrolls the box into view.
    - **On a phone 360 wide the second player's bonus column was cut off**,
      with nothing to say that the board scrolls (many Android phones are
      360 wide). Two players' cells now narrow to fit (22 instead of 26);
      with three to five players the columns still scroll. The browser check
      now measures the board on its 360px phone too, and failed on the board
      as it was ("16px wider than the screen").
    - Where a form is one box and its button (a game's code, a club's code,
      a club's name, joining), the keyboard's key says Go and does what the
      button does: the keyboard covers the button.
  - Checked: the app's 42 tests (4 new), typecheck, lint, all seven browser
    flows; every Python test on 3.13 (296; the 8 database tests skipped, no
    Postgres here) and on 3.8 (294). No load-test row: nothing the website
    runs changed.
  - Not checked: an iPhone (Xcode is the owner's to install), a real phone.

- **The rules screen in the phone app (owner: "Keep going", Backlog item 25,
  C2, fourth part):** PR #66.
  - The rules text moved from the website's Streamlit module to the game
    package (`abaka/rules.py`). The website shows it as before: the same
    Markdown, byte for byte, in both languages.
  - The API's new `rules` operation (protocol 1 kept: an operation added)
    gives the rules as blocks an app draws itself: headings, paragraphs with
    their bold parts, and the table of combinations. A test checks that the
    table names every combination as the board does, in both languages.
  - The app's "How to play" screen opens from home and from a game's "?".
    Back from it, the game is where it was.
  - The game's top bar showed "Одно уст…" and lost the game's code in
    Russian. It now shows the website's icon for the kind of game (👥 or 🌐)
    and the code. The language switch moved from the game's bar to the rules
    screen, one tap away, as the website keeps it in the game's menu.
    - The browser check measures the bar with the widest code there can be
      ("WWWWW"), on a 360px phone in Russian. Measured this way, the bar
      before this change cut the code by 20px at 390px.
  - The app asks for the rules in the language it shows, even when the
    connection has not switched yet. A screen's request could go out before
    the app had changed the connection's language (React runs a screen's
    effects before the app's).
  - Checked: the app's 38 tests, typecheck, lint, Expo's 20 project checks,
    all seven browser flows; every Python test on 3.8, 3.9 and 3.13 (296, none
    skipped). Load-test row: no slowdown (34% CPU, 8.8 ms median poll).
  - Next: the app's own look on a phone (icon, name, haptics) needs the
    owner's decisions on the name and icon (D1), and a check on a real phone.

- **Clubs in the phone app (owner: "Keep going", Backlog item 25, C2, third
  part):** PR #65.
  - The app now does what the website's clubs do: create a club, open one by
    its code, its table and latest games, club games on one device or
    online, the ratings on a club game's results, and the club's players
    offered as names to tap.
  - A club made in the app is the website's club too: the browser check
    opens it on the website and finds the same table.
  - Found and fixed on the server, for the website too: in an online club
    game, a player already at the table could join again under another
    spelling ("ann" next to "Ann"). The club then counted one member twice,
    playing against herself (shown on a scratch store before the fix: one
    member, two games, from one game). Joining is now refused with "Each
    player needs a different name.", as a game on one device already was.
  - Checked in headless Chromium at 390px (`tools/app_check.py`, seven
    flows):
    - a club made in the app; a game on one device for it, played to its end
      through the API; the ratings on its results and "club game" in the
      running score; the club's table and latest game;
    - the next game's names tapped from the club's players;
    - an online club game: the invite (in Russian) offers only the player not
      at the table, and a seated player typed again is refused;
    - the same club's table on the website.
    - With the invite offering players already at the table, the check
      failed at that step.
  - The browser check now starts a server of its own in CI (`--serve`): a
    client may start 10 games in 10 minutes, and the app's client tests use 8
    on theirs.
  - The scan of the app's texts (`tests/test_mobile_texts.py`) read an
    escaped quote (`'the club\'s'`) as written, not as the app shows it. It
    reads it as the app does now.
  - The app's 37 tests, typecheck, lint and Expo's 20 project checks pass;
    every Python test passes on 3.8, 3.9 and 3.13 (295, none skipped).
  - The load-test row is flagged (33% CPU and 8.5 ms median poll, against
    24% and 6.3 ms). Main measured the same as the branch, round after round
    (Decision log), so the previous row was low.
  - Next: the rules screen, then the app's own look on a phone.

- **Reactions, effects and the chat in the phone app (owner: "Keep going",
  Backlog item 25, C2, second part):** PR #64.
  - The app now has what an online game has on the website:
    - the eight reaction buttons, with "Send to" one player at a table of
      three or more; each screen shows a reaction as a bubble for 3.5 s;
    - fireworks, bigger fireworks and sparkles with a banner, as the dice
      land, queued so two never overlap, by the rules of Backlog item 23;
    - the chat card (deleted by the move that ends the game), and a bubble
      when another player writes.
  - The words come from the server with each event (`abaka/effects.py`), in
    each player's language: "Ann → you", "Abaka! You · first roll". The web
    page takes its words from the same place.
    - Its HTML is unchanged: 31,920 bubbles and banners were compared before
      and after, byte for byte (hostile names, both languages, every viewer).
  - Checked in headless Chromium at 390px (`tools/app_check.py`, six flows):
    - two phones: a reaction from one is a bubble on the other, in Russian
      there; a chat message arrives in the other's chat, and as a bubble;
    - **a website player and an app player at one table**: each sees the
      other's dice, move, reaction and chat message;
    - an Abaka on the first roll with steered dice: bigger fireworks on both
      phones, "Abaka! You · first roll" on one and "Абака! Test Ann · с
      первого броска" on the other, gone when they end.
    - With reactions not drawn and the banner's title swapped on purpose,
      three of the flows failed, each naming what was missing.
  - The app's 28 tests, typecheck, lint and Expo's 20 project checks pass;
    every Python test passes on 3.8, 3.9 and 3.13 (294, none skipped).
  - No load-test row: the machine was busy with another project, and the
    tool's flag was the machine's (Decision log). Main and the branch
    measured the same.
  - Not checked on a real phone: how the fireworks look and run there.
  - Next: clubs in the app, then the rules screen.

- **The test round in the phone app (Backlog item 26):** PR #63.
  - Found by reading the app's code, then shown in its web build in Chromium
    before anything was changed:
    - **"‹ Home" in the waiting room gave up the seat.** A host who tapped it
      closed the game, and the code friends had led nowhere. It only goes
      home now; the game stays under "Continue a game". Leave and Cancel give
      the seat up, as their names say.
    - **After a server restart, a phone missed what happened until the next
      move.** A game's counts of picked dice and events are not saved, so they
      begin again, and the app took the game's news for older than what it
      showed. Seen with picked dice: one phone showed dice 0 and 2 picked, the
      other still only die 0. The same would have hidden chat messages after
      every deploy.
    - **"Continue a game" offered finished games**, and games closed on
      another device. It now asks the server, as the website's home page does.
    - **In a tie for the first turn, the throw of the player who was out
      vanished** (the website keeps it, dimmed: Backlog item 16).
  - Found by reading, and shown with a scripted server (below):
    - **A connection that dies without closing** (a phone that changes
      networks) was never replaced: no more news, and every tap failed after
      15 s. The app now asks the server whether it is there when nothing has
      arrived for 20 s, and replaces a connection that does not answer.
    - **A screen that closed late stopped the next screen's game.** While one
      screen slides over another, the old one closes after the new one has
      opened. Each screen now stops only its own watch.
  - Changed with them: one connection for every screen. Leaving a game's
    screen sends `unwatch` instead of closing the connection, so going home
    and into another game needs no new connection (on a phone network, a
    handshake each time).
  - Tests:
    - `mobile/tests/connection.test.ts`: the connection against a scripted
      server in the test's own process, 12 cases (a restart, states out of
      order, a connection that goes silent, a request never answered, a
      connection that never opens, screens closing late). No game server
      needed. 11 of them fail on the connection as it was; the twelfth
      guards a case it already handled. 38 runs in a row passed, 18 of them
      six at a time with every core kept busy.
    - `tools/app_check.py` now also goes home and back from the waiting room
      and from a game, plays a game to its end through the API and looks for
      it on the home page, and makes a tie for the first turn with **steered
      dice**: a real game server inside the check's process, whose dice the
      check chooses. Each new step fails on the app as it was.
    - The server's `unwatch` has its test (`tests/test_server.py`).
  - Checked: the app's 18 tests, typecheck, lint, Expo's 20 project checks,
    its web build in Chromium; every Python test on 3.8, 3.9 and 3.13.
    Load-test row: no slowdown (24% CPU, 6.3 ms median poll).
  - Not explained: one run of the two-phone check took 11 s instead of 4. It
    did not happen again in 34 runs, with step timings switched on.
  - Still not checked on a real phone.
  - Next: reactions, effects and the chat in the app.


- **A full test round with a new model (owner: "test everything again",
  Backlog item 26):** PR #62.
  - Run again, all passing:
    - every test on Python 3.8, on 3.9 with Streamlit 1.48, and on 3.13 with
      Streamlit 1.67, Chromium and Postgres;
    - 852 random complete games with rule checks after each of their 134,010
      moves, on 3.8 and 3.9, the scoreboard drawn 8,656 times;
    - 5 whole games of the text version, wrong answers included;
    - the phone app: typecheck, lint, Expo's 20 project checks, its 5 client
      tests, and its web build played in Chromium;
    - the website checks on both local servers and on the live app.
  - New in this round:
    - Malformed and hostile requests at the API, from a scratch tool: the
      first 30,000 met the bug below 45 times; 420,000 more after the fix
      met no server fault. A 4,000-request version is now a test.
    - 16 kinds of broken message over the network (not JSON, binary, 1 MB,
      5,000 arrays deep...): after the fix each is refused or answered, and
      the connection goes on answering.
    - The live connection under load (Known issues, Capacity).
  - All the code was read again: the engine, rooms, clubs, saving, the API,
    the server, the pages and the app.
  - Found and fixed:
    - **Half of a surrogate pair** (`"\ud83d"`: JSON can carry it, UTF-8
      cannot) in a name, a chat message or a club name, sent through the API.
      Checked on a local server:
      - the game's web page showed an error box with a traceback;
      - the other players' live connections brought no more news, and a new
        connection was closed as soon as it watched the game;
      - HTTP answers were a plain 500;
      - the game could not be saved to Postgres.
      Anyone with a game's code could do it. Names and messages now lose such
      characters like the invisible ones, and the server's answers can always
      be sent.
    - **A connection the server cannot go on serving** is now closed (code
      1011), so the app reconnects. Before, a failed push left it open and
      silent.
    - **The import of saved files into the database** stopped at the first
      game the database refused. It goes on now, and gives up after 3
      failures in a row (an unreachable database).
    - **The club player's name typed in** (Backlog item 21) was tested
      nowhere: AppTest cannot send a typed-in option on Streamlit 1.67 either,
      so the step was skipped in CI too. The test now sends what a browser
      sends. With the name picker broken on purpose, it fails on 1.67.
  - Each fix has tests that fail without it.
  - Load-test row: no slowdown (28% CPU, 7.6 ms median poll).
  - The live app does not serve the API yet, so the website was not at risk.
  - Next: what the round found in the app (its own pull request), then
    reactions, effects and the chat in the app.


- **The app for phones: React Native with Expo, and its first screens (owner:
  "React native", Backlog item 25, C1 and the first part of C2):** PR #61.
  - `mobile/`: Expo SDK 58 (React Native 0.88), TypeScript, Expo Router.
  - It plays a whole game through the API, on one device or online:
    - home, the invite and the waiting room;
    - the starting throw and the turns;
    - the results and Play again;
    - English and Russian.
  - Its API client against a real `abaka_server.py` (`mobile/tests/`):
    - a 3-player game on one device and a 2-player online game, played to the
      end, every offered move written where its preview said;
    - the other player's screen getting each move pushed;
    - refusals, a seat taken back, an unreachable server.
    - 8 runs in a row passed after the fix below.
  - Its web build in headless Chromium at 390px (`tools/app_check.py`):
    - home in English and Russian;
    - a game on one device: two dice rolled again, the best option written, a
      row crossed out, both players' columns on the screen;
    - an online game between two phones (one in Russian): join by code, the
      starting throws, the same dice on both phones, the move on the other
      phone.
    - Proven to catch breakage: a misspelled move failed both games, naming
      the server's refusal; a board too wide for a phone failed the
      one-device game.
  - Expo's 20 project checks (`expo-doctor`), the typecheck and the lint
    (React's rules included) pass.
  - CI's new job "Phone app (Expo)" runs all of it on every pull request.
  - Not checked on a real phone: there is no simulator here. The web build
    runs all of the app's code; the owner can try it in Expo Go (README).
  - The website is unchanged. `abaka/i18n.py` got the app's three new texts,
    and `docs/API.md` now spells out a rule the server already had (Decision
    log). Load-test row: no slowdown (29% CPU, 7.6 ms median poll).
  - Next: reactions, effects and the chat; clubs; the rules screen; a check on
    real phones. Stages B and D still need the owner's decisions.

- **Where the phone app's code lives (owner: "Add to the app plan", Backlog
  item 25):** PR #60. In this repository, in `mobile/`, made with the app
  (C2). The plan lists the folder's rules:
  - its own `package.json`;
  - the CI jobs running on every pull request, plus a required job for the
    app;
  - the texts exported from `abaka/i18n.py` and checked;
  - a guide for agents in the folder.
  No code changed.

- **The website keeps working while the apps are built (owner, Backlog
  item 25):** PR #59.
  - `tools/website_check.py` plays the website in headless Chromium:
    - the home page in English and Russian, and where games are saved;
    - a game on one device: starting throw, roll, a die rolled again, the best
      option written, a row crossed out;
    - an online game between a desktop and a phone: join, the starting
      throws, a roll seen on the other screen, the turn passing, a chat
      message and a reaction;
    - no error box, no page error, no sideways scrolling on the phone.
  - CI runs it on every pull request (`tests/test_website.py`), on
    `abaka_ui.py` as Cloud runs it and on `abaka_server.py`. The app job
    installs Chromium and fails if the browser is missing.
  - Proven to catch breakage, on a scratch copy of the code:
    - with the most-points mark removed, both one-device games failed;
    - with the chat raising an error, the online game failed and the report
      named the error.
  - Locally on Streamlit 1.67 the whole check takes about 30 s per server.
  - AGENTS.md now has the rules: browser checks in CI, the live check after
    every merge, an immediate revert if the live app breaks, app work in its
    own files, and Cloud kept until the owner moves the website.

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
- **Tests:** on Python 3.9 with Streamlit 1.48, 343 run and 20 are skipped:
  the 9 database tests, which need a test database (CI has one), the 10
  network tests, which need Streamlit 1.67's packages, and the website
  checks, which need Streamlit 1.67 and Chromium (CI has them all). On 3.8,
  343 run and 65 are skipped (9 need a database or psycopg; the others need
  Streamlit). On 3.13 with Streamlit 1.67, Chromium and a test database, all
  345 run and none is skipped. 13 standings tests (`test_standings.py`: row
  differences with two and three players, on one device, adding up to the
  totals over whole games; the score history after every move, saved, cloned,
  and for games saved before it; the API; the board's HTML and the chart; the
  switch on the page). 16 game-key tests (`test_game_keys.py`: a
  key per game, saved, made once for older saved games; the code alone or a
  wrong key refused as a missing game in the store and the API; the key typed
  any way, or as a pasted link; the pages for a code alone, a wrong key and
  the full link; the home page's full code; the waiting room's key). 3 tests of the phone app's texts (`test_mobile_texts.py`: the export
  is current, every `t()` text in `mobile/src` has a Russian version, the
  scan reads both quotes). The phone app has its own 47 tests (`node --test`),
  1 of them of the full code (`mobile/tests/codes.test.ts`: typed, pasted as a
  link, or a code alone, read as the server reads them).
  8 against a real server (`mobile/tests/api.test.ts`: complete games on one
  device and online through its API client, pushes, reactions and chat with
  their words, a club game and its table, the rules in a request's own
  language, refusals, a seat taken back, the games to continue, an
  unreachable server). 14 against a scripted server
  (`mobile/tests/connection.test.ts`: a server restart, states out of order,
  connections that die silently or never open, requests never answered,
  screens closing late, each event handed over once, the chat gathered). 9 of
  what plays over the screen (`mobile/tests/shows.test.ts`: bubbles, effects
  that wait for the dice and for each other, tears, old news skipped). 8 of clubs on
  the screen (`mobile/tests/clubs.test.ts`: the table's rows, numbers rounded
  as Python rounds them, the latest games, the names offered and tapped). 4 of
  the score table's size (`mobile/tests/board.test.ts`: two players' columns
  fit every common phone width, down to 360). 3 of the dice
  (`mobile/tests/dice.test.ts`: every face centred whatever the border, the
  pips where the website puts them). CI
  also plays its web build (`tools/app_check.py`, with a server of its own). 2 website tests (`test_website.py`: `tools/website_check.py` in
  headless Chromium on `abaka_ui.py`, as on Cloud, and on `abaka_server.py`).
  12 server tests (`test_server.py`: `unwatch`; HTTP statuses for every refusal,
  the limit on new games per client and behind a proxy, a server fault
  answered with `retry` without the token in the log, the live connection's
  pushes (only new chat, no echo of the app's own move), a closed game
  reported once, text that UTF-8 cannot carry (cleaned, and never the end of
  a connection), a connection that cannot be served closed with 1011,
  connections closed with 1012 after a code update, one store
  until the code changes, a page joining a game made through the API, and
  `streamlit run abaka_server.py` serving the page and the API). 23 API tests (`test_api.py`: 4,000 malformed and hostile
  requests answered or refused, never a server fault; the rules as blocks, in
  both languages, naming every combination as the board does; events with their words
  for each player and language; complete games for 2 and 5
  players online and on one device through the API only, every preview
  matched by the move it describes; what a seat and an outsider see, tokens
  never in a state, outdated and out-of-turn moves, a seat taken back, picks,
  reactions and chat, a web move seen by an app, the shared game never
  changed by drawing a state, club games, malformed requests, languages, and
  `docs/API.md` naming every operation and error). 7 PR tool tests (`test_pr_tool.py`:
  remote URLs, and `merge` with a fake GitHub: a required job not started
  yet, a failing job, a branch behind `main`, a conflict). 28 reaction and
  celebration tests (`test_reactions.py`: a reaction is not a move, aimed
  reactions, the rate limit, never saved, which throws bring which effect
  (wild jokers included), tears for Abaka or the royal full house with its row
  full and sparkles only with room for them, tears drawn on the page, effects at the throw and not at the move, none for
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
  comparable rows compared). 12 club tests
  (`test_clubs.py`: ratings, the running score, club tables, a member once
  in an online club game, saving, the club pages through the app). 16 race
  tests (`test_races.py`: cells left in column I and II, a crossed-out
  column, column III left out, decided races gone, the row warning for the
  one move that caught up and who can still win it, three players, Russian, random whole
  games against the board and the bonus rules, the API, the page with
  hostile names, each player a row of the page's table). CI runs them on 3.13 with
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
  - The apps' live connection (`WS /api/v1/live`), measured on one M1 core
    with a scratch tool (2026-11-21, Python 3.13, Streamlit 1.67):
    - A connection watching a game where nothing happens costs about 0.4 ms
      of CPU a second, 7 times less than a page: 600 of them take 25% of a
      core.
    - 600 connections in 300 two-player games, each game making a move about
      every 0.75 s: 94% of a core. A move was answered in 7 ms (median) and
      reached the other player in 138 ms (256 ms at the 95th percentile).
    - 1,200 connections that busy are too many: moves answered in 0.4 s,
      pushes after 0.6 s. Nothing was lost.
    - The cost is the server looking at each watched game four times a
      second. Change notifications from the store would remove it (Stage 3).
- (Fixed in PR #28 and PR #30: memory only grew. Finished games stayed in
  memory for 7 days, and every code update left the previous store behind.)
- (Fixed in PR #28: the global lock was held across deep copies and file
  writes, so every poll and render waited behind any room's save.)
- **Security, "friends only":**
  - anyone with a game's link or full code can take any seat by its name;
  - (Fixed in PR #72: a game's 5-character code alone, which can be seen on a
    screen or guessed, let anyone join, take a seat or fill a waiting room. A
    game now opens only with its 8-character key as well: 40 bits, about 17
    years of a thousand guesses a second for one game.)
  - room creation was unlimited (now 10 per browser per 10 minutes, and
    rooms beyond 2,000 leave memory; a script opening new sessions is not
    stopped yet).
  - (Fixed in PR #29: player names reached Markdown unescaped, so a name
    could be a link or an image.)
  - (Fixed in PR #62: through the API, half of a surrogate pair in a name or
    a chat message broke that game's page and connections for everyone.)
  - Not limited yet: how many requests one live connection may send, and how
    many connections one client may open.
- The phone app has not run on a real phone yet, nor on an iPhone at all.
  It runs on Android's emulator here (Backlog item 27), where coming back from
  the background and a network switched off and on worked; a real phone's
  network that changes (Wi-Fi to mobile data) has not been tried.
  - In the emulator the bigger fireworks ran at about 30 frames a second
    (median 32 ms a frame, 18 ms of it drawing), while scrolling ran at 60.
    They put about 230 animated views on the screen. The emulator draws
    through the Mac, so whether a phone keeps up is for a real phone to say.
- The text version (`python -m abaka`), found in the test round of
  2026-11-21 and left as it is:
  - when players tie for the top score it names only the first of them as
    the winner;
  - a row name it does not know is answered with the bare name
    (`Error: 'SCHOOL 9'`).
  Whether the text version stays is an open decision (Backlog item 11).
- (Fixed in PR #32: Streamlit was unpinned and there was no CI. Expired and
  unreadable save files are deleted or quarantined since PR #30.)

### Roadmap

The scale-up plan is Backlog item 11, as a checklist.

Other ideas, not planned:
- a dark theme (the scoreboard CSS colours would need to follow the theme);

## Decision log

**2026-11-26: a tester's second round, second part (Claude Code, PR #74)**

- The row differences are behind a switch, off at first. The tester had just
  said the board area carried too much information, and asked for these
  "as a whim". The column also does not fit beside two players on a 360px
  phone, where the board was made to fit exactly (PR #67). On the website the
  switch lasts the session; in the app, the game screen.
- A row's points are its three cells and its row bonus, the way the total adds
  them up: the School rows' balance changes count as written. Against the best
  of the others with three or more players: "how much you are losing" is to
  whoever leads the row. With two players the rows and the column bonuses add
  up to the difference in totals, apart from the School penalty (a test checks
  this over whole games).
- On one device the column is read for the player whose turn it is, the
  player deciding. After the game nobody's turn is on, so it is not shown
  there.
- The chart's history lives in the engine, appended at the end of every move,
  because the game's totals cannot be rebuilt later from the board (the order
  of the moves is not kept). It is a tuple, so `clone()` shares it, as the
  other immutable fields. A game saved before starts its line at its next
  move; a made-up point at 0 would draw a jump.
- Drawn without a library on both sides: an inline SVG on the website (the
  lines stretch, the labels are HTML and keep their size on a phone), plain
  views in the app (a line's pieces are thin turned bars; Expo Go has only its
  bundled native modules). Colours per seat are the same on both.
- The chart is under the board, where the scores are, so the play card keeps
  only what a turn needs.

**2026-11-26: a tester's second round, first part (Claude Code, PR #73)**

- The tester said the row warning of PR #70 was not what he meant: he meant a
  warning "for one move, when someone catches up and leaves the bonus
  hanging". Shown all the time, it was "a lot of information that hangs there
  and blurs".
  - So the warning is about a move: the one that brought its player to one
    cell from a row's bonus where someone already was. It is worked out from
    `engine.last_move`, not remembered anywhere, so every screen, a reload and
    the app all show it until the next move, and nothing is saved.
  - A player who comes to one cell alone gets no warning (no race), as before.
    Nor does a crossed-out cell that brings a player to one cell, unless
    someone in the race can still win the bonus.
  - `races.rows` in the API keeps its fields (one `by` added). What it lists
    changed, from every such row to the one the last move started. No app is
    released, and the app shows `text` as it comes, so it follows the server.
    docs/API.md says so.
  - The column table under the dice stays: the tester asked for it, and did
    not mention it now.
- Tears, not fireworks, for Abaka or the royal full house with no room for it.
  The tester offered "out of place, or add crying"; crying instead of
  fireworks answers both. Its row means the row the combination is written in
  (Abaka; Full house for the royal full house). Abaka counts as a full house
  too (item 20), but it still brings tears when the Abaka row is full: that is
  the tester's case.
  - The same reason applies to sparkles, so they now need a free cell in their
    combination's row as well. A throw that makes two (four 3s with the wild
    joker are also a full house) sparkles for the one with room.
  - An app that does not know an effect plays sparkles under its banner
    (docs/API.md), so an older app shows the right words.
- The teasing reactions: "rude ones are missing". Mild ones only: the app will
  be in the App Store and Google Play, and the game is played with family
  too. They go after the nine there were. The app takes its buttons from the
  server, so it shows them without an update.
- The board's row differences and the chart of scores by move are next, in
  their own pull request: both change the score table, which on a 360px phone
  just fits two players.
- The scratch Python 3.13 in the session's temporary folder lost files to
  macOS's cleanup of old temporary files ("No module named 'encodings'").
  `uv python install --reinstall 3.13` and a new venv brought it back.

**2026-11-25: a game opens only with its key (Claude Code, PR #72)**

- The owner asked to fix seat protection now: "the link should be somewhat
  encrypted, one shouldn't be able to enter a game just knowing the code".
- A secret key next to the code, rather than a longer code:
  - the 5-character code stays the game's name everywhere it already is (the
    top bar, file names, the database, logs, what the owner reports: "game
    LWUNK"), and it is no longer a secret;
  - the key goes only where it is needed: the link, the full code, a state.
- 8 characters of the code alphabet (no 0/O, 1/I) are 40 bits. Online guessing
  at a thousand tries a second takes about 17 years for one game, and games
  are deleted after a week unused, so no lockout is needed (a lockout would
  let anyone who knows a code block its players).
- The full code is `CODE-KEY`, and the link carries the same text in `?room=`.
  One parameter: what players see in a link is what they type. A typed full
  code may have any case, spaces, no dash, or be a whole pasted link.
- A wrong key, a missing key and a missing game get the same answer, so trying
  codes tells nothing. Only the website's page for a code alone says "This link
  is not complete", the same whether or not the game exists.
- Seated players need no key: their token proves the seat. So moves, picks,
  reactions and chat did not change.
- The key is kept in the room as it is, not hashed: the waiting room and the
  menu must show it again after a reload, and the database already holds the
  seat tokens.
- Games saved before have no key. One is made the first time such a game is
  loaded and saved at once (a version bump, since the repository refuses a save
  that is not newer); otherwise the next load would make another and the
  players' links would stop working. Pages already in such a game switch the
  address bar to the full link by themselves. Players who were not seated and
  only had an old `?room=CODE` link need the full link from someone at the
  table.
- Taking a seat by its name with the link stays as it was: the owner's words
  were about the code. Protecting a seat from another holder of the link (item
  11) is the next layer, if wanted; the new web client (item 25, B1) can keep a
  seat's own key in the browser, which Streamlit cannot.
- Protocol 1 changed what `join`, `rejoin`, `resume`, and `state` and `seen`
  without a seat need. That breaks the rule in docs/API.md (Versions) once,
  knowingly: no app has been released, the only installs are test devices, and
  every client had to stop opening games by code. The exception is written
  there. The app's client and its tests send the key.
- Clubs are unchanged: a club's code still opens its page and lets anyone add
  games to its table. The owner's words were about games; clubs can get the
  same key if wanted.

**2026-11-25: choosing a host (Claude Code)**

- The owner asked to select a host, and does not mind leaving Streamlit for
  the web version. The comparison and the recommendation (Fly.io in Virginia)
  are in Backlog item 25, B1. Nothing is set up until the owner has an account
  and a domain.
- What decided it: one server process holds the games in memory, so a host
  must never run two copies at once, even during a deploy. Fly.io with one
  machine stops the old one first; Render and Railway overlap them. Each
  host's deploy would close live connections anyway; the app reconnects.
- The web version without Streamlit: the app's web build, which `tools/app_check.py`
  already plays in Chromium on every pull request, served next to the API by a
  plain Starlette server (`server/http.py` is Starlette already).

**2026-11-24: the race box, a row per player (Claude Code, PR #71)**

- The owner said "Run it" to the check on the emulator that PR #70 had not
  had. It found five players' names cut to "Test…" in the box, and the
  website's play card cut them too.
- Players as rows, columns I and II as columns, for every number of players,
  rather than a second layout for four and five:
  - a name gets 40% of the box, the same with two players as with five;
  - a line per player instead of one per column: two players racing for
    both columns take the same three lines, five take three more. The box is
    under the move picker, so the dice and buttons keep their place;
  - one layout is one thing to draw and check, on the website and in the app.
- Not chosen:
  - initials or shortened names: "TA" and "TB", or two Анна at one table,
    tell players apart less well than the board does;
  - "I" and "II" as the column headings, which would need a new field in the
    API. "Столбец II" fits its column at the narrowest (five players on a
    desktop) and may wrap there.
- A very long name (the limit is longer than a row) still ends in "…"; the
  board above shows it whole, and the website's cell names it on hover.
- The app's browser check measures the name cell with "Александра", a long
  first name, on its 360px phone. Its width no longer depends on the number
  of players, so the two-player game there covers five.

**2026-11-23: the races for the shared bonuses (Claude Code, PR #70)**

- A tester, through the owner, asked for hints in the fight for bonuses
  ("optional"): how many cells are left to a column for you and the opponent,
  since on a phone the board is below the dice and has to be scrolled and
  counted; and a warning that you have been caught up in a row when you have
  one cell left to its bonus.
- The races are the bonuses that the first player to complete decides for
  everyone (`bonus.py`): every row, and columns I and II. Column III is each
  player's own, so it is left out.
- A column is shown from its first written cell until its bonus is decided,
  or until nobody can earn it. A player who crossed out a combination in it
  can no longer earn it, but completing it first still closes it for the
  others. So their count stays, grey with ✕, and a note says why.
- The row warning is the tester's case: two or more players one cell from the
  same row's bonus, at least one of whom can still win it. It is shown to
  everyone at the table, with the viewer named first ("you and Bob").
  - A player one cell away alone gets no line: there is no race to warn about.
  - Nor does a row where one player is one cell away and the others are
    further. Late in a game that is most rows; the board shows them.
- The words come from the server with the state, as for effects (PR #64). So
  the website and the app say the same, and the rules for races stay in one
  place. The Russian avoids declining names: "Одна клетка до бонуса — вы и
  Ann: Сумма."
- The box sits at the foot of the play card, under the move picker, so the
  dice and the buttons keep their place on a phone.
- No load-test row, for the second pull request in a row (PR #69 too): the
  machine was busy with another project. Main and the branch were measured in
  turn instead, as in PR #64. The next pull request that changes the app's
  code on a quiet machine records one.

**2026-11-23: the "Mr. Lucky" reaction (Claude Code, PR #69)**

- "Прушник" is slang for someone luck keeps following; "Mr. Lucky" is the
  owner's English for it.
- 😎 is my choice: most reactions are faces or hands, and 🍀 is "Lucky!"'s.
  It sits right after "Lucky!", so the two lucky ones are side by side.
- A reaction added is protocol 1 (docs/API.md): the app draws the buttons in
  `info.reaction_list`, and a bubble's words come with its event.

**2026-11-21: the app's dice (Claude Code, PR #68)**

- The owner found the app's dice ugly. The website's dice are the reference:
  the owner has played with them since PR #12, and `Dice.tsx` said it drew
  them "like the web's". So the app now uses the website's grid exactly,
  rather than a new design.
- In React Native a child with `position: 'absolute'` is placed from inside
  its parent's border. The pips were placed as if from the outer edge, so the
  whole face sat the border's width right of and below centre. The browser
  check could not see it: it reads the dice's values, not where their pips
  are. A test now checks the arithmetic.
- The pips are still views with rounded corners, not an SVG as on the web:
  no new package (`react-native-svg` is not in the app), and a round view is
  drawn the same on every platform.

**2026-11-21: Android's emulator, and what it found (Claude Code, PR #67)**

- The owner asked whether there is a phone simulator for the Mac, and chose
  Android ("Set up android one"). The iPhone simulator comes with Xcode,
  which needs the owner's Apple ID.
- Google's command-line tools instead of Android Studio: the emulator, adb
  and one system image are all the app needs (Expo Go is installed by
  `npx expo start --android`), at a third of Android Studio's size. Android
  Studio can be added later and finds the same SDK in `~/Library/Android/sdk`.
- Android 16 (API 36) with Google's apps: a version most phones are on or
  near, with Chrome and Google's fonts as on a phone. No Play Store, which
  Expo Go does not need. A Pixel 7 (411 wide), and `wm density 480` for a
  phone 360 wide, the narrowest common one, without a second virtual phone.
- 2 GB of memory for the phone: this Mac has 8.
- The fixes are in `Screen` (`src/components/ui.tsx`), which every screen
  uses, so one change covers home, the game, the clubs and the rules:
  - The page still scrolls under the gesture bar (Android's and iOS's own
    look), and ends the bar's height higher, so its last line can be
    scrolled clear of it. The safe area's bottom edge would have cut the page
    off above the bar instead.
  - The layer of bubbles and fireworks keeps to the safe area on every side.
  - On Android, a `KeyboardAvoidingView` shrinks the page to the space above
    the keyboard, and Android's scroll view then brings the focused box into
    view by itself. iOS keeps `automaticallyAdjustKeyboardInsets`, which
    already worked there, and the web build has no keyboard to avoid. Not
    `react-native-keyboard-controller`: Expo Go has only its bundled native
    modules (mobile/AGENTS.md).
- The board: narrower cells for two players on a small phone, rather than a
  scroll bar or a smaller font. Two players were meant to fit without
  scrolling (Decision log, 2026-11-20); the arithmetic assumed 390 wide.
  - 22 is the narrowest cell: it still holds "160" (Abaka on the first roll)
    in the board's font, seen on the emulator.
  - With three to five players the columns scroll at the usual size, as
    before: they never fitted a phone.
  - The sizes moved to `src/lib/board.ts`, with tests, as the app's other
    logic is.
- The keyboard's Go key does what a form's button does only where the form is
  one box and one button. Where more choices follow the box (the online
  card's number of players, the boxes of a game on one device), Go would
  skip them, so the key only closes the keyboard there.
- The emulator is not in CI. The browser check already runs all of the app's
  code in every pull request; the emulator is for what only a phone has, and
  is used by hand on a change to how the app sits on the screen (the safe
  areas, the keyboard, gestures).
- The check of the 3.13 suite here skipped only the 8 database tests (no
  Postgres running); CI runs them.
- Found while driving it, for whoever drives it next (mobile/AGENTS.md):
  uiautomator's view of the screen leaves out what is scrolled out of view,
  and waits forever while something animates (a spinner); a fling goes on
  after the swipe, so positions are read once the screen has stopped; and in
  Expo Go the app comes back through the app switcher, not the launcher icon,
  which opens Expo Go's own home page.

**2026-11-21: the rules screen in the app (Claude Code, PR #66)**

- The rules text belongs to the game, not to the web page, so it moved to
  `abaka/rules.py`. `ui_components/rules.py` keeps the dialog and imports
  the text; `abaka_ui.py` did not change.
- Blocks, not Markdown, for apps. A phone has no Markdown table, and an app
  that parses Markdown would carry a second copy of the format.
  `rules_blocks()` turns the website's Markdown into headings, paragraphs and
  the table, so there is still one text. Bold stays as `**` marks, which the
  app already draws (`Rich`).
- A `rules` operation rather than a field of `info`: `info` is asked for once
  per language and kept, while the owner changes the rules from time to time.
  The app asks for them each time the screen opens.
- A request may name its own `lang` now (the client sends the connection's
  language unless the request has one). The rules screen asks for the
  language it shows: React runs the screen's effects before the app's, so
  the connection could still have the old language.
- The game's bar is where players look for the game's code, so the code must
  always fit: the kind of game is the website's icon (👥, 🌐), with the words
  for screen readers. The language switch went to the rules screen, one tap
  from the game, as the website has it in the game menu.
  - The first check of the bar passed on a bar that was too narrow: the code
    was random and its letters happened to fit. It now measures the widest
    code there can be, on a 360px phone (a common Android width).

**2026-11-21: clubs in the app (Claude Code, PR #65)**

- The owner said "Keep going": the next part of the app's screens (Backlog
  item 25, C2).
- No combo box in React Native, so the website's "pick a player or type a new
  name" became the club's players as chips above the name boxes.
  - On one device a tap fills the next empty box, and a tap on a name already
  in a box empties that box. So picking a table of four is four taps.
  - The boxes keep the last game's names when the player comes back to the
    club, ready for the same players again.
  - Online and on an invite, a tap fills the one name box.
  - The invite of an online club game asks the server for the club's names
    (`club` with `games: 0`) and offers those not at the table. The server
    decides who may join.
- The table's numbers are rounded as Python rounds them (a half to the even
  neighbour), so the app and the website show the same rating for a club.
  JavaScript's `Math.round` rounds halves up.
- Who a name is (capitals and spaces aside) is now `member_key` in
  `abaka/rooms.py`, for the rooms and the clubs alike. The app's copy uses
  lower case where Python uses casefold; they differ for a few letters (ß),
  which can only change what the app offers.
- Joining an online club game under a name already at the table is refused
  ("Each player needs a different name."). The owner's rule for a game on one
  device (Backlog item 21) is that two names that are one member cannot play
  together; joining had no such check. Outside clubs nothing changed: an
  exact twin becomes "Ann (2)", another spelling is kept.
- A club's link is a code in the app, as a game's is: links that open the app
  wait for C3. The code is shared with the phone's share sheet.
- "Club table" on the results goes back to the club's screen if it is under
  the game (the game was started there), or opens it.
- The browser check got a server of its own in CI (`--serve`) instead of a
  second limit for test servers. The limit on new games stays as it is
  everywhere.
- The load-test row was flagged against the previous one (24% → 33% CPU,
  6.3 → 8.5 ms median poll) on a quiet machine. Main and the branch, measured
  in turn from two equal copies, gave the same in three rounds each (33-34%,
  8.7-8.9 ms), and nothing on the poll path changed. So the previous row was
  low, as happened in PR #56. The row is kept: it is what main measures now.

**2026-11-21: reactions, effects and the chat in the app (Claude Code, PR #64)**

- The owner said "Keep going": the next part of the app's screens (Backlog
  item 25, C2).
- The words of a reaction and of an effect come from the server, with each
  event, for the player the state is drawn for.
  - The app is a thin client: move labels and errors already come this way.
    "Who sent it to whom" and a banner's line name rows and players, and the
    rules for them belong in one place.
  - An app installed today then shows a reaction or an effect the server
    adds later: its button from `info.reaction_list`, its words from the
    event. An effect it does not know plays as sparkles under its own banner.
  - The words moved from `ui_components/effects.py` to `abaka/effects.py`,
    as plain text. The web page escapes them for HTML, the app shows them in
    `<Text>`.
  - The facts stay in the event too (`reaction`, `to`, `effect`, `what`,
    `first`), for a client that draws its own. Adding fields keeps
    protocol 1.
- The connection gathers the chat. The server sends each message once (a
  push holds only what is new), so the screen would otherwise have to know
  which states are whole and which are additions.
  - The answer to `watch` is whole: it replaces the chat, which matters
    after a server restart, when the chat is gone.
  - Requests about the watched seat carry `since`, so their answers hold only
    what is new. Events are still filtered by id when handed over, since a
    queued request's `since` can be old.
  - The chat is emptied when the game is over, as the server does.
- What plays, and when, is decided in `mobile/src/lib/shows.ts`, without any
  screen code, by the website's rules: nothing from before the screen opened
  the game, nothing first seen 15 s late, a throw's effect after the dice's
  0.45 s, one effect at a time.
  - Taking a seat counts as opening the game. Otherwise a seat taken back in
    the middle of a game announced its whole chat as new.
- The fireworks are drawn with React Native's own `Animated`, one timeline
  per effect, moved by the native driver on phones. No animation library:
  Expo Go has only its bundled native modules.
  - With "reduce motion" on, an effect is its banner alone.
  - The banner sits in the lower part of the screen and takes no touches, so
    the dice stay in view and the buttons under it still work.
- The reaction buttons and the chat sit under the play card, above the
  score table, as the website stacks them on a phone.
- The mixed check (a website player and an app player) needs a server that
  serves the pages too, so it runs against `abaka_server.py`, as CI starts
  it. The steered checks bring their own server.
- No load-test row this time. The tool flagged a slowdown (page run 79 →
  131 ms, median poll 6.3 → 10.4 ms) while another project's browser tests
  kept this machine busy.
  - Main and the branch, measured in turn from two equal copies, three
    rounds each, gave the same: page run 119 and 115 ms on average, median
    poll 9.6 and 10.8 ms. So the change does not slow the pages.
  - A row from a busy machine would spoil the next comparison, so none was
    kept. The next pull request that changes the app's code records one on a
    quiet machine.

**2026-11-21: the test round in the phone app (Claude Code, PR #63)**

- The second half of the owner's "test everything again". Each finding was
  first shown to happen, in the app's web build or with a scripted server,
  and only then fixed.
- "‹ Home" only goes home. A seat is given up by a button that says so.
  - The website's waiting room has no way home except Leave, so the app's
    first version made Home leave too. On a phone the system's back gesture
    left the screen without giving up the seat, so the two ways home differed.
  - Leave now waits for the server's answer. If it fails, the app says so and
    stays, since the seat is still held.
- The order of a game's states is the connection's job, not each screen's.
  - `seen` (version, picks, latest event) orders the states of one
    connection, where an answer and a push can cross.
  - The answer to `watch` is a fresh start. The counts of picks and events
    live in the server's memory and begin again after a restart, with the
    same version. Compared with what the screen showed before, the game's
    news looked older and was dropped until the next move.
  - `docs/API.md` now says both, for any other client.
- A dead connection is found by asking, because a phone's WebSocket cannot
  see the server's pings.
  - Only when nothing has arrived for 20 s, so a game being played costs
    nothing extra. The question is `seen`, which also tells whether the
    screen fell behind (then the app asks for the game again).
  - A request that is never answered counts too: it fails as `offline`, and
    the connection is closed rather than trusted again.
  - A connection that has not opened after 10 s is given up and tried again.
- One connection for every screen, and `unwatch`.
  - Before, leaving a game's screen closed the connection, because protocol 1
    had no way to stop the pushes. Every trip home and back made a new one.
  - Closing it also failed the home page's own requests when the two
    overlapped.
  - `unwatch` is a request of the live connection, like `watch`. Adding it
    keeps protocol 1. It answers the same when nothing is watched, so the app
    uses it as its "are you there?" on the home page.
- `startWatching` returns what stops that watch only. A shared "stop
  watching" let a screen that closed late stop the game of the screen opened
  after it.
- "Continue a game" asks the server about the games the device remembers, in
  order, until it has 4 to offer, as the website's home page does (each look
  can make the server read a game). The device also remembers that a game
  ended, so the list is right at once and corrected a moment later.
  - It asks without the seat's token: an invite's view already says whether
    a game is over.
- The scripted server for `mobile/tests/connection.test.ts` is the `ws`
  package, version 7, which React Native's own tools already bring. It is a
  development dependency, never part of the app.
- Steered dice (`Steered` in `tools/app_check.py`): the real API over the
  network on a store inside the check's process, with `roll_dice` answered
  from a list. The next part of the app (fireworks for an Abaka) needs it too.
  - First the check failed on the old app only because a test hook was
    missing there. So the fix's one line was reverted alone, and the check
    failed for the right reason.

**2026-11-21: a full test round, the server's side (Claude Code, PR #62)**

- The owner asked to test everything again with the new model. The round ran
  every check the project has, and added what it lacked: requests nobody
  well-meaning would send.
- How the surrogate bug was found: reading `server/http.py`, where a failed
  send only set a flag. So what can make a send fail? Text that UTF-8 cannot
  encode. Python's JSON reader turns `"\ud83d"` into half of a surrogate
  pair, and `clean_name` let it through.
  - The web page cannot send one. Streamlit refuses the browser's whole
    message as bad UTF-8, so the click does nothing (checked in Chromium, with
    half a pair put into the name box by a script). So the bug came with the
    API, in PR #58 and PR #59.
- Fixed at the door and at the exit:
  - `clean_name` and `clean_message` drop the Unicode category Cs with Cc
    and Cf. A club's name is cleaned by `clean_name` too (it had a copy of
    the code).
  - `server/http.py` writes its answers with `as_json`, which falls back to
    `\u` escapes for text UTF-8 cannot carry. Only a message's `id`, echoed
    as it came, can still hold such text.
- A failed send used to set `closed` and leave the socket open. The app then
  saw an open connection, got no pushes, and did not reconnect. Now the
  socket is closed with 1011, and a fault in the pushing loop closes it too.
  - 1011 and not 1012: 1012 says the server restarted, which is not true
    here. The app reconnects after any close.
- Not changed, on purpose:
  - A reroll of no dice (`"dice": []`) still uses up a reroll. Only a
    client's bug sends one, since the website and the app disable the button.
    Refusing it would change what an operation of protocol 1 accepts.
  - The engine's messages for moves no client offers ("Two Pairs needs two
    different pairs.") are English only and older than Backlog items 19 and
    20. Players never see them.
- The fuzz is a test now (`TestHostileRequests`), not only a tool. Each
  request starts as a well-formed one for a game in some phase, then one
  field is replaced or others are added. Random fields alone were mostly
  refused at the first check: a run of 3,000 such requests on the code
  before the fix did not meet the bug.
  - The games' dice are not seeded, so runs differ. 25 runs in a row passed;
    without the fix, 3 of 3 failed.
- The Decision log of 2026-11-19 (PR #51) said the typed-in club name ran on
  Streamlit 1.67 in CI. It did not: AppTest 1.67 refuses a typed-in option
  like 1.48, and the test skipped itself. So "skipped=1" was in every CI log
  since. On 3.13 with a database nothing is skipped now, which makes a new
  skip easy to see.
- The live connection's numbers (Known issues, Capacity) come from a scratch
  tool, not from `tools/loadtest.py`, which drives pages. If the apps get
  users, it should become a tool with a recorded baseline, like the pages'.

**2026-11-20: the app in React Native with Expo, first screens (Claude Code, PR #61)**

- The owner chose React Native ("React native"). It is built with Expo, the
  recommendation the owner had:
  - React Native's own documentation starts apps with a framework, and Expo
    is the one it names;
  - Expo builds both stores' apps in its cloud, without Xcode or Android
    Studio, neither of which is installed here.
- Made with `create-expo-app` (SDK 58, the blank TypeScript template), plus
  Expo Router, from Expo's own default template.
  - Not kept: the template's license file (Expo's copyright; the repository
    has its own) and its `.claude/` settings, which switched on a plugin.
  - The template's guide for agents became `mobile/AGENTS.md`, with this
    project's rules added.
- Every request goes over the live connection, not over HTTP:
  - answers and pushes come in one ordered channel;
  - after a drop the client reconnects and watches the game again;
  - the web build needs no cross-origin permission from the server.
- Found while testing, in about 1 run in 6: the screen of the player who had
  asked for `state` missed the last moves of a game.
  - The server counts every reply that carries the watched seat's state as
    sent, and pushes only later changes. The first client handed only move
    replies to the screen.
  - It now hands on every such reply, and `docs/API.md` says so. The server
    did not change.
- Answers and pushes can cross: a push worked out just before a move's reply
  can arrive after it. The client keeps the newest state by `seen`. A state
  with the same `seen` replaces the one shown, because it may be in the other
  language.
- Seat tokens are kept in the phone's secure storage (Keychain, Keystore); the
  web build keeps them in the browser's. A device remembers 10 games and shows
  4, as the web does.
- There is no server for apps yet (stage B). The app finds one this way:
  - `EXPO_PUBLIC_ABAKA_SERVER`, when set;
  - otherwise the computer running Expo's development server, port 8501, so
    Expo Go on a phone on the same Wi-Fi works;
  - the web build also takes `?server=`, but only for this computer, so a
    link cannot send players' moves to someone else's server.
- The web build is the check, as no simulator is installed here. It runs all
  of the app's code through react-native-web; what only a phone has (its
  fonts, keyboard and gestures) needs a real phone later.
- The texts are an export, committed (`mobile/src/texts.json`), so an app
  build needs no Python. Plural forms come from i18n's own functions.
  `tests/test_mobile_texts.py` scans the app's `t()` calls (not its comments)
  in every CI job.
- CI's third job, "Phone app (Expo)", runs on Node 26, the current LTS, as
  here. It becomes a required check after the merge, like the other two.
- Two players' columns fit a 390px phone (cells of 26px). With 3 to 5 players
  the columns scroll sideways under fixed row names, as on the web.

**2026-11-20: the phone app in this repository (Claude Code, PR #60)**

- The owner asked whether the app and the website need separate GitHub
  projects, and agreed to one repository ("Add to the app plan").
- Why one:
  - The app is a thin client of this server, so most features change both
    sides: a field in the API and the screen that shows it. One pull request
    carries both, and CI tests them together before either merges. With two
    repositories, a break between them would show only after both merged.
  - The app reuses the texts in `abaka/i18n.py`, with no copies kept in step
    by hand.
  - Both agents keep one AGENTS.md, one log, one set of required checks and
    `tools/pr.py`, and see each other's pull requests. A second repository
    would double these and split the log.
  - The website and the server cannot be split anyway: they are one program
    and share the games in memory.
- It costs the website nothing:
  - Streamlit Cloud ignores the folder, as it ignores the Neon files at the
    root;
  - every pull request, the app's included, passes the website checks before
    it merges.
- `mobile/`, not `app/`: "the app" in this file usually means the website,
  and `abaka_server.py` already has an `app`.
- The export of the texts is committed, not made at build time:
  - an app build (in Expo's cloud, if C1 picks Expo) needs no Python;
  - CI sees when the export is out of date.
- Split it only if someone should see the app alone (an outside developer,
  for example) or the repository becomes unwieldy.
  `git subtree split --prefix=mobile` moves the folder out with its history,
  so starting together closes nothing.

**2026-11-20: the website kept working while the apps are built (Claude Code, PR #59)**

- The owner asked to make sure the website will not break while the apps are
  built.
- What could break it:
  - a change to code the website shares with the apps (`abaka/`,
    `server/stores.py`, `abaka_ui.py`);
  - Streamlit 1.67 behaving differently from the local 1.48;
  - later, moving the website to another host.
- What protects it:
  - **A check in a real browser, required for every merge.** AppTest runs the
    script but not the page. A broken style or a missing element passes it
    (the gold option in PR #56 did). So `tests/test_website.py` drives the
    website's main flows in headless Chromium, in the CI job branch
    protection already requires, without renaming it.
    `ABAKA_REQUIRE_BROWSER` turns a missing browser into a failure: a skipped
    check would protect nothing while looking green.
  - **One check for CI and for the live app.** `tools/website_check.py` runs
    in both, so after a merge the same steps run where players are, at a
    desktop and a phone width.
  - **Proven by breaking things on purpose** (a scratch copy, not the repo).
    A check that cannot fail protects nothing.
  - **A revert first, then the fix,** if the live app breaks: a revert goes
    through CI like any change, and players get the working version back
    within minutes.
  - **For the move to a new host (stage B),** the new host runs next to
    Cloud on its own Neon branch until the owner switches. Two servers
    writing the same games would lose moves.
- The check plays with its own games ("Test Ann", "Test Bob"). `--cleanup`
  marks only those deleted, and only in the database given in
  `ABAKA_DATABASE_URL`.
- Playwright is pinned in `requirements-dev.txt`, apart from
  `requirements.txt`. Streamlit Cloud installs only the latter, and a change
  there restarts the live app.
- The guard is in the same pull request as step A2, so the first app change
  that touches the website's code passes it before it merges.

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
