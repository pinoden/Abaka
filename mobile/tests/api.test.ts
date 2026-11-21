/// <reference types="node" />
/**
 * The app's API client (src/lib/api.ts) against a real server: complete games played only
 * with the moves the server offers, as the app's screens play them.
 *
 *   ABAKA_SERVER=http://localhost:8501 node --test tests/
 *
 * The server is `streamlit run abaka_server.py` (CI starts one). Without ABAKA_SERVER the
 * tests are skipped. Run in Node, which runs the TypeScript file as it is.
 */

import assert from 'node:assert/strict';
import { after, describe, test } from 'node:test';

import { ApiError, Connection, isNewer, type Move, type Seat, type State } from '../src/lib/api.ts';

const SERVER = process.env.ABAKA_SERVER;
const skip = SERVER ? false : 'set ABAKA_SERVER to a running server (streamlit run abaka_server.py)';
const connections: Connection[] = [];

function connect(lang: 'en' | 'ru' = 'en'): Connection {
  const connection = new Connection(SERVER ?? 'http://localhost:1');
  connection.setLanguage(lang);
  connections.push(connection);
  return connection;
}

after(() => connections.forEach((c) => c.close()));

/** A small seeded random generator, so a failing game can be played again. */
function random(seed: number): () => number {
  let x = seed >>> 0;
  return () => {
    x = (x * 1664525 + 1013904223) >>> 0;
    return x / 2 ** 32;
  };
}

async function until(check: () => boolean, what: string, ms = 5000): Promise<void> {
  const end = Date.now() + ms;
  while (!check()) {
    if (Date.now() > end) throw new Error(`timed out waiting for ${what}`);
    await new Promise((resolve) => setTimeout(resolve, 20));
  }
}

type Player = { connection: Connection; token: string };

/**
 * Play the game in `code` to its end: `players` by seat, or one player for a game on one
 * device. Every move is one the state offers; after it, the written cell must hold the
 * value its preview promised.
 */
async function play(code: string, players: Player[], seed: number): Promise<State> {
  const rand = random(seed);
  let moves = 0;
  for (;;) {
    let state = (await players[0].connection.request<{ state: State }>('state', { code, token: players[0].token })).state;
    if (state.phase === 'over') return state;
    const { connection, token } = players.length === 1 ? players[0] : players[state.game!.current];
    state = (await connection.request<{ state: State }>('state', { code, token })).state;
    const base = { code, token, version: state.version };
    if (state.can.includes('throw')) {
      await connection.act('throw', base);
    } else if (state.can.includes('roll')) {
      await connection.act('roll', base);
    } else if (state.can.includes('reroll') && rand() < 0.4) {
      const dice = [0, 1, 2, 3, 4].filter(() => rand() < 0.5);
      await connection.act('reroll', { ...base, dice: dice.length ? dice : [0] });
    } else {
      assert.ok(state.moves, 'dice on the table come with moves');
      const scoring = state.moves.score.length > 0 && state.can.includes('score');
      const options: Move[] = scoring ? state.moves.score : state.moves.cross;
      assert.ok(options.length > 0, 'a turn always has a move');
      const best = options.filter((m) => m.best);
      if (scoring) assert.ok(best.length > 0, 'the option with the most points is marked');
      const move = options[Math.floor(rand() * options.length)];
      const seat = state.game!.current;
      const after = await connection.act(scoring ? 'score' : 'cross', { ...base, row: move.row, slot: move.slot });
      const written = after.game!.players[seat].rows[move.row][move.slot];
      assert.equal(written, move.value, `${move.row} holds what its preview said`);
      assert.deepEqual(after.game!.last_move, { seat, row: move.row, slot: move.slot });
      moves++;
    }
    assert.ok(moves < 500, 'the game ends');
  }
}

