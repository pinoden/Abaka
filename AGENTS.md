# AGENTS.md

How coding agents work on Abaka. Two agents work here, Codex and Claude Code,
sometimes on the same day, for one owner. Codex reads this file by itself;
Claude Code reads it through CLAUDE.md. Keep it short: the details live in
ProjectLibrary.md.

## The files

| File | What it is |
|---|---|
| `AGENTS.md` | This file: how agents share the project. The same for every agent |
| `ProjectLibrary.md` | The project guide and shared working log: commands, architecture, conventions, Rules for changes, Backlog, Status, Known issues, Decision log |
| `CLAUDE.md` | Loads AGENTS.md and ProjectLibrary.md for Claude Code. Nothing else goes in it |

Do not rename or move these three: each tool finds its file by name.

## Before you change anything

- Read the parts of `ProjectLibrary.md` the task touches. It is long (search
  it): at least **Rules for changes**, the **Backlog** item, and the sections
  on the code you change. Its rules apply to every change.
- Start from the latest `main`: `git checkout main && git pull --ff-only`.
- See what is in flight: `python tools/pr.py status` lists the open pull
  requests and their branches. Do not change files an open pull request of the
  other agent changes, unless the owner asked you to; if you must, say so in
  your pull request.

## Making a change

1. Work on a branch named after your agent: `codex/<topic>` or
   `claude/<topic>`. Never commit to `main`: it is protected and only takes
   pull requests.
2. Run the tests (Commands in ProjectLibrary.md). The engine must keep working
   on Python 3.8.
3. In the same pull request, update `ProjectLibrary.md`:
   - the Backlog item (with the pull request number);
   - a Status line;
   - a Decision log entry headed with the date, the topic, your agent and the
     pull request, for example `2026-11-18: dice picking (Codex, PR #38)`.
   Add to the log; change another agent's entries only to correct facts.
4. Ship it with `python tools/pr.py`:
   - `open --title "..." --body-file notes.md` pushes the branch and opens the
     pull request;
   - `wait` waits for CI and, if it fails, prints the failing lines;
   - `merge NUMBER` merges once CI passed and updates local `main`;
   - `ship --title "..." --body-file notes.md` does all three.
   Merge only if the owner asked for it or has said changes may go in without
   asking. Otherwise open the pull request and tell the owner.
   GitHub refuses a merge until both CI jobs passed on a branch that is up to
   date with `main`. If `main` moved, `merge` brings it into the branch and
   waits for CI again; if they conflict, do step 5. Do not rename the CI jobs
   (`.github/workflows/tests.yml`): the protection names them.
5. If `main` moved meanwhile: `git pull --rebase origin main` on your branch,
   run the tests again, and push. In `ProjectLibrary.md` keep both sides'
   entries.
6. A merge updates the live app (https://mipt-abaka.streamlit.app/) within a
   few minutes. Check a visible change there, and run the website check
   (below).

## The website must keep working

The owner: "Make sure that the websites version won't brake while developing
the app transform". People keep playing on the live app while the apps for
phones are built (Backlog item 25). So:

- **CI checks the website in a real browser** on every pull request
  (`tests/test_website.py`, running `tools/website_check.py`):
  - the home page in English and Russian;
  - a game on one device;
  - an online game between a desktop and a phone.
  A change that breaks them cannot be merged. Never skip, loosen or delete
  these checks to get a change in: fix the change. Extend them when the
  website gains something people rely on.
- **After every merge**, once the live app shows the change, run
  `python tools/website_check.py` against the live app. Add `--cleanup`, with
  `ABAKA_DATABASE_URL` from `.env.local`, to remove its test games.
- **If the live app is broken, revert at once.** Open a pull request with
  `git revert -m 1 <merge commit>`, merge it as soon as CI passes, tell the
  owner, then fix the change on a new branch.
- **App work goes in its own places:** `abaka/api.py`, `server/`,
  `abaka_server.py`, and later `mobile/`, the phone app's folder in this
  repository (Backlog item 25). Code the website runs
  (the rest of `abaka/`, `ui_components/`, `abaka_ui.py`, `server/stores.py`,
  `code_version.py`, `.streamlit/`, `requirements.txt`) changes only as far
  as the apps need it.
- **The website stays on Streamlit Cloud** until the owner decides to move it.
  A new host first runs next to it with a database of its own (a Neon
  branch), never the production one. Two servers writing the same games would
  lose moves.

## Things both agents must know

- Pushes use the owner's GitHub account, so a failing CI run emails the owner,
  even on a branch. If a run fails, tell the owner what failed and how you
  fixed it.
- An agent's own memory is private to it. Anything the other agent or the
  owner needs (a decision, a rule the owner gave, a finding, a workaround)
  goes into `ProjectLibrary.md`, in the same pull request.
- Do not commit scratch files, test output, credentials or agent settings
  (`.claude/settings.local.json`).
- The game rules are the owner's own. Do not change them unless the owner
  asks.
