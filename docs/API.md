# The game API for apps

How an app (Android, iOS, or any other client) plays Abaka on the server: what it
sends, what it gets back, and what it may rely on. Protocol version **1**.

The code is `abaka/api.py`; `tests/test_api.py` plays complete games through it and
checks that this document names every operation and error. The plan this is part of
is Backlog item 25 in `ProjectLibrary.md`.

## How it works

- **The server is the referee.** An app shows the state it receives and offers the
  moves that state lists, with their exact previews. It never applies the rules
  itself, so a rule change on the server reaches every app at once.
- **One game, any client.** Every move goes through the same `RoomStore` as a move
  from the web app, with the same turn check and version. A web player and an app
  player can play at one table.
- **Messages are JSON.** A request is an object naming its operation (`op`); the
  answer is an object, or an error. In Python:
  `api.handle(request, store, clubs) -> response`, raising `ApiError`.
- **Over the network:** `POST /api/v1` for one request at a time, and a live
  WebSocket that also pushes a game's state whenever it changes (see "Over the
  network" below).

## Requests

Every request may carry:

| Field | Meaning |
|---|---|
| `op` | The operation (below). Required. |
| `protocol` | The protocol version the app speaks. Default 1. Any other version is refused with `protocol`. |
| `lang` | `"en"` or `"ru"`: the language of the texts in the answer (labels, error messages). Default `"en"`. |

Most operations name a game by `code` (5 characters; spaces and lower case are
accepted) and a seat by `token`. The token is a secret: the app keeps it on the
device and never shows it.
- It comes from `create`, `create_local`, `join`, `rejoin` or `resume`, and it never
  appears in a state.
- A token stops working when the seat is taken back on another device (`rejoin`).

Every game also has a `key`, 8 characters of the same alphabet as codes (Backlog
item 31). A game's code alone opens nothing: `join`, `rejoin` and `resume` need
the key, and so do `state` and `seen` for anyone without a seat in the game. A
missing or wrong key is answered `not_found`, exactly as a game that does not
exist, so trying codes tells nothing.
- The key comes in every state (`key`), which only someone in the game gets.
- Players share the game's full code, `CODE-KEY` ("Q47CH-8XJ4PN2R"), and its link
  (`?room=Q47CH-8XJ4PN2R`). Spaces, a missing dash and lower case are accepted.
- A request gives the key as `key`, or as the full code in `code`.
- Keep the key with the token: with a token that lost its seat, `state` needs the
  key to show the invite.

Moves also carry `version`: the `version` of the state the player chose the move
on. If the game has changed since, the move is refused with `outdated` and nothing
changes. This catches double taps and moves made on an old screen.

The server cleans every name and chat message it is given, so show the text that
comes back in the state, not what was typed:
- spaces are collapsed, and the text is cut to its limit (`info.limits`);
- control characters and invisible ones (such as right-to-left overrides) are
  removed;
- so is half of a surrogate pair, which JSON can carry (`"\ud83d"`) and UTF-8
  cannot. A whole emoji is kept.

## Operations

### Starting and finding games

#### `info`
What an app needs once per language: `protocol`, `languages`, `players` (`min`,
`max`), `limits` (name, chat message and club name lengths), `reactions` (their
ids), `reaction_list` and `rows`.
- `rows` lists the board's 15 rows in board order, each
  `{"row": "SCHOOL_1", "name": "School 1", "hint": "...", "school": true}`, with the
  name and hint in the request's language.
- `reaction_list` lists the reaction buttons in their order, each
  `{"id": "lucky", "emoji": "🍀", "label": "Lucky!"}`, with the label in the
  request's language. Show these, and a reaction the server adds later appears by
  itself.