describe('the API client against a real server', { skip }, () => {
  test('a game on one device, played to the end', async () => {
    const connection = connect();
    const seat = await connection.request<Seat>('create_local', { names: ['Test Ann', 'Test Bob', 'Test Cy'] });
    assert.equal(seat.state.local, true);
    assert.equal(seat.state.phase, 'starting_throw');
    const end = await play(seat.code, [{ connection, token: seat.token }], 1);
    assert.equal(end.phase, 'over');
    assert.ok(end.game!.winners.length >= 1);
    assert.ok(end.can.includes('rematch'));
    const again = await connection.act('rematch', { code: seat.code, token: seat.token });
    assert.equal(again.phase, 'starting_throw');
    assert.equal(again.game!.number, 2);
    assert.equal(again.table.games, 1);
  });

  test('an online game between two devices: each sees the other’s moves pushed', async () => {
    const ann = connect();
    const bob = connect('ru');
    const created = await ann.request<Seat>('create', { name: 'Test Ann', players: 2 });
    assert.equal(created.state.phase, 'waiting');
    assert.deepEqual(created.state.can, ['leave']);

    // Bob opens the code: without a seat he is offered to join.
    const invite = (await bob.request<{ state: State }>('state', { code: created.code })).state;
    assert.equal(invite.seated, false);
    assert.ok(invite.can.includes('join'));

    let annSees: State | null = null;
    ann.startWatching(created.code, created.token,
      (s) => { if (isNewer(s, annSees)) annSees = s; }, (e) => assert.fail(e.message));
    await until(() => annSees !== null, 'the watch');

    const joined = await bob.request<Seat>('join', { code: created.code, name: 'Test Bob' });
    assert.equal(joined.state.you, 1);
    // Ann's screen learns that Bob joined without asking.
    await until(() => annSees!.names.length === 2 && annSees!.phase === 'starting_throw', 'the join pushed');

    let bobSees: State | null = null;
    bob.startWatching(created.code, joined.token,
      (s) => { if (isNewer(s, bobSees)) bobSees = s; }, (e) => assert.fail(e.message));
    await until(() => bobSees !== null, "Bob's watch");
    // Bob's texts come in Russian, Ann's in English.
    const rows = (await bob.request<{ rows: { name: string }[] }>('info')).rows;
    assert.equal(rows[0].name, 'Школа 1');

    const players: Player[] = [
      { connection: ann, token: created.token },
      { connection: bob, token: joined.token },
    ];
    const playerFor = (state: State) => (state.game ? players[state.game.current] : players[0]);

    // The first moves: the other screen gets each new state pushed.
    for (let i = 0; i < 3; i++) {
      const state = (await ann.request<{ state: State }>('state', { code: created.code, token: created.token })).state;
      const mover = playerFor(state);
      const other = mover === players[0] ? () => bobSees : () => annSees;
      const now = (await mover.connection.request<{ state: State }>('state', { code: created.code, token: mover.token })).state;
      const op = now.can.includes('throw') ? 'throw' : now.can.includes('roll') ? 'roll' : null;
      if (!op) break;
      const after = await mover.connection.act(op, { code: created.code, token: mover.token, version: now.version });
      await until(() => other()!.version >= after.version, `the ${op} pushed to the other player`);
    }

    // A move out of turn is refused, and so is a move made on an old state.
    const state = (await ann.request<{ state: State }>('state', { code: created.code, token: created.token })).state;
    const waiting = players[state.game!.current === 0 ? 1 : 0];
    const refused = await waiting.connection.act(state.phase === 'starting_throw' ? 'throw' : 'roll',
      { code: created.code, token: waiting.token, version: state.version }).catch((e) => e);
    assert.ok(refused instanceof ApiError);
    assert.equal(refused.code, 'refused');
    const outdated = await players[state.game!.current].connection.act('roll',
      { code: created.code, token: players[state.game!.current].token, version: state.version - 1 }).catch((e) => e);
    assert.ok(outdated instanceof ApiError);
    assert.equal(outdated.code, 'outdated');

    const end = await play(created.code, players, 2);
    assert.equal(end.phase, 'over');
    // Each screen saw the end, whoever made the last move (a state its own connection
    // asked for counts as seen, so it is not pushed again: the client hands it on).
    await until(() => annSees!.phase === 'over' && bobSees!.phase === 'over', 'the end on both screens');
    ann.stopWatching();
    bob.stopWatching();
  });

  test('a seat taken back on another device', async () => {
    const ann = connect();
    const other = connect();
    const created = await ann.request<Seat>('create', { name: 'Test Ann', players: 2 });
    await other.request<Seat>('join', { code: created.code, name: 'Test Bob' });
    const taken = await other.request<Seat>('rejoin', { code: created.code, seat: 0 });
    assert.equal(taken.state.you, 0);
    // The old token holds no seat any more: its state is the invite's.
    const old = (await ann.request<{ state: State }>('state', { code: created.code, token: created.token })).state;
    assert.equal(old.seated, false);
    assert.ok(old.can.includes('rejoin'));
  });

  test('errors carry the code and the message in the request’s language', async () => {
    const connection = connect('ru');
    const missing = await connection.request('state', { code: 'ZZZZZ' }).catch((e) => e);
    assert.ok(missing instanceof ApiError);
    assert.equal(missing.code, 'not_found');
    assert.match(missing.message, /Игра не найдена/);
  });

  test('a server that cannot be reached fails a request as offline', async () => {
    const nowhere = new Connection('http://127.0.0.1:9');
    connections.push(nowhere);
    const failed = await nowhere.request('info').catch((e) => e);
    assert.ok(failed instanceof ApiError);
    assert.equal(failed.code, 'offline');
  });
});
