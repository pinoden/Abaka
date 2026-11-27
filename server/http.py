"""
The API for apps (abaka/api.py) over the network. abaka_server.py serves it next to the
web app, so apps and web pages share the games (docs/API.md, Over the network).

    POST /api/v1        a request as JSON; its answer as JSON (a refusal with an HTTP status)
    WS   /api/v1/live   the same requests as messages, and the state of a watched game
                        pushed whenever it changes (`watch`, until `unwatch`)

Starlette, which Streamlit 1.67 runs on. The store's methods take its lock and may wait for
the database, so they run in worker threads, never on the event loop, which also serves the
web pages.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from starlette.concurrency import run_in_threadpool
from starlette.requests import HTTPConnection, Request
from starlette.responses import Response
from starlette.websockets import WebSocket

from abaka import api
from abaka.rooms import within_limit
from server import stores

log = logging.getLogger("abaka")

MAX_REQUEST_BYTES = 16 * 1024      # the largest real request is a chat message of 200 characters
STATUS = {"bad_request": 400, "protocol": 400, "not_found": 404, "not_seated": 403, "outdated": 409,
          "too_fast": 429, "retry": 503, "refused": 422}
GAMES_PER_CLIENT = 10              # games and clubs one client address may start...
GAMES_PER_CLIENT_WINDOW = 10 * 60  # ...in this many seconds (the web allows the same per browser)
ADDRESSES_KEPT = 10000             # client addresses the limit remembers at most
WATCH_EVERY_SECONDS = 0.25         # how often a live connection looks for changes to its game
CODE_UPDATED = 1012                # the WebSocket close code "service restart": reconnect
SERVER_FAULT = 1011                # the close code "internal error": the connection cannot be served

_THIS = sys.modules[__name__]      # this module as loaded (a code update loads a new one)
_started: Dict[str, List[float]] = {}  # per client address: when it started its latest games
_started_lock = threading.Lock()


def client_address(connection: HTTPConnection) -> str:
    """
    Who is asking, for the limit on new games: the connection's address or, behind a proxy,
    the header named by $ABAKA_CLIENT_ADDRESS_HEADER (for example Fly-Client-IP).
    """
    header = os.environ.get("ABAKA_CLIENT_ADDRESS_HEADER", "").strip()
    if header:
        value = connection.headers.get(header, "").split(",")[0].strip()
        if value:
            return value
    return connection.client.host if connection.client else "unknown"


def may_start(address: str) -> bool:
    """Whether this client may start another game or club now (and count it if so)."""
    now = time.time()
    with _started_lock:
        if address not in _started and len(_started) >= ADDRESSES_KEPT:
            for key in [k for k, times in _started.items() if not times or now - times[-1] >= GAMES_PER_CLIENT_WINDOW]:
                del _started[key]
            if len(_started) >= ADDRESSES_KEPT:  # still full: a flood from many addresses
                _started.clear()
        allowed, _started[address] = within_limit(_started.get(address, []), now, GAMES_PER_CLIENT,
                                                  GAMES_PER_CLIENT_WINDOW)
        return allowed


def answer(request: Any, address: str) -> Tuple[int, dict]:
    """One request, answered by the API: (HTTP status, JSON data). Runs in a worker thread."""
    try:
        response = api.handle(request, stores.get_store(), stores.get_clubs(),
                              may_create=lambda: may_start(address))
    except api.ApiError as e:
        return STATUS.get(e.code, 400), e.to_data()
    except Exception:  # noqa: BLE001 - a fault of the server: log it, and tell the app to try again
        log.exception("the API failed on %r", request.get("op") if isinstance(request, dict) else None)
        return 500, api.failure(request).to_data()
    return 200, response


def as_json(data: Any) -> str:
    """
    `data` as JSON text that can always be sent. Text that UTF-8 cannot carry is written as
    \\u escapes instead: half of a surrogate pair, which JSON allows (a message's `id` is
    echoed as it came). Names and chat messages never hold one (rooms.clean_name).
    """
    text = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        text = json.dumps(data, separators=(",", ":"))
    return text


def _parsed(text) -> Any:
    """A message's JSON data. ValueError if it is not JSON (or is nested too deep to read)."""
    try:
        return json.loads(text)
    except RecursionError:
        raise ValueError("nested too deep") from None


async def post(request: Request) -> Response:
    """POST /api/v1: one request in the body, its answer in the response."""
    body = await _body(request)
    if body is None:
        return _refusal(413, f"A request is at most {MAX_REQUEST_BYTES // 1024} KB.")
    try:
        data = _parsed(body)
    except ValueError:
        return _refusal(400, "The request is not JSON.")
    status, response = await run_in_threadpool(answer, data, client_address(request))
    return _json_response(response, status)


