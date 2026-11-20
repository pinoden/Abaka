"""
Load test: many browsers keeping an Abaka game open, simulated over websockets.

Starts the app on a local port with a temporary save folder full of games, then
opens N simulated browsers. Each one opens a saved same-device game (3 players,
mid-game, dice on the table) and then polls it like the page's `_watch_room`
fragment does in a real browser, at the interval the page asks for (a
same-device game: every 10 s). `--interval 1` polls every second instead, like
a page watching another player's turn online: the worst case. Reports server
CPU and memory, polls answered per second, and poll latency.

  python tools/loadtest.py --clients 100 --interval 1
  python tools/loadtest.py --clients 100 --rooms 5000 --seconds 20 --interval 1
  python tools/loadtest.py --clients 100 --interval 1 --set runner.postScriptGC=true   # compare a setting
  python tools/loadtest.py --baseline --record docs/LOADTEST.md   # the release baseline, kept in the repo

`--baseline` runs the standard measurement (100 pages polling every second,
200 saved games, 20 s). `--record FILE` adds the run as a row to FILE's table
and compares it with the latest row from the same machine and Streamlit
version, so a release that makes the server slower shows up.

The server never gets a database URL: a load test saves to a temporary folder only.

Needs the Python environment that runs the app: Streamlit and its protobuf, and
a websocket client, `websockets` (a dependency of Streamlit 1.5x and later) or
Tornado (Streamlit 1.4x runs on it).
A simulated browser sends no cached-message hashes, so it receives a little more
data than a real one; it skips a poll while its previous one is unanswered (a
real browser keeps firing), so real overload is somewhat worse than reported.
"""

import argparse
import asyncio
import datetime
import os
import platform
import random
import shutil
import statistics
import subprocess
import sys
import tempfile
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from streamlit.proto.BackMsg_pb2 import BackMsg  # noqa: E402
from streamlit.proto.ForwardMsg_pb2 import ForwardMsg  # noqa: E402

from abaka.rooms import RoomStore  # noqa: E402

DONE = {ForwardMsg.FINISHED_SUCCESSFULLY, ForwardMsg.FINISHED_FRAGMENT_RUN_SUCCESSFULLY,
        ForwardMsg.FINISHED_WITH_COMPILE_ERROR}


def make_games(save_dir: str, rooms: int, seed: int = 1) -> list:
    """Saved same-device games, 3 players each, a few turns in, dice rolled."""
    random.seed(seed)
    store = RoomStore(save_dir=save_dir)
    codes = []
    for _ in range(rooms):
        code, key = store.create_local(["Ann", "Bob", "Cy"])
        while store.view(code).engine.choosing_first_player:
            store.throw_for_start(code, key)
        for _ in range(random.randint(0, 6)):
            store.roll(code, key)
            store.score(code, key, *_any_cell(store, code))
        store.roll(code, key)
        codes.append(code)
    return codes


def _any_cell(store, code):
    from abaka.moves import cross_options, score_options
    g = store.view(code).engine
    move = (score_options(g) or cross_options(g))[0]
    return move.category, move.slot


def server_stats(pid: int):
    """(cpu seconds, rss MB) of a process, from ps."""
    out = subprocess.run(["ps", "-o", "cputime=,rss=", "-p", str(pid)], capture_output=True, text=True).stdout.split()
    if len(out) < 2:
        return 0.0, 0.0
    parts = [float(p) for p in out[0].replace("-", ":").split(":")]
    seconds = 0.0
    for p in parts:
        seconds = seconds * 60 + p
    return seconds, int(out[1]) / 1024


