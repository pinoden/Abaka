#!/usr/bin/env python3
"""
The website's main flows in a real browser (headless Chromium, through Playwright), so the
web app keeps working while the apps for phones are built (Backlog item 25).

    python tools/website_check.py                       # the live app
    python tools/website_check.py --serve abaka_ui.py   # a local server, started for the check
    python tools/website_check.py --url http://127.0.0.1:8501/

It checks, at a desktop and a phone width:
- the home page in English and in Russian, and its note on where games are saved;
- a game on one device: the starting throw, a roll, a die picked and rolled again, the
  option with the most points written, the race for column I's bonus shown, then a row
  crossed out, the chart of scores by move, and the row differences switched on;
- an online game between a desktop and a phone: created, joined, the starting throws on
  each player's screen, a roll seen on the other screen, the turn passing with the bonus
  race shown, a chat message and a reaction;
- a game against the computer on a phone: one seat for the computer, the starting throw,
  and the computer playing its turn by itself (its mark on the turn, then its move in the
  "Last move" line), until the player's turn comes back, with the computer's final dice
  left on the table until the player rolls;
- on every page: no error box, no page error, and on the phone no sideways scrolling.

Test games are played by "Test Ann" and "Test Bob" (or "Test Ann" and the computer). With --cleanup and $ABAKA_DATABASE_URL,
the games this check made are marked deleted in that database afterwards (only games with
exactly those players).

Needs Playwright and its Chromium: pip install -r requirements-dev.txt, then
python -m playwright install chromium-headless-shell. Exits with 1 if anything failed.
tests/test_website.py runs it in CI against local servers.
"""

import argparse
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from typing import Callable, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent.parent
LIVE_URL = "https://mipt-abaka.streamlit.app/"
DESKTOP, PHONE = (1300, 900), (390, 844)
NAMES = ("Test Ann", "Test Bob")  # the players of the check's games
WAIT_MS = 30000    # for what a page shows after a click, or after another screen's move
START_MS = 150000  # for a page's first view (the live app may be waking up)
COMPUTER = "Computer"  # the computer's seat in the check's game against it (English page)
FLOWS = ("home", "one device", "online", "computer")


class Problem(Exception):
    """Something the website did not do as it should."""


