"""
The phone app (mobile/) in a real browser: its web build, played in headless Chromium at a
phone's size against a real game server, as tools/website_check.py plays the website.
The phones' own builds share all of the app's code with the web build; only the drawing
underneath differs.

Build the app for the web first, then check it:

    cd mobile && npx expo export --platform web && cd ..
    python tools/app_check.py --serve                         # starts abaka_server.py itself
    python tools/app_check.py --server http://127.0.0.1:8501  # a server already running

The checks:
- home in English and Russian;
- a game on one device: the starting throw, a roll, two dice picked and rolled again, the
  best option written, a row crossed out, and both players' columns on the screen;
- an online game between two phones: one creates it, the other opens its code and joins,
  the starting throws, and a roll and a move seen on the other phone.
Any page error and any sideways scrolling is a problem too.

Needs Playwright and its Chromium (requirements-dev.txt), and Streamlit 1.67 for --serve.
"""

import argparse
import functools
import http.server
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable, List, Tuple
from urllib.parse import quote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import website_check  # noqa: E402  (the same tools folder: its server start and browser test)

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "mobile" / "dist"
PHONE = (390, 844)
NAMES = ("Test Ann", "Test Bob")
WAIT_MS = 20000
FLOWS = ("home", "one device", "online")


class Problem(Exception):
    """A step of the app did not work."""


def serve_build(folder: Path) -> Tuple[http.server.ThreadingHTTPServer, str]:
    """Serve the web build on a free port; every unknown path gets index.html (the app's routes)."""

    class Handler(http.server.SimpleHTTPRequestHandler):
        def send_head(self):
            if not Path(self.translate_path(self.path)).is_file():
                self.path = "/index.html"
            return super().send_head()

        def log_message(self, *args) -> None:
            pass

    httpd = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(folder)))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, f"http://127.0.0.1:{httpd.server_address[1]}/"


class Phone:
    """One phone (a browser context at a phone's size) with the app open."""

    def __init__(self, browser, url: str, name: str, locale: str = "en-US") -> None:
        self.name = name
        self.context = browser.new_context(viewport={"width": PHONE[0], "height": PHONE[1]}, locale=locale)
        self.page = self.context.new_page()
        self.errors: List[str] = []
        self.page.on("pageerror", lambda e: self.errors.append(str(e)))
        self.page.on("console", lambda m: self.errors.append(m.text) if m.type == "error" else None)
        self.page.goto(url)

    def id(self, test_id: str):
        return self.page.get_by_test_id(test_id)

    def see(self, locator, what: str, timeout: int = WAIT_MS):
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
            self.page.wait_for_timeout(100)

    def why(self) -> str:
        alerts = self.page.get_by_role("alert")
        try:
            if alerts.count():
                return f" (the app says: {alerts.first.inner_text()[:200]})"
        except Exception:  # noqa: BLE001 - the page itself is gone
            pass
        return f" (page errors: {self.errors[:2]})" if self.errors else ""

    def text(self) -> str:
        return self.page.inner_text("body")

    def dice(self) -> List[str]:
        """The dice on the table: each die's value, and J for the joker (from its label, in any language)."""
        labels = [self.id(f"die-{i}").first.get_attribute("aria-label") or "" for i in range(5)]
        return [label.split(" ")[0] + ("J" if " " in label else "") for label in labels]

    def healthy(self) -> None:
        if self.errors:
            raise Problem(f"{self.name}: page errors: {self.errors[:3]}")
        sideways = self.page.evaluate("() => document.documentElement.scrollWidth - innerWidth")
        if sideways > 0:
            raise Problem(f"{self.name}: the page scrolls sideways by {sideways}px")

    def throw_until_decided(self, other: "Phone" = None) -> "Phone":
        """Throw for who goes first (on whichever phone may) until someone rolls. Returns that phone."""
        phones = [self] + ([other] if other else [])
        deadline = time.time() + WAIT_MS / 1000
        while time.time() < deadline:
            for phone in phones:
                if phone.id("roll").count() and phone.id("roll").first.is_visible():
                    return phone
                button = phone.id("start-throw")
                if button.count() and button.first.is_visible() and button.first.is_enabled():
                    button.first.click()
                    phone.page.wait_for_timeout(300)
            self.page.wait_for_timeout(200)
        raise Problem(f"{self.name}: the starting throw did not end{self.why()}")

    def close(self) -> None:
        self.context.close()


