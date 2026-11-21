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
| `src/components/` | The board, the dice, buttons and cards (the web app's colours) |
| `src/lib/api.ts` | The API client and its types. No React Native imports: the tests run it in Node |
| `src/lib/app.tsx` | Shared state: language, the connection, the board's row names |
| `src/lib/texts.ts`, `src/texts.json` | Texts (below). `texts.json` is generated: never edit it |
| `src/lib/storage.ts` | Games and seat tokens on the device (secure storage; the browser's on the web) |
| `tests/` | The API client against a real server (`node --test`) |

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
npx expo export --platform web           # the web build, in dist/ (not committed)
python tools/app_check.py --serve        # from the repository: the web build in a real browser
npx expo install <package>               # add a package: picks the version that fits SDK 58
npx expo-doctor                          # Expo's checks of the project
```

CI's "Phone app (Expo)" job runs the typecheck, the lint, the client tests against a
real server, the web build and `tools/app_check.py`. Run them before a pull request.

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
- Seat tokens are secrets: only in `src/lib/storage.ts`, never in a log or on screen.
- `src/lib/api.ts` stays free of React Native imports and of TypeScript that Node cannot
  run as it is (no enums, no parameter properties; `erasableSyntaxOnly` enforces it).
- The app's name, icon, identifiers and store accounts are the owner's decisions (item
  25, D1). Until then `app.json` keeps the template's icons and no bundle identifiers.
- Builds and store releases (`eas build`, `eas submit`, `eas update`) need the owner's
  Expo and store accounts: do not start them without the owner.
