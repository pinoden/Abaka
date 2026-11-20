"""
The website in a real browser (tools/website_check.py), on local servers with Streamlit 1.67,
as on Streamlit Cloud:
- abaka_ui.py alone, which is what the live app runs;
- abaka_server.py, the app with the API (Backlog item 25).

The owner asked that the website keep working while the apps for phones are built. CI runs
this on every pull request, so a change that breaks the home page, a game on one device or
an online game cannot be merged.

Needs Playwright and its Chromium (requirements-dev.txt). CI installs them and sets
ABAKA_REQUIRE_BROWSER=1, so there a missing browser fails the test instead of skipping it.
"""

import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
try:
    import website_check
finally:
    sys.path.pop(0)

try:
    import streamlit
except ImportError:  # the base Python 3.8
    streamlit = None


def why_not() -> str:
    """Why the checks cannot run here ("" if they can)."""
    if streamlit is None or not hasattr(streamlit, "App"):
        return "the checks follow Streamlit 1.67's pages, as on Streamlit Cloud"
    return website_check.unavailable() or ""


class TestWebsiteInABrowser(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        why = why_not()
        if why and os.environ.get("ABAKA_REQUIRE_BROWSER"):
            raise RuntimeError(f"the website checks must run here, but cannot: {why}")
        if why:
            raise unittest.SkipTest(why)

    def check(self, script, flows=website_check.FLOWS):
        problems = website_check.check_local(script, flows, report=lambda line: None)
        self.assertEqual(problems, [], "\n\n".join(problems))

    def test_the_web_app_as_streamlit_cloud_runs_it(self):
        self.check("abaka_ui.py")

    def test_the_web_app_served_with_the_api(self):
        self.check("abaka_server.py", ("home", "online"))


if __name__ == "__main__":
    unittest.main()
