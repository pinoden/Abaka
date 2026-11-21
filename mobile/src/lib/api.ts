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
};

export type State = {
  protocol: number;
  code: string;
  version: number;
  seen: string;
  now: number;
  local: boolean;
  capacity: number;
  club: string | null;
  names: string[];
  seated: boolean;
  you: number | null;
  phase: Phase;
  can: string[];
  game: Game | null;
  moves: { score: Move[]; cross: Move[] } | null;
  events: unknown[];
  chat: unknown[];
  table: { games: number; wins: number[]; draws: number };
  club_result: unknown;
};

export type RowInfo = { row: string; name: string; hint: string; school: boolean };

export type Info = {
  protocol: number;
  languages: string[];
  players: { min: number; max: number };
  limits: { name: number; message: number; club_name: number };
  reactions: string[];
  rows: RowInfo[];
};

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

const REQUEST_TIMEOUT_MS = 15000;
const RETRY_FIRST_MS = 500;
const RETRY_MOST_MS = 5000;

type Pending = {
  resolve: (response: any) => void;
  reject: (error: ApiError) => void;
  timer: ReturnType<typeof setTimeout>;
  /** The seat the request was made for: its answer is the watched game's news if it matches. */
  code?: unknown;
  token?: unknown;
};

type Watch = {
  code: string;
  token?: string;
  onState: (state: State) => void;
  onError: (error: ApiError) => void;
};

/** `http://host:8501` -> `ws://host:8501/api/v1/live` (https -> wss). */
export function liveUrl(server: string): string {
  return server.replace(/\/+$/, '').replace(/^http/, 'ws') + '/api/v1/live';
}

/**
 * Whether state `a` is newer than state `b` of the same game. Answers and pushes travel
 * separately, so an older state can arrive after a newer one; `seen` orders them (the room
 * version, then the dice picks, then the latest event).
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
 * One connection to the server. It connects when it has something to send, reconnects
 * after a drop (watching the same game again), and fails a request with `offline` when
 * the server cannot be reached.
 */
export class Connection {
  private lang: Lang = 'en';
  private listeners = new Set<(connected: boolean) => void>();
  private url: string;
  private socket: WebSocket | null = null;
  private isOpen = false;
  private nextId = 1;
  private pending = new Map<number, Pending>();
  private queue: { id: number; op: string; text: string }[] = [];
  private watch: Watch | null = null;
  private retryMs = RETRY_FIRST_MS;
  private retryTimer: ReturnType<typeof setTimeout> | null = null;
  private closed = false;

  constructor(server: string) {
    this.url = liveUrl(server);
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

  /** Send one request; resolves with its answer, rejects with an ApiError. */
  request<T = any>(op: string, fields: Record<string, unknown> = {}): Promise<T> {
    const id = this.nextId++;
    const text = JSON.stringify({ ...fields, op, protocol: PROTOCOL, lang: this.lang, id });
    return new Promise<T>((resolve, reject) => {
      const timer = setTimeout(() => {
        // Never sent late: a move the player was told had failed must not happen later.
        this.queue = this.queue.filter((m) => m.id !== id);
        this.pending.delete(id);
        reject(new ApiError('offline', ''));
      }, REQUEST_TIMEOUT_MS);
      this.pending.set(id, { resolve, reject, timer, code: fields.code, token: fields.token });
      this.send({ id, op, text });
    });
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
   * Watch a game: `onState` gets its state now and whenever it changes; `onError` gets a
   * refusal of the watch (the game is gone, the seat was taken back).
   */
  startWatching(code: string, token: string | undefined, onState: (state: State) => void,
                onError: (error: ApiError) => void): void {
    this.watch = { code, token, onState, onError };
    this.sendWatch();
  }

  /** Stop watching (the connection closes, and opens again for the next request). */
  stopWatching(): void {
    this.watch = null;
    this.dropSocket();
  }

  /** Watch the same game again, in the current language. */
  rewatch(): void {
    if (this.watch) this.sendWatch();
  }

  /** Reconnect now if the connection is down (the app came back to the foreground). */
  wake(): void {
    if (!this.isOpen && (this.watch || this.queue.length)) {
      this.retryMs = RETRY_FIRST_MS;
      this.connect();
    }
  }

  /** Close for good. */
  close(): void {
    this.closed = true;
    this.watch = null;
    this.dropSocket();
  }

  private sendWatch(): void {
    const watch = this.watch;
    if (!watch) return;
    const fields: Record<string, unknown> = { code: watch.code };
    if (watch.token) fields.token = watch.token;
    this.request<{ state: State }>('watch', fields).then(
      () => { /* the state goes to the watcher like every answer about the watched game */ },
      (error: ApiError) => {
        // Offline: the watch is sent again when the connection opens.
        if (this.watch === watch && error.code !== 'offline') watch.onError(error);
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
    socket.onopen = () => {
      if (this.socket !== socket) return;
      this.isOpen = true;
      this.retryMs = RETRY_FIRST_MS;
      for (const listener of this.listeners) listener(true);
      const queued = this.queue;
      this.queue = [];
      // A watch queued before the drop is in `queued`; otherwise watch the game again.
      const watching = queued.some((m) => m.op === 'watch');
      for (const message of queued) socket.send(message.text);
      if (this.watch && !watching) this.sendWatch();
    };
    socket.onmessage = (event) => this.receive(String(event.data));
    socket.onclose = () => {
      if (this.socket !== socket) return;
      const wasOpen = this.isOpen;
      this.socket = null;
      this.isOpen = false;
      if (wasOpen) for (const listener of this.listeners) listener(false);
      // Requests already sent may or may not have been made: fail them, and let the
      // watch (sent again on reconnect) bring the game's true state.
      this.failPending();
      if (this.watch || this.queue.length) this.scheduleRetry();
    };
    socket.onerror = () => {
      // onclose follows.
    };
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
    this.retryMs = Math.min(this.retryMs * 2, RETRY_MOST_MS);
  }

  private failPending(): void {
    const queuedIds = new Set(this.queue.map((m) => m.id));
    for (const [id, pending] of this.pending) {
      if (queuedIds.has(id)) continue; // not sent yet: it goes out when the connection opens
      clearTimeout(pending.timer);
      this.pending.delete(id);
      pending.reject(new ApiError('offline', ''));
    }
  }

  private dropSocket(): void {
    const socket = this.socket;
    this.socket = null;
    this.isOpen = false;
    if (this.retryTimer) {
      clearTimeout(this.retryTimer);
      this.retryTimer = null;
    }
    this.failPending();
    if (socket) socket.close();
  }

  private receive(text: string): void {
    let message: any;
    try {
      message = JSON.parse(text);
    } catch {
      return;
    }
    if (message.type === 'state') {
      const watch = this.watch;
      if (watch && message.state?.code === watch.code) watch.onState(message.state);
      return;
    }
    const pending = message.id != null ? this.pending.get(message.id) : undefined;
    if (message.type === 'reply' && pending) {
      clearTimeout(pending.timer);
      this.pending.delete(message.id);
      // The server notes every state it sends for the watched seat and pushes only later
      // changes, so such an answer is the watcher's news too.
      const state = message.response?.state as State | undefined;
      const watch = this.watch;
      if (watch && state && state.code === watch.code && (pending.token ?? undefined) === watch.token) {
        watch.onState(state);
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