async def _body(request: Request) -> Optional[bytes]:
    """The request's body, or None if it is larger than MAX_REQUEST_BYTES (read no further)."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > MAX_REQUEST_BYTES:
        return None
    body = bytearray()
    async for chunk in request.stream():
        body += chunk
        if len(body) > MAX_REQUEST_BYTES:
            return None
    return bytes(body)


def _json_response(data: dict, status: int) -> Response:
    return Response(as_json(data), status_code=status, media_type="application/json")


def _refusal(status: int, message: str) -> Response:
    return _json_response({"error": "bad_request", "message": message}, status)


# ---------------------------------------------------------------- live connections ----

async def live(websocket: WebSocket) -> None:
    """WS /api/v1/live: requests and answers as messages, and the state of the watched game pushed."""
    await websocket.accept()
    connection = _Live(websocket, client_address(websocket))
    pushing = asyncio.ensure_future(connection.push_changes())
    try:
        await connection.serve()
    finally:
        pushing.cancel()


class _Live:
    """One live connection: the requests it sends, and the one game it watches."""

    def __init__(self, websocket: WebSocket, address: str) -> None:
        self.websocket = websocket
        self.address = address
        self.watching: Optional[dict] = None  # the state request of the watched game: code, key, token, lang
        self.seen: Optional[str] = None       # its `seen` when its state was last sent
        self.since = 0                        # its events and chat messages up to this id have been sent
        self.closed = False
        self.sending = asyncio.Lock()

    async def serve(self) -> None:
        """Answer every message, until the app goes."""
        while not self.closed:
            message = await self.websocket.receive()
            if message["type"] == "websocket.disconnect":
                return
            text = message.get("text")
            if text is None and message.get("bytes") is not None:
                text = message["bytes"].decode("utf-8", "replace")
            if text is None:
                continue
            if len(text) > MAX_REQUEST_BYTES:
                await self.send({"type": "error", "id": None, "error": "bad_request",
                                 "message": f"A message is at most {MAX_REQUEST_BYTES // 1024} KB."})
                continue
            try:
                data = _parsed(text)
            except ValueError:
                await self.send({"type": "error", "id": None, "error": "bad_request",
                                 "message": "The message is not JSON."})
                continue
            await self.answer(data)

    async def answer(self, data: Any) -> None:
        """
        A request, answered with its `id`. `watch` is a state request that also makes this
        connection push the game's state whenever it changes, until the app watches another
        or sends `unwatch`.
        """
        ref = data.get("id") if isinstance(data, dict) else None
        request = {k: v for k, v in data.items() if k != "id"} if isinstance(data, dict) else data
        if isinstance(request, dict) and request.get("op") == "unwatch":
            # The app left the game's screen and keeps the connection for what it asks next.
            self.watching, self.seen, self.since = None, None, 0
            await self.send({"type": "reply", "id": ref, "response": {"watching": None}})
            return
        watch = isinstance(request, dict) and request.get("op") == "watch"
        if watch:
            request["op"] = "state"
        status, response = await run_in_threadpool(answer, request, self.address)
        if status != 200:
            await self.send(dict(response, type="error", id=ref))
            return
        state = response.get("state")
        if watch:
            self.watching = {k: request[k] for k in ("token", "lang", "protocol") if request.get(k) is not None}
            # The key comes from the state (so only someone in the game has it): the pushes ask with it.
            self.watching.update(op="state", code=state["code"], key=state["key"])
            since = request.get("since")
            self.since = since if isinstance(since, int) and not isinstance(since, bool) else 0
        if state is not None and self._is_watched(state, request):
            self._note(state)
        await self.send({"type": "reply", "id": ref, "response": response})

    async def push_changes(self) -> None:
        """
        Send the watched game's state whenever it changes (checking every WATCH_EVERY_SECONDS).
        If that fails, the connection is closed: an app must never be left on a connection
        that looks open and brings no news.
        """
        try:
            while not self.closed:
                await asyncio.sleep(WATCH_EVERY_SECONDS)
                if sys.modules.get(__name__) is not _THIS:
                    # The code was updated in place: the app reconnects, and the new code serves it.
                    await self.close(CODE_UPDATED)
                    return
                watching = self.watching
                if watching is None:
                    continue
                changed = await run_in_threadpool(_changed_state, dict(watching, since=self.since), self.seen,
                                                  self.address)
                if changed is None or self.watching is not watching:
                    continue  # nothing new, or the app watches another game now
                status, response = changed
                if status != 200:
                    if response["error"] == "not_found":
                        self.watching = None  # the game is gone
                    await self.send(dict(response, type="error", id=None))
                    continue
                self._note(response["state"])
                await self.send({"type": "state", "state": response["state"]})
        except asyncio.CancelledError:  # the app went: live() stops the pushing
            raise
        except Exception:  # noqa: BLE001 - a fault of the server: the app reconnects
            log.exception("pushing a watched game's changes failed")
            await self.close(SERVER_FAULT)

    async def send(self, message: dict) -> None:
        """Send one message. If it cannot be sent, the connection is closed, and the app reconnects."""
        if self.closed:
            return
        try:
            text = as_json(message)
        except (TypeError, ValueError):  # not JSON data: a fault of the server
            log.exception("a message for an app could not be written")
            await self.close(SERVER_FAULT)
            return
        try:
            async with self.sending:
                await self.websocket.send_text(text)
        except Exception:  # noqa: BLE001 - the app went away meanwhile
            await self.close(SERVER_FAULT)

    async def close(self, code: int) -> None:
        """Close the connection for good. serve() then ends, and an app that is still there reconnects."""
        if self.closed:
            return
        self.closed = True
        try:
            await self.websocket.close(code)
        except Exception:  # noqa: BLE001 - closed already
            pass

    def _is_watched(self, state: dict, request: dict) -> bool:
        watching = self.watching
        return (watching is not None and state.get("code") == watching["code"]
                and request.get("token") == watching.get("token"))

    def _note(self, state: dict) -> None:
        """This state has been sent: push again only when the game changes, and only newer events."""
        self.seen = state["seen"]
        self.since = max([self.since] + [e["id"] for e in state["events"]] + [m["id"] for m in state["chat"]])


def _changed_state(request: dict, seen: Optional[str], address: str) -> Optional[Tuple[int, dict]]:
    """The watched game's (status, state) if it changed since `seen`, else None. Runs in a worker thread."""
    # With the seat's token, so the server knows this seat's device is here (rooms.py, SEAT_HERE_SECONDS).
    status, response = answer({k: v for k, v in (("op", "seen"), ("code", request["code"]), ("key", request["key"]),
                                                 ("token", request.get("token"))) if v is not None}, address)
    if status == 200 and response["seen"] == seen:
        return None
    return (status, response) if status != 200 else answer(request, address)