def unavailable() -> Optional[str]:
    """Why the check cannot run here (None if it can): Playwright or its Chromium is missing."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return "Playwright is not installed (pip install -r requirements-dev.txt)"
    try:
        with sync_playwright() as p:
            p.chromium.launch().close()
    except Exception as e:  # noqa: BLE001 - no browser: say so
        return f"Chromium does not start ({str(e).splitlines()[0]}): python -m playwright install chromium-headless-shell"
    return None


class Screen:
    """One browser tab on the site. `app` is the app's frame (on Streamlit Cloud, inside Cloud's own page)."""

    def __init__(self, browser, url: str, size: Tuple[int, int], name: str) -> None:
        self.name = name
        self.phone = size[0] < 640
        self.context = browser.new_context(viewport={"width": size[0], "height": size[1]}, locale="en-US")
        self.page = self.context.new_page()
        self.errors: List[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.goto(url, timeout=START_MS)
        self.app = self._app_frame()

    def _app_frame(self):
        if ".streamlit.app" not in self.page.url:
            return self.page.main_frame
        deadline = time.time() + START_MS / 1000
        while time.time() < deadline:
            frame = next((f for f in self.page.frames if "/~/+/" in f.url), None)
            if frame is not None:
                return frame
            self.page.wait_for_timeout(500)
        raise Problem(f"{self.name}: the app did not appear in Streamlit Cloud's page")

    def see(self, locator, what: str, timeout: int = WAIT_MS):
        """The first element `locator` finds, once it is visible."""
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
        except Exception:  # noqa: BLE001 - Playwright's timeout
            raise Problem(f"{self.name}: {what} did not appear{self.why()}") from None
        return locator.first

    def until(self, condition: Callable[[], bool], what: str, timeout: int = WAIT_MS) -> None:
        deadline = time.time() + timeout / 1000
        while not condition():
            if time.time() > deadline:
                raise Problem(f"{self.name}: {what} did not happen{self.why()}")
            self.page.wait_for_timeout(200)

    def why(self) -> str:
        """An error box or page error on this screen, to explain a step that did not happen."""
        try:
            boxes = self.app.locator('[data-testid="stException"]')
            if boxes.count():
                return f" (the page shows an error: {' '.join(boxes.first.inner_text().split())[:300]})"
        except Exception:  # noqa: BLE001 - the page itself is gone
            pass
        return f" (page errors: {self.errors[:2]})" if self.errors else ""

    def key(self, key: str):
        """The button of the widget with this key (Streamlit adds the class st-key-<key>)."""
        return self.app.locator(f".st-key-{key} button")

    def options(self):
        return self.app.locator('[class*="st-key-pick-"] button')

    def room(self) -> str:
        return self.app.evaluate("() => new URLSearchParams(location.search).get('room')") or ""

    def dice(self) -> List[str]:
        return self.app.locator('[class*="st-key-die-"] button').all_text_contents()

    def healthy(self) -> None:
        boxes = self.app.locator('[data-testid="stException"]')
        if boxes.count():
            raise Problem(f"{self.name}: an error box: {boxes.first.inner_text()[:300]}")
        if self.errors:
            raise Problem(f"{self.name}: page errors: {self.errors[:3]}")
        if self.phone:
            sideways = self.app.evaluate("() => document.documentElement.scrollWidth - innerWidth")
            if sideways > 0:
                raise Problem(f"{self.name}: the page scrolls sideways by {sideways}px")

    def close(self) -> None:
        self.context.close()


def check_home(browser, url: str, size: Tuple[int, int], label: str) -> str:
    """The home page in Russian and in English. Returns its note on where games are saved."""
    ru = Screen(browser, url + "?lang=ru", size, f"the home page in Russian ({label})")
    ru.see(ru.app.get_by_role("button", name="Начать игру"), 'the "Начать игру" button', START_MS)
    ru.see(ru.app.get_by_text("Одно устройство", exact=True), 'the "Одно устройство" card')
    ru.healthy()
    ru.close()
    en = Screen(browser, url + "?lang=en", size, f"the home page ({label})")
    en.see(en.app.get_by_role("button", name="Start game"), 'the "Start game" button', START_MS)
    note = en.see(en.app.get_by_text(re.compile(r"^Games are saved")), "the note on where games are saved")
    text = note.inner_text().strip()
    en.healthy()
    en.close()
    return text


def write_best(screen: Screen) -> str:
    """Pick the option marked as the most points and write it. Returns the confirm button's text."""
    screen.see(screen.options(), "the options to write the roll")
    options = screen.options()
    screen.until(lambda: any(options.nth(i).locator("strong").count() for i in range(options.count())),
                 "an option marked as the most points")
    best = next(i for i in range(options.count()) if options.nth(i).locator("strong").count())
    options.nth(best).click()
    confirm = screen.key("confirm")
    screen.until(lambda: re.search(r"\b(Score|Write)\b", confirm.inner_text() or "") is not None,
                 "the confirm button naming the move")
    text = " ".join(confirm.inner_text().split()[1:])  # without the icon's name
    confirm.click()
    return text


