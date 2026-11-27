"""
This browser's secret, which holds its seats in online games (Backlog item 37; rooms.py keeps
its hash per seat). The browser keeps it, and tells the server at the start of every session.

Streamlit gives a page's script no cookie to set, and on Streamlit Cloud the app never receives
a cookie the page sets itself (Cloud passes only its own; found on the live app, PR #80). So on
Streamlit 1.67 a small component keeps the secret in the browser's local storage and sends it
over the page's own connection, as a widget's value: the server knows it from the session's
second run on, a moment after the first. Streamlit 1.48 (local runs) has no such components;
there the secret is a cookie, which a local server does receive.
"""

from typing import Optional

import streamlit as st

from abaka.rooms import is_device, new_device

STORAGE_NAME = "abaka_device"     # the name in the browser's local storage, and of the cookie on 1.48
COOKIE_RUNS = 3                   # 1.48: a session writes the cookie on this many of its first runs
GIVE_UP_AFTER = 3                 # checks of a page waiting for the browser's answer (device_wait)

# Runs in the page. The secret it finds is checked here and again on the server (is_device);
# what it stores is the server's own offer, made of letters, digits, - and _ only.
_JS = """
export default function(component) {
  const { setStateValue, data } = component;
  let secret = null;
  try { secret = window.localStorage.getItem(data.name); } catch (e) {}
  if (!/^[A-Za-z0-9_-]{16,128}$/.test(secret || '')) {
    secret = data.offer;
    try { window.localStorage.setItem(data.name, secret); } catch (e) {}
  }
  setStateValue('device', secret);
}
"""

try:
    _keeper = st.components.v2.component("abaka_device", js=_JS)
except AttributeError:  # Streamlit 1.48
    _keeper = None


def _nothing() -> None:
    """The component's value needs a callback to be sent; the run it causes is all that is wanted."""


def keep_device() -> None:
    """
    Call at the start of every run. Until the browser's secret is known it asks the browser for
    it, offering a new one to keep if it has none. Takes no room on the page (style.py).
    """
    ss = st.session_state
    if _keeper is None:
        _keep_in_a_cookie()
        return
    if ss.get("device"):
        return
    ss.setdefault("device_offer", new_device())
    with st.container(key="device-keeper"):
        result = _keeper(key="device-secret", data={"offer": ss.device_offer, "name": STORAGE_NAME},
                         on_device_change=_nothing)
    kept = getattr(result, "device", None)
    if is_device(kept):
        ss.device = kept


def _keep_in_a_cookie() -> None:
    """Streamlit 1.48: the secret from the browser's cookie, known at once; a new one is written by the page."""
    ss = st.session_state
    if not ss.get("device"):
        try:
            kept = st.context.cookies.get(STORAGE_NAME, "")
        except Exception:  # noqa: BLE001 - no browser behind this run
            kept = ""
        ss.device = kept if is_device(kept) else new_device()
        ss.device_cookie_runs = 0 if kept == ss.device else COOKIE_RUNS
    if ss.get("device_cookie_runs", 0) > 0:  # more than once: a run can be cut short before the page drew it
        ss.device_cookie_runs -= 1
        import streamlit.components.v1 as components  # a frame of the page's own origin
        with st.container(key="device-keeper"):
            components.html("<script>document.cookie = '%s=%s; path=/; max-age=31536000; SameSite=Lax';</script>"
                            % (STORAGE_NAME, ss.device), height=0)


def device() -> Optional[str]:
    """This browser's secret, or None in a session's first moment, before the browser has said."""
    return st.session_state.get("device")


def device_to_keep() -> str:
    """The secret to take a seat or ask for one with: the browser's, or the one it was offered to keep."""
    ss = st.session_state
    return ss.get("device") or ss.setdefault("device_offer", new_device())


@st.fragment(run_every=1.0)
def device_wait() -> None:
    """
    On a page that waits for the browser's secret: the browser's answer redraws the page by
    itself; if none comes (GIVE_UP_AFTER checks), go on with the offered secret, as a new browser.
    """
    ss = st.session_state
    if ss.get("device"):
        st.rerun()
    ss.device_waits = ss.get("device_waits", 0) + 1
    if ss.device_waits >= GIVE_UP_AFTER:
        ss.device = ss.setdefault("device_offer", new_device())
        st.rerun()