class Stream:
    """The app's websocket, through `websockets` if it is installed, else Tornado."""

    @classmethod
    async def open(cls, url: str) -> "Stream":
        stream = cls()
        try:
            import websockets
        except ImportError:
            from tornado.websocket import websocket_connect
            stream.ws, stream.tornado = None, await websocket_connect(url, subprotocols=["streamlit"])
        else:
            stream.closed_error = websockets.ConnectionClosed
            stream.ws = await websockets.connect(url, subprotocols=["streamlit"], max_size=None)
        return stream

    async def send(self, data: bytes) -> None:
        if self.ws is not None:
            await self.ws.send(data)
        else:
            await self.tornado.write_message(data, binary=True)

    async def recv(self):
        """The next message, or None once the connection is closed."""
        if self.ws is None:
            return await self.tornado.read_message()
        try:
            return await self.ws.recv()
        except self.closed_error:
            return None

    async def close(self) -> None:
        if self.ws is not None:
            await self.ws.close()
        else:
            self.tornado.close()


class Browser:
    """One simulated browser tab."""

    def __init__(self, url: str, code: str, interval: float = None):
        self.url, self.code = url, code
        self.query = f"room={code}"
        self.fragment = None
        self.forced_interval = interval  # None: poll as often as the page asks
        self.interval = interval or 1.0
        self.latencies, self.skipped, self.sent = [], 0, 0
        self.full_runs = []

    async def run_script(self, fragment=None) -> float:
        msg = BackMsg()
        state = msg.rerun_script
        state.query_string = self.query
        if fragment:
            state.fragment_id = fragment
            state.is_auto_rerun = True
        t0 = time.perf_counter()
        await self.conn.send(msg.SerializeToString())
        while True:
            raw = await self.conn.recv()
            if raw is None:
                raise ConnectionError("closed")
            fwd = ForwardMsg()
            fwd.ParseFromString(raw)
            kind = fwd.WhichOneof("type")
            if kind == "auto_rerun":
                self.fragment = fwd.auto_rerun.fragment_id
                self.interval = self.forced_interval or fwd.auto_rerun.interval or 1.0
            elif kind == "page_info_changed" and fwd.page_info_changed.query_string:
                self.query = fwd.page_info_changed.query_string
            elif kind == "script_finished" and fwd.script_finished in DONE:
                return time.perf_counter() - t0

    async def open(self):
        self.conn = await Stream.open(self.url)
        for _ in range(3):  # the invite page resumes the game and reruns into it
            self.full_runs.append(await self.run_script())
            if self.fragment:
                return
        raise RuntimeError(f"no polling fragment on the page for game {self.code}")

    async def poll_until(self, stop_at: float, measure_from: float):
        next_poll = time.perf_counter() + random.random() * self.interval
        pending = None
        while True:
            await asyncio.sleep(max(0.0, min(next_poll, stop_at) - time.perf_counter()))
            if time.perf_counter() >= stop_at:
                break
            next_poll += self.interval
            if pending is not None and not pending.done():
                if time.perf_counter() >= measure_from:
                    self.skipped += 1
                continue
            started = time.perf_counter()
            pending = asyncio.ensure_future(self.run_script(self.fragment))

            def record(task, started=started):
                if not task.cancelled() and task.exception() is None and started >= measure_from:
                    self.latencies.append(task.result())
            pending.add_done_callback(record)
            if started >= measure_from:
                self.sent += 1
        if pending is not None and not pending.done():
            pending.cancel()


def pct(values, q):
    if not values:
        return float("nan")
    values = sorted(values)
    return values[min(len(values) - 1, int(q / 100 * len(values)))]


