/**
 * The game API (docs/API.md, protocol 1) over the server's live connection.
 *
 * Every request goes over one WebSocket (`/api/v1/live`): its answer comes back with the
 * request's id, and the watched game's state is pushed whenever it changes. The server is
 * the referee: the app shows the states it gets and offers the moves they list.
 *
 * No React Native imports here, so tests/api.test.ts runs this file in Node against a real
 * server. Keep it to syntax Node can run as it is (no enums, no parameter properties).
 */

export const PROTOCOL = 1;

export type Lang = 'en' | 'ru';
export type Cell = number | 'X' | null;
export type Die = { value: number; joker: boolean };
export type Phase = 'waiting' | 'starting_throw' | 'playing' | 'over';

export type Move = {
  row: string;
  slot: number;
  value: number | 'X';
  points: number | null;
  bonus: number;
  best: boolean;
  balance_change: number | null;
  bonus_lost: boolean;
  column_bonus_lost: boolean;
  label: string;
  action: string;
  preview: string;
};

export type PlayerBoard = {
  name: string;
  total: number;
  school_balance: number;
  balance_cell: Cell;
  rows: Record<string, Cell[]>;
  column_bonus: Cell[];
};

export type StartingThrow = { round: number; seat: number; dice: Die[]; total: number };

/** A club's member, as `club` lists them: best first. */
export type ClubMember = {
  name: string;
  rating: number;
  /** How the rating moved in the member's latest game. */
  change: number;
  games: number;
  wins: number;
  points: number;
  best: number;
  last_played: number;
};

/** A finished club game: when (server time, s), and each player's score and rating change. */
export type ClubGame = { id: string; at: number; players: { name: string; score: number; change: number }[] };

/** A club, as `club` and `create_club` answer (docs/API.md, Clubs). */
export type Club = {
  code: string;
  name: string;
  members: ClubMember[];
  /** Newest first. */
  games: ClubGame[];
  /** The members' names, the most recently played first: for name pickers. */
  names: string[];
};

/** After a club game: the club's name, and how each player's rating moved. */
export type ClubResult = {
  club: string;
  players: { name: string; score: number; change: number; rating: number }[];
};

/** A chat message. `text` is a player's: show it as plain text. */
export type ChatMessage = { id: number; seat: number; text: string; at: number };

/**
 * A reaction or an effect (docs/API.md, events), with its words for this player in the
 * request's language. The words hold players' names: show them as plain text.
 */
export type GameEvent = {
  id: number;
  /** When it happened, on the server's clock (compare with the state's `now`). */
  at: number;
  /** `reaction` or `effect`; a newer server may send kinds this app does not know. */
  kind: string;
  seat: number;
  // A reaction: its emoji and label, who sent it to whom, and whether it was aimed at this player.
  reaction?: string;
  to?: number | null;
  emoji?: string;
  label?: string;
  who?: string;
  to_you?: boolean;
  // An effect: `grand_fireworks`, `fireworks` or `sparkles`, what earned it, and its banner.
  effect?: string;
  what?: string;
  first?: boolean;
  title?: string;
  text?: string;
};

export type Game = {
  number: number;
  current: number;
  dice: Die[];
  rolls_left: number;
  first_roll: boolean;
  picked: number[];
  rerolled: number[];
  last_move: { seat: number; row: string; slot: number } | null;
  starting_throw: {
    round: number;
    throwing: number[];
    throws: StartingThrow[];
    first_player: number | null;
  };
  players: PlayerBoard[];
  winners: number[];
  /** Every player's total after each move, for the chart of scores by move (docs/API.md). */
  history?: { move: number; totals: number[] }[];
};

/**
 * The difference row by row (docs/API.md, `differences`): `seat`'s points in each row minus the
 * opponent's (the best of the others'), null while nobody wrote in the row. Words included.
 */
export type Differences = {
  seat: number;
  rows: Record<string, number | null>;
  columns: number;
  total: number;
  title: string;
  hint: string;
};

