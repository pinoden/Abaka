# Load-test baseline

One row per release, from `tools/loadtest.py --baseline --record docs/LOADTEST.md`:
100 simulated pages polling their game every second (the most a page polls: while
watching another player's turn online), 200 saved games, measured for 20 s after 5 s
of warm-up. The server runs the app as it is in the repository, saving to a
temporary folder only.

- **Pages:** simulated browser tabs and how often each polls.
- **CPU %:** the server process's CPU over the window (100% = one core).
- **Polls/s offered / answered:** answered below offered means the server fell behind.
- **Poll p50 / p95 ms:** time from a poll's request to its finished run.
- **CPU ms per poll:** server CPU spent per answered poll.
- **Page run ms:** a full page run when a tab opens its game (median).
- **RSS MB:** the server's memory at the end.

Compare rows only from the same machine and versions: the tool does that when it
records a row, and says if the new one is more than 25% worse.

| Date | Commit | Machine | Python / Streamlit | Pages | Rooms | CPU % | Polls/s offered / answered | Poll p50 / p95 ms | CPU ms per poll | Page run ms | RSS MB | Options |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 2026-11-19 | 996d5f5 | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 31 | 100 / 97 | 8.2 / 21.3 | 3.2 | 76.9 | 50 | - |
| 2026-11-19 | 555b807+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 30 | 100 / 97 | 7.1 / 15.4 | 3.1 | 77.2 | 51 | - |
| 2026-11-19 | 000c752+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 30 | 100 / 98 | 7.0 / 16.3 | 3.0 | 76.0 | 51 | - |
| 2026-11-19 | 095042a+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 30 | 100 / 98 | 7.5 / 17.4 | 3.1 | 77.8 | 51 | - |
| 2026-11-19 | 460b14c+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 29 | 100 / 98 | 7.2 / 17.2 | 3.0 | 76.5 | 51 | - |
| 2026-11-19 | c106f92+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 25 | 100 / 99 | 6.1 / 15.5 | 2.5 | 77.5 | 52 | - |
| 2026-11-19 | 304ecd4+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 28 | 100 / 99 | 7.7 / 20.7 | 2.9 | 77.3 | 59 | - |
| 2026-11-19 | 29d653e+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 25 | 100 / 100 | 6.8 / 29.7 | 2.5 | 80.5 | 49 | - |
| 2026-11-19 | 69d2f9e+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 33 | 100 / 98 | 8.6 / 19.8 | 3.4 | 76.1 | 62 | - |
| 2026-11-19 | d817d25+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 34 | 100 / 97 | 8.9 / 18.6 | 3.5 | 79.4 | 52 | - |
| 2026-11-20 | a892cec+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 25 | 100 / 93 | 6.9 / 24.9 | 2.7 | 94.3 | 29 | - |
| 2026-11-20 | fc63c90+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 26 | 100 / 97 | 7.1 / 19.4 | 2.6 | 78.1 | 27 | - |
| 2026-11-20 | 42fe29b+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 29 | 100 / 97 | 7.6 / 20.8 | 3.0 | 86.2 | 51 | - |
| 2026-11-21 | 8a58a5c+changes | Apple M1, 8 cores, Darwin | 3.9.20 / 1.48.1 | 100 every 1 s | 200 | 28 | 100 / 97 | 7.6 / 20.7 | 2.9 | 80.6 | 45 | - |
