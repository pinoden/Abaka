"""
Pull requests from the command line, for people and coding agents alike.

`main` is protected: every change goes in through a pull request. `gh` is not
needed: this talks to the GitHub REST API with the credential git already uses
(`git credential fill`), so it works wherever `git push` does. The token is
never printed.

  python tools/pr.py status                     # open pull requests and their branches
  python tools/pr.py open --title "..." [--body-file notes.md]
                                                # push this branch, open its pull request
  python tools/pr.py wait [NUMBER]              # wait for CI; on failure, print the failing lines
  python tools/pr.py merge NUMBER               # merge once CI passed, then update local main
  python tools/pr.py ship --title "..." [--body-file notes.md]
                                                # open + wait + merge

Without NUMBER, `wait` uses the pull request of the current branch.

GitHub enforces the rest: `main` takes a pull request only when the required CI
checks passed on a branch that is up to date with `main` (branch protection).
If `main` moved after a branch was tested, `merge` brings `main` into the branch
on GitHub (a merge commit), waits for CI again on the combined code, and then
merges. If the two conflict, it stops: rebase the branch yourself (AGENTS.md).
"""

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

API = "https://api.github.com"
CI_TIMEOUT_SECONDS = 20 * 60
POLL_SECONDS = 15
UPDATE_ATTEMPTS = 3   # how many times `merge` brings a moving main into the branch before giving up


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout.strip()


def repo_slug(remote_url: str) -> str:
    """'owner/name' from an https or ssh GitHub remote URL."""
    match = re.search(r"github\.com[:/]+([^/]+)/([^/]+?)(?:\.git)?/?$", remote_url.strip())
    if not match:
        raise SystemExit(f"not a GitHub remote: {remote_url}")
    return f"{match.group(1)}/{match.group(2)}"


def token() -> str:
    out = subprocess.run(["git", "credential", "fill"], input="protocol=https\nhost=github.com\n\n",
                         capture_output=True, text=True).stdout
    for line in out.splitlines():
        if line.startswith("password="):
            return line.split("=", 1)[1]
    raise SystemExit("git has no stored GitHub credential (push once with git to store one)")


class GitHub:
    def __init__(self) -> None:
        self.repo = repo_slug(git("remote", "get-url", "origin"))
        self._token = token()

    def call(self, method: str, path: str, body: dict = None):
        url = path if path.startswith("http") else f"{API}/repos/{self.repo}{path}"
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(url, data=data, method=method, headers={
            "Authorization": "Bearer " + self._token, "Accept": "application/vnd.github+json"})
        try:
            with urllib.request.urlopen(request) as response:
                text = response.read().decode()
        except urllib.error.HTTPError as e:
            raise SystemExit(f"GitHub {method} {path}: {e.code} {e.read().decode()[:500]}")
        return json.loads(text) if text else None

    def job_log(self, job_id: int) -> str:
        """A job's log. GitHub redirects to storage that must not get the token."""
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None

        request = urllib.request.Request(f"{API}/repos/{self.repo}/actions/jobs/{job_id}/logs", headers={
            "Authorization": "Bearer " + self._token, "Accept": "application/vnd.github+json"})
        try:
            urllib.request.build_opener(NoRedirect).open(request)
            return ""
        except urllib.error.HTTPError as e:
            location = e.headers.get("Location")
        if not location:
            return ""
        with urllib.request.urlopen(location) as response:
            return response.read().decode("utf-8", "replace")

    def pull_for_branch(self, branch: str):
        owner = self.repo.split("/")[0]
        pulls = self.call("GET", f"/pulls?state=open&head={owner}:{branch}")
        return pulls[0] if pulls else None


def current_branch() -> str:
    branch = git("branch", "--show-current")
    if not branch:
        raise SystemExit("not on a branch")
    return branch


def cmd_status(gh: GitHub, args) -> None:
    pulls = gh.call("GET", "/pulls?state=open&per_page=50")
    if not pulls:
        print("no open pull requests")
    for p in pulls:
        print(f"#{p['number']}  {p['head']['ref']:<32} {p['title']}  ({p['html_url']})")


def cmd_open(gh: GitHub, args) -> int:
    branch = current_branch()
    if branch == "main":
        raise SystemExit("on main: create a branch first (git checkout -b <agent>/<topic>)")
    if git("status", "--porcelain"):
        print("note: there are uncommitted changes; only commits are pushed", file=sys.stderr)
    subprocess.run(["git", "push", "-q", "-u", "origin", branch], check=True)
    existing = gh.pull_for_branch(branch)
    if existing:
        print(f"#{existing['number']} already open: {existing['html_url']}")
        return existing["number"]
    body = open(args.body_file, encoding="utf-8").read() if args.body_file else ""
    pull = gh.call("POST", "/pulls", {"title": args.title, "head": branch, "base": "main", "body": body})
    print(f"#{pull['number']} opened: {pull['html_url']}")
    return pull["number"]


def required_checks(gh: GitHub) -> list:
    """
    The CI checks main's branch protection requires before a merge. Empty if they cannot be
    read (only repository admins may read the protection); GitHub enforces them anyway.
    """
    try:
        data = gh.call("GET", "/branches/main/protection/required_status_checks") or {}
    except SystemExit:
        return []
    return [c["context"] for c in data.get("checks") or []] or list(data.get("contexts") or [])


