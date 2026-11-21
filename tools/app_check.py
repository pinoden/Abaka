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
  best option written, a row crossed out, and both players' columns on the screen; then
  home and back to it from "Continue a game", and once it has ended (the check plays it
  to the end through the API) it is not offered there any more;
- an online game between two phones: one creates it, goes home and comes back to the
  waiting room (the seat is kept), the other opens its code and joins, the starting
  throws, a roll and a move seen on the other phone, then a reaction and a chat message;
- a player on the website and a player in the app at one table: each sees the other's
  dice, move, reaction and chat message (the server must serve the pages too, as
  abaka_server.py does);
- with dice the check chooses (Steered):
  - a tie for the first turn among three players: the player who is out of the next
    round keeps their throw on the screen;
  - an Abaka on the first roll: bigger fireworks on both phones, each in its language.
Any page error and any sideways scrolling is a problem too.

Needs Playwright and its Chromium (requirements-dev.txt), and Streamlit 1.67's packages
(the steered server, and --serve).
"""

import argparse
import functools
import http.server
import json
import socket
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
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
FLOWS = ("home", "one device", "online", "website", "a tie", "fireworks")


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


class Steered:
    """
    A game server inside this process, with dice the check chooses: the real API over the
    network (server/http.py) on a store of its own. What cannot be thrown on purpose (a tie
    for the first turn) can then be shown to the app.

    `throws` lists the next throws of all five dice, each as five values with the joker
    last; once it is empty the dice are left to chance again.
    """

    def __init__(self) -> None:
        import uvicorn
        from starlette.applications import Starlette
        from starlette.routing import Route, WebSocketRoute

        if str(ROOT) not in sys.path:
            sys.path.insert(0, str(ROOT))
        import abaka.engine as engine
        from abaka import rooms
        from abaka.clubs import ClubStore
        from abaka.models import Die
        from server import http as live

        self.store, clubs = rooms.RoomStore(), ClubStore()  # in memory: nothing is saved anywhere
        live.stores.get_store = lambda: self.store
        live.stores.get_clubs = lambda: clubs
        self.throws: List[List[int]] = []
        self._engine, self._roll_dice = engine, engine.roll_dice
        engine.roll_dice = lambda: ([Die(value, is_joker=i == 4) for i, value in enumerate(self.throws.pop(0))]
                                    if self.throws else self._roll_dice())
        self._socket = socket.socket()
        self._socket.bind(("127.0.0.1", 0))
        self.url = f"http://127.0.0.1:{self._socket.getsockname()[1]}"
        app = Starlette(routes=[Route("/api/v1", live.post, methods=["POST"]),
                                WebSocketRoute("/api/v1/live", live.live)])
        self._server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))
        self._thread = threading.Thread(target=self._server.run, kwargs={"sockets": [self._socket]}, daemon=True)
        self._thread.start()
        deadline = time.time() + 15
        while not self._server.started:
            if time.time() > deadline:
                raise Problem("the steered server did not start")
            time.sleep(0.02)

    def stop(self) -> None:
        self._engine.roll_dice = self._roll_dice
        self._server.should_exit = True
        self._thread.join(10)
        self._socket.close()


def api(server: str, **request) -> dict:
    """One request to the game server's API: its answer, or its refusal."""
    asked = urllib.request.Request(server.rstrip("/") + "/api/v1", json.dumps(request).encode(),
                                   {"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(asked, timeout=20) as answer:
            return json.loads(answer.read())
    except urllib.error.HTTPError as e:
        return json.loads(e.read())


def finish_game(server: str, code: str, token: str) -> None:
    """Play a game on one device to its end through the API, taking the first move each state offers."""
    for _ in range(2000):
        state = api(server, op="state", code=code, token=token)["state"]
        if state["phase"] == "over":
            return
        ask = dict(code=code, token=token, version=state["version"])
        if "throw" in state["can"] or "roll" in state["can"]:
            api(server, op="throw" if "throw" in state["can"] else "roll", **ask)
        else:
            kind = "score" if state["moves"]["score"] else "cross"
            move = state["moves"][kind][0]
            api(server, op=kind, row=move["row"], slot=move["slot"], **ask)
    raise Problem(f"game {code} did not end")


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


def check_one_device(browser, url: str, server: str, games: List[str]) -> None:
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
        if not label:
            raise Problem("one device: the best option had no label")
        # Home and back: the game is kept, and offered under "Continue a game".
        code = games[-1]
        phone.id("home").click()
        phone.see(phone.id(f"continue-{code}"), "the game under 'Continue a game'").click()
        phone.see(phone.id("roll"), "the game again, where it was left")
        # Once it has ended (played to the end through the API), it is not offered any more.
        token = phone.page.evaluate("code => localStorage.getItem('abaka.token.' + code)", code)
        finish_game(server, code, token)
        phone.see(phone.id("results"), "the results, without a tap")
        phone.id("home").click()
        phone.see(phone.id("start-local"), "the home page")
        phone.page.wait_for_timeout(1000)  # the list is drawn a moment after the page
        if phone.id(f"continue-{code}").count():
            raise Problem("one device: the finished game is still offered under 'Continue a game'")
        phone.healthy()
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
        # Home and back while waiting: the seat is kept, so the game is still there for friends.
        ann.id("home").click()
        ann.see(ann.id(f"continue-{code}"), "the waiting game under 'Continue a game'").click()
        ann.see(ann.id("game-code"), "the waiting room again")

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
        # A reaction and a chat message reach the other phone (Bob's is in Russian).
        ann.see(ann.id("react-lucky"), "the reaction buttons").click()
        bob.see(bob.id("bubble").filter(has_text=f"{NAMES[0]}  Повезло!"), "Ann's reaction, on Bob's phone")
        bob.see(bob.id("chat-text"), "the chat box").fill("Test hello")
        bob.id("chat-send").click()
        ann.see(ann.id("chat-message").filter(has_text="Test hello"), "Bob's message, in Ann's chat")
        ann.see(ann.id("bubble").filter(has_text="Test hello"), "Bob's message, announced on Ann's phone")
        for phone in (ann, bob):
            phone.healthy()
    finally:
        ann.close()
        bob.close()


def check_website_and_app(browser, url: str, server: str, games: List[str]) -> None:
    """One table, a player on the website and one in the app: each sees the other's dice, move, reaction and message."""
    web = website_check.Screen(browser, server.rstrip("/") + "/?lang=en", website_check.DESKTOP,
                               "website and app, the website")
    phone = Phone(browser, url, "website and app, the app")

    def web_dice() -> List[str]:  # as Phone.dice() names them: the value, and J for the joker
        return [text.strip().split(" ")[0] + ("J" if " " in text.strip() else "") for text in web.dice()]

    try:
        web.see(web.app.get_by_label("Your name"), "the website's name box", website_check.START_MS).fill(NAMES[0])
        web.see(web.app.get_by_role("button", name="Create game"), 'the website\'s "Create game" button').click()
        web.see(web.app.get_by_text("Invite a friend"), "the website's waiting room")
        code = web.room()
        games.append(code)
        phone.see(phone.id("open-code"), "the app's home page").fill(code)
        phone.id("open-game").click()
        phone.see(phone.id("join-name"), "the invite, in the app").fill(NAMES[1])
        phone.id("join").click()
        web.see(web.app.get_by_text("Who goes first?"), "the game starting on the website")
        phone.see(phone.id("starting-throw"), "the game starting in the app")

        def may_roll(where) -> bool:
            button = where.key("roll") if where is web else where.id("roll")
            return button.count() > 0 and button.first.is_visible()

        deadline = time.time() + 60
        while not (may_roll(web) or may_roll(phone)):  # each player throws on their own screen
            if time.time() > deadline:
                raise Problem("website and app: the starting throws did not end" + web.why() + phone.why())
            for throw in (web.key("start-throw"), phone.id("start-throw")):
                if throw.count() and throw.first.is_visible() and throw.first.is_enabled():
                    throw.first.click()
            web.page.wait_for_timeout(700)
        if may_roll(web):  # the website's player goes first
            web.key("roll").first.click()
            web.see(web.options(), "the website's options to write the roll")
            rolled = web_dice()
            phone.see(phone.id("die-4"), "the website's roll, in the app")
            phone.until(lambda: phone.dice() == rolled, f"the website's dice in the app ({rolled})")
            website_check.write_best(web)
            phone.see(phone.id("last-move"), "the website's move, in the app")
            phone.see(phone.id("roll"), "the turn passing to the app")
        else:  # the app's player goes first
            phone.id("roll").first.click()
            phone.see(phone.id("die-4"), "the app's dice")
            rolled = phone.dice()
            web.until(lambda: web_dice() == rolled, f"the app's dice on the website ({rolled})")
            write_best(phone)
            web.see(web.app.get_by_text("Last move:"), "the app's move, on the website")
            web.see(web.key("roll"), "the turn passing to the website")
        # Reactions and chat, both ways.
        web.see(web.key("react-lucky"), 'the website\'s "Lucky!" reaction').click()
        phone.see(phone.id("bubble").filter(has_text="Lucky!"), "the website's reaction, in the app")
        phone.see(phone.id("chat-text"), "the app's chat box").fill("Test hello")
        phone.id("chat-send").click()
        web.see(web.app.get_by_text("Test hello"), "the app's message, on the website")
        web.see(web.app.locator(".st-key-chat-text input"), "the website's chat box").fill("Test hi back")
        web.see(web.app.get_by_role("button", name="Send"), 'the website\'s "Send" button').click()
        phone.see(phone.id("chat-message").filter(has_text="Test hi back"), "the website's message, in the app")
        phone.see(phone.id("react-nice"), "the app's reaction buttons").click()
        web.see(web.app.locator(".ab-bubble", has_text="Nice!"), "the app's reaction, on the website")
        web.healthy()
        phone.healthy()
    finally:
        web.close()
        phone.close()


def check_tie(browser, build_url: str) -> str:
    """Three players on one device tie for the first turn: the one who is out keeps their throw on the screen."""
    try:
        steered = Steered()
    except ImportError as e:
        raise Problem(f"the steered server needs Streamlit 1.67's packages ({e})") from None
    phone = Phone(browser, f"{build_url}?server={quote(steered.url, safe='')}", "a tie, phone")
    try:
        phone.see(phone.id("start-local"), "the home page")
        phone.id("local-count").get_by_role("radio", name="3").click()
        players = ("Test Ann", "Test Bob", "Test Cy")
        for i, name in enumerate(players):
            phone.see(phone.id(f"local-name-{i}"), f"the box for player {i + 1}").fill(name)
        steered.throws = [[1, 1, 1, 1, 5], [6, 6, 4, 2, 2], [2, 2, 2, 2, 1]]  # 9, 20 and 9: Ann and Cy tie
        phone.id("start-local").click()
        for name in players:
            phone.see(phone.page.get_by_text(f"Throw for {name}"), f"{name}'s starting throw").click()
        phone.until(lambda: "throw again" in phone.text(), "the tie for the lowest total")
        out = phone.id("throw-1").first.inner_text()
        if "20" not in out:
            raise Problem(f"a tie: Test Bob is out, and his throw of 20 is no longer shown ({out!r})")
        for seat in (0, 2):  # the two who throw again wait for their new throw
            if "9" in phone.id(f"throw-{seat}").first.inner_text():
                raise Problem("a tie: a player who throws again still shows the old throw")
        phone.healthy()
        return "Test Bob, out with 20, keeps his throw"
    finally:
        phone.close()
        steered.stop()


def check_fireworks(browser, build_url: str) -> str:
    """An Abaka on the first roll, with steered dice: bigger fireworks on both phones as the dice land."""
    try:
        steered = Steered()
    except ImportError as e:
        raise Problem(f"the steered server needs Streamlit 1.67's packages ({e})") from None
    url = f"{build_url}?server={quote(steered.url, safe='')}"
    ann = Phone(browser, url, "fireworks, Ann's phone")
    bob = Phone(browser, url, "fireworks, Bob's phone", locale="ru-RU")
    try:
        ann.see(ann.id("create-online"), "the home page")
        ann.id("online-name").fill(NAMES[0])
        ann.id("create-online").click()
        code = ann.see(ann.id("game-code"), "the game code").inner_text().strip()
        bob.see(bob.id("open-code"), "Bob's home page").fill(code)
        bob.id("open-game").click()
        bob.see(bob.id("join-name"), "the invite").fill(NAMES[1])
        steered.throws = [[1, 1, 1, 1, 1], [6, 6, 6, 6, 5]]  # the starting throws: Ann's 5 goes first
        bob.id("join").click()
        if ann.throw_until_decided(bob) is not ann:
            raise Problem("fireworks: Test Ann threw 5 against 29 and does not go first")
        steered.throws = [[6, 6, 6, 6, 6]]  # five sixes
        ann.id("roll").first.click()
        for phone, title, text in ((ann, "Abaka!", "You · first roll"),
                                   (bob, "Абака!", f"{NAMES[0]} · с первого броска")):
            phone.see(phone.id("effect-grand_fireworks"), "the bigger fireworks")
            banner = " | ".join(phone.id("effect-banner").first.inner_text().split("\n"))
            if title not in banner or text not in banner:
                raise Problem(f"{phone.name}: the banner says {banner!r}, not {title!r} and {text!r}")
        # They play once and end; nothing is left over the screen.
        for phone in (ann, bob):
            phone.until(lambda: phone.page.locator('[data-testid^="effect-"]').count() == 0,
                        "the fireworks ending")
            phone.healthy()
        return "Abaka! on both phones, in English and in Russian"
    finally:
        ann.close()
        bob.close()
        steered.stop()


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
                     ("one device", "a game on one device, phone",
                      lambda: check_one_device(browser, url, server, games)),
                     ("online", "an online game, two phones", lambda: check_online(browser, url, games)),
                     ("website", "a website player and an app player at one table",
                      lambda: check_website_and_app(browser, url, server, games)),
                     ("a tie", "a tie for the first turn, steered dice", lambda: check_tie(browser, build_url)),
                     ("fireworks", "an Abaka on the first roll, steered dice",
                      lambda: check_fireworks(browser, build_url))]
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