#### `create`
An online game. `name` (blank: "Player 1"), `players` (2 to 5, default 2), `club`
(optional: the game counts for that club's table).
Answer: `{"code", "token", "state"}`. The creator is seat 0. The game starts when
every seat is taken, or when the creator sends `start_now`.

#### `create_local`
A game on one device: `names` (2 to 5; blank names become "Player 2"...), `club`
(optional), `computers` (optional). One token plays every seat. Answer:
`{"code", "token", "state"}`.
In a club game every name must be different, ignoring capitals and spaces;
otherwise the request is `refused`.

`computers` lists the seats the computer plays, as positions in `names`
(`[1]`: the second seat). A blank name there becomes "Computer" ("Computer 1",
"Computer 2"... with several), in the request's language. At least one seat must
be a person's, and games against the computer do not count for a club: either is
`refused`. The server plays the computer's turns by itself (see "The computer"
below).

#### `join`
Take the next free seat of an online game: `code`, `key`, `name`. Names are made distinct
("Ann (2)"). Answer: `{"code", "token", "state"}`.
In a club game a name already at the table, ignoring capitals and spaces, is
`refused`: the club would count both as one member.

#### `rejoin`
Take a seat back: `code`, `key`, `seat`. The seat gets a new token, and the device
that held it before loses it (its requests are refused with `not_seated`). Anyone
with the game's key (its link or full code) may do this.

#### `resume`
Carry on with a game played on one device from its `code` and `key`: answers with
its token. An online game is `refused`.

#### `state`
The game as the holder of `token` sees it: `code`, `token` (optional), `key`
(needed without a seat), `since` (optional). Answer: `{"state": ...}`. Without a
seat (no token, or one that was taken over), the state shows only what an invite
shows: the names, and in `can` how to take a seat.

#### `seen`
`code` and a seat's `token` or the game's `key` → `{"seen": "12.3.1795157785252"}`. The text changes whenever the state
does (a move, a pick, a reaction, a chat message). It is cheap, so an app can ask
every second and fetch `state` only when it changes.

#### The computer
In a game with `computers`, the server plays those seats: the starting throw, the
roll, the dice it keeps (shown as picked dice, `game.picked`, about a second
before it rolls the others), its rerolls and its move, one step about every
second, so the player sees each one. A step is made when the game is looked at
with `seen`, which `watch` on the live connection does four times a second: watch
the game (or ask `seen` every half second) while it is the computer's turn. Its
moves are ordinary moves: they change `version`, and bring effects like anyone's.
On the computer's turn `can` offers no move and `moves` is null.

### Playing

Each of these takes `code`, `token` and `version`. The answer is the new state:
`{"state": ...}`.

#### `throw`
This player's throw for who goes first (phase `starting_throw`). The lowest total
starts; players who tie throw again.

#### `roll`
The first roll of the turn.

#### `reroll`
`dice`: positions (0 to 4) of the dice to roll again. At most two rerolls a turn.

#### `score`
Write the dice into `row` (for example `"SUM"`), in `slot` (0 to 2). Without
`slot`, the row's next free cell, which is the only one the rules allow. Offer the
moves from `state.moves.score`.

#### `cross`
Cross out a combination row (`row`, optional `slot`), giving up its bonuses as
`state.moves.cross` says. School rows cannot be crossed out.

### At the table

These take `code` and `token`, and no `version`: they are not moves. The answer is
the new state.

#### `pick`
`dice`: the dice the player whose turn it is has picked to roll again, so the
others see them. Online games only.

#### `react`
`reaction` (one of `info.reactions`) to everyone, or `to` one seat. Online games,
one every 2 seconds per player (`too_fast`).

#### `say`
A chat message, `text`. The server cleans it and cuts it to 200 characters. Online
games, while the game is being played, at most 3 messages in 3 seconds
(`too_fast`). The move that ends the game deletes the chat.

#### `rematch`
After the game: the next game with the same players. If someone else started it
first, the answer is that game.

#### `start_now`
The creator starts the game with the players who have joined (at least two).

#### `leave`
Give up a seat in the waiting room: later players move up a seat, and an empty
game is closed. Once the game has started, seats are kept. Answer: `{"left": true}`.

### Clubs

#### `club`
`club` (the club's 6-character code), `games` (how many recent games to list,
default 10, at most 200). Answer `{"club": ...}`:
- `code` and `name`;
- `members`, best first: `name`, `rating`, `change` (in their latest game),
  `games`, `wins`, `points`, `best`, `last_played`;