def wait_for_ci(gh: GitHub, number: int, required=()) -> bool:
    """
    Wait until CI finished on the pull request's latest commit: every check run there, and
    every check in `required` (a job may not have started yet when the others have finished).
    """
    sha = gh.call("GET", f"/pulls/{number}")["head"]["sha"]
    deadline = time.time() + CI_TIMEOUT_SECONDS
    print(f"waiting for CI on #{number} ({sha[:7]})...", flush=True)
    while True:
        runs = gh.call("GET", f"/commits/{sha}/check-runs")["check_runs"]
        missing = set(required) - {r["name"] for r in runs}
        if runs and not missing and all(r["status"] == "completed" for r in runs):
            break
        if time.time() > deadline:
            raise SystemExit("CI did not finish in time: " + ", ".join(
                [f"{r['name']}={r['status']}" for r in runs] + [f"{name}=not started" for name in sorted(missing)]))
        time.sleep(POLL_SECONDS)
    ok = True
    for r in runs:
        print(f"  {r['conclusion']:<9} {r['name']}")
        if r["conclusion"] not in ("success", "skipped", "neutral"):
            ok = False
            lines = [line[29:] if len(line) > 29 and line[4] == "-" else line
                     for line in gh.job_log(r["id"]).splitlines()]
            failing = [line for line in lines if re.search(r"(FAIL|ERROR)[:\s]|Error|Traceback|assert", line)]
            print("\n".join("    " + line for line in failing[-40:]))
    return ok


def cmd_wait(gh: GitHub, args) -> bool:
    number = args.number
    if number is None:
        pull = gh.pull_for_branch(current_branch())
        if not pull:
            raise SystemExit("this branch has no open pull request")
        number = pull["number"]
    return wait_for_ci(gh, number, required_checks(gh))


def mergeability(gh: GitHub, number: int) -> dict:
    """The pull request, once GitHub has worked out whether it can be merged (it does so in the background)."""
    for _ in range(20):
        pull = gh.call("GET", f"/pulls/{number}")
        if pull["mergeable"] is not None and pull["mergeable_state"] != "unknown":
            return pull
        time.sleep(3)
    return pull


def bring_main_in(gh: GitHub, pull: dict) -> None:
    """Merge main into the pull request's branch on GitHub, and wait until the branch has the new commit."""
    number, old = pull["number"], pull["head"]["sha"]
    print(f"#{number} is behind main: bringing main into the branch; CI runs again on the combined code",
          flush=True)
    try:
        gh.call("PUT", f"/pulls/{number}/update-branch", {"expected_head_sha": old})
    except SystemExit as e:
        raise SystemExit(f"{e}\n#{number}: main could not be brought into the branch (a conflict?). Rebase it "
                         "yourself: git pull --rebase origin main, run the tests, push (AGENTS.md).")
    for _ in range(40):
        if gh.call("GET", f"/pulls/{number}")["head"]["sha"] != old:
            print("  the branch on GitHub has main now; your local branch does not (git pull to get it)")
            return
        time.sleep(3)
    raise SystemExit(f"#{number}: GitHub did not update the branch in time; run merge again")


def cmd_merge(gh: GitHub, number: int) -> None:
    required = required_checks(gh)
    for _ in range(UPDATE_ATTEMPTS + 1):
        if not wait_for_ci(gh, number, required):
            raise SystemExit(f"CI failed on #{number}: not merged")
        pull = mergeability(gh, number)
        if pull["mergeable_state"] == "behind":  # main moved: the checks must pass on the combined code
            bring_main_in(gh, pull)
            continue
        if not pull["mergeable"]:
            raise SystemExit(f"#{number} cannot be merged ({pull['mergeable_state']}): rebase it on main "
                             "(git pull --rebase origin main, run the tests, push), then merge again")
        break
    else:
        raise SystemExit(f"#{number}: main kept moving; run merge again")
    result = gh.call("PUT", f"/pulls/{number}/merge", {"merge_method": "merge", "sha": pull["head"]["sha"]})
    print(f"#{number} merged ({result['sha'][:7]})")
    subprocess.run(["git", "checkout", "-q", "main"], check=True)
    subprocess.run(["git", "pull", "-q", "--ff-only"], check=True)
    print("local main is up to date")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status")
    for name in ("open", "ship"):
        p = sub.add_parser(name)
        p.add_argument("--title", required=True)
        p.add_argument("--body-file")
    p = sub.add_parser("wait")
    p.add_argument("number", nargs="?", type=int)
    p = sub.add_parser("merge")
    p.add_argument("number", type=int)
    args = parser.parse_args()

    gh = GitHub()
    if args.command == "status":
        cmd_status(gh, args)
    elif args.command == "open":
        cmd_open(gh, args)
    elif args.command == "wait":
        sys.exit(0 if cmd_wait(gh, args) else 1)
    elif args.command == "merge":
        cmd_merge(gh, args.number)
    elif args.command == "ship":
        cmd_merge(gh, cmd_open(gh, args))


if __name__ == "__main__":
    main()
