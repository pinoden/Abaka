/// <reference types="node" />
/**
 * Clubs on the app's screens (src/lib/clubs.ts): the table, the latest games, the rating
 * changes, and the club's players offered as names. The website's numbers and rules
 * (abaka_ui.py). Pure logic: no server, no screen.
 *
 *   node --test tests/
 */

import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import type { ClubMember } from '../src/lib/api.ts';
import {
  changeText, gameLine, inBoxes, memberKey, offered, resultRows, roundHalfEven, tableRows, togglePlayer,
} from '../src/lib/clubs.ts';

function member(name: string, more: Partial<ClubMember> = {}): ClubMember {
  return { name, rating: 1000, change: 0, games: 1, wins: 0, points: 0, best: 0, last_played: 0, ...more };
}

describe('clubs on the screen', () => {
  test('a name is the same player whatever its capitals and spaces', () => {
    assert.equal(memberKey('  Ann   Lee '), 'ann lee');
    assert.equal(memberKey('АНЯ'), 'аня');
    assert.equal(memberKey(''), '');
  });

  test('numbers are rounded as Python rounds them, so the app shows the website’s', () => {
    // Python: round(0.5) == 0, round(1.5) == 2, round(2.5) == 2, round(-0.5) == 0, round(-1.5) == -2.
    const python: [number, number][] = [[0.5, 0], [1.5, 2], [2.5, 2], [3.5, 4], [-0.5, 0], [-1.5, -2], [-2.5, -2],
      [1007.5, 1008], [1008.5, 1008], [1016.4999, 1016], [1016.5001, 1017], [-15.6, -16], [7, 7]];
    for (const [x, rounded] of python) assert.equal(roundHalfEven(x) + 0, rounded, `round(${x})`);
  });

  test('a rating’s change: ▲, ▼ or =', () => {
    assert.deepEqual(changeText(16), { text: '▲16', trend: 'up' });
    assert.deepEqual(changeText(-7.6), { text: '▼8', trend: 'down' });
    assert.deepEqual(changeText(0.4), { text: '=', trend: 'same' });
    assert.deepEqual(changeText(-0.5), { text: '=', trend: 'same' });
  });

  test('the table: medals for the first three, the server’s order, averages rounded', () => {
    const rows = tableRows([
      member('Ann', { rating: 1031.5, change: 15.5, games: 2, wins: 2, points: 625, best: 330 }),
      member('Bob', { rating: 1000.2, change: -3.2, games: 2, points: 401 }),
      member('Cy', { rating: 990 }),
      member('Dee', { rating: 978.7, change: -12.6, games: 0 }),
    ]);
    assert.deepEqual(rows.map((r) => [r.rank, r.name, r.rating, r.change.text, r.average]), [
      ['🥇', 'Ann', 1032, '▲16', 312], ['🥈', 'Bob', 1000, '▼3', 200], ['🥉', 'Cy', 990, '=', 0], ['4', 'Dee', 979, '▼13', 0],
    ]);
    assert.deepEqual([rows[0].games, rows[0].wins, rows[0].best], [2, 2, 330]);
  });

  test('a finished game: its day, its players by score, the winners marked', () => {
    const at = new Date(2026, 10, 21, 18, 30).getTime() / 1000; // 21 November, on this computer's clock
    const line = gameLine({ id: 'ABCDE:0', at, players: [
      { name: 'Ann', score: 250, change: -8 }, { name: 'Bob', score: 312, change: 16 }, { name: 'Cy', score: 312, change: -8 },
    ] });
    assert.equal(line.day, '21.11');
    assert.deepEqual(line.players.map((p) => [p.name, p.won]), [['Bob', true], ['Cy', true], ['Ann', false]]);
  });

  test('after a club game: each rating now, and its change, by score', () => {
    const rows = resultRows({ club: 'Friday dice', players: [
      { name: 'Ann', score: 200, change: -16, rating: 984 }, { name: 'Bob', score: 312, change: 16, rating: 1016.4 },
    ] });
    assert.deepEqual(rows.map((r) => [r.name, r.rating, r.change.text]), [['Bob', 1016, '▲16'], ['Ann', 984, '▼16']]);
  });

  test('joining: the club’s players not at the table yet', () => {
    assert.deepEqual(offered(['Ann', 'Bob', 'Cy'], ['ann ', 'Dee']), ['Bob', 'Cy']);
    assert.deepEqual(offered([], ['Ann']), []);
  });

  test('one device: a tap puts a player in the first empty box, or takes them out', () => {
    let boxes = ['', '', ''];
    boxes = togglePlayer(boxes, 'Ann');
    boxes = togglePlayer(boxes, 'Bob');
    assert.deepEqual(boxes, ['Ann', 'Bob', '']);
    assert.ok(inBoxes(boxes, ' ANN') && !inBoxes(boxes, 'Cy'));
    boxes = togglePlayer(boxes, 'ann'); // Ann again: out, whatever the spelling
    assert.deepEqual(boxes, ['', 'Bob', '']);
    boxes = togglePlayer(togglePlayer(boxes, 'Cy'), 'Dee');
    assert.deepEqual(boxes, ['Cy', 'Bob', 'Dee']);
    assert.deepEqual(togglePlayer(boxes, 'Eve'), boxes); // every box is full: nothing changes
    assert.deepEqual(togglePlayer(['Ann typed', ''], 'Bob'), ['Ann typed', 'Bob']); // a typed name stays
    assert.ok(!inBoxes(['', ''], ''));
  });
});