export type State = {
  protocol: number;
  code: string;
  /** The game's secret key (a state is only sent to someone in the game): the full code is `code-key`. */
  key: string;
  version: number;
  seen: string;
  now: number;
  local: boolean;
  capacity: number;
  club: string | null;
  names: string[];
  /** The seats the computer plays (Backlog item 33): the server makes their moves. Older servers leave it out. */
  computers?: number[];
  /** How well the computer plays in this game (Backlog item 34): an id of `info.computer_levels`. Null without computers. */
  computer_level?: string | null;
  /**
   * The computer's final dice, still on the table until the next player rolls (Backlog item 35),
   * with what it wrote from them, in the player's language. Null otherwise.
   */
  last_throw?: { seat: number; dice: Die[]; text: string } | null;
  seated: boolean;
  you: number | null;
  phase: Phase;
  can: string[];
  game: Game | null;
  moves: { score: Move[]; cross: Move[] } | null;
  /** The races for the shared bonuses, drawn for this player; null when there is none. Older servers leave it out. */
  races?: Races | null;
  /** The difference row by row, for this player (on one device: whose turn it is). Older servers leave it out. */
  differences?: Differences | null;
  /**
   * In an answer: the events and messages newer than the request's `since`. In a state
   * handed to a watcher (`Connection.startWatching`): `events` are the ones not handed
   * over before, and `chat` is the game's whole chat.
   */
  events: GameEvent[];
  chat: ChatMessage[];
  table: { games: number; wins: number[]; draws: number };
  /** After a club game, once the club has it: how the ratings moved. */
  club_result: ClubResult | null;
  /** Devices asking to be let in to a seat, which this player may answer (`answer`). Older servers leave it out. */
  asks?: SeatRequest[];
  /** Without a seat: the seat this device holds and may come back to (`rejoin`), or null. */
  held?: number | null;
};

/**
 * The races for the shared bonuses (docs/API.md, `races`): cells left in column I and II per
 * seat, and the row race the last move started, if it did (`by`: its mover). Words included.
 */
export type Races = {
  title: string;
  heads: string[];
  columns: { column: number; label: string; left: number[]; open: boolean[] }[];
  rows: { rows: string[]; seats: number[]; by?: number; text: string }[];
  note: string | null;
};

export type RowInfo = { row: string; name: string; hint: string; school: boolean };

export type Info = {
  protocol: number;
  languages: string[];
  players: { min: number; max: number };
  limits: { name: number; message: number; club_name: number };
  reactions: string[];
  /** The reaction buttons in their order, with labels in the request's language. */
  reaction_list?: { id: string; emoji: string; label: string }[];
  /** How well the computer can play, weakest first (Backlog item 34), and the level to offer first. */
  computer_levels?: { id: string; label: string }[];
  computer_level_suggested?: string;
  rows: RowInfo[];
};

/** A block of the rules (`rules`): a heading, a paragraph (bold parts marked **so**), or the table. */
export type RulesBlock = {
  heading?: string;
  text?: string;
  table?: { head: string[]; rows: string[][] };
};

export type Rules = { title: string; blocks: RulesBlock[] };

/**
 * A device asking to be let in to a seat (Backlog item 37): a seat belongs to the device that
 * took it. `yours`: it is this player's own seat. The words are the server's, in the player's language.
 */
export type SeatRequest = { seat: number; name: string; yours: boolean; title: string; text: string };

/** What `asked` answers: what became of this device's request to be let in to a seat. */
export type Asked = { status: 'waiting' | 'refused' | 'gone' } | ({ status: 'in' } & Seat);

/** The operations that say which device is asking: the server keeps a seat for the device that took it. */
const DEVICE_OPS = new Set(['create', 'join', 'rejoin', 'ask', 'asked']);

/** A seat in a game: what create, create_local, join, rejoin and resume answer. */
export type Seat = { code: string; token: string; state: State };

/**
 * A refused request. `code` is the server's (docs/API.md, Errors), or `offline` when the
 * server could not be reached; `message` is the server's text, in the request's language.
 */
export class ApiError extends Error {
  code: string;

  constructor(code: string, message: string) {
    super(message || code);
    this.code = code;
  }
}

/**
 * Of the games a device remembers (`codes`, newest first), which can be continued: `open`
 * holds at most `limit` that still exist and are not over, as the server shows them now;
 * `over` and `gone` list the finished ones and the ones that no longer exist, among the
 * games looked at. Like the web's home page, it looks no further than it must: each look
 * can make the server read a game from its storage. Null when the server cannot be asked
 * (offline): show what the device remembers.
 */
