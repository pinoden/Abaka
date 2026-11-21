"""
The API for apps over the network (Backlog item 25, step A2):
- server/http.py on a real server: HTTP statuses, the limit on new games, the live
  WebSocket and what it pushes;
- abaka_server.py started with `streamlit run`, serving the pages and the API together;
- the pages sharing the API's stores (server/stores.py).

The network tests need Streamlit 1.67's packages (Starlette, uvicorn, websockets) and are
skipped elsewhere (Python 3.8, Streamlit 1.48). The shared stores need Streamlit.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest import mock

import abaka.rooms as rooms
import code_version
from abaka import api
from abaka.clubs import ClubStore

try:
    import streamlit
    from streamlit.testing.v1 import AppTest
    from server import stores
except ImportError:  # the base Python 3.8
    streamlit = AppTest = stores = None
try:
    import uvicorn
    from starlette.applications import Starlette
    from starlette.routing import Route, WebSocketRoute
    from websockets.exceptions import ConnectionClosed
    from websockets.sync.client import connect
    from server import http
except ImportError:  # no Starlette: Streamlit before 1.67, or none
    http = None

ROOT = Path(__file__).resolve().parent.parent
APP = str(ROOT / "abaka_ui.py")


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def post(port, body=None, raw=None, headers=None):
    """POST /api/v1: (HTTP status, JSON answer, or None if the answer is not JSON)."""
    data = raw if raw is not None else json.dumps(body).encode()
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1", data=data, method="POST",
                                     headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=10) as answer:
            status, text = answer.status, answer.read()
    except urllib.error.HTTPError as e:
        status, text = e.code, e.read()
    try:
        return status, json.loads(text)
    except ValueError:
        return status, None


def receive(ws, timeout=5.0):
    return json.loads(ws.recv(timeout=timeout))


@unittest.skipIf(http is None, "needs Streamlit 1.67's Starlette, uvicorn and websockets")
class TestOverTheNetwork(unittest.TestCase):
    """server/http.py's two routes on a real server (uvicorn in a thread), with stores of the test's own."""

    def setUp(self):
        self.store, self.clubs = rooms.RoomStore(), ClubStore()
        for name, value in (("get_store", lambda: self.store), ("get_clubs", lambda: self.clubs)):
            patch = mock.patch.object(http.stores, name, value)
            patch.start()
            self.addCleanup(patch.stop)
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("ABAKA_CLIENT_ADDRESS_HEADER", None)
        http._started.clear()
        self.addCleanup(http._started.clear)
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        self.port = sock.getsockname()[1]
        app = Starlette(routes=[Route("/api/v1", http.post, methods=["POST"]),
                                WebSocketRoute("/api/v1/live", http.live)])
        server = uvicorn.Server(uvicorn.Config(app, log_level="warning", lifespan="off"))
        thread = threading.Thread(target=server.run, kwargs={"sockets": [sock]}, daemon=True)
        thread.start()

        def stop():
            server.should_exit = True
            thread.join(10)
            sock.close()

        self.addCleanup(stop)
        deadline = time.time() + 15
        while not server.started:
            self.assertLess(time.time(), deadline, "the server did not start")
            time.sleep(0.02)

    def post(self, body=None, **kwargs):
        return post(self.port, body, **kwargs)

    def live(self):
        return connect(f"ws://127.0.0.1:{self.port}/api/v1/live", open_timeout=10)

    def game(self, players=2):
        """A game for Ann and Bob: (code, Ann's token, Bob's token, the latest state)."""
        made = self.post({"op": "create", "name": "Ann", "players": players})[1]
        joined = self.post({"op": "join", "code": made["code"], "name": "Bob"})[1]
        return made["code"], made["token"], joined["token"], joined["state"]

    def test_answers_and_refusals_have_their_http_status(self):
        code, ann, bob, state = self.game()
        self.assertEqual(self.post({"op": "info", "lang": "ru"})[1]["rows"][6]["name"], "Пара")
        version = state["version"]  # Ann (seat 0) throws first
        for request, status, error in (
                ({"op": "state", "code": "ZZZZZ"}, 404, "not_found"),
                ({"op": "fly"}, 400, "bad_request"),
                ({"op": "info", "protocol": 2}, 400, "protocol"),
                ({"op": "say", "code": code, "token": "nobody", "text": "hi"}, 403, "not_seated"),
                ({"op": "throw", "code": code, "token": bob, "version": version}, 422, "refused"),
                ({"op": "throw", "code": code, "token": ann, "version": version - 1}, 409, "outdated")):
            with self.subTest(request=request):
                answer_status, answer = self.post(request)
                self.assertEqual((answer_status, answer["error"]), (status, error))
                self.assertTrue(answer["message"])
        self.assertEqual(self.post(raw=b"{not json")[0], 400)
        self.assertEqual(self.post(raw=b" " * (http.MAX_REQUEST_BYTES + 1))[0], 413)
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(f"http://127.0.0.1:{self.port}/api/v1", timeout=10)  # GET
        self.assertEqual(caught.exception.code, 405)
        status, answer = self.post({"op": "throw", "code": code, "token": ann, "version": version})
        self.assertEqual((status, len(answer["state"]["game"]["starting_throw"]["throws"])), (200, 1))

    def test_new_games_are_limited_per_client(self):
        requests = ([{"op": "create", "name": "Ann"}] * 4 + [{"op": "create_local", "names": ["A", "B"]}] * 4
                    + [{"op": "create_club", "name": "Friday"}] * 2)
        self.assertEqual([self.post(r)[0] for r in requests], [200] * 10)
        status, answer = self.post({"op": "create", "name": "Ann", "lang": "ru"})
        self.assertEqual((status, answer["error"]), (429, "too_fast"))
        self.assertIn("Подождите", answer["message"])
        self.assertEqual(self.post({"op": "join", "code": "ZZZZZ", "name": "Bob"})[0], 404)  # joining is not limited
        # Behind a proxy, the address comes from the header the proxy sets.
        os.environ["ABAKA_CLIENT_ADDRESS_HEADER"] = "X-Client"
        self.assertEqual(self.post({"op": "create", "name": "Cy"}, headers={"X-Client": "203.0.113.7"})[0], 200)

    def test_a_server_fault_is_answered_with_retry(self):
        with mock.patch.object(http.api, "handle", side_effect=KeyError("a bug")), \
                self.assertLogs("abaka", level="ERROR") as logged:
            status, answer = self.post({"op": "info", "lang": "ru", "token": "secret-token"})
        self.assertEqual((status, answer["error"]), (500, "retry"))
        self.assertEqual(answer["message"], "На сервере что-то пошло не так. Попробуйте ещё раз.")
        self.assertIn("the API failed on 'info'", "\n".join(logged.output))
        self.assertNotIn("secret-token", "\n".join(logged.output))

    def test_a_watched_game_is_pushed_when_it_changes(self):
        made = self.post({"op": "create", "name": "Ann"})[1]
        code, ann = made["code"], made["token"]
        with self.live() as ws:
            ws.send(json.dumps({"id": 1, "op": "watch", "code": code.lower(), "token": ann}))
            reply = receive(ws)
            self.assertEqual((reply["type"], reply["id"], reply["response"]["state"]["names"]), ("reply", 1, ["Ann"]))
            started = time.time()
            bob = self.post({"op": "join", "code": code, "name": "Bob"})[1]["token"]  # another device
            push = receive(ws)
            self.assertEqual((push["type"], push["state"]["names"]), ("state", ["Ann", "Bob"]))
            self.assertLess(time.time() - started, 2)
            # Ann's move over the socket comes back as its reply, and is not pushed again.
            ws.send(json.dumps({"id": 2, "op": "throw", "code": code, "token": ann,
                                "version": push["state"]["version"]}))
            reply = receive(ws)
            self.assertEqual((reply["type"], reply["id"]), ("reply", 2))
            with self.assertRaises(TimeoutError):
                ws.recv(timeout=0.8)
            # Bob's throw, from his device, is pushed.
            self.post({"op": "throw", "code": code, "token": bob, "version": reply["response"]["state"]["version"]})
            push = receive(ws)
            self.assertEqual(len(push["state"]["game"]["starting_throw"]["throws"]), 2)
            # Chat messages and events come once: a push has only what is new.
            self.post({"op": "say", "code": code, "token": bob, "text": "hi"})
            self.assertEqual([m["text"] for m in receive(ws)["state"]["chat"]], ["hi"])
            self.post({"op": "say", "code": code, "token": bob, "text": "again"})
            self.assertEqual([m["text"] for m in receive(ws)["state"]["chat"]], ["again"])
            # Refused messages say so, with the message's id.
            ws.send("not json")
            self.assertEqual(receive(ws)["error"], "bad_request")
            ws.send(json.dumps({"id": 3, "op": "state", "code": "ZZZZZ"}))
            self.assertEqual((receive(ws)["error"], 3), ("not_found", 3))

    def test_a_watched_game_that_ends_is_reported_once(self):
        made = self.post({"op": "create", "name": "Ann", "players": 3})[1]
        with self.live() as ws:
            ws.send(json.dumps({"op": "watch", "code": made["code"], "token": made["token"]}))
            receive(ws)
            self.post({"op": "leave", "code": made["code"], "token": made["token"]})  # alone: the game is closed
            self.assertEqual(receive(ws)["error"], "not_found")
            with self.assertRaises(TimeoutError):
                ws.recv(timeout=0.8)

    def test_text_that_utf8_cannot_carry(self):
        """
        Half of a surrogate pair, which JSON can carry: cleaned from names and messages, and
        never the end of a connection (one in a chat message used to cut the other players off).
        """
        code, ann, bob, _ = self.game()
        with self.live() as ws:
            ws.send(json.dumps({"id": 1, "op": "watch", "code": code, "token": ann}))
            receive(ws)
            say = '{"op": "say", "code": "%s", "token": "%s", "text": "hi \\ud83d there"}' % (code, bob)
            status, answer = self.post(raw=say.encode())
            self.assertEqual((status, [m["text"] for m in answer["state"]["chat"]]), (200, ["hi there"]))
            self.assertEqual([m["text"] for m in receive(ws)["state"]["chat"]], ["hi there"])
            self.post({"op": "say", "code": code, "token": bob, "text": "still here?"})
            self.assertEqual([m["text"] for m in receive(ws)["state"]["chat"]], ["still here?"])
            # A message's id is echoed as it came, in a form that can be sent.
            ws.send('{"id": "\\ud83d", "op": "info"}')
            reply = receive(ws)
            self.assertEqual((reply["type"], reply["id"]), ("reply", "\ud83d"))
        status, answer = self.post(raw=b'{"op": "create", "name": "Eve\\udc00"}')
        self.assertEqual((status, answer["state"]["names"]), (200, ["Eve"]))
        self.assertEqual(self.post(raw=b"[" * 5000 + b"]" * 5000)[0], 400)  # however deep it is nested: not a fault

    def test_a_connection_that_cannot_be_served_is_closed(self):
        """An app is never left on a connection that looks open and brings no news: it reconnects instead."""
        code, ann, bob, _ = self.game()

        def watch():
            ws = self.live()
            self.addCleanup(ws.close)
            ws.send(json.dumps({"op": "watch", "code": code, "token": ann}))
            receive(ws)
            return ws

        def closed_by_the_server(ws):
            with self.assertRaises(ConnectionClosed) as caught:
                ws.recv(timeout=5)
            return caught.exception.rcvd.code

        ws = watch()  # looking for changes fails
        with mock.patch.object(http, "_changed_state", side_effect=KeyError("a bug")), \
                self.assertLogs("abaka", level="ERROR"):
            self.assertEqual(closed_by_the_server(ws), http.SERVER_FAULT)

        ws, as_json = watch(), http.as_json  # a push that cannot be written

        def no_pushes(message):
            if message.get("type") == "state":
                raise TypeError("not JSON data")
            return as_json(message)

        with mock.patch.object(http, "as_json", no_pushes), self.assertLogs("abaka", level="ERROR"):
            self.post({"op": "say", "code": code, "token": bob, "text": "hi"})
            self.assertEqual(closed_by_the_server(ws), http.SERVER_FAULT)

    def test_live_connections_close_after_a_code_update(self):
        made = self.post({"op": "create", "name": "Ann"})[1]
        with self.live() as ws:
            ws.send(json.dumps({"op": "watch", "code": made["code"], "token": made["token"]}))
            receive(ws)
            loaded = sys.modules["server.http"]
            sys.modules["server.http"] = types.ModuleType("server.http")  # as code_version leaves it
            try:
                with self.assertRaises(ConnectionClosed) as caught:
                    ws.recv(timeout=5)
            finally:
                sys.modules["server.http"] = loaded
        self.assertEqual(caught.exception.rcvd.code, http.CODE_UPDATED)


@unittest.skipIf(AppTest is None, "Streamlit is not installed")
class TestPagesShareTheApiStores(unittest.TestCase):
    """With abaka_server.py, the pages and the API use one store (server/stores.py)."""

    def setUp(self):
        env = mock.patch.dict(os.environ, {"ABAKA_SAVE_DIR": "", "ABAKA_DATABASE_URL": ""})
        env.start()
        self.addCleanup(env.stop)
        registry = stores._registry()
        before = {k: registry[k] for k in ("api", "store", "clubs")}

        def restore():
            if registry["store"] is not None and registry["store"] is not before["store"]:
                registry["store"].retire()
            registry.update(before)

        self.addCleanup(restore)
        registry.update(store=None, clubs=None)
        stores.serve_api()
        code_version.mark_current()
        # AppTest 1.48 reads every button group's value as a list (see test_shown_dice.py).
        from streamlit.testing.v1 import element_tree
        if not hasattr(element_tree.ButtonGroup, "_is_single_select"):
            group_value = element_tree.ButtonGroup.value.fget

            def one_or_more(group):
                value = group_value(group)
                return [] if value is None else value if isinstance(value, list) else [value]

            patcher = mock.patch.object(element_tree.ButtonGroup, "value", property(one_or_more))
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_one_store_until_the_code_changes(self):
        first = stores.get_store()
        self.assertIs(stores.get_store(), first)
        self.assertIsNotNone(stores.get_clubs())

        class ReloadedRoomStore(rooms.RoomStore):  # what a code update brings
            pass

        with mock.patch.object(rooms, "RoomStore", ReloadedRoomStore):
            second = stores.get_store()
        self.assertIs(type(second), ReloadedRoomStore)
        self.assertTrue(first._retired)

    def test_a_game_made_in_an_app_is_joined_on_a_page(self):
        made = api.handle({"op": "create", "name": "Ann"}, stores.get_store(), stores.get_clubs())
        page = AppTest.from_file(APP, default_timeout=30)
        page.query_params["room"] = made["code"]
        page.run()
        self.assertFalse(page.exception, [e.value for e in page.exception])
        page.text_input(key="join_name").input("Bob")
        page.button(key="FormSubmitter:join_game-Join game").click().run()
        self.assertFalse(page.exception, [e.value for e in page.exception])
        state = api.handle({"op": "state", "code": made["code"], "token": made["token"]},
                           stores.get_store(), stores.get_clubs())["state"]
        self.assertEqual((state["names"], state["phase"]), (["Ann", "Bob"], "starting_throw"))


@unittest.skipIf(http is None or not hasattr(streamlit, "App"), "needs Streamlit 1.67 (st.App)")
class TestServerProcess(unittest.TestCase):
    """`streamlit run abaka_server.py`, as a host would start it: the pages and the API on one port."""

    def test_streamlit_run_serves_the_pages_and_the_api(self):
        port = free_port()
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        output = open(os.path.join(folder.name, "server.log"), "w+")
        self.addCleanup(output.close)
        env = dict(os.environ, ABAKA_SAVE_DIR=os.path.join(folder.name, "games"), ABAKA_DATABASE_URL="")
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", "abaka_server.py", "--server.port", str(port),
             "--server.address", "127.0.0.1", "--server.headless", "true", "--server.fileWatcherType", "none",
             "--browser.gatherUsageStats", "false"],
            cwd=ROOT, env=env, stdout=output, stderr=subprocess.STDOUT)

        def stop():
            process.terminate()
            try:
                process.wait(10)
            except subprocess.TimeoutExpired:
                process.kill()

        self.addCleanup(stop)
        deadline = time.time() + 90
        while True:
            try:
                with urllib.request.urlopen(f"http://127.0.0.1:{port}/_stcore/health", timeout=2):
                    break
            except OSError:
                output.seek(0)
                self.assertIsNone(process.poll(), output.read())
                self.assertLess(time.time(), deadline, "the server did not start")
                time.sleep(0.5)

        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10) as page:
            self.assertIn(b'id="root"', page.read())  # the web app's page
        status, info = post(port, {"op": "info"})
        self.assertEqual((status, info["protocol"]), (200, api.PROTOCOL))
        made = post(port, {"op": "create", "name": "Ann"})[1]
        with connect(f"ws://127.0.0.1:{port}/api/v1/live", open_timeout=10) as ws:
            ws.send(json.dumps({"op": "watch", "code": made["code"], "token": made["token"]}))
            self.assertEqual(receive(ws)["type"], "reply")
            post(port, {"op": "join", "code": made["code"], "name": "Bob"})
            self.assertEqual(receive(ws)["state"]["names"], ["Ann", "Bob"])


if __name__ == "__main__":
    unittest.main()