def check_one_device(browser, url: str, size: Tuple[int, int], label: str, games: List[str]) -> None:
    """A game on one device, from the home page to a row crossed out; the score chart and the row differences."""
    s = Screen(browser, url + "?lang=en", size, f"a game on one device ({label})")
    s.see(s.app.get_by_label("Player 1"), "the Player 1 box", START_MS).fill(NAMES[0])
    s.see(s.app.get_by_label("Player 2"), "the Player 2 box").fill(NAMES[1])
    s.see(s.app.get_by_role("button", name="Start game"), 'the "Start game" button').click()
    s.see(s.app.get_by_text("Who goes first?"), '"Who goes first?"')
    games.append(s.room().split("-")[0])  # the address holds the full code: the code and its key
    roll = s.key("roll")
    for _ in range(40):  # each player throws in turn; a tie throws again
        if roll.count():
            break
        throw = s.key("start-throw")
        if throw.count():
            throw.first.click()
        s.page.wait_for_timeout(1200)
    s.see(roll, "the Roll dice button after the starting throw").click()
    s.see(s.options(), "the options to write the roll")
    s.see(s.key("die-0"), "the first die").click()  # picked to roll again
    s.see(s.app.get_by_role("button", name="Reroll 1 die"), 'the "Reroll 1 die" button').click()
    s.see(s.app.locator('[class*="st-key-reroll-all-1"] button'), '"Reroll all" with one reroll left')
    write_best(s)
    s.see(s.app.get_by_text("Last move:"), 'the "Last move" line')
    s.see(s.app.locator(".ab-race", has_text="Column I"), "the race for column I's bonus under the dice")
    s.see(roll, "the next player's Roll dice button").click()
    s.see(s.app.get_by_text("Cross out", exact=True), 'the "Cross out" switch').click()
    confirm = s.key("confirm")
    s.until(lambda: "Choose a row to cross out" in (confirm.inner_text() or ""), "the rows to cross out")
    s.see(s.options(), "the rows to cross out").click()
    s.until(lambda: "Cross out " in (confirm.inner_text() or ""), "the confirm button naming the row")
    confirm.click()
    s.see(s.app.get_by_text(re.compile(r"Last move:.*crossed out")), 'the crossed-out row in the "Last move" line')
    s.see(s.app.locator(".ab-chart"), "the chart of scores by move under the board")
    # Its lines are an image, and the browser must have drawn it (an <svg> element is removed from the page).
    s.until(lambda: s.app.locator(".ab-chart-plot img").count() == 1 and s.app.locator(".ab-chart-plot img").first
            .evaluate("e => e.complete && e.naturalWidth > 0 && e.getBoundingClientRect().height > 50"),
            "the chart's lines being drawn")
    s.see(s.app.locator(".st-key-diffs-switch label"), 'the "Row differences" switch').click()
    s.see(s.app.locator("table.ab-board.ab-diffs"), "the column of row differences, switched on")
    s.healthy()
    s.close()


def check_computer(browser, url: str, size: Tuple[int, int], label: str, games: List[str]) -> None:
    """A game against the computer (Backlog item 33), at a chosen level (item 34): it throws, rolls
    and writes by itself."""
    s = Screen(browser, url + "?lang=en", size, f"a game against the computer ({label})")
    s.see(s.app.locator(".st-key-local_computers_2 button", has_text="1"), 'the "Computer players" choice',
          START_MS).click()
    s.see(s.app.locator(".ab-computers", has_text=COMPUTER), "the computer's seat in the card")
    s.until(lambda: s.app.get_by_label("Player 2").count() == 0, "the second name box giving way to the computer")
    # Its level (Backlog item 34): Easy, Medium or Hard, shown with its mark on its turn.
    s.see(s.app.locator(".st-key-local_level button", has_text="Easy"), 'the "Level" choice').click()
    s.see(s.app.get_by_label("Player 1"), "the Player 1 box").fill(NAMES[0])
    s.see(s.app.get_by_role("button", name="Start game"), 'the "Start game" button').click()
    s.see(s.app.get_by_text("Who goes first?"), '"Who goes first?"')
    games.append(s.room().split("-")[0])
    roll, mark = s.key("roll"), s.app.locator(".ab-chip", has_text="computer · easy")
    for _ in range(60):  # the player throws; the computer throws by itself; a tie throws again
        if roll.count() or (mark.count() and not s.app.get_by_text("Who goes first?").count()):
            break
        throw = s.key("start-throw")
        if throw.count():
            throw.first.click()
        s.page.wait_for_timeout(1000)
    if roll.count():  # the player goes first
        roll.first.click()
        write_best(s)
    s.see(mark, "the computer's mark and level on its turn")
    s.see(s.app.get_by_text(re.compile(f"Last move: {COMPUTER} ")), "the computer's move in the \"Last move\" line")
    s.see(roll, "the player's Roll dice button after the computer's turn")
    # Its final dice stay on the table, with what it wrote, until the player rolls (Backlog item 35).
    left = s.app.locator(".ab-last-throw", has_text=f"{COMPUTER}’s last throw")
    s.see(left, "the computer's final dice left on the table")
    s.until(lambda: s.app.locator(".st-key-last-throw button").count() == 5, "the computer's five dice")
    roll.first.click()
    s.until(lambda: left.count() == 0 and s.app.locator(".st-key-last-throw").count() == 0,
            "the computer's dice giving way to the player's roll")
    s.healthy()
    s.close()