export async function gamesToContinue(connection: Connection, games: { code: string; key?: string }[],
                                      limit: number): Promise<{ open: State[]; over: string[]; gone: string[] } | null> {
  const open: State[] = [];
  const over: string[] = [];
  const gone: string[] = [];
  for (const { code, key } of games) {
    if (open.length === limit) break;
    try {
      // With the game's key: the code alone opens nothing, and the invite's view says whether it is over.
      const { state } = await connection.request<{ state: State }>('state', { code, ...(key ? { key } : {}) });
      if (state.phase === 'over') over.push(code);
      else open.push(state);
    } catch (e) {
      if (!(e instanceof ApiError) || e.code !== 'not_found') return null;
      gone.push(code);
    }
  }
  return { open, over, gone };
}

/**
 * How long the connection waits. Every value can be changed for a test (the second
 * argument of `new Connection`).
 */
export type Timings = {
  /** A request that got no answer for this long fails as `offline`. */
  requestMs: number;
  /** A connection that has not opened after this long is given up, and tried again. */
  connectMs: number;
  /** While a game is watched and nothing has arrived for this long, ask the server if it is there. */
  heartbeatMs: number;
  /** ...and how long its answer may take before the connection counts as dead. */
  heartbeatAnswerMs: number;
  /** The wait before reconnecting: first this, then doubling up to `retryMostMs`. */
  retryFirstMs: number;
  retryMostMs: number;
};

export const TIMINGS: Timings = {
  requestMs: 15000,
  connectMs: 10000,
  heartbeatMs: 20000,
  heartbeatAnswerMs: 8000,
  retryFirstMs: 500,
  retryMostMs: 5000,
};

type Watch = {
  code: string;
  token?: string;
  /** The game's key, so that the game can be watched without a seat (the invite). */
  key?: string;
  onState: (state: State) => void;
  onError: (error: ApiError) => void;
  /** The latest state handed to `onState`. */
  shown: State | null;
  /** Events and chat messages up to this id have been handed over. */
  since: number;
  /** The game's chat so far (the server sends each message once). */
  chat: ChatMessage[];
};

const CHAT_KEPT = 50; // as the server keeps (abaka/rooms.py)

type Pending = {
  resolve: (response: any) => void;
  reject: (error: ApiError) => void;
  timer: ReturnType<typeof setTimeout>;
  /** The seat the request was made for: its answer is the watched game's news if it matches. */
  code?: unknown;
  token?: unknown;
  /** For a `watch` request: the watch it was sent for. */
  watch?: Watch;
};

/** `http://host:8501` -> `ws://host:8501/api/v1/live` (https -> wss). */
export function liveUrl(server: string): string {
  return server.replace(/\/+$/, '').replace(/^http/, 'ws') + '/api/v1/live';
}

/**
 * Whether state `a` is newer than state `b` of the same game, on one connection. Answers
 * and pushes travel separately, so an older state can arrive after a newer one; `seen`
 * orders them (the room version, then the dice picks, then the latest event).
 */
export function isNewer(a: State, b: State | null): boolean {
  if (b === null || a.code !== b.code) return true;
  const x = a.seen.split('.').map(Number);
  const y = b.seen.split('.').map(Number);
  for (let i = 0; i < Math.max(x.length, y.length); i++) {
    if ((x[i] ?? 0) !== (y[i] ?? 0)) return (x[i] ?? 0) > (y[i] ?? 0);
  }
  return false;
}

/**
 * One connection to the server, for every screen. It connects when it has something to
 * send, stays open from then on, and fails a request with `offline` when the server cannot
 * be reached.
 *
 * It looks after itself:
 * - while a game is watched, it reconnects after a drop and watches the game again;
 * - a connection can die without closing (a phone that changed networks, a server that
 *   went away mid-sentence). So when nothing has arrived for a while it asks the server
 *   whether it is there, and a request that is never answered counts as a dead
 *   connection too: it is closed, and replaced if a game is watched;
 * - if the server's answer shows that the screen fell behind, it asks for the game again.
 */
export class Connection {
  private lang: Lang = 'en';
  private listeners = new Set<(connected: boolean) => void>();
  private url: string;
  private timings: Timings;
  private socket: WebSocket | null = null;
  private isOpen = false;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private queue: { id: number; op: string; text: string }[] = [];
  private watch: Watch | null = null;
  private retryMs: number;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private openTimer: ReturnType<typeof setTimeout> | null = null;
  private heartbeat: ReturnType<typeof setInterval> | null = null;
  private heardAt = 0;
  private asking = false;
  private closed = false;
  private deviceSource: (() => Promise<string>) | null = null;
  private device: string | null = null;