def check_home(browser, url: str) -> str:
    phone = Phone(browser, url, "home, phone")
    try:
        phone.see(phone.id("start-local"), "the home page")
        if "Same device" not in phone.text():
            raise Problem("home: no 'Same device' card in English")
        phone.page.get_by_role("radio", name="RU").click()
        phone.until(lambda: "Одно устройство" in phone.text(), "the switch to Russian")
        phone.page.get_by_role("radio", name="EN").click()
        phone.until(lambda: "Same device" in phone.text(), "the switch back to English")
        phone.healthy()
        return "English and Russian"
    finally:
        phone.close()


def write_best(phone: Phone) -> str:
    """Pick the option with the most points and confirm it. Returns its label."""
    best = phone.see(phone.page.locator('[data-testid^="option-"][data-testid$="-best"]'), "the best option")
    label = best.inner_text()
    best.click()
    phone.until(lambda: phone.id("confirm").first.is_enabled(), "the confirm button")
    phone.id("confirm").first.click()
    return label


def board_fits(phone: Phone) -> None:
    """Two players' columns fit the phone's width, without scrolling the table."""
    overflow = phone.page.evaluate("""() => {
        const board = document.querySelector('[data-testid="board"]');
        const scroller = board && [...board.querySelectorAll('div')]
            .find(d => ['auto', 'scroll'].includes(getComputedStyle(d).overflowX));
        return scroller ? scroller.scrollWidth - scroller.clientWidth : null;
    }""")
    if overflow is None:
        raise Problem(f"{phone.name}: the board's scrolling part was not found")
    if overflow > 0:
        raise Problem(f"{phone.name}: two players' columns are {overflow}px wider than the screen")


def check_one_device(browser, url: str, games: List[str]) -> None:
    phone = Phone(browser, url, "one device, phone")
    try:
        phone.see(phone.id("start-local"), "the home page")
        phone.id("local-name-0").fill(NAMES[0])
        phone.id("local-name-1").fill(NAMES[1])
        phone.id("start-local").click()
        phone.see(phone.id("start-throw"), "the starting throw")
        games.append(phone.page.url.rstrip("/").split("/")[-1].split("?")[0])
        phone.throw_until_decided()
        phone.id("roll").first.click()
        phone.see(phone.id("die-4"), "the dice")
        phone.until(lambda: "Roll 1 of 3" in phone.text(), "the first roll")
        phone.id("die-1").click()
        phone.id("die-3").click()
        phone.see(phone.page.get_by_text("Reroll 2 dice"), "two picked dice")
        phone.id("reroll-picked").click()
        phone.until(lambda: "Roll 2 of 3" in phone.text(), "the reroll")
        label = write_best(phone)
        phone.see(phone.id("last-move"), "the last move under the board")
        board_fits(phone)
        # The next player crosses a row out.
        phone.see(phone.id("roll"), "the next player's turn").click()
        phone.see(phone.id("die-4"), "the next player's dice")
        phone.page.get_by_role("radio", name="Cross out").click()
        phone.see(phone.page.locator('[data-testid^="option-"]'), "a row to cross out").click()
        phone.id("confirm").first.click()
        phone.until(lambda: "crossed out" in phone.id("last-move").first.inner_text(), "the crossed-out row")
        phone.healthy()
        if not label:
            raise Problem("one device: the best option had no label")
    finally:
        phone.close()


