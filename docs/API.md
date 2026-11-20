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
- **Transport (next step).** The HTTP and WebSocket server that carries these
  messages is the next stage of the plan. This document will then add its URLs. The
  messages stay as they are.

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

Moves also carry `version`: the `version` of the state the player chose the move
on. If the game has changed since, the move is refused with `outdated` and nothing
changes. This catches double taps and moves made on an old screen.

## Operations

### Starting and finding games

#### `info`
What an app needs once per language: `protocol`, `languages`, `players` (`min`,
`max`), `limits` (name, chat message and club name lengths), `reactions` (their
ids) and `rows`. `rows` lists the board's 15 rows in board order, each
`{"row": "SCHOOL_1", "name": "School 1", "hint": "...", "school": true}`, with the
name and hint in the request's language.

#### `create`
An online game. `name` (blank: "Player 1"), `players` (2 to 5, default 2), `club`
(optional: the game counts for that club's table).
Answer: `{"code", "token", "state"}`. The creator is seat 0. The game starts when
every seat is taken, or when the creator sends `start_now`.

#### `create_local`
A game on one device: `names` (2 to 5; blank names become "Player 2"...), `club`
(optional). One token plays every seat. Answer: `{"code", "token", "state"}`.
In a club game every name must be different, ignoring capitals and spaces;
otherwise the request is `refused`.

#### `join`
Take the next free seat of an online game: `code`, `name`. Names are made distinct
("Ann (2)"). Answer: `{"code", "token", "state"}`.

#### `rejoin`
Take a seat back: `code`, `seat`. The seat gets a new token, and the device that
held it before loses it (its requests are refused with `not_seated`). Anyone with
the code may do this today; protecting seats is an open decision (Backlog item 11).

#### `resume`
Carry on with a game played on one device from its `code`: answers with its token.
An online game is `refused`.

#### `state`
The game as the holder of `token` sees it: `code`, `token` (optional), `since`
(optional). Answer: `{"state": ...}`. Without a seat (no token, or one that was
taken over), the state shows only what an invite shows: the names, and in `can`
how to take a seat.

#### `seen`
`code` → `{"seen": "12.3.1795157785252"}`. The text changes whenever the state
does (a move, a pick, a reaction, a chat message). It is cheap, so an app can ask
every second and fetch `state` only when it changes.

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

## The state

```json
{
  "protocol": 1,
  "code": "Q47CH",
  "version": 12,
  "seen": "12.3.1795157785252",
  "now": 1795157790.125,
  "local": false,
  "capacity": 3,
  "club": null,
  "names": ["Ann", "Bob", "Cy"],
  "seated": true,
  "you": 1,
  "phase": "playing",
  "can": ["react", "say"],
  "game": { ... },
  "moves": null,
  "events": [ ... ],
  "chat": [ ... ],
  "table": {"games": 2, "wins": [1, 1, 0], "draws": 0},
  "club_result": null
}
```

| Field | Meaning |
|---|---|
| `version` | Send it back with a move. |
| `seen` | As the `seen` operation gives it. |
| `now` | The server's clock, in seconds. Use it to tell how old an event is, whatever the device's clock says. |
| `local` | A game on one device: `you` is null, and the token plays whoever's turn it is. |
| `capacity` | How many players the game is for. |
| `names` | The players in seat order. Seat 0 created the game. |
| `seated`, `you` | Whether the token holds a seat, and which one (null on one device). |
| `phase` | `waiting` (players joining), `starting_throw` (deciding who goes first), `playing`, `over`. |
| `can` | What this player may do now: the operations to offer. |
| `game` | The game (below), once it has started and the token holds a seat. |
| `moves` | The moves to offer, when it is this player's turn and the dice are on the table. |
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

### `events`

Each event has `id` (it only grows), `at` (server time), `kind` and `seat` (who
sent it, or whose throw or move it was).
- **Reaction:** `"kind": "reaction"`, with `reaction` and `to` (a seat, or null for
  everyone). Show it for about 3.5 seconds.
- **Effect:** `"kind": "effect"`, with `effect` and `what`.
  - `effect` is `grand_fireworks`, `fireworks` or `sparkles`.
  - `what` names what earned it: a row name (`ABAKA`, `KARE`, `FULL`,
    `LARGE_STRAIGHT`, `SMALL_STRAIGHT`), `ROYAL` for 1-1-1-2-2, or `BONUS`.
  - `first` (throws only) is true for a first roll.
  - A `BONUS` effect lists the bonuses earned: `rows` (`[row, points]`) and
    `columns` (`[column 0-2, points]`).
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
| `not_found` | No game or club with this code (any more): go back to the start. |
| `not_seated` | The token holds no seat here; it was taken back on another device. Offer to rejoin. |
| `outdated` | The move was made on an old state: draw the new state. Nothing to show. |
| `too_fast` | Too many reactions or messages: show the message. |
| `retry` | The server is busy or was just updated: try again in a moment. |
| `refused` | The rules or the game refused it (not your turn, the game is full, a row that cannot be written): show the message. |

## Versions

- Adding an operation, a field, a value of `can` or an event kind keeps protocol 1.
  Apps ignore what they do not know.
- Changing what an existing field means, or what an operation needs, makes
  protocol 2. The server then answers both versions while older apps are still in
  use.