def check_online(browser, url: str, games: List[str]) -> None:
    """An online game: the host on a desktop, the guest on a phone."""
    host = Screen(browser, url + "?lang=en", DESKTOP, "an online game, the host (desktop)")
    host.see(host.app.get_by_label("Your name"), "the online game's name box", START_MS).fill(NAMES[0])
    host.see(host.app.get_by_role("button", name="Create game"), 'the "Create game" button').click()
    host.see(host.app.get_by_text("Invite a friend"), "the waiting room")
    full = host.room()  # the game's full code, its code and its key: the address holds it
    code, key = full.split("-") if full.count("-") == 1 else (full, "")
    games.append(code)
    if len(key) != 8:
        raise Problem(f"the host's address does not hold the game's full code ({full!r})")
    # The code alone opens nothing (Backlog item 31): not even the host's name shows.
    alone = Screen(browser, f"{url}?room={code}&lang=en", PHONE, "an online game opened by its code alone")
    alone.see(alone.app.get_by_text("This link is not complete"), "the page for a code alone", START_MS)
    if alone.app.get_by_text(NAMES[0]).count() or alone.app.get_by_role("button", name="Join game").count():
        raise Problem("the game's code alone showed the game")
    alone.close()
    guest = Screen(browser, f"{url}?room={full}&lang=en", PHONE, "an online game, the guest (phone)")
    guest.see(guest.app.get_by_text(f"{NAMES[0]} invited you to play"), "the invitation", START_MS)
    guest.see(guest.app.get_by_label("Your name"), "the name box").fill(NAMES[1])
    guest.see(guest.app.get_by_role("button", name="Join game"), 'the "Join game" button').click()
    screens = (host, guest)
    for screen in screens:
        screen.see(screen.app.get_by_text("Who goes first?"), '"Who goes first?"')
    mover = None
    for _ in range(60):  # each player throws on their own screen
        mover = next((s for s in screens if s.key("roll").count()), None)
        if mover is not None:
            break
        for screen in screens:
            throw = screen.key("start-throw")
            if throw.count() and throw.first.is_enabled():
                throw.first.click()
        host.page.wait_for_timeout(1000)
    if mover is None:
        raise Problem("an online game: nobody could roll after the starting throws" + host.why() + guest.why())
    watcher = guest if mover is host else host
    mover.see(mover.key("roll"), "the Roll dice button").click()
    mover.see(mover.options(), "the options to write the roll")
    rolled = mover.dice()
    watcher.until(lambda: watcher.dice() == rolled, f"the roll ({' '.join(rolled)}) on the other screen")
    write_best(mover)
    watcher.see(watcher.key("roll"), "the Roll dice button on the other screen (its turn)")
    watcher.see(watcher.app.locator(".ab-race", has_text="Column I"), "the bonus race on the other screen")
    guest.see(guest.app.locator(".st-key-chat-text input"), "the chat box").fill("Test hello")
    guest.see(guest.app.get_by_role("button", name="Send"), 'the "Send" button').click()
    host.see(host.app.get_by_text("Test hello"), "the guest's chat message on the host's screen")
    host.see(host.key("react-lucky"), 'the "Lucky!" reaction').click()
    guest.see(guest.app.locator(".ab-bubble", has_text="Lucky!"), "the host's reaction on the guest's screen")
    for screen in screens:
        screen.healthy()
        screen.close()


