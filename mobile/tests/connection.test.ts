/// <reference types="node" />
/**
 * The app's connection (src/lib/api.ts) against a scripted server: what a real one does
 * only on a bad day. A server that restarts, states that arrive in the wrong order, a
 * connection that dies without closing, a request that is never answered.
 *
 *   node --test tests/
 *
 * The scripted server is a WebSocket server in this process (the `ws` package); each test
 * says what it answers. No game server is needed.
 */

import assert from 'node:assert/strict';
import net from 'node:net';
import { after, describe, test } from 'node:test';

import Ws from 'ws';

import {
  ApiError, type ChatMessage, Connection, type GameEvent, type State, type Timings,
} from '../src/lib/api.ts';

type Message = { id?: number; op: string; [field: string]: unknown };

const closing: (() => void)[] = [];
after(() => closing.forEach((close) => close()));

/** A game server that answers what the test tells it to. */
class Scripted {
  /** Every connection made so far: its socket, and the messages it has received. */
  connections: { socket: Ws; got: Message[] }[] = [];
  /** What to do with a message (`connection` counts from 0). Nothing, unless a test says so. */
  answer: (message: Message, socket: Ws, connection: number) => void = () => {};
  private server: Ws.Server;

  private constructor(server: Ws.Server) {
    this.server = server;
    server.on('connection', (socket) => {
      const n = this.connections.length;
      const got: Message[] = [];
      this.connections.push({ socket, got });
      socket.on('message', (data) => {
        const message = JSON.parse(String(data)) as Message;
        got.push(message);
        this.answer(message, socket, n);
      });
    });
  }

  static async start(): Promise<Scripted> {
    const server = new Ws.Server({ port: 0, host: '127.0.0.1' });
    await new Promise((resolve) => server.once('listening', resolve));
    const scripted = new Scripted(server);
    closing.push(() => {
      scripted.connections.forEach((c) => c.socket.terminate());
      server.close();
    });
    return scripted;
  }

  get url(): string {
    return `http://127.0.0.1:${(this.server.address() as net.AddressInfo).port}`;
  }

  /** The messages of one kind that a connection has received. */
  got(connection: number, op: string): Message[] {
    return this.connections[connection].got.filter((m) => m.op === op);
  }
}

const CODE = 'ABCDE';
const TOKEN = 'a-seat-token';

/** A state of the watched game with this `seen` (its version is the first number). */
function state(seen: string, more: Partial<State> = {}): State {
  return { code: CODE, seen, version: Number(seen.split('.')[0]), names: ['Ann', 'Bob'], ...more } as State;
}

const event = (id: number): GameEvent => ({ id, at: 1, kind: 'reaction', seat: 1 });
const said = (id: number, text: string): ChatMessage => ({ id, seat: 1, text, at: 1 });

function reply(socket: Ws, message: Message, response: unknown): void {
  socket.send(JSON.stringify({ type: 'reply', id: message.id, response }));
}

function push(socket: Ws, pushed: State): void {
  socket.send(JSON.stringify({ type: 'state', state: pushed }));
}

function connect(server: Scripted, timings: Partial<Timings> = {}): Connection {
  const connection = new Connection(server.url, { retryFirstMs: 20, ...timings });
  closing.push(() => connection.close());
  return connection;
}

/** Watch the game; returns the `seen` of every state the screen was handed, in order. */
function watch(connection: Connection): string[] {
  const shown: string[] = [];
  connection.startWatching(CODE, TOKEN, (s) => shown.push(s.seen), (e) => assert.fail(e.message));
  return shown;
}

