# mobile/AGENTS.md

The Abaka app for Android and iOS: React Native with Expo (SDK 58), in TypeScript.
The repository's AGENTS.md and ProjectLibrary.md apply here too (branches, pull requests,
the shared log, "The website must keep working"); this file adds what is particular to
the app. The plan is Backlog item 25 in ProjectLibrary.md.

## What the app is

- **A thin client.** The server is the referee: the app shows the states it gets and
  offers the moves they list, with the server's previews and texts. It never applies the
  rules itself. The protocol is `docs/API.md` (protocol 1); never rely on anything it
  does not promise.
- **Every request goes over the live connection** (`WS /api/v1/live`, `src/lib/api.ts`),
  which also pushes the watched game's state. An answer that carries the watched game's
  state for the watching seat counts as sent: the server will not push it again, so the
  client hands it to the watcher too.
- **One connection serves every screen, and looks after itself** (`Connection`):
  - It stays open between screens. A screen that stops watching sends `unwatch`.
  - A screen gets the game's states in order, never an older one after a newer one. The
    answer to `watch` is a fresh start: after a server restart a game's counters begin
    again.
  - A connection can die without closing (a phone that changed networks). When nothing
    has arrived for 20 s it asks the server whether it is there; no answer, or a request
    that is never answered, and the connection is replaced.
  - A request that failed as `offline` is never made later.
- **Installed apps update slowly**, so the server answers every protocol in use. An app
  change never needs the server to change what an existing field means.
- **The server for apps** is not live yet (item 25, stage B). The app plays on a server
  run for development: `streamlit run abaka_server.py` in the repository (Streamlit
  1.67), port 8501. `src/lib/server.ts` says how the app finds it.

## Layout

