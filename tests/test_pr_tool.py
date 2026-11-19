"""
tools/pr.py, with no network: the repository is found from any GitHub remote URL, and
`merge` waits for the required CI checks, brings a moved main into the branch and tests
again before merging (branch protection requires both since 2026-11-19).
"""

import contextlib
import importlib.util
import io
import os
import unittest
from unittest import mock

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


APP, ENGINE = "App on Python 3.13 (as on Streamlit Cloud)", "Engine on Python 3.8"


def run(name, status="completed", conclusion="success"):
    return {"id": 1, "name": name, "status": status, "conclusion": conclusion if status == "completed" else None}


class FakeGitHub:
    """Answers the calls pr.py makes, from a script: check runs per commit, poll by poll."""

    def __init__(self, runs, behind=False, conflict=False, required=(APP, ENGINE)):
        self.runs = {sha: list(polls) for sha, polls in runs.items()}
        self.head, self.behind, self.conflict, self.required = "c1", behind, conflict, required
        self.polls, self.updates, self.merged = 0, [], None

    def call(self, method, path, body=None):
        if path == "/branches/main/protection/required_status_checks":
            if self.required is None:
                raise SystemExit("GitHub GET: 404 (not an admin)")
            return {"strict": True, "checks": [{"context": name, "app_id": 15368} for name in self.required]}
        if path == "/pulls/7" and method == "GET":
            return {"number": 7, "head": {"sha": self.head}, "mergeable": True,
                    "mergeable_state": "behind" if self.behind else "clean"}
        if path.startswith("/commits/"):
            self.polls += 1
            polls = self.runs[path.split("/")[2]]
            return {"check_runs": polls.pop(0) if len(polls) > 1 else polls[0]}
        if path == "/pulls/7/update-branch":
            self.updates.append(body["expected_head_sha"])
            if self.conflict:
                raise SystemExit("GitHub PUT /pulls/7/update-branch: 422 merge conflict")
            self.head, self.behind = "c2", False
            return {"message": "Updating pull request branch."}
        if path == "/pulls/7/merge":
            self.merged = body
            return {"sha": "f" * 40}
        raise AssertionError(f"unexpected call {method} {path}")

    def job_log(self, job_id):
        return "FAIL: test_something\n"


class TestMerge(unittest.TestCase):
    def setUp(self):
        for target, name in ((pr_tool.time, "sleep"), (pr_tool.subprocess, "run")):
            patcher = mock.patch.object(target, name)  # no waiting, and no git checkout / pull
            patcher.start()
            self.addCleanup(patcher.stop)

    def merge(self, gh):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            pr_tool.cmd_merge(gh, 7)
        return out.getvalue()

    def test_waits_for_a_required_check_that_has_not_started(self):
        gh = FakeGitHub({"c1": [[run(APP)], [run(APP), run(ENGINE, "in_progress")], [run(APP), run(ENGINE)]]})
        self.merge(gh)
        self.assertEqual(gh.polls, 3)  # the finished App job alone was not enough
        self.assertEqual(gh.merged, {"merge_method": "merge", "sha": "c1"})

    def test_a_failing_check_stops_the_merge(self):
        gh = FakeGitHub({"c1": [[run(APP), run(ENGINE, conclusion="failure")]]})
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(io.StringIO()) as out:
            pr_tool.cmd_merge(gh, 7)
        self.assertIn("CI failed on #7", str(stop.exception))
        self.assertIn("FAIL: test_something", out.getvalue())  # the failing lines are shown
        self.assertIsNone(gh.merged)

    def test_a_branch_behind_main_is_brought_up_to_date_and_tested_again(self):
        gh = FakeGitHub({"c1": [[run(APP), run(ENGINE)]], "c2": [[], [run(APP), run(ENGINE)]]}, behind=True)
        out = self.merge(gh)
        self.assertEqual(gh.updates, ["c1"])  # only if the branch is still the commit CI tested
        self.assertEqual(gh.merged, {"merge_method": "merge", "sha": "c2"})  # the combined code, tested
        self.assertIn("behind main", out)

    def test_a_conflict_with_main_asks_for_a_rebase(self):
        gh = FakeGitHub({"c1": [[run(APP), run(ENGINE)]]}, behind=True, conflict=True)
        with self.assertRaises(SystemExit) as stop, contextlib.redirect_stdout(io.StringIO()):
            pr_tool.cmd_merge(gh, 7)
        self.assertIn("git pull --rebase origin main", str(stop.exception))
        self.assertIsNone(gh.merged)

    def test_without_admin_rights_the_checks_on_the_commit_decide(self):
        gh = FakeGitHub({"c1": [[run(APP), run(ENGINE)]]}, required=None)
        self.merge(gh)
        self.assertEqual(gh.merged["sha"], "c1")


if __name__ == "__main__":
    unittest.main()