async def main_async(args, codes, pid):
    url = f"ws://127.0.0.1:{args.port}/_stcore/stream"
    browsers = [Browser(url, codes[i % len(codes)], args.interval) for i in range(args.clients)]
    for b in browsers:  # open them one by one, as people arrive
        await b.open()
    opening = [r for b in browsers for r in b.full_runs[-1:]]
    start = time.perf_counter()
    measure_from = start + args.warmup
    stop_at = measure_from + args.seconds
    tasks = [asyncio.ensure_future(b.poll_until(stop_at, measure_from)) for b in browsers]
    await asyncio.sleep(args.warmup)
    cpu0, _ = server_stats(pid)
    await asyncio.gather(*tasks)
    cpu1, rss = server_stats(pid)
    for b in browsers:
        await b.conn.close()
    latencies = [x for b in browsers for x in b.latencies]
    sent = sum(b.sent for b in browsers)
    offered = args.clients * args.seconds / browsers[0].interval
    served = len(latencies)
    cpu = cpu1 - cpu0
    return {
        "clients": args.clients, "rooms": args.rooms,
        "cpu %": round(100 * cpu / args.seconds), "rss MB": round(rss),
        "polls/s offered": round(offered / args.seconds), "polls/s answered": round(served / args.seconds),
        "skipped (still waiting)": sum(b.skipped for b in browsers),
        "poll p50 ms": round(pct(latencies, 50) * 1000, 1), "poll p95 ms": round(pct(latencies, 95) * 1000, 1),
        "cpu ms per poll": round(1000 * cpu / served, 1) if served else None,
        "page run p50 ms": round(statistics.median(opening) * 1000, 1), "sent": sent,
    }


# --- the baseline file -------------------------------------------------------------------------
COLUMNS = ["Date", "Commit", "Machine", "Python / Streamlit", "Pages", "Rooms", "CPU %",
           "Polls/s offered / answered", "Poll p50 / p95 ms", "CPU ms per poll", "Page run ms", "RSS MB",
           "Options"]
BASELINE = {"clients": 100, "rooms": 200, "seconds": 20, "warmup": 5, "interval": 1.0}
WORSE_BY = 1.25  # flag a number at least this much worse than the previous row


def _run(cmd):
    try:
        return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def machine() -> str:
    brand = _run(["sysctl", "-n", "machdep.cpu.brand_string"]) or platform.processor() or platform.machine()
    return f"{brand}, {os.cpu_count()} cores, {platform.system()}"


APP_PATHS = ["abaka", "ui_components", "abaka_ui.py", "code_version.py", ".streamlit", "requirements.txt"]


def commit() -> str:
    """The commit measured, with "+changes" if the app's files differ from it (other files do not count)."""
    head = _run(["git", "rev-parse", "--short", "HEAD"]) or "?"
    changed = _run(["git", "status", "--porcelain", "--untracked-files=no", "--"] + APP_PATHS)
    return head + ("+changes" if changed else "")


def row_for(result: dict, args) -> list:
    import streamlit
    pages = f"{args.clients} every {args.interval:g} s" if args.interval else f"{args.clients} as asked"
    return [datetime.date.today().isoformat(), commit(), machine(),
            f"{platform.python_version()} / {streamlit.__version__}", pages, str(args.rooms),
            str(result["cpu %"]), f'{result["polls/s offered"]} / {result["polls/s answered"]}',
            f'{result["poll p50 ms"]} / {result["poll p95 ms"]}', str(result["cpu ms per poll"]),
            str(result["page run p50 ms"]), str(result["rss MB"]), " ".join(args.set) or "-"]


def read_rows(path: str) -> list:
    """The table rows of a baseline file, oldest first (each a list of cells)."""
    if not os.path.exists(path):
        return []
    rows = []
    with open(path, encoding="utf-8") as f:
        lines = f.read().splitlines()
    for line in lines:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if line.startswith("|") and len(cells) == len(COLUMNS) and cells[0] != "Date" \
                and not set(cells[0]) <= set("-: "):
            rows.append(cells)
    return rows