| Path | What it is |
|---|---|
| `src/app/` | Screens (Expo Router: every file is a route; `_layout.tsx` is the navigator) |
| `src/app/index.tsx` | Home: continue a game, a game on one device, an online game, open by code |
| `src/app/game/[code].tsx` | One game: invite, waiting room, starting throw, turns, results |
| `src/app/club/[code].tsx` | A club: its table, latest games, a new club game, its code to share |
| `src/app/rules.tsx` | How to play: the rules from the server (`rules`), and the language switch |
| `src/components/` | The board, the dice, buttons and cards (the web app's colours) |
| `src/components/Reactions.tsx`, `Chat.tsx` | The reaction buttons and the chat card of an online game |
| `src/components/Shows.tsx` | What plays over the game: bubbles, fireworks and sparkles with their banner |
| `src/components/Club.tsx` | A club's table, its latest games, the ratings after a club game, its players to tap as names |
| `src/lib/clubs.ts` | The club's rows and numbers (rounded as Python rounds them), the names offered and tapped. Tested in Node |
| `src/lib/board.ts` | The score table's sizes: two players' columns fit the screen down to 360 wide. Tested in Node |
| `src/lib/dice.ts` | Where a die's pips go: the website's grid, centred inside the die's border. Tested in Node |
| `src/lib/start.ts` | Start a game from a screen (home, a club): the seat kept, the game opened |
| `src/lib/shows.ts` | Which of them play, and when (the website's rules). No React Native imports: tested in Node |
| `src/lib/api.ts` | The API client and its types. No React Native imports: the tests run it in Node |
| `src/lib/app.tsx` | Shared state: language, the connection, the board's row names |
| `src/lib/texts.ts`, `src/texts.json` | Texts (below). `texts.json` is generated: never edit it |
| `src/lib/storage.ts` | Games and seat tokens on the device (secure storage; the browser's on the web) |
| `tests/api.test.ts` | The API client against a real server (`node --test`; skipped without `ABAKA_SERVER`) |
| `tests/connection.test.ts` | The connection against a scripted server in the test's own process: restarts, states out of order, connections that die silently. Needs no game server |
| `tests/shows.test.ts` | What plays over the game, and when. Needs no server |
| `tests/clubs.test.ts` | Clubs on the screen: rows, numbers, names offered and tapped. Needs no server |
| `tests/board.test.ts` | The score table's sizes on common phone widths. Needs no server |
| `tests/dice.test.ts` | The dice's faces: centred whatever the border, as on the website. Needs no server |

## Texts

English in the code, `t("...")`, as on the web. Russian comes from `abaka/i18n.py`:

1. add the text with its Russian version to `abaka/i18n.py` (`RU`);
2. run `python tools/export_texts.py`, which writes `src/texts.json`;
3. commit both.

`tests/test_mobile_texts.py` (in the repository) fails when a `t("...")` text has no
Russian version or the export is out of date. Plurals come from i18n's own functions
through the export (`plural('reroll_dice', n)`). Texts the server sends (move labels, row
names, errors) are already in the request's language.

## Commands

Run from `mobile/` unless noted. The server for the tests and the check runs from the
repository, on Python 3.13 with Streamlit 1.67 (ProjectLibrary.md, Notes for this machine).

```bash
npm ci                                   # install exactly what package-lock.json says
npx expo start                           # the development server (Expo Go on a phone, or press w for the web)
npx tsc --noEmit                         # typecheck
npx expo lint                            # lint (React's rules included)
ABAKA_SERVER=http://127.0.0.1:8501 npm test   # the API client against a running abaka_server.py
npm test                                 # only the connection against its scripted server
npx expo export --platform web           # the web build, in dist/ (not committed)
python tools/app_check.py --serve        # from the repository: the web build in a real browser
npx expo install <package>               # add a package: picks the version that fits SDK 58
npx expo-doctor                          # Expo's checks of the project
```

CI's "Phone app (Expo)" job runs the typecheck, the lint, the client tests against a
real server, the web build and `tools/app_check.py`. Run them before a pull request.

## On Android: the emulator

Google's Android emulator is on this Mac (ProjectLibrary.md, Notes for this machine). It
runs the app in Expo Go as a phone does, so it shows what the web build cannot: the
status bar and the gesture bar, the keyboard, Android's back button, the app sent to the
background, a network that goes away, the native animations and Android's fonts. Use it
for any change to how the app sits on the screen.

```bash
~/Library/Android/sdk/emulator/emulator -avd Pixel_7_API_36 &   # the phone, in a window (about 50 s to boot)
npx expo start --android                 # installs Expo Go on it and opens the app; it reloads on save
ADB=~/Library/Android/sdk/platform-tools/adb
$ADB shell wm density 480                # a phone 360 wide (411 otherwise); wm density reset puts it back
$ADB exec-out screencap -p > screen.png  # a screenshot
$ADB exec-out uiautomator dump /dev/tty  # what is on the screen: a test id is the element's resource-id
$ADB shell input tap X Y; $ADB shell input text 'Test%sAnn'   # a tap; typing (%s is a space)
$ADB shell svc wifi disable; $ADB shell svc data disable      # no network (enable: back again)
```

- The game server runs on this Mac (`abaka_server.py`, port 8501). The emulator reaches it
  at the Mac's address, as a phone on the same Wi-Fi does. A second player can play
  through the API (`POST /api/v1`) while the emulator plays the first.
- uiautomator's dump holds only what is on the screen, so scroll to an element first. It
  waits until nothing animates, so it hangs while a spinner turns. After a swipe the page
  goes on moving: read positions once two dumps agree.
- In Expo Go the app is its own entry in the recent apps. Come back to it through the app
  switcher; Expo Go's launcher icon opens Expo Go's home page instead.
- `npx expo start --android` opens the app without Expo Go's floating tools button. A
  project opened by hand (`adb shell am start -d exp://...`) shows it, over the top right
  of the screen; add `?__expo_disable_fab=1` to the address.
- Changing the density restarts the app.
- The phone has the Mac's keyboard, so Android hides its own unless
  `adb shell settings put secure show_ime_with_hard_keyboard 1` (already set here).

## Expo has changed: do not trust your training data

Expo ships breaking changes every SDK release. Before writing code that touches an Expo,
EAS or React Native API:

1. read the major version of the `expo` package in `package.json`;
2. read the matching versioned docs: `https://docs.expo.dev/versions/v<major>.0.0/`;
3. for anything else, start from https://docs.expo.dev/llms.txt, an index of all Expo docs
   with corrections to common misconceptions.

Things already found here: SDK 58's `ThemeProvider`, `DarkTheme` and `DefaultTheme` come
from `expo-router`; TypeScript 6 loads no global types by default (a file that needs
Node's says `/// <reference types="node" />`); `expo-secure-store` has no web version.

## Rules

- Routes live in `src/app/`; everything else outside it. Import `router`, `Link`,
  `Stack` and `useLocalSearchParams` from `expo-router`.
- `ios/` and `android/` are generated (Continuous Native Generation). Never create or
  edit them: configure the app in `app.json` and config plugins.
- Expo Go has only its bundled native modules. A library with native code of its own
  needs a development build (`eas build --profile development`); prefer Expo's modules.
- Player names and chat are text: show them in `<Text>`, never as HTML or Markdown.
- A screen stops its own watch with what `startWatching` returns, never with
  `stopWatching()`: while one screen slides over another, the old one closes after the
  new one has opened.
- Leaving a screen never gives up a seat. "‹ Home" only goes home, and the game stays
  under "Continue a game"; a seat is given up by its own button (Leave, Cancel).
- What cannot be thrown on purpose (a tie, an Abaka) is checked with steered dice:
  `Steered` in `tools/app_check.py` is a real game server in the check's process.
- The words of reactions and effects come from the server with each event (`who`,
  `label`, `title`, `text`), and the reaction buttons from `info.reaction_list`. Do not
  build them in the app: a reaction or an effect the server adds later then works in an
  app already installed.
- A watcher's state has the game's whole chat and only the events not handed over
  before (`Connection` gathers them). A screen never merges messages itself.
- A test id is unique among the screens in the stack, not only on one screen: a screen
  under another stays in the page (the web build) and a check that finds its element
  first waits for one that cannot be seen.
- Numbers the website also shows are rounded with `roundHalfEven` (lib/clubs.ts), as
  Python rounds them.
- A request that must be in the language the screen shows passes `lang` itself
  (`connection.request('rules', { lang })`): a screen's effect can run before the app
  has switched the connection's language.
- What must always fit (the game's code at the top) is checked in `tools/app_check.py`
  with the widest text it can hold, on a 360px phone, not with today's text. So is the
  board with two players.
- Every screen is a `Screen` (`src/components/ui.tsx`). It keeps the page clear of the
  status bar and the gesture bar, keeps bubbles and fireworks inside the safe area, and on
  Android shrinks the page above the keyboard. Nothing else positions itself against the
  screen's edges.
- A form of one box and its button gives the box `onSubmit`, so the keyboard's Go does
  what the button does: on a phone the keyboard covers the button.
- Seat tokens are secrets: only in `src/lib/storage.ts`, never in a log or on screen.
- `src/lib/api.ts` stays free of React Native imports and of TypeScript that Node cannot
  run as it is (no enums, no parameter properties; `erasableSyntaxOnly` enforces it).
- The app's name, icon, identifiers and store accounts are the owner's decisions (item
  25, D1). Until then `app.json` keeps the template's icons and no bundle identifiers.
- Builds and store releases (`eas build`, `eas submit`, `eas update`) need the owner's
  Expo and store accounts: do not start them without the owner.