def check_online(browser, url: str, games: List[str]) -> None:
    ann = Phone(browser, url, "online, Ann's phone")
    bob = Phone(browser, url, "online, Bob's phone", locale="ru-RU")
    try:
        ann.see(ann.id("create-online"), "the home page")
        ann.id("online-name").fill(NAMES[0])
        ann.id("create-online").click()
        code = ann.see(ann.id("game-code"), "the game code").inner_text().strip()
        games.append(code)

        bob.see(bob.id("open-code"), "Bob's home page")
        bob.id("open-code").fill(code)
        bob.id("open-game").click()
        bob.see(bob.id("join-name"), "the invite").fill(NAMES[1])
        bob.id("join").click()
        ann.see(ann.id("starting-throw"), "the start, on Ann's phone, without a tap")

        roller = ann.throw_until_decided(bob)
        watcher = bob if roller is ann else ann
        roller.id("roll").first.click()
        roller.see(roller.id("die-4"), "the roller's dice")
        dice = roller.dice()
        watcher.see(watcher.id("die-4"), "the dice, on the other phone")
        watcher.until(lambda: watcher.dice() == dice, f"the same dice on both phones ({dice})")
        write_best(roller)
        watcher.see(watcher.id("last-move"), "the move, on the other phone")
        watcher.until(lambda: watcher.id("roll").count() > 0, "the turn passing to the other phone")
        for phone in (ann, bob):
            phone.healthy()
    finally:
        ann.close()
        bob.close()


def run(build_url: str, server: str, flows=FLOWS, report=print) -> Tuple[List[str], List[str]]:
    """Run the checks; returns (problems, codes of the games played)."""
    from playwright.sync_api import sync_playwright

    url = f"{build_url}?server={quote(server.rstrip('/'), safe='')}"
    problems: List[str] = []
    games: List[str] = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        try:
            steps = [("home", "home page, phone", lambda: check_home(browser, url)),
                     ("one device", "a game on one device, phone", lambda: check_one_device(browser, url, games)),
                     ("online", "an online game, two phones", lambda: check_online(browser, url, games))]
            for flow, label, step in steps:
                if flow not in flows:
                    continue
                started = time.time()
                try:
                    note = step()
                    report(f"ok   {label} ({time.time() - started:.0f} s){': ' + note if note else ''}")
                except Exception as e:  # noqa: BLE001 - report every failing step, then go on
                    problems.append(f"{label}: {e}")
                    report(f"FAIL {label}: {e}")
        finally:
            browser.close()
    return problems, games


def main() -> int:
    parser = argparse.ArgumentParser(description="The phone app's web build in a real browser.")
    parser.add_argument("--build", default=str(BUILD), help="the web build (npx expo export --platform web)")
    where = parser.add_mutually_exclusive_group(required=True)
    where.add_argument("--server", help="a running game server on this computer, e.g. http://127.0.0.1:8501")
    where.add_argument("--serve", action="store_true", help="start abaka_server.py for the check")
    parser.add_argument("--only", choices=FLOWS, action="append", help="check only these flows")
    args = parser.parse_args()
    reason = website_check.unavailable()
    if reason:
        print(reason)
        return 2
    build = Path(args.build)
    if not (build / "index.html").is_file():
        print(f"no web build in {build}: cd mobile && npx expo export --platform web")
        return 2
    httpd, build_url = serve_build(build)
    process = None
    try:
        if args.serve:
            folder = tempfile.mkdtemp(prefix="abaka-app-check-")
            process, server, _ = website_check.serve("abaka_server.py", folder)
        else:
            server = args.server
        print(f"checking the app's web build against {server}")
        problems, games = run(build_url, server, tuple(args.only or FLOWS))
        if games:
            print("test games:", ", ".join(games))
    finally:
        httpd.shutdown()
        if process is not None:
            process.terminate()
    print("APP OK" if not problems else f"APP BROKEN: {len(problems)} problem(s)")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