- `games`, newest first: `id`, `at`, `players` (`name`, `score`, `change`);
- `names`: the members' names, the most recently played first, for name pickers.

#### `create_club`
`name` → `{"club": ...}`, the new club, as `club` gives it.

### The rules

#### `rules`
The rules, in the request's language, as the website shows them:
`{"rules": {"title": "How to play", "blocks": [...]}}`. Each block is one of:
- `{"heading": "Combinations"}`;
- `{"text": "..."}`: a paragraph. Bold parts are marked `**like this**`; there is
  no other markup;
- `{"table": {"head": ["Row", "Needs", "Scores"], "rows": [[...], ...]}}`: the
  combinations, one row each.

The owner changes the rules from time to time, and the server's text changes with
them: ask for the rules again rather than keeping them in the app.

## The state

```json
{
  "protocol": 1,
  "code": "Q47CH",
  "key": "8XJ4PN2R",
  "version": 12,
  "seen": "12.3.1795157785252",
  "now": 1795157790.125,
  "local": false,
  "capacity": 3,
  "club": null,
  "names": ["Ann", "Bob", "Cy"],
  "computers": [],
  "seated": true,
  "you": 1,
  "phase": "playing",
  "can": ["react", "say"],
  "game": { ... },
  "moves": null,
  "races": { ... },
  "differences": { ... },
  "events": [ ... ],
  "chat": [ ... ],
  "table": {"games": 2, "wins": [1, 1, 0], "draws": 0},
  "club_result": null
}
```

