/// <reference types="node" />
/**
 * The score table's sizes (src/lib/board.ts): two players' columns fit a phone's width,
 * bonuses included, down to 360 wide. Pure logic: no server, no screen.
 *
 *   node --test tests/
 */

import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { BONUS_W, boardRoom, boardWidth, cellWidths, CELL_W, isWide, pageWidth } from '../src/lib/board.ts';

describe('the score table', () => {
  test('two players fit every common phone width, bonus columns included', () => {
    for (const width of [360, 375, 390, 393, 411, 414, 428, 430]) {
      const { cell, bonus } = cellWidths(width, 2);
      assert.ok(boardWidth(2, cell, bonus) <= boardRoom(width), `${width} wide: ${boardWidth(2, cell, bonus)} > ${boardRoom(width)}`);
    }
  });

  test('the cells keep their usual size where they fit, and shrink only as much as needed', () => {
    assert.deepEqual(cellWidths(390, 2), { cell: CELL_W, bonus: BONUS_W });
    assert.deepEqual(cellWidths(1024, 2), { cell: CELL_W, bonus: BONUS_W }); // a tablet: the column stops at 560
    assert.deepEqual(cellWidths(360, 2), { cell: 22, bonus: 24 });
  });

  test('three to five players scroll sideways at the usual size', () => {
    for (const players of [3, 4, 5]) assert.deepEqual(cellWidths(360, players), { cell: CELL_W, bonus: BONUS_W });
  });

  test('a wide screen gives the board a column of its own, where five players fit', () => {
    assert.equal(isWide(899), false); // a tablet upright: one column, as on a phone
    assert.equal(isWide(900), true);
    assert.equal(pageWidth(1300, true), 1180);
    assert.equal(pageWidth(1300, false), 560); // home, a club, the rules: one column at any width
    assert.equal(pageWidth(390, true), 358);
    // Five players, and the column of row differences (38), without scrolling on a desktop.
    assert.ok(boardWidth(5, CELL_W, BONUS_W) + 38 <= boardRoom(1300), `${boardWidth(5, CELL_W, BONUS_W) + 38} > ${boardRoom(1300)}`);
    // Two players fit from the first wide width on, at the usual size.
    assert.deepEqual(cellWidths(900, 2), { cell: CELL_W, bonus: BONUS_W });
    assert.ok(boardWidth(2, CELL_W, BONUS_W) <= boardRoom(900));
  });

  test('never below the smallest cell, even on a very narrow screen', () => {
    assert.deepEqual(cellWidths(320, 2), { cell: 22, bonus: 24 });
  });
});