async function until(check: () => boolean, what: string, ms = 3000): Promise<void> {
  const end = Date.now() + ms;
  while (!check()) {
    if (Date.now() > end) throw new Error(`timed out waiting for ${what}`);
    await new Promise((resolve) => setTimeout(resolve, 5));
  }
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

describe('the connection against a scripted server', () => {
  test('after a server restart the game is shown as the server has it now', async () => {
    const server = await Scripted.start();
    let now = '4.3.0'; // version 4, three changes of the picked dice
    server.answer = (m, socket) => { if (m.op === 'watch') reply(socket, m, { state: state(now) }); };
    const shown = watch(connect(server));
    await until(() => shown.length === 1, 'the game');

    // The server restarts: the game comes back from its storage, its counters of picks
    // and events begin again. What the screen showed before says nothing any more.
    now = '4.0.0';
    server.connections[0].socket.terminate();
    await until(() => shown.length === 2, 'the game after the restart');
    const socket = server.connections[1].socket;
    push(socket, state('4.1.0')); // a pick or a chat message: no new version
    await until(() => shown.length === 3, 'a change that is not a move');
    push(socket, state('4.0.0')); // an older state arriving late
    push(socket, state('4.2.0'));
    await until(() => shown.length === 4, 'the next change');
    assert.deepEqual(shown, ['4.3.0', '4.0.0', '4.1.0', '4.2.0']);
  });

  test('an older state never replaces a newer one', async () => {
    const server = await Scripted.start();
    server.answer = (m, socket) => {
      if (m.op === 'watch') reply(socket, m, { state: state('5.0.0') });
      if (m.op === 'roll') {
        reply(socket, m, { state: state('6.0.0') });
        push(socket, state('5.1.0')); // worked out before the roll, sent after its answer
        push(socket, state('6.0.0', { names: ['Аня', 'Боб'] })); // the same state in another language
      }
      // A state for another seat, and one of another game: not this screen's.
      if (m.op === 'state') reply(socket, m, { state: state('9.0.0', m.token ? {} : { code: 'OTHER' }) });
    };
    const connection = connect(server);
    const shown: State[] = [];
    connection.startWatching(CODE, TOKEN, (s) => shown.push(s), (e) => assert.fail(e.message));
    await until(() => shown.length === 1, 'the game');
    const rolled = await connection.act('roll', { code: CODE, token: TOKEN, version: 5 });
    assert.equal(rolled.seen, '6.0.0');
    await until(() => shown.length === 3, 'the roll, and the same state again');
    await connection.request('state', { code: CODE, token: 'another-seat' });
    await connection.request('state', { code: 'OTHER' });
    assert.deepEqual(shown.map((s) => s.seen), ['5.0.0', '6.0.0', '6.0.0']);
    assert.deepEqual(shown[2].names, ['Аня', 'Боб']);
  });

  test('a connection that dies without closing is replaced', async () => {
    const server = await Scripted.start();
    const dead = new Set<number>();
    server.answer = (m, socket, n) => {
      if (dead.has(n)) return; // the server went away mid-sentence
      if (m.op === 'watch') reply(socket, m, { state: state(`3.${n}.0`) });
      if (m.op === 'seen') reply(socket, m, { seen: `3.${n}.0` });
    };
    const connection = connect(server, { heartbeatMs: 50, heartbeatAnswerMs: 80 });
    const ups: boolean[] = [];
    connection.listen((up) => ups.push(up));
    const shown = watch(connection);
    await until(() => server.connections.length === 1 && server.got(0, 'seen').length >= 2, 'two heartbeats');
    assert.deepEqual([server.connections.length, shown.length], [1, 1]); // answered: nothing else happens

    dead.add(0);
    await until(() => shown.length === 2, 'the game on a new connection');
    assert.equal(server.connections.length, 2);
    assert.equal(server.connections[1].got[0].op, 'watch');
    assert.deepEqual(ups, [true, false, true]);
  });

  test('back in the foreground it checks the connection at once', async () => {
    const server = await Scripted.start();
    const dead = new Set<number>();
    server.answer = (m, socket, n) => {
      if (m.op === 'watch' && !dead.has(n)) reply(socket, m, { state: state('3.0.0') });
    };
    const connection = connect(server, { heartbeatAnswerMs: 80 }); // the heartbeat itself is 20 s away
    const shown = watch(connection);
    await until(() => shown.length === 1, 'the game');
    dead.add(0); // the connection died while the app slept
    connection.wake();
    await until(() => shown.length === 2, 'the game on a new connection');
    assert.equal(server.got(0, 'seen').length, 1);
  });

  test('a screen that fell behind asks for the game again', async () => {
    const server = await Scripted.start();
    let now = '6.0.0';
    server.answer = (m, socket) => {
      if (m.op === 'watch') reply(socket, m, { state: state(now) });
      if (m.op === 'seen') reply(socket, m, { seen: now });
    };
    const shown = watch(connect(server, { heartbeatMs: 50 }));
    await until(() => shown.length === 1, 'the game');
    now = '7.0.0'; // a move whose push never arrived
    await until(() => shown.length === 2, 'the game asked for again');
    assert.deepEqual(shown, ['6.0.0', '7.0.0']);
    assert.equal(server.connections.length, 1); // the connection itself was fine
  });

  test('a request that is never answered fails as offline, and is not made later', async () => {
    const server = await Scripted.start();
    server.answer = (m, socket, n) => {
      if (m.op === 'watch') reply(socket, m, { state: state(`2.${n}.0`) });
    };
    const connection = connect(server, { requestMs: 150 });
    const shown = watch(connection);
    await until(() => shown.length === 1, 'the game');
    const failed = await connection.act('roll', { code: CODE, token: TOKEN, version: 2 }).catch((e) => e);
    assert.ok(failed instanceof ApiError);
    assert.equal(failed.code, 'offline');
    // No answer means the connection is dead: a new one brings the game's true state.
    await until(() => shown.length === 2, 'the game on a new connection');
    assert.equal(server.got(0, 'roll').length, 1);
    assert.equal(server.got(1, 'roll').length, 0);
  });

  test('the screen gets each event once, and the game’s whole chat every time', async () => {
    const server = await Scripted.start();
    const playing: Partial<State> = { phase: 'playing' };
    server.answer = (m, socket) => {
      if (m.op === 'watch') {
        reply(socket, m, { state: state('5.0.10', { ...playing, events: [event(9), event(10)], chat: [said(8, 'one')] }) });
      }
      // A move's answer holds what is newer than the request's `since`; a server may repeat an event.
      if (m.op === 'roll') {
        reply(socket, m, { state: state('6.0.12', { ...playing, events: [event(10), event(11)], chat: [said(12, 'two')] }) });
      }
    };
    const connection = connect(server);
    const shown: State[] = [];
    connection.startWatching(CODE, TOKEN, (s) => shown.push(s), (e) => assert.fail(e.message));
    await until(() => shown.length === 1, 'the game');
    assert.deepEqual([shown[0].events.map((e) => e.id), shown[0].chat.map((m) => m.text)], [[9, 10], ['one']]);
    assert.equal(server.got(0, 'watch')[0].since, undefined); // the watch asks for everything

    await connection.act('roll', { code: CODE, token: TOKEN, version: 5 });
    assert.equal(server.got(0, 'roll')[0].since, 10); // a move asks only for what the screen lacks
    await until(() => shown.length === 2, 'the roll');
    assert.deepEqual([shown[1].events.map((e) => e.id), shown[1].chat.map((m) => m.text)], [[11], ['one', 'two']]);

    const socket = server.connections[0].socket;
    push(socket, state('6.0.13', { ...playing, events: [], chat: [said(13, 'three')] }));
    await until(() => shown.length === 3, 'a message');
    assert.deepEqual(shown[2].chat.map((m) => m.text), ['one', 'two', 'three']);

    // The move that ends the game deletes the chat, and the next game starts without one.
    push(socket, state('7.0.13', { phase: 'over', events: [], chat: [] }));
    await until(() => shown.length === 4, 'the end of the game');
    assert.deepEqual(shown[3].chat, []);
    push(socket, state('8.0.14', { phase: 'starting_throw', events: [], chat: [said(14, 'again?')] }));
    await until(() => shown.length === 5, 'the next game');
    assert.deepEqual(shown[4].chat.map((m) => m.text), ['again?']);
  });

  test('after a reconnect the chat is the server’s, and no event is handed over twice', async () => {
    const server = await Scripted.start();
    server.answer = (m, socket, n) => {
      if (m.op !== 'watch') return;
      // The first connection, then the server after a restart: its chat begins again.
      const chat = n === 0 ? [said(8, 'one'), said(9, 'two')] : [said(11, 'after')];
      const events = n === 0 ? [event(10)] : [event(10), event(12)];
      reply(socket, m, { state: state(`5.${n}.0`, { phase: 'playing', events, chat }) });
    };
    const shown: State[] = [];
    connect(server).startWatching(CODE, TOKEN, (s) => shown.push(s), (e) => assert.fail(e.message));
    await until(() => shown.length === 1, 'the game');
    server.connections[0].socket.terminate();
    await until(() => shown.length === 2, 'the game again');
    assert.deepEqual(shown.map((s) => s.events.map((e) => e.id)), [[10], [12]]);
    assert.deepEqual(shown.map((s) => s.chat.map((m) => m.text)), [['one', 'two'], ['after']]);
  });

  test('leaving a game keeps the connection, and tells the server to send it no more', async () => {
    const server = await Scripted.start();
    server.answer = (m, socket) => {
      if (m.op === 'watch') reply(socket, m, { state: state('5.0.0') });
      if (m.op === 'unwatch') reply(socket, m, { watching: null });
      if (m.op === 'info') reply(socket, m, { protocol: 1 });
    };
    const connection = connect(server);
    const shown = watch(connection);
    await until(() => shown.length === 1, 'the game');
    connection.stopWatching();
    await until(() => server.got(0, 'unwatch').length === 1, 'the server being told');
    push(server.connections[0].socket, state('6.0.0')); // one that was already on its way
    assert.deepEqual(await connection.request('info'), { protocol: 1 });
    assert.equal(server.connections.length, 1); // the next screen's request used the same connection
    assert.deepEqual(shown, ['5.0.0']);
  });

  test('a screen that closes late does not stop the next screen’s game', async () => {
    const server = await Scripted.start();
    server.answer = (m, socket) => {
      if (m.op === 'watch') reply(socket, m, { state: state('1.0.0', { code: String(m.code) }) });
    };
    const connection = connect(server);
    const first: string[] = [];
    const second: string[] = [];
    const closeFirst = connection.startWatching(CODE, TOKEN, (s) => first.push(s.code), (e) => assert.fail(e.message));
    await until(() => first.length === 1, 'the first game');
    // The next screen opens while the first is still sliding away...
    connection.startWatching('OTHER', TOKEN, (s) => second.push(s.seen), (e) => assert.fail(e.message));
    closeFirst(); // ...and only then does the first one close.
    await until(() => second.length === 1, 'the next game');
    push(server.connections[0].socket, state('2.0.0', { code: 'OTHER' }));
    await until(() => second.length === 2, 'its news');
    assert.equal(server.got(0, 'unwatch').length, 0);
    assert.deepEqual(first, [CODE]);
  });

  test('a game left before the connection opened is never watched', async () => {
    const server = await Scripted.start();
    const connection = connect(server);
    watch(connection);
    connection.stopWatching();
    await pause(150);
    assert.deepEqual(server.connections.flatMap((c) => c.got), []);
  });

  test('a connection with no game to watch is checked too', async () => {
    const server = await Scripted.start();
    let there = true;
    server.answer = (m, socket) => {
      if (there) reply(socket, m, m.op === 'unwatch' ? { watching: null } : { protocol: 1 });
    };
    const connection = connect(server, { heartbeatMs: 50, heartbeatAnswerMs: 80 });
    const ups: boolean[] = [];
    connection.listen((up) => ups.push(up));
    await connection.request('info');
    await until(() => server.got(0, 'unwatch').length >= 2, 'two checks');
    there = false; // the connection dies without closing
    await until(() => ups.length === 2, 'the dead connection being closed');
    assert.deepEqual(ups, [true, false]);
    await pause(120);
    assert.equal(server.connections.length, 1); // nothing to reconnect for
    there = true;
    assert.deepEqual(await connection.request('info'), { protocol: 1 });
    assert.equal(server.connections.length, 2);
  });

  test('with no game to watch, a dead connection is dropped and the next request opens another', async () => {
    const server = await Scripted.start();
    server.answer = (m, socket, n) => { if (n === 1) reply(socket, m, { protocol: 1 }); };
    const connection = connect(server, { requestMs: 100 });
    const failed = await connection.request('info').catch((e) => e);
    assert.ok(failed instanceof ApiError && failed.code === 'offline');
    await pause(100);
    assert.equal(server.connections.length, 1); // nothing to reconnect for
    assert.deepEqual(await connection.request('info'), { protocol: 1 });
    assert.equal(server.connections.length, 2);
  });

  test('a connection that never opens is given up', async () => {
    const accepted: net.Socket[] = [];
    const swallow = net.createServer((socket) => accepted.push(socket)); // accepts, and never answers
    await new Promise<void>((resolve) => swallow.listen(0, '127.0.0.1', resolve));
    closing.push(() => {
      accepted.forEach((socket) => socket.destroy());
      swallow.close();
    });
    const connection = new Connection(`http://127.0.0.1:${(swallow.address() as net.AddressInfo).port}`,
      { connectMs: 100 });
    closing.push(() => connection.close());
    const started = Date.now();
    const failed = await connection.request('info').catch((e) => e);
    assert.ok(failed instanceof ApiError && failed.code === 'offline');
    assert.ok(Date.now() - started < 2000, 'well before the request itself would time out');
  });
});