| Field | Meaning |
|---|---|
| `key` | The game's key: the full code to share is `code-key`. A state goes only to someone in the game. |
| `version` | Send it back with a move. |
| `seen` | As the `seen` operation gives it. |
| `now` | The server's clock, in seconds. Use it to tell how old an event is, whatever the device's clock says. |
| `local` | A game on one device: `you` is null, and the token plays whoever's turn it is, except the computer's seats. |
| `capacity` | How many players the game is for. |
| `names` | The players in seat order. Seat 0 created the game. |
| `computers` | The seats the computer plays (`create_local`'s `computers`), empty in other games. |
| `seated`, `you` | Whether the token holds a seat, and which one (null on one device). |
| `phase` | `waiting` (players joining), `starting_throw` (deciding who goes first), `playing`, `over`. |
| `can` | What this player may do now: the operations to offer. |
| `game` | The game (below), once it has started and the token holds a seat. |
| `moves` | The moves to offer, when it is this player's turn and the dice are on the table. |
| `races` | The races for the shared bonuses (below), while the game is played, or null when there is none. |
| `differences` | The difference row by row (below), for this seat; on one device for the player whose turn it is. Null in the waiting room, during the starting throw, and on one device once the game is over. |
| `events` | Recent reactions and effects (below), newer than `since`. |
| `chat` | The game's messages, newer than `since`: `id`, `seat`, `text`, `at`. Show `text` as plain text, never as HTML or Markdown. |
| `table` | The running score at this table: games finished here, wins per seat, draws. |
| `club_result` | After a club game: `club` (its name) and `players` (`name`, `score`, `change`, `rating`). |

### `can`

| Value | When |
|---|---|
| `join`, `rejoin`, `resume` | No seat yet: join a waiting game, take a seat back, or carry on a game on one device. |
| `leave`, `start_now` | The waiting room (`start_now`: the creator, with at least two players). |
| `throw` | This player's starting throw. |
| `roll` | This player's turn, before the first roll. |
| `reroll`, `pick` | Dice on the table and a reroll left (`pick`: online only). |
| `score`, `cross` | Dice on the table and something to write (or cross out). |
| `rematch` | The game is over. |
| `react`, `say` | Online games, once they have started (`say` until the game is over). |

### `game`

| Field | Meaning |
|---|---|
| `number` | Games at this table so far, this one included. |
| `current` | The seat whose turn (or starting throw) it is. |
| `dice` | `[{"value": 1-6, "joker": bool}]`, five of them, or `[]` before the turn's first roll. The joker is wild when it shows 1. |
| `rolls_left` | Rerolls left this turn (2, 1, 0). |
| `first_roll` | The dice are from the turn's first roll, which doubles a combination's score. |
| `picked` | Dice the current player has picked to roll again (online). |
| `rerolled` | Dice the latest reroll rolled again: spin exactly these. |
| `last_move` | `{"seat", "row", "slot"}` of the cell the latest move wrote, or null. |
| `starting_throw` | `round`, `throwing` (the seats throwing in this round; empty once decided), `throws` (`round`, `seat`, `dice`, `total`), `first_player`. |
| `players` | Per seat: `name`, `total`, `school_balance`, `balance_cell`, `rows`, `column_bonus` (below). |
| `winners` | Once the game is over, the seats with the top score. Two or more means a draw. |
| `history` | Every player's total after each move, for a chart of the scores by move: `[{"move": 0, "totals": [0, 0]}, {"move": 1, "totals": [24, 0]}, ...]`. `move` counts the moves made (cells written). A game saved before the history was kept (2026-11-26) starts where it was then, without a point at 0. |

`rows` gives each row its three cells, then its row bonus cell, for example
`"SUM": [22, 18, null, null]`.
- A cell is `null` (empty), a number, or `"X"`.
- In a combination row, `"X"` is a crossed-out cell.
- In a School row, `"X"` is a settled cell: exactly three of its number, or an
  earlier balance. The current School balance is written in `balance_cell`.
- In a bonus cell, `"X"` means the bonus is lost: given up by this player, or
  closed by another player who completed the row or column first.
- `column_bonus` holds the three column bonuses (I, II, III) the same way.

### `moves`

```json
{"score": [{"row": "SUM", "slot": 1, "value": 22, "points": 22, "bonus": 0, "best": true,
            "balance_change": null, "bonus_lost": false, "column_bonus_lost": false,
            "label": "Sum · 22", "action": "Score 22 in Sum", "preview": "22"}],
 "cross": [{"row": "PAIR", "slot": 0, "value": "X", "points": null, "bonus": 0, "best": false,
            "balance_change": null, "bonus_lost": true, "column_bonus_lost": true,
            "label": "Pair", "action": "Cross out Pair (lose the row and column bonuses)",
            "preview": "✕"}]}
```

| Field | Meaning |
|---|---|
| `row`, `slot` | Send them back with `score` or `cross`. |
| `value` | What the cell will hold: a number, or `"X"`. |
| `points` | What the move adds to the player's total now, any bonus it earns included. |
| `bonus` | Row and column bonus points the move earns at once. |
| `best` | Among the options with the most points: highlight it. All of them on a tie. |
| `balance_change` | School rows: the balance change (negative: paid from the balance). |
| `bonus_lost`, `column_bonus_lost` | The move gives up the row bonus or the column bonus: show their cells crossed out in the preview. |
| `label`, `action`, `preview` | Texts in the request's language: the option, its confirm button, and the cell's text on the board. |

### `differences`

"How much you are losing in each row" (a tester, 2026-11-26): this player's
points in each row (its three cells and its bonus) minus the opponent's, or
minus the best of the others' at a table of three or more. The website shows it
as a last column of the board, behind a switch that is off at first.

```json
{"seat": 0, "rows": {"PAIR": 12, "SUM": -6, "ABAKA": null, ...},
 "columns": 0, "total": 6, "title": "±",
 "hint": "Your points in each row minus Bob's"}
```

| Field | Meaning |
|---|---|
| `seat` | Whose points are compared. |
| `rows` | Per row name, the difference; null while nobody has written in the row. |
| `columns`, `total` | The same for the column bonuses and for the totals. |
| `title`, `hint` | A heading for the column, and what it means, in the request's language. |

### `races`

The first player to complete a row, or column I or II, decides its bonus for
everyone. These are the races for those bonuses, drawn for this player, so a
phone can show them next to the dice instead of the player counting cells on
the board. Column III is each player's own, so it is no race.

```json
{"title": "Cells to the bonus",
 "heads": ["Ann", "You"],
 "columns": [{"column": 0, "label": "Column I", "left": [4, 6], "open": [true, false]}],
 "rows": [{"rows": ["SUM"], "seats": [0, 1], "by": 0,
           "text": "Ann caught up in Sum: one cell to the bonus for you and Ann."}],
 "note": "✕ — the bonus is crossed out, but whoever completes the column first still closes it for the others."}
```

| Field | Meaning |
|---|---|
| `columns` | Column I and II while their bonus is undecided, someone can still earn it, and someone has written in it. Per seat: `left`, its empty cells, and `open`, false once that player's bonus there is crossed out (they can still close it for the others by completing the column first). |
| `rows` | The row race the last move started, if it did (at most one entry), until the next move: its mover (`by`) has just come to one cell from the row's bonus, where another player already was, and one of them can still earn it. `seats` are everyone one cell from it, `text` says it. Since 2026-11-26 a race is told only on the move that starts it (before, every such row stayed listed); a client shows `text` as it comes. |
| `title`, `heads`, `label` | Words for a small table of `columns`: its corner, one heading per seat ("You" for this player), each column's name. |
| `note` | What a crossed-out column means, when `columns` shows one; otherwise null. |

All of it is plain text in the request's language, holding players' names:
show it as text. The whole field is null during the starting throw, after the
game, and when there is no race.

### `events`

Each event has `id` (it only grows), `at` (server time), `kind` and `seat` (who
sent it, or whose throw or move it was). It also carries its words, for the player
the state is drawn for and in the request's language. Show the words as plain
text; they hold players' names.
- **Reaction:** `"kind": "reaction"`, with `reaction` and `to` (a seat, or null for
  everyone). Show it for about 3.5 seconds.
  - Its words: `emoji` ("🍀"), `label` ("Lucky!") and `who` ("Ann", "You",
    "Ann → Bob", "Ann → you").
  - `to_you` is true when it was aimed at this player.
- **Effect:** `"kind": "effect"`, with `effect` and `what`.
  - `effect` is `grand_fireworks`, `fireworks`, `sparkles` or `tears`. Tears: Abaka
    or the royal full house thrown when the thrower's row for it (Abaka, Full house) is
    already full. A combination counts for an effect only while its row has a free
    cell. A client that does not know an effect shows its banner with sparkles.
  - `what` names what earned it: a row name (`ABAKA`, `KARE`, `FULL`,
    `LARGE_STRAIGHT`, `SMALL_STRAIGHT`), `ROYAL` for 1-1-1-2-2, or `BONUS`.
  - `first` (throws only) is true for a first roll.
  - A `BONUS` effect lists the bonuses earned: `rows` (`[row, points]`) and
    `columns` (`[column 0-2, points]`).
  - Its words, for a banner: `title` ("Abaka!", "Bonus!") and `text`
    ("Ann · first roll", "You · Sum row +52").
  - The website shows bigger fireworks for 6 seconds, fireworks and tears for
    4.5 and sparkles for 2.8. An effect that arrives while another plays waits for it to
    end.
- An effect from a throw should start when the dice land.
- Skip events from before the game was opened, and events more than 15 seconds
  old (use `now`).

## Errors

A refused request gets `{"error": code, "message": text}` (`ApiError.to_data()`).
The message is in the request's language and can be shown as it is. The code says
what the app should do:

| Code | What the app does |
|---|---|
| `bad_request` | A bug in the app: the request is malformed. The message is for developers, in English. |
| `protocol` | The app and the server speak different versions: ask the player to update the app. |
| `not_found` | No game or club with this code (any more), or a game's code without its key: go back to the start. |
| `not_seated` | The token holds no seat here; it was taken back on another device. Offer to rejoin. |
| `outdated` | The move was made on an old state: draw the new state. Nothing to show. |
| `too_fast` | Too many reactions or messages: show the message. |
| `retry` | The server is busy or was just updated: try again in a moment. |
| `refused` | The rules or the game refused it (not your turn, the game is full, a row that cannot be written): show the message. |

## Over the network

`streamlit run abaka_server.py` (Streamlit 1.67 or newer) serves the web app and
the API from one process, so web and app players share the games. The code is
`server/http.py`. Streamlit Community Cloud runs the web app alone, so the live
app does not offer the API until the server moves to a host of its own (Backlog
item 25, stage B).

| Route | What it does |
|---|---|
| `POST /api/v1` | One request: its JSON in the body, the answer as JSON. |
| `WS /api/v1/live` | Requests and answers as messages, and the state of a watched game pushed whenever it changes. |

### HTTP

- **Answer:** `200` with the answer.
- **Refusal:** an error status with `{"error", "message"}`:

  | Code | Status |
  |---|---|
  | `bad_request` | 400 (413 for a body larger than 16 KB) |
  | `protocol` | 400 |
  | `not_seated` | 403 |
  | `not_found` | 404 |
  | `outdated` | 409 |
  | `refused` | 422 |
  | `too_fast` | 429 |
  | `retry` | 503, or 500 when the server itself failed |
- **Limit on new games:** one client address may start at most 10 games and
  clubs (`create`, `create_local`, `create_club`) in 10 minutes, as one browser
  may on the web. Beyond that: `too_fast`.
- **Behind a proxy**, set `ABAKA_CLIENT_ADDRESS_HEADER` to the header that carries
  the client's address (for example `Fly-Client-IP`). Otherwise every client counts
  as the proxy.

### The live connection

Open `ws://<host>/api/v1/live` (`wss://` with TLS) and send requests as text
messages: any operation above, with an optional `id` that comes back with its
answer. Two more requests exist only here:

| Request | What it does |
|---|---|
| `{"op": "watch", "code", "token", "key", "lang", "since"}` | Answers like `state` (so it needs a seat's token or the game's key), and from then on pushes the game's state whenever it changes. A connection watches one game; `watch` another to switch. |
| `{"op": "unwatch"}` | Stops the pushes (the player left the game's screen); the connection stays for other requests. Answers `{"watching": null}`, also when nothing was watched, so it can serve as a check that the server is there. |

The server sends:

| Message | When |
|---|---|
| `{"type": "reply", "id", "response"}` | The answer to a request. |
| `{"type": "error", "id", "error", "message"}` | A refused request (`id` is null for a message that was not JSON). |
| `{"type": "state", "state"}` | The watched game changed. A push lists only events and chat messages the connection has not sent before. |

- The server looks for changes four times a second, so a push follows a change
  within about a quarter of a second.
- A move the app makes over the connection comes back as its reply and is not
  pushed again. The same holds for any reply on the connection that carries the
  watched game's state for the watching seat (a `state` request with the same token,
  for example): the server counts it as sent and pushes only later changes. So an app
  hands such replies to whatever shows the game, as `mobile/src/lib/api.ts` does.
- If the watched game is closed, the server sends one `not_found` error and stops
  watching.
- `seen` orders the states that arrive on one connection: an answer and a push can
  cross, so drop a state older than the one shown. The answer to `watch` is a fresh
  start, though. After the server restarts, a game's counts of picks and events begin
  again, and comparing with a state from before would hide the game's news until its
  next move.
- A connection can die without closing (a phone that changed networks). If nothing
  has arrived for a while, ask `seen` (or `unwatch`, when nothing is watched); if no
  answer comes, open a new connection and `watch` again.
- When the server's code is updated while it runs, it closes the connection with
  code 1012 (service restart). Reconnect and `watch` again; a deploy that restarts
  the server closes it too.
- If the server cannot go on serving a connection (a fault on its side), it closes
  it with code 1011 (internal error) instead of leaving it open without news.
  Reconnect and `watch` again, as after any drop.

## Versions

- Adding an operation, a field, a value of `can` or an event kind keeps protocol 1.
  Apps ignore what they do not know.
- Changing what an existing field means, or what an operation needs, makes
  protocol 2. The server then answers both versions while older apps are still in
  use.
- One exception, before any app was released: the game's key (Backlog item 31,
  2026-11-25) made `join`, `rejoin`, `resume`, and `state` and `seen` without a
  seat, need `key`, within protocol 1. No app was installed anywhere but on test
  devices, and a game's code alone had to stop opening it for every client. From the
  first release on, the rule above holds.