def compare(new: list, rows: list) -> list:
    """Lines saying how `new` differs from the latest comparable row (same machine, versions, pages)."""
    same = [r for r in rows if r[2:6] == new[2:6] and r[12] == new[12]]
    if not same:
        return ["No earlier row from this machine with the same versions and load to compare with."]
    old = same[-1]

    def first(cell):
        try:
            return float(cell.split("/")[0])
        except ValueError:
            return None

    def second(cell):
        try:
            return float(cell.split("/")[1])
        except (ValueError, IndexError):
            return None

    lines = [f"Compared with {old[0]} ({old[1]}):"]
    worse = False
    for name, index, pick, higher_is_worse in (("CPU %", 6, first, True), ("polls answered", 7, second, False),
                                               ("poll p50 ms", 8, first, True), ("CPU ms per poll", 9, first, True),
                                               ("page run ms", 10, first, True)):
        a, b = pick(old[index]), pick(new[index])
        if a is None or b is None:
            continue
        bad = (b > a * WORSE_BY and b - a > 1) if higher_is_worse else (b < a / WORSE_BY)
        worse = worse or bad
        lines.append(f"  {name:<16} {a:g} -> {b:g}{'   WORSE' if bad else ''}")
    lines.append("  Slower than before: look into it before releasing." if worse else "  No slowdown.")
    return lines


def record(path: str, row: list) -> None:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write("# Load-test baseline\n\n| " + " | ".join(COLUMNS) + " |\n|"
                    + "|".join("---" for _ in COLUMNS) + "|\n")
    with open(path, "a", encoding="utf-8") as f:
        f.write("| " + " | ".join(row) + " |\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--clients", type=int, default=50, help="simulated browsers (default 50)")
    parser.add_argument("--rooms", type=int, default=200, help="saved games loaded by the server (default 200)")
    parser.add_argument("--seconds", type=float, default=15, help="measurement window (default 15)")
    parser.add_argument("--warmup", type=float, default=5, help="seconds of polling before measuring (default 5)")
    parser.add_argument("--interval", type=float, default=None,
                        help="poll every this many seconds instead of as often as the page asks "
                             "(1 = a page watching another player's turn online)")
    parser.add_argument("--port", type=int, default=8790)
    parser.add_argument("--baseline", action="store_true",
                        help="the standard release measurement: 100 pages polling every second, 200 games, 20 s")
    parser.add_argument("--record", metavar="FILE",
                        help="add the result to FILE's table (docs/LOADTEST.md) and compare it with the last row")
    parser.add_argument("--set", action="append", default=[], metavar="SECTION.OPTION=VALUE",
                        help="extra Streamlit option for the server, e.g. runner.postScriptGC=true")
    args = parser.parse_args()
    if args.baseline:
        for name, value in BASELINE.items():
            setattr(args, name, value)

    save_dir = tempfile.mkdtemp(prefix="abaka-loadtest-")
    server = None
    try:
        codes = make_games(save_dir, args.rooms)
        cmd = [sys.executable, "-m", "streamlit", "run", os.path.join(ROOT, "abaka_ui.py"),
               "--server.port", str(args.port), "--server.address", "127.0.0.1", "--server.headless", "true",
               "--browser.gatherUsageStats", "false"]
        for option in args.set:
            name, value = option.split("=", 1)
            cmd += [f"--{name}", value]
        # An empty database URL: the app then saves to files only and ignores any secrets file,
        # so a load test never reaches the production database.
        env = dict(os.environ, ABAKA_SAVE_DIR=save_dir, ABAKA_DATABASE_URL="")
        server = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        import urllib.request
        for _ in range(120):
            try:
                urllib.request.urlopen(f"http://127.0.0.1:{args.port}/_stcore/health", timeout=1)
                break
            except OSError:
                time.sleep(0.25)
        else:
            raise SystemExit("the app did not start")
        result = asyncio.run(main_async(args, codes, server.pid))
        width = max(len(k) for k in result)
        for key, value in result.items():
            print(f"{key:<{width}}  {value}")
        if args.record:
            row = row_for(result, args)
            path = args.record if os.path.isabs(args.record) else os.path.join(ROOT, args.record)
            earlier = read_rows(path)
            record(path, row)
            print("\n".join([f"Recorded in {args.record}."] + compare(row, earlier)))
    finally:
        if server is not None:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
        shutil.rmtree(save_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
