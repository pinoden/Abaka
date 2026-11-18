"""tools/pr.py: the repository is found from any GitHub remote URL (no network here)."""

import importlib.util
import os
import unittest

_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "tools", "pr.py")
_spec = importlib.util.spec_from_file_location("pr_tool", _PATH)
pr_tool = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pr_tool)


class TestRepoSlug(unittest.TestCase):
    def test_https_and_ssh_remotes(self):
        for url in ("https://github.com/pinoden/Abaka.git", "https://github.com/pinoden/Abaka",
                    "git@github.com:pinoden/Abaka.git", "ssh://git@github.com/pinoden/Abaka.git",
                    "https://github.com/pinoden/Abaka/\n"):
            self.assertEqual(pr_tool.repo_slug(url), "pinoden/Abaka", url)

    def test_other_hosts_are_refused(self):
        with self.assertRaises(SystemExit):
            pr_tool.repo_slug("https://gitlab.com/pinoden/Abaka.git")


if __name__ == "__main__":
    unittest.main()
