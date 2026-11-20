"""
Abaka's server: the web app and the API for apps (Android, iOS) in one process, so they
share the games (Backlog item 25).

    streamlit run abaka_server.py          (Streamlit 1.67 or newer)

`streamlit run` finds `app` below and serves, next to the pages of abaka_ui.py:

    POST /api/v1        the API (docs/API.md), one request at a time
    WS   /api/v1/live   the API as messages, and the state of a watched game pushed

Streamlit Community Cloud runs abaka_ui.py directly, without the API, until the server
moves to a host of its own (Backlog item 25, stage B).

This file only connects the routes, which are made once, when the server starts. Each
request asks for the code that answers it (server/http.py) again, so a code update
applied in place (code_version) reaches the API as it reaches the pages.
"""

import importlib

import streamlit as st

if not hasattr(st, "App"):  # Streamlit before 1.67 runs this file as a page: say what it needs
    st.error("abaka_server.py needs Streamlit 1.67 or newer. Run abaka_ui.py for the web app alone.")
    st.stop()

from starlette.routing import Route, WebSocketRoute  # noqa: E402 (Streamlit 1.67 runs on Starlette)


def _http():
    """server/http.py as it is on disk now (after a code update: the new code)."""
    importlib.import_module("code_version").load_current()
    return importlib.import_module("server.http")


async def _post(request):
    return await _http().post(request)


async def _live(websocket):
    await _http().live(websocket)


importlib.import_module("server.stores").serve_api()  # the pages share the API's stores
app = st.App("abaka_ui.py", routes=[
    Route("/api/v1", _post, methods=["POST"]),
    WebSocketRoute("/api/v1/live", _live),
])