  constructor(server: string, timings: Partial<Timings> = {}) {
    this.url = liveUrl(server);
    this.timings = { ...TIMINGS, ...timings };
    this.retryMs = this.timings.retryFirstMs;
  }

  /** The language of the texts in the answers (sent with every request). */
  setLanguage(lang: Lang): void {
    this.lang = lang;
  }

  language(): Lang {
    return this.lang;
  }

  /** `listener` gets true when the connection opens, false when it drops. Returns a remover. */
  listen(listener: (connected: boolean) => void): () => void {
    this.listeners.add(listener);
    return () => { this.listeners.delete(listener); };
  }

  /**
   * Where this device's secret comes from (the app: its storage, or the server the first
   * time). It goes out as `device` with the requests that take a seat or ask for one, so the
   * seat is this device's to come back to, and nobody else's (docs/API.md, `rejoin`).
   */
  useDevice(source: () => Promise<string>): void {
    this.deviceSource = source;
    this.device = null;
  }

  /** The device's secret, read once. Null while it cannot be had (offline on the first start). */
  async loadDevice(): Promise<string | null> {
    if (this.device || !this.deviceSource) return this.device;
    try {
      this.device = await this.deviceSource();
    } catch {
      return null; // asked for again with the next request that needs it
    }
    // An invite watched before the secret was read: ask again, to learn which seat is this device's.
    if (this.watch && !this.watch.token) this.sendWatch();
    return this.device;
  }

  /** Send one request; resolves with its answer, rejects with an ApiError. */
  async request<T = any>(op: string, fields: Record<string, unknown> = {}): Promise<T> {
    if (DEVICE_OPS.has(op) && fields.device === undefined) {
      const device = await this.loadDevice();
      if (device) fields = { ...fields, device };
    }
    return this.ask<T>(op, fields, this.timings.requestMs);
  }

  /**
   * A move or another request that answers with the game's state. Like every answer that
   * carries the watched game's state for the watching seat, it also goes to the watcher:
   * the server counts it as sent and does not push it again.
   */
  async act(op: string, fields: Record<string, unknown>): Promise<State> {
    const response = await this.request<{ state: State }>(op, fields);
    return response.state;
  }

  /**
   * Watch a game: `onState` gets its state now and whenever it changes, never an older
   * one after a newer one; `onError` gets a refusal of the watch (the game is gone).
   *
   * Returns what stops this watch, and only this one: a screen that closes after the next
   * one has opened (while one slides over the other) must not stop the next screen's game.
   */
  startWatching(code: string, token: string | undefined, onState: (state: State) => void,
                onError: (error: ApiError) => void, key?: string): () => void {
    const watch: Watch = { code, token, key, onState, onError, shown: null, since: 0, chat: [] };
    this.watch = watch;
    this.sendWatch();
    return () => {
      if (this.watch === watch) this.stopWatching();
    };
  }

  /**
   * Stop watching, whatever is watched: the player left the game's screen. The connection
   * stays for the next screen's requests, and the server is told to send this game no more.
   */
  stopWatching(): void {
    if (!this.watch) return;
    this.watch = null;
    // A watch that has not gone out yet (the connection is still opening) never needs to.
    for (const message of this.queue.filter((m) => m.op === 'watch')) this.fail(message.id);
    this.queue = this.queue.filter((m) => m.op !== 'watch');
    if (this.isOpen) {
      this.ask('unwatch', {}, this.timings.requestMs).catch(() => {});
    } else if (!this.queue.length) {
      this.dropSocket(); // it was opening, or waiting to try again, for the watch alone
    }
  }

  /** Watch the same game again, in the current language. */
  rewatch(): void {
    if (this.watch) this.sendWatch();
  }

  /**
   * The app came back to the foreground: reconnect now if the connection is down, and if
   * it looks open, make sure it is (it may have died while the app slept).
   */
  wake(): void {
    if (this.isOpen) {
      this.askIfThere();
    } else if (this.watch || this.queue.length) {
      this.retryMs = this.timings.retryFirstMs;
      this.connect();
    }
  }

  /** Close for good. */
  close(): void {
    this.closed = true;
    this.watch = null;
    this.dropSocket();
  }