def run(url: str, flows=FLOWS, report=print) -> Tuple[List[str], List[str]]:
    """Check the site at `url`. Returns (problems found, codes of the games it made)."""
    from playwright.sync_api import sync_playwright
    url = url if url.endswith("/") else url + "/"
    problems: List[str] = []
    games: List[str] = []

    def step(name: str, check: Callable[[], Optional[str]]) -> None:
        started = time.time()
        try:
            said = check()
        except Exception as e:  # noqa: BLE001 - a Problem, or Playwright failing on the page
            problems.append(f"{name}: {e}")
            report(f"FAIL {name} ({time.time() - started:.0f} s): {e}")
        else:
            report(f"ok   {name} ({time.time() - started:.0f} s)" + (f": {said}" if said else ""))

    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            for label, size in (("desktop", DESKTOP), ("phone", PHONE)):
                if "home" in flows:
                    step(f"home page, {label}", lambda: check_home(browser, url, size, label))
                if "one device" in flows:
                    step(f"a game on one device, {label}", lambda: check_one_device(browser, url, size, label, games))
            if "online" in flows:
                step("an online game, desktop and phone", lambda: check_online(browser, url, games))
            if "computer" in flows:
                step("a game against the computer, phone",
                     lambda: check_computer(browser, url, PHONE, "phone", games))
        finally:
            browser.close()
    return problems, [g for g in games if g]


def serve(script: str, folder: str):
    """
    Start `streamlit run <script>` on a free port, saving games in `folder` and never in a
    database. Returns (process, url, log path). Stop it with process.terminate().
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    log_path = os.path.join(folder, "server.log")
    env = dict(os.environ, ABAKA_SAVE_DIR=os.path.join(folder, "games"), ABAKA_DATABASE_URL="")
    with open(log_path, "w") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", script, "--server.port", str(port),
             "--server.address", "127.0.0.1", "--server.headless", "true", "--server.fileWatcherType", "none",
             "--browser.gatherUsageStats", "false"],
            cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}/"
    deadline = time.time() + 90
    while True:
        try:
            with urllib.request.urlopen(url + "_stcore/health", timeout=2):
                return process, url, log_path
        except OSError:
            if process.poll() is not None or time.time() > deadline:
                process.terminate()
                raise RuntimeError(f"{script} did not start: {Path(log_path).read_text()[-2000:]}")
            time.sleep(0.5)


def check_local(script: str, flows=FLOWS, report=print) -> List[str]:
    """Start `script` on a local server, check it, stop it. Returns the problems found."""
    with tempfile.TemporaryDirectory() as folder:
        process, url, log_path = serve(script, folder)
        try:
            problems, _ = run(url, flows, report)
        finally:
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()
        if problems:
            problems.append(f"the server's log: {Path(log_path).read_text()[-2000:]}")
        return problems


def clean_up(codes: List[str]) -> str:
    """Mark the check's games deleted in $ABAKA_DATABASE_URL (only games with exactly the test players)."""
    url = os.environ.get("ABAKA_DATABASE_URL", "").strip()
    if not url or not codes:
        return "nothing to clean up" if codes else "no games made"
    import psycopg
    deleted = []
    with psycopg.connect(url, prepare_threshold=None, application_name="abaka-website-check") as db:
        for code in codes:
            row = db.execute("select data->'names' from abaka_rooms where code = %s and not deleted",
                             (code,)).fetchone()
            if row is not None and row[0] in (list(NAMES), [NAMES[0], COMPUTER]):
                db.execute("update abaka_rooms set deleted = true, data = null where code = %s", (code,))
                deleted.append(code)
    return f"marked deleted in the database: {', '.join(deleted) or 'none'}"


def main() -> int:
    parser = argparse.ArgumentParser(description="The website's main flows in a real browser.")
    parser.add_argument("--url", default=LIVE_URL, help=f"the site to check (default: the live app, {LIVE_URL})")
    parser.add_argument("--serve", metavar="SCRIPT",
                        help="start this app script on a local server and check it (abaka_ui.py or abaka_server.py)")
    parser.add_argument("--only", choices=FLOWS, action="append", help="check only these flows")
    parser.add_argument("--cleanup", action="store_true",
                        help="mark the check's games deleted in $ABAKA_DATABASE_URL afterwards")
    args = parser.parse_args()
    reason = unavailable()
    if reason:
        print(reason)
        return 2
    flows = tuple(args.only or FLOWS)
    if args.serve:
        problems = check_local(args.serve, flows)
        games: List[str] = []
    else:
        print(f"checking {args.url}")
        problems, games = run(args.url, flows)
        if games:
            print("test games:", ", ".join(games))
        if args.cleanup:
            print(clean_up(games))
    print("WEBSITE OK" if not problems else f"WEBSITE BROKEN: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
