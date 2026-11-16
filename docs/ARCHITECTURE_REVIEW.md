<!-- Architecture review of 2026-11-16, written by a separate review agent (role: senior architect)
     at the owner's request. Read-only review; measurements were made locally (Apple M1, Python 3.9,
     Streamlit 1.48.1). Line numbers refer to commit 44b08e1 (main after PR #24). -->

# Abaka architecture review: readiness for many parallel games

**How I worked**
- **Paths:** repository paths below are relative to `/Users/dpinchuk/Documents/PycharmProjects/Abaka/`. Streamlit paths are relative to the Python39 env's `site-packages/streamlit/`.
- **Environment:** Apple M1, Python 3.9.20, Streamlit 1.48.1. The engine and rooms were also run on Python 3.8.5.
- **No script files.** My session was read-only, so I did not create `scratchpad/arch/` or any benchmark scripts. Every benchmark ran as an inline script piped to the interpreter with `-B`, so nothing was written to the repo either. I can write them out as files if you want to keep them.
- **One leftover temp folder.** Temporary save folders were made inside the scratchpad and removed automatically. One run I had to stop left a temp folder of 200 small JSON files behind (since deleted).
- **Local server only.** I started a Streamlit server on 127.0.0.1:8790 from inside the benchmark process and stopped it after each scenario; nothing is left running. I did not contact the live app or GitHub. For the Community Cloud limits I read Streamlit's public docs.
- **Tests:** on 3.9, 92 pass and `tests/test_abaka_engine.py` fails to import (already known). On 3.8 the 9 Streamlit tests are skipped.
- p50 / p95 / p99 mean the median and the 95th / 99th percentile.

---

## 1. Executive summary

- **Not ready for dozens to hundreds of parallel games as deployed.**
  - On one fast laptop core, the live configuration saturates at 50-100 browsers that are only waiting. That is about 17-33 three-player games before anyone moves.
  - At 100 browsers, 60% of polls went unanswered and the median poll took 2.3 s. At 200 browsers it took 10 s.
  - Community Cloud gives the single process 0.078-2 shared cores, so the live app will fail sooner than this.
- **The main cost is Streamlit's machinery, not the game.**
  - Every browser reruns the `_watch_room` fragment once a second. Each rerun starts a new script thread and sends protobuf messages.
  - It then ends with a full `gc.collect(2)`, which Streamlit runs after every script run (`runner.postScriptGC`, on by default).
  - That collection scans the whole process, so every poll gets slower as rooms and sessions accumulate. With 5,000 rooms in memory, 100 browsers got no poll answered within 10 s.
- **One config line is the biggest win.** `[runner] postScriptGC = false` changed the measured costs as follows:
  - a poll dropped from 17-51 ms to 2.5-5.4 ms of CPU;
  - a full rerun dropped from 35-65 ms to about 20 ms;
  - 200 browsers then used 51% of a core, with a 10 ms median poll.
- **The heap only grows.**
  - Rooms stay in memory for 7 days, finished games included, and every saved room is loaded when the store is created.
  - Each code update also leaves the previous `RoomStore`, with all its rooms, in `st.cache_resource` for the life of the process.
- **Everyone shares one process and one GIL.**
  - Under load, a trivial `version()` call waited 7-114 ms at the median and up to 1.08 s.
  - Saving JSON while holding the global lock makes the queue longer.
  - A prototype that shares the copy-on-write snapshot, clones cheaply and writes the file outside the lock brought the median wait for `version()` and `view()` to about 0.
- **Engine hotspots are secondary but cheap to fix.**
  - `score_options` deep-copies the engine 15 times per render (3.5-6.2 ms).
  - A hand-written clone gave identical results on 23,535 positions. It is about 20 times faster than `deepcopy` and makes `score_options` about 10 times cheaper.
- **Scaling out needs the game state outside the process.**
  - In-memory rooms rule out a second process, and saved games are lost whenever Cloud sleeps (after 12 h without traffic) or is rebooted.
  - For hundreds of games: a shared store (Postgres or Redis), plus either several Streamlit replicas behind sticky sessions on paid hosting, or a push-based game server (FastAPI + WebSockets) that reuses `abaka/` unchanged.
- **Security and build quality are "friends only".**
  - Anyone with a game code can take any seat or remove players from a waiting room, and codes can be guessed.
  - Player names reach Markdown unescaped, and room creation is unlimited.
  - Streamlit is unpinned on Cloud, there is no CI, and the test suite is red because of the legacy test.

## 2. Measurements

### In-process benchmarks (M1, Python 3.9)

| What | How | Result |
|---|---|---|
| Engine `deepcopy` | Median of 5 batches, positions taken from random games | 2 players 220-250 µs; 3 players 256-325 µs; 5 players 392-500 µs |
| `score_options` per render, dice rolled | Same positions | Start/mid game: 2p 3.5 ms, 3p 3.8-4.3 ms, 5p 5.0-6.2 ms. Late game: 0.9-2.2 ms. Still 3.6-5 ms when no row can be scored. `cross_options`: 5-12 µs |
| Prototype hand-written clone | 23,535 random positions; every option compared; original checked unchanged after each trial | 0 mismatches. Clone 10-14 µs (about 20x faster). `score_options` 3.13 → 0.30 ms (2p), 0.70 → 0.09 ms (3p, late game) |
| `RoomStore.version()` / `view()` | 20,000 / 2,000 calls | `version()` 0.65 µs. `view()` 177 µs (2p), 372-387 µs (5p): a deep copy made while holding the global lock |
| One move through `_act`, single thread | About 770 roll / reroll / score calls | Without saving: p50 0.23 ms (2p), 0.47 ms (5p). With saving to a temp folder: p50 0.53 / 0.87 ms, p99 about 1.8 ms |
| Save path, 5 players | Timed step by step | `to_data` 41 µs, `json.dumps` 62 µs, file write 122 µs, write plus `os.replace` 213 µs, whole `_save` 344 µs |
| Saved JSON per room | `len(json.dumps(room.to_data()))` | 1.8-2.1 KB (2p), 2.4-2.8 KB (3p), 3.9-4.5 KB (5p) |
| Memory per engine / room | tracemalloc over 200 copies, then 20,000 rooms | 8-9 KB (2p), 10-11 KB (3p), 16-17 KB (5p). 9.9 KB per 3-player room. About 76 garbage-collector-tracked objects per room |
| `gc.collect(2)` time vs rooms in memory | Streamlit server modules imported | 5.9 ms with no rooms, 16.7 ms at 1,000, 52 ms at 5,000, 183 ms at 20,000 |
| Contention | Threads play many rooms through the store as fast as possible, while other threads call `version()` (polls) and `view()` (renders) | Throughput caps at about 500-700 actions/s (GIL). `version()` p50 7-114 ms, p99 up to 683 ms, max 1.08 s. With saving on, `_act` p50 goes from 0.26 ms to 3.8-22 ms |
| Prototype "lean store" | Same harness and run: shared snapshot, cheap clone, file written outside the lock | At 96 threads: `version()` p50 50 → about 0 ms, p99 419 → 204 ms. `view()` p50 51 → about 0 ms. Actions/s 305 → 518 |
| Full script run (AppTest on the real `abaka_ui.py`) | 30 reruns per screen | Home 32 ms. Game screen 30-33 ms without dice, 36-40 ms with dice and the move picker (2-5 players) |
| Module-reload check | `code_version.fingerprint()`, 200 calls | 1.17 ms on every full run |
| Scoreboard HTML, 5 players | 300 calls | 0.36 ms and 19.7 KB per render |
| `_drop_idle_rooms` | Store holding 20,000 rooms | 10.9 ms, under the lock, on every room creation |
| Saved files on disk | Restart with one expired and one corrupt file | Both files stay forever; the warning about the corrupt one repeats on every store creation |

### Real Streamlit server (local, 127.0.0.1:8790)

- **Setup:** a websocket driver with no browsers. Each simulated browser opens its own saved same-device game, 3 players, mid-game with dice rolled. It then sends the `_watch_room` fragment rerun once a second, the way the frontend timer does.
- **CPU** was read with `ps` over a 10-second window.
- **"Full rerun"** means 40 sequential reruns of the game page.

| Rooms in memory | Polling browsers | `postScriptGC` | Server CPU (1 core) | Polls served / offered per s | Poll latency p50 / p95 | CPU per poll | Full rerun CPU |
|---|---|---|---|---|---|---|---|
| 200 | 50 | on (default) | 85% | 51 / 50 | 222 / 595 ms | 16.8 ms | 35 ms |
| 200 | 100 | on | 94% (saturated) | 40 / 100 | 2.3 / 3.8 s | 23 ms | 48 ms |
| 200 | 200 | on | 94% (saturated) | 18 / 200 | 10.1 / 12.1 s | 51 ms | 65 ms |
| 5,000 | 100 | on | 98% (saturated) | 0 / 100 | none completed in 10 s | n/a | 221 ms |
| 200 | 50 | off | 27% | 50 / 50 | 10 / 22 ms | 5.4 ms | 18.5 ms |
| 200 | 100 | off | 35% | 100 / 100 | 9 / 145 ms | 3.5 ms | 19 ms |
| 200 | 200 | off | 51% | 202 / 200 | 10 / 40 ms | 2.5 ms | 20 ms |
| 5,000 | 100 | off | 37% | 100 / 100 | 9 / 24 ms | 3.7 ms | 19.5 ms |

- **First page after a restart or deploy** (this is when the store loads every saved room): 0.3-0.4 s with 200 saved rooms, 1.9-2.0 s with 5,000.
- **Server RSS:** about 56 MB with 200 rooms and about 117 MB with 5,000, so roughly 13 KB per room. Extra sessions did not move RSS beyond its noise (a few KB per session).
- **Caveats:**
  - The simulated browsers send no widget state.
  - They skip a poll while one is still outstanding; the real frontend keeps firing, so real overload is worse.
  - Cloud vCPUs are slower and shared compared with an M1 core.

### Capacity in real play

- **Reruns per turn.** One move makes the mover's browser run the script about 1.5 times: the button run plus `st.rerun()`. Every other browser in the room runs it once after its poll sees the new version. Die taps and row picks add reruns for the mover. A 3-player turn therefore costs about 15 full runs.
- **With GC off (M1):** 15 runs × 20 ms per roughly 20-second turn, plus 3 polls/s × about 3 ms. That is about 2.5% of a core per active game, so about 25 games at a healthy 60% load (35-40 at 100%).
- **With today's default:** 8-10% of a core per game, so about 6-10 games.
- **On Cloud:** divide by roughly 1.5-3.

## 3. Findings

### A. Architecture for scale

**A1. Each browser runs the whole Streamlit machinery once a second, ending in a full garbage collection. Critical.**
- **Evidence:**
  - `abaka_ui.py:318-322` polls with `st.fragment(run_every=1.0)`.
  - Every run, including fragment runs, ends in `gc.collect(2)` (`runtime/scriptrunner/script_runner.py:747-752`; `runner.postScriptGC` defaults to True at `config.py:611-619`).
  - An idle session starts a new ScriptRunner thread for each poll (`runtime/app_session.py:436-450`, `script_runner.py:303-307`).
  - Measured: 17-51 ms of CPU per poll, rising with sessions and rooms; collapse between 50 and 100 browsers.
- **Impact:** the cost of a poll grows with the heap, and the number of polls grows with browsers, so total cost grows roughly quadratically. The single process stalls for everyone at once.
- **Recommendation:**
  - Set `[runner] postScriptGC = false` now.
  - Poll adaptively:
    - 1 s while another player in your room is acting;
    - 3-5 s on your own turn, in the waiting room and after the game ends;
    - about 10 s for same-device games (the only reason they poll is a second device).
  - Longer term, replace polling with push (Stage 3).

**A2. One process and one GIL serve every game, so all games share latency. High.**
- **Evidence:** the contention benchmark: `version()` p50 7-114 ms, max 1.08 s. Each `gc.collect` holds the GIL for its whole duration, 6-180 ms in the measurements.
- **Impact:** a heavy rerun or a collection in any game delays all other games.
- **Recommendation:** cut CPU per request (A1, A4, B1, B2). Beyond about one core of work, more processes are required (Stage 3).

**A3. The heap is unbounded, and every code update leaks a full store. High.**
- **Evidence:**
  - `abaka/rooms.py:39`: rooms are kept 7 days, finished games included.
  - `abaka/rooms.py:379-391`: every saved room is loaded when a store is created.
  - `abaka_ui.py:58-60`: `@st.cache_resource` has no `max_entries`, which defaults to unbounded (`runtime/caching/cache_resource_api.py:96-97`). It is keyed by `id(RoomStore)`, so each deploy creates a new store while the old one, with all its rooms, stays referenced. `tests/test_ui_store.py:64` asserts that the two stores coexist.
- **Impact:**
  - Each room costs about 13 KB and about 76 objects the collector must scan, per store copy. Collections take 17 ms at 1,000 rooms and 52 ms at 5,000.
  - Startup takes 2 s at 5,000 rooms.
  - With about 10 merges a day (PRs #13-#24 on 2026-11-16), the leaked copies add up quickly.
- **Recommendation:**
  - Keep only active rooms in memory: evict finished games after about 10 minutes and idle games after about an hour, and load a room from disk on demand by its code.
  - Retire old stores. A small registry that survives module reloads (for example a `cache_resource` holding `{"current": store}`) lets the new store mark the old one as retired. The old store's `version()` then returns -1, so old pages rerun into the new code, and the old store drops its rooms.
  - Optionally call `gc.freeze()` after loading.

**A4. The global lock is held across deep copies and disk writes. High.**
- **Evidence:**
  - `abaka/rooms.py:254-258`: `view()` deep-copies the engine under the lock.
  - `abaka/rooms.py:311-328`: `_act` deep-copies and then calls `_save` under the lock; `_save` is at `abaka/rooms.py:359-369`.
  - Measured: with saving on and under load, `_act` p50 rises from 0.26 ms to 3.8-22 ms. The lean prototype brings `version()` and `view()` medians to about 0 and raises throughput by 70%.
- **Impact:** every poll and render of every room waits behind any room's save.
- **Recommendation:**
  - `_act` already swaps in a fresh copy (copy-on-write), so `view()` can return the shared engine without copying. I checked that no UI code assigns engine state; add a test that a full render leaves `engine_to_data(snapshot)` unchanged.
  - Add `GameEngine.clone()` and `PlayerState.clone()` and use them in `_act`.
  - Serialize under the lock but write the file after releasing it, writing only if the version is newer and using a unique temp file per write.
  - With these changes, per-room locks are not needed; the GIL becomes the limit.

**A5. The 6-hour session lifetime holds for at most 128 disconnected sessions. Medium.**
- **Evidence:** `.streamlit/config.toml:9` sets the 6 hours, but Streamlit stores disconnected sessions in `MemorySessionStorage(maxsize=128)` (`runtime/memory_session_storage.py:43`, created in `web/server/server.py:308-310`).
- **Impact:** at scale, as phones lock and unlock, older disconnected sessions are evicted within minutes. Those players lose `ss.my_games` and have to tap their name again. Memory stays bounded, but the behaviour described in CLAUDE.md does not hold.
- **Recommendation:**
  - Make coming back independent of the session: a personal per-seat link (see F1).
  - Keep "my games" in the URL or in browser storage.
  - Otherwise, document the limit.

**A6. In-process state rules out horizontal scaling. High.**
- **Evidence:**
  - There is one `RoomStore` per process (`abaka/rooms.py:5-8`).
  - Files are read only when a store is created (`abaka/rooms.py:121-122`), with no locking or invalidation between processes.
  - `code_version` and `cache_resource` both assume a single long-lived process.
- **Impact:**
  - A second process would split rooms between processes and overwrite the other's files (last writer wins).
  - Community Cloud cannot add replicas, and its disk is wiped when the app sleeps or is rebooted.
- **Recommendation:** a shared store with per-room version checks and change notifications (Stage 2), plus sticky sessions or a game server (Stage 3).

**What breaks first, in order:**
1. CPU, from polls, reruns and garbage collection.
2. Shared latency through the GIL.
3. Games lost when Cloud sleeps or reboots.
4. Memory, only later (about 117 MB at 5,000 rooms against Cloud's 690 MB-2.7 GB), unless deploy leaks or abuse multiply it.
5. Disk is not a concern (2-4.5 KB per room).

### B. Performance hotspots

**B1. `score_options` deep-copies the engine for every candidate row on every render. High.**
- **Evidence:** `ui_components/moves.py:153-157`: 3.5-6.2 ms per render. It runs again on every die tap and every row pick, because each one is a full rerun.
- **Recommendation:**
  - Use `GameEngine.clone()`. The prototype gave identical results on 23,535 positions and took 0.09-0.3 ms.
  - Cache the move list per room code and version. Move texts are translated only when they are read, so a cached list is safe for both languages.

**B2. Every action costs two script runs for the player who acts. Medium.**
- **Evidence:** the pattern `if st.button(...): act(); st.rerun()` appears at `ui_components/main_ui.py:114-122` and `148-154`, `ui_components/move_selection.py:57-68`, `ui_components/dice.py:98-110`, and `abaka_ui.py:143-149`, `157-161`, `416-424`, `433-440`.
- **Recommendation:** use `on_click=` callbacks. The state then changes before the script runs, and one run is enough.

**B3. The module-reload check reads and hashes every source file on every full run. Low.**
- **Evidence:** `code_version.py:26-33`: 1.17 ms per run, about 6% of a 20 ms rerun.
- **Recommendation:** compare file `(st_mtime_ns, st_size)` first and hash only when they change, or check at most every few seconds.

**B4. Small per-render waste. Low.**
- **Evidence:**
  - `_render_my_games` takes a full `view()` for every remembered game; the list is never trimmed (`abaka_ui.py:206-215`, `463`).
  - The invite page takes two views (`abaka_ui.py:401`, `406`).
  - `_drop_idle_rooms` scans every room on each room creation (`abaka/rooms.py:349-353`): 10.9 ms at 20,000 rooms.
- **Recommendation:** keep about 10 remembered games and use a cheap summary instead of `view()`; take one view per invite render; sweep idle rooms on a timer.

### C. Data and persistence

**C1. Saved games do not survive Cloud sleeping or being rebooted. High.**
- **Evidence:** the save folder is the container's disk; Cloud apps sleep after 12 hours without traffic. Already listed in CLAUDE.md under Known issues.
- **Impact:** at scale, games simply vanish.
- **Recommendation:** an external store (Stage 2).

**C2. Expired and unreadable save files are never deleted. Medium.**
- **Evidence:** `abaka/rooms.py:386-390` skips such files without deleting them. I verified it on 3.8: both files survive a restart, and the warning repeats on every store creation, which means every deploy.
- **Recommendation:** delete expired files when loading; move unreadable ones to a `quarantine/` folder.

**C3. Two stores can write the same file around a deploy. Medium.**
- **Evidence:**
  - Every room uses the same fixed temp file name, `<CODE>.json.tmp` (`abaka/rooms.py:365`).
  - After a deploy, the old and new stores share the save folder but have separate locks (`abaka_ui.py:58-74`), and the new store reads the disk only once.
- **Impact:** a move made through the old store after the new one has loaded is silently lost, and two writers can collide on the temp file. It is rare, but nothing reports it.
- **Recommendation:** retire old stores (A3), use `tempfile.mkstemp(dir=save_dir)`, and write only newer versions.

**C4. Crash safety and error handling are adequate but thin. Low.**
- **Evidence:** the atomic replace without `fsync` survives a process crash but not necessarily a power loss. `_save` catches only `OSError`, so any other error reaches the player after the move was already applied in memory (`abaka/rooms.py:325-328`, `368`).
- **Recommendation:** fine for a game. If you want more: `flush` plus `os.fsync` (about 0.25 ms locally), and catch and log any exception in `_save`.

**C5. Save-format versioning is only half done. Medium.**
- **Evidence:**
  - The engine has `FORMAT = 1` and refuses anything else (`abaka/saving.py:17`, `71-72`).
  - Old fields are handled with ad-hoc `getattr` and `.get` defaults (`abaka/saving.py:59-66`, `85-92`).
  - The room record has no version of its own (`abaka/rooms.py:89-106`), and seat tokens are saved in plain text.
- **Recommendation:**
  - Add a top-level `"schema"` field to the room record, with a chain of `migrate()` functions.
  - Keep golden save files for each version in `tests/fixtures/`.
  - Store `sha256(token)` instead of the token.

**Proposed shared store.** The JSON produced by `saving.py` stays the stored document.

*Postgres*

```sql
rooms(code text primary key, state jsonb not null, version int not null, local bool not null,
      capacity smallint not null, games_played int not null, created_at timestamptz,
      updated_at timestamptz not null, finished_at timestamptz)
seats(room_code text references rooms on delete cascade, seat smallint, name text,
      token_hash bytea, last_seen timestamptz, primary key (room_code, seat))
moves(room_code text, seq int, seat smallint, action text, payload jsonb, at timestamptz,
      primary key (room_code, seq))   -- optional log for audit and replay
```

- **An action:**
  1. Read `state` and `version` and apply the engine.
  2. Run `UPDATE ... WHERE code=$1 AND version=$2`; retry if no row was updated.
  3. Send `NOTIFY room_changed, 'CODE:version'`.
- **Notifications:** each process runs one `LISTEN` and keeps a `{code: version}` map in memory, so a poll never touches the database.
- **Expiry:** a periodic `DELETE` of rooms not updated for 7 days.

*Redis*
- Store each room under `room:{code}` with a 7-day `EXPIRE`, refreshed on every write.
- Make the version check atomic with `WATCH/MULTI` or a small Lua script, and `PUBLISH room:{code}` the new version.
- Rate limits are `INCR` plus `EXPIRE`.

*Migration path*
1. Introduce a `RoomRepository` interface (`load`, `save(expected_version)`, `delete`, `scan`) and put today's files behind it, with no change in behaviour.
2. Add the database implementation, with the same contract tests run against both.
3. At startup, import the existing JSON files once (upsert by code and version).
4. Write to both for one release.
5. Switch reads to the database, keeping files as a fallback for one more release.
6. Remove the files.

A flag in Streamlit secrets selects the implementation, so rollback is a one-line change.

### D. Code quality and structure

**D1. Module boundaries are mixed. Medium.**
- **Evidence:**
  - The engine imports the CLI text renderer (`abaka/engine.py:11`, `185-192`).
  - `abaka/rooms.py` combines the room logic, saving, locking, and the UI proxy `RoomEngine` (`abaka/rooms.py:420-451`).
  - The move logic in `ui_components/moves.py` reaches into the proxy's private `_engine` (`ui_components/moves.py:133-135`).
- **Recommendation:**
  - `abaka/` holds the engine, a `clone()` method and the move queries.
  - Rooms split into a service (turn checks), a repository and a UI adapter.
  - `print_scoreboard` and `_category_label` move to the CLI.

**D2. Errors are translated by exact English text. Medium.**
- **Evidence:** `ui_components/i18n.py:73-117` maps engine and room messages by their exact wording. The messages from `_explain_mismatch` (`abaka/engine.py:122-149`) have no Russian version.
- **Recommendation:** raise errors with codes and parameters, and translate the codes.

**D3. Typing and naming. Low.**
- **Evidence:**
  - Cell values are `None | int | 'X'`, and `'X'` means crossed out, a settled School row, or a lost bonus depending on context (`abaka/school.py:31-33`, `abaka/bonus.py:27-38`, `ui_components/scoreboard.py:39-43`).
  - The "is this a School row" check is repeated (`abaka/engine.py:152`, `abaka/bonus.py:22`, `abaka/scoring.py:47`, `ui_components/moves.py:44`).
  - `player.py`, `scoring.py` and `models.py` have no type hints.
  - `ss.engine` is dead state (`ui_components/main_ui.py:26`).
- **Recommendation:** add mypy gradually, starting with the engine. Add `Category.is_school` and `Category.number`, and named constants for cell markers; neither needs a change to the save format.

**D4. Dead code and stale docs. Low.**
- `abaka/ui_components/requirements.txt` and `ui_components/requirements.txt` are unused: delete them.
- `main.py` duplicates `python -m abaka`.
- `abaka/render.py` and `abaka/cli.py` are not dead: the CLI uses them (`abaka/cli.py:61`, `85`, `94`). Keep them if the owner wants the CLI, but take the engine's dependency on them away.
- `tests/test_abaka_engine.py:2` imports a module that no longer exists. Move it out of test discovery, or skip it with a reason, until the owner decides which rules are right.
- Stale documentation:
  - `README_MULTIPLAYER.md:15-16`, `19`, `22` and `40-42` (12 hours; games lost on restart; who starts);
  - `DEPLOYMENT_GUIDE.md:16`, `32` and `38` (Pillow; "Online (2 players)");
  - `README.md:20`, `129` and `145` (2-player rooms; "Python 3.9+"; a LICENSE file that does not exist).

**D5. The Python version policy is unenforced. Medium.**
- **Evidence:** Streamlit 1.48 requires Python >=3.9 and not 3.9.7 (package metadata), so only the engine and CLI can run on 3.8. Python 3.8 reached end of life in October 2024 and 3.9 in October 2025. The 3.8 rule is kept only by habit; nothing checks it.
- **Recommendation:**
  - The owner should decide: either keep 3.8 for the engine and add a 3.8 CI job for engine tests, or raise the floor to 3.10+ everywhere.
  - Check which Python the live app uses in the Cloud dashboard. Moving it to a current Python means redeploying the app.

**D6. The `code_version` module reload. Medium.**
- **Evidence:** it deletes modules from `sys.modules` while other sessions may be mid-run (`code_version.py:44-47`), so one run can mix old and new classes. It costs 1.17 ms per run. Combined with the per-class store cache, it is the source of the leak in A3.
- **Recommendation:** in the short term, the stat-based check (B3) plus retiring old stores. In the long term, deploy by restarting the process; with an external store, a restart costs nothing.

**D7. i18n. Low.**
- **Evidence:** English text as the key plus a test that scans every `t("...")` works well for two languages. But the per-thread language is set only in full runs (`abaka_ui.py:88`). Any future fragment or dialog that renders text would run in a new thread and fall back to English (`ui_components/i18n.py:24-25`).
- **Recommendation:** set the language at the start of fragment runs too, and switch errors to codes (D2).

### E. Build, deploy and operations

**E1. Streamlit is not pinned on Cloud. High.**
- **Evidence:** `requirements.txt:1` says `streamlit>=1.48`. Cloud already runs a newer Streamlit whose widgets render differently, while the tests run against 1.48.
- **Recommendation:** pin the version the live app runs today (it is in the Cloud logs) and lock the transitive dependencies. Upgrade on purpose, in a PR that CI checks.

**E2. There is no CI, and the suite is red. High.**
- **Recommendation:**
  - Run GitHub Actions on every PR:
    - `unittest` with Streamlit on the deploy Python and on 3.9;
    - engine-only tests on 3.8, on an `ubuntu-22.04` runner;
    - `ruff`, and later mypy on `abaka/`.
  - Take the legacy test out of discovery and make the checks required on `main`.
  - GitHub Actions is free for public repositories.

**E3. Test gaps. Medium.**
- **What exists:** 92 good behavioural tests, including full AppTest flows.
- **What is missing:**
  - The 1,092-game simulation and the AppTest scenarios live only in the scratchpad (`sim/simulate.py`, `sim/ui_apptest.py`), not in the repo.
  - There are no golden save files.
  - Nothing tests escaping, limits, deletion of expired files, or two stores after a deploy.
  - There is no performance check and no coverage report.
- **Recommendation:** commit the simulation and a websocket load test as opt-in tests, and track CPU per poll and per rerun for each release.

**E4. Observability is minimal. Medium.**
- **Evidence:** the only signals are `print(..., file=sys.stderr)` at `abaka/rooms.py:369` and `387`.
- **Recommendation:**
  - Use `logging`, and write one stats line a minute: rooms in memory, sessions, polls per second, p95 save time, garbage-collection time, RSS.
  - Add a small admin page protected by a secret in `st.secrets`.

**E5. Configuration. Low.**
- **Recommendation:**
  - Add `[runner] postScriptGC = false` and `[browser] gatherUsageStats = false`. The second also stops the page-profile message sent after every run, polls included (`script_runner.py:699-716`).
  - `address = "0.0.0.0"` (`.streamlit/config.toml:4`) exposes a laptop server to the whole local network. That is intended for home play; document it.
  - `.devcontainer/devcontainer.json` turns off XSRF and CORS protection; that is acceptable for development only.

### F. Security and abuse

**F1. Anyone with the code can take a seat without proof. Medium.**
- **Evidence:**
  - `abaka/rooms.py:218-233`: `reclaim` gives any seat a new token with no check, one tap per name (`abaka_ui.py:431-440`).
  - After taking a seat in a waiting room, `leave` removes that player (`abaka/rooms.py:195-216`).
  - `resume_local` gives full control of a same-device game to anyone with its code (`abaka/rooms.py:157-163`).
- **Impact:** invite links forwarded in group chats let strangers play for others, empty waiting rooms, or vandalize games.
- **Recommendation (no accounts needed):**
  - A personal rejoin link per seat, `?room=CODE&seat=KEY`, with the key stored hashed.
  - Allow tap-to-rejoin only when the seat's holder has not polled for N minutes; otherwise ask the holder to confirm.
  - An optional PIN for same-device games.

**F2. Game codes can be guessed. Medium.**
- **Evidence:** 5 characters from 32 symbols gives 33.5 million codes (`abaka/rooms.py:34-35`). Nothing limits probing through `?room=` or "Open game" (`abaka_ui.py:163-172`).
- **Impact:** with 10,000 rooms kept for 7 days, about 1 random code in 3,400 finds a game, and a scripted websocket client can try dozens per second.
- **Recommendation:** 6-7 characters for new codes (existing codes keep working), a probe limit per session, and F1.

**F3. Player names are rendered as Markdown without escaping. Medium.**
- **Evidence:**
  - `st.caption` at `ui_components/main_ui.py:127` and `145`;
  - `st.toast` at `abaka_ui.py:280` and `338`;
  - button labels at `abaka_ui.py:227` and `433`, and `ui_components/main_ui.py:147`.
  - Streamlit renders links and images in button labels (`elements/widgets/button.py:113-114`) and Markdown in captions and toasts.
  - HTML contexts are escaped correctly.
- **Impact:** a 19-character name such as `![](https://x.yz/a)` can make other players' browsers load third-party content, which leaks their IP address, or show a phishing link inside the game.
- **Recommendation:** escape Markdown in those places, or restrict `clean_name` (`abaka/rooms.py:46-48`) to letters, digits, spaces and basic punctuation, removing control and bidi characters.

**F4. Room creation is unlimited. Medium.**
- **Evidence:** no cap or rate limit at `abaka/rooms.py:125-155`. Each room costs about 13 KB of memory, 2-4.5 KB of disk and about 76 objects the collector must scan.
- **Impact:** a script that creates rooms in a loop slows every poll (A1) long before memory runs out.
- **Recommendation:**
  - A hard cap on rooms in memory, after evicting idle ones.
  - A limit per session, such as 5 per 10 minutes.
  - A best-effort limit per IP from `X-Forwarded-For` in `st.context.headers`. `st.context.ip_address` may be the proxy's address on Cloud.

**F5. What is already solid. Low.**
- Seat tokens are 128-bit `secrets.token_urlsafe(16)` (`abaka/rooms.py:149`, `229`, `338`), kept only in server-side session state and never sent to the browser.
- Escaping in `st.html` contexts is consistent.
- The server enforces input limits itself (`abaka/rooms.py:47`, `127-128`, `143-144`).
- Plain-text tokens in the save files should become hashes once a shared store is used.

## 4. Quick wins (no new infrastructure or accounts)

1. **Garbage collection and usage stats.**
   - Change: add `[runner] postScriptGC = false` and `[browser] gatherUsageStats = false` to `.streamlit/config.toml`.
   - Measured effect: a poll from 17-51 ms to 2.5-5.4 ms of CPU, a rerun from 35-65 ms to about 20 ms, and the collapse at 100 browsers and 5,000 rooms removed.
   - Effort: minutes. Watch RSS afterwards.
2. **Retire old stores after each code update**, which fixes the leak and the double writer (A3, C3). Effort: S.
3. **Make reads and trial moves cheap.**
   - `view()` returns the shared copy-on-write snapshot.
   - `GameEngine.clone()` is used by `_act` and `score_options`.
   - The move list is cached per room code and version.
   - Add a test that rendering never changes the snapshot.
   - Effort: S.
4. **Write files outside the global lock**, with unique temp files and newest-version-wins. Effort: S.
5. **Manage the room lifecycle.** Evict finished and idle rooms from memory and load them on demand, delete expired and unreadable files, and cap rooms and creations per session. Effort: S-M.
6. **Poll adaptively and use `on_click` callbacks** instead of `st.rerun()` after actions. Effort: S.
7. **Escape Markdown in names**, or restrict the characters names may contain. Effort: S.
8. **Clean up build and docs.**
   - Pin Streamlit.
   - Add GitHub Actions CI and take the legacy test out of discovery.
   - Delete the two stray requirements files and `main.py`.
   - Fix the three READMEs.
   - Effort: S.
9. **Add basic monitoring and trim small costs.** Logging and a stats line once a minute, a cap on `ss.my_games`, and the stat-based `code_version` check. Effort: S.
10. **Commit the measurement tools**: the simulation and a websocket load test, as opt-in tests, so every release can be measured. Effort: S.

## 5. Target architecture and staged roadmap

**Effort scale** (one developer, tests included): S is up to 2 days, M is 1-2 weeks, L is 3-6 weeks.

### Options

| Option | Capacity (estimate) | Pros | Cons | Effort | Owner cost |
|---|---|---|---|---|---|
| **A. Streamlit, one process, hardened** (the quick wins plus room lifecycle) | About 25-40 three-player games per M1-class core; about 1.5-3 times fewer on Cloud | No accounts; same code | Still polls; one process; games lost when Cloud sleeps | S-M | None |
| **B. Streamlit plus an external store and change notifications** (repository; Postgres LISTEN/NOTIFY or Redis pub/sub feeding an in-process version map; optionally a small component that subscribes to a hosted pub/sub and reruns only on change, removing polling) | Same as A per replica; scales by adding replicas | Games survive restarts; incremental; can scale out | Each rerun still costs about 20 ms per browser; replicas need paid hosting and sticky sessions | M, plus M for replicas | Database free tier or a small plan; paid hosting for replicas |
| **C. Game server plus thin client** (FastAPI and WebSockets reusing `abaka/` unchanged; per-room locking; state in Redis or Postgres; client in HTMX + SSE reusing the scoreboard HTML and CSS, or a small TypeScript single-page app) | Thousands of connections per instance; well under 1 ms of CPU per action (measured engine plus serialization 0.05-0.5 ms), against about 90 ms of Streamlit reruns per action today | True push in under 100 ms; idle players cost almost nothing; normal web security (cookies, rate limits); scales by room | Rewrite of the UI: dice, move picker, scoreboard, i18n, phone layout; new operations work | L | Hosting and database; possibly a domain |

### Roadmap (the game stays playable at every step)

**Stage 0: Stabilize. S, about 2-4 days.**
- **Changes:** quick wins 1-4 and 7-10, shipped one PR at a time and checked against the stats line.
- **Owner decides:** approve the config change and the version pin; decide the Python policy; decide whether the CLI and the old docs stay.

**Stage 1: Harden the single process. M.**
- **Changes:**
  - room lifecycle (only active rooms in memory);
  - the `RoomRepository` interface with today's files behind it;
  - player presence and seat protection with personal links;
  - caps and rate limits;
  - adaptive polling and callbacks;
  - logging, a stats line, and a load-test baseline.
- **Owner decides:** how rejoining should work (personal link, PIN or host approval); the limits; how long finished games are kept.

**Stage 2: Durable shared store. M.**
- **Changes:** Postgres or Redis behind the repository; a one-time import of the JSON files; one release writing to both; then reads switch to the database, controlled by a flag. Games then survive Cloud sleeping and reboots.
- **Owner decides:**
  - Creates a database account: Supabase or Neon for Postgres, Upstash or Redis Cloud for Redis. Check current free-tier pauses and quotas, and never query the database on every poll.
  - Adds the connection URL to Streamlit secrets.
  - Accepts that player names and games are stored by a third party.
  - Sets the retention period.

**Stage 3: Scale out. M or L.** Start this when the stats show over about 50% CPU at peak, or when hundreds of games are a real target.
- **3a. Stay on Streamlit (M).**
  - Move to a paid host with two or more replicas and sticky sessions.
  - Store notifications update a per-process version map.
  - Optionally add the push component.
- **3b. Game server (L).**
  - A FastAPI and WebSocket service using `abaka/` unchanged.
  - During migration the Streamlit app reads and writes the same store, so both UIs can play the same rooms.
  - Ship the new client for online games first and keep Streamlit for same-device games until the new client matches it, then retire Streamlit. The upstream abaka_cc project is a useful architecture reference; do not take its rule details.
- **Owner decides:** a hosting budget (small paid instances typically cost a few dollars to a few tens of dollars a month each; check current prices), a domain, 3a or 3b, and whether a UI rewrite is acceptable.

If "hundreds of parallel games" is not a near-term target, Stages 0-2 are enough. They keep the free Community Cloud, make games durable, and raise capacity several-fold.

### Critical Files for Implementation
- /Users/dpinchuk/Documents/PycharmProjects/Abaka/.streamlit/config.toml
- /Users/dpinchuk/Documents/PycharmProjects/Abaka/abaka/rooms.py
- /Users/dpinchuk/Documents/PycharmProjects/Abaka/abaka_ui.py
- /Users/dpinchuk/Documents/PycharmProjects/Abaka/ui_components/moves.py
- /Users/dpinchuk/Documents/PycharmProjects/Abaka/abaka/engine.py