  private ask<T>(op: string, fields: Record<string, unknown>, timeoutMs: number, watch?: Watch): Promise<T> {
    const id = this.nextId++;
    // A request for the watched seat asks only for the events and messages the screen has
    // not been given yet. (The watch itself asks for everything: a fresh start.)
    const watched = this.watch;
    if (!watch && watched && fields.code === watched.code && fields.token === watched.token
        && fields.since === undefined) {
      fields = { ...fields, since: watched.since };
    }
    // A request may name its own language: a screen's request can go out before the app has
    // switched the connection to a new one (React runs a screen's effects before the app's).
    const text = JSON.stringify({ lang: this.lang, ...fields, op, protocol: PROTOCOL, id });
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        // Never sent late: a move the player was told had failed must not happen later.
        const unsent = this.queue.some((m) => m.id === id);
        this.queue = this.queue.filter((m) => m.id !== id);
        this.pending.delete(id);
        reject(new ApiError('offline', ''));
        // Sent and never answered: the connection is dead, even if it looks open.
        if (!unsent) this.replaceSocket();
      }, timeoutMs);
      this.pending.set(id, { resolve, reject, timer, code: fields.code, token: fields.token, watch });
      this.send({ id, op, text });
    });
  }

  private sendWatch(): void {
    const watch = this.watch;
    if (!watch) return;
    const fields: Record<string, unknown> = { code: watch.code };
    if (watch.token) fields.token = watch.token;
    if (watch.key) fields.key = watch.key;
    if (!watch.token && this.device) fields.device = this.device; // the answer names this device's seat (`held`)
    this.ask<{ state: State }>('watch', fields, this.timings.requestMs, watch).then(
      () => { /* the state went to the watcher (receive) */ },
      (error: ApiError) => {
        // Offline: the watch is sent again when the connection opens.
        if (this.watch === watch && error.code !== 'offline') watch.onError(error);
      },
    );
  }

  /**
   * Ask the server whether it is there and, if a game is watched, whether the screen shows
   * it as it is now. With no game to watch, `unwatch` is the question: it changes nothing.
   */
  private askIfThere(): void {
    if (!this.isOpen || this.asking) return;
    const watch = this.watch;
    this.asking = true;
    const question = watch
      ? this.ask<{ seen?: string }>('seen', { code: watch.code, token: watch.token, key: watch.key },
                                    this.timings.heartbeatAnswerMs)
      : this.ask<{ seen?: string }>('unwatch', {}, this.timings.heartbeatAnswerMs);
    question.then(
      (answer) => {
        this.asking = false;
        // The screen fell behind (a push that never arrived): ask for the game again.
        if (watch && this.watch === watch && watch.shown && answer.seen !== watch.shown.seen) this.sendWatch();
      },
      () => {
        // A refusal is an answer too. No answer at all: the request's timeout has closed
        // the connection. A game that is gone is reported by the server itself.
        this.asking = false;
      },
    );
  }

  private send(message: { id: number; op: string; text: string }): void {
    if (this.isOpen && this.socket) {
      this.socket.send(message.text);
      return;
    }
    this.queue.push(message);
    this.connect();
  }

  private connect(): void {
    if (this.closed || this.socket) return;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    let socket: WebSocket;
    try {
      socket = new WebSocket(this.url);
    } catch {
      this.scheduleRetry();
      return;
    }
    this.socket = socket;
    // A connection that never opens (a network that swallows everything) is given up.
    this.openTimer = setTimeout(() => {
      this.openTimer = null;
      if (this.socket !== socket || this.isOpen) return;
      this.dropSocket();
      if (this.watch || this.queue.length) this.scheduleRetry();
    }, this.timings.connectMs);
    socket.onopen = () => {
      if (this.socket !== socket) return;
      this.clearOpenTimer();
      this.retryMs = this.timings.retryFirstMs;
      this.heardAt = Date.now();
      this.setOpen(true);
      const queued = this.queue;
      this.queue = [];
      // A watch queued before the drop is in `queued`; otherwise watch the game again.
      const watching = queued.some((m) => m.op === 'watch');
      for (const message of queued) socket.send(message.text);
      if (this.watch && !watching) this.sendWatch();
    };
    socket.onmessage = (event) => {
      if (this.socket === socket) this.receive(String(event.data));
    };
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.clearOpenTimer();
      this.socket = null;
      this.setOpen(false);
      // Requests already sent may or may not have been made: fail them, and let the
      // watch (sent again on reconnect) bring the game's true state.
      this.failPending();
      if (this.watch || this.queue.length) this.scheduleRetry();
    };
    socket.onerror = () => {
      // onclose follows.
    };
  }

  private setOpen(open: boolean): void {
    if (this.isOpen === open) return;
    this.isOpen = open;
    if (this.heartbeat) clearInterval(this.heartbeat);
    this.heartbeat = !open ? null : setInterval(() => {
      if (Date.now() - this.heardAt >= this.timings.heartbeatMs) this.askIfThere();
    }, this.timings.heartbeatMs);
    for (const listener of this.listeners) listener(open);
  }

  private clearOpenTimer(): void {
    if (this.openTimer) clearTimeout(this.openTimer);
    this.openTimer = null;
  }

  private scheduleRetry(): void {
    if (this.closed || this.retryTimer) return;
    if (!this.watch) {
      // Nothing watched: fail queued requests instead of trying forever.
      this.queue = [];
      this.failPending();
      return;
    }
    this.retryTimer = setTimeout(() => {
      this.retryTimer = null;
      this.connect();
    }, this.retryMs);
    this.retryMs = Math.min(this.retryMs * 2, this.timings.retryMostMs);
  }

  /** Requests already sent get no answer any more: they fail as `offline`. */
  private failPending(): void {
    const queuedIds = new Set(this.queue.map((m) => m.id));
    for (const id of [...this.pending.keys()]) {
      if (!queuedIds.has(id)) this.fail(id); // one not sent yet goes out when the connection opens
    }
  }

  private fail(id: number): void {
    const pending = this.pending.get(id);
    if (!pending) return;
    clearTimeout(pending.timer);
    this.pending.delete(id);
    pending.reject(new ApiError('offline', ''));
  }

  /** Close the connection, if any. Requests already sent fail as `offline`. */
  private dropSocket(): void {
    const socket = this.socket;
    this.socket = null;
    this.clearOpenTimer();
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.setOpen(false);
    this.failPending();
    if (socket) socket.close();
  }

  /** A connection that stopped answering: close it, and open a new one if there is anything to send or watch. */
  private replaceSocket(): void {
    this.dropSocket();
    if (this.watch || this.queue.length) this.connect();
  }

  /**
   * Hand a state of the watched game to the screen, unless it is older than the one shown:
   * answers and pushes can cross. `fresh` is the answer to the watch itself, which always
   * counts: after a server restart the game's counters start again, and comparing with
   * what was shown before would hide the game's news until its next move.
   *
   * The screen gets each event once, and the game's whole chat every time: the server
   * sends a message once, so the messages are gathered here. The chat lasts as long as
   * the game is played (the server deletes it with the move that ends the game).
   */
  private deliver(state: State, fresh: boolean): void {
    const watch = this.watch;
    if (!watch || state.code !== watch.code) return;
    if (!fresh && watch.shown && isNewer(watch.shown, state)) return;
    const events = (state.events ?? []).filter((event) => event.id > watch.since);
    const said = state.chat ?? [];
    const played = state.phase === 'playing' || state.phase === 'starting_throw';
    watch.chat = !played ? []
      : fresh ? said
        : [...watch.chat, ...said.filter((message) => message.id > watch.since)].slice(-CHAT_KEPT);
    watch.since = Math.max(watch.since, ...(state.events ?? []).map((e) => e.id), ...said.map((m) => m.id));
    watch.shown = { ...state, events, chat: watch.chat };
    watch.onState(watch.shown);
  }

  private receive(text: string): void {
    let message: any;
    try {
      message = JSON.parse(text);
    } catch {
      return;
    }
    this.heardAt = Date.now();
    if (message.type === 'state') {
      if (message.state) this.deliver(message.state, false);
      return;
    }
    const pending = message.id != null ? this.pending.get(message.id) : undefined;
    if (message.type === 'reply' && pending) {
      clearTimeout(pending.timer);
      this.pending.delete(message.id);
      const state = message.response?.state as State | undefined;
      const watch = this.watch;
      if (pending.watch) {
        if (state && pending.watch === watch) this.deliver(state, true);
      } else if (watch && state && (pending.token ?? undefined) === watch.token) {
        // The server notes every state it sends for the watched seat and pushes only later
        // changes, so such an answer is the watcher's news too.
        this.deliver(state, false);
      }
      pending.resolve(message.response);
    } else if (message.type === 'error') {
      const error = new ApiError(message.error, message.message);
      if (pending) {
        clearTimeout(pending.timer);
        this.pending.delete(message.id);
        pending.reject(error);
      } else if (this.watch && (error.code === 'not_found' || error.code === 'not_seated')) {
        this.watch.onError(error); // a push: the watched game is gone, or the seat was taken
      }
    }
  }
}
