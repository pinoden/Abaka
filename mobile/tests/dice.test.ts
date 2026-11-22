/// <reference types="node" />
/**
 * Where a die's pips go (src/lib/dice.ts): centred on the face whatever its border, and
 * clear of its rounded corners, as on the website. Pure logic: no screen.
 *
 *   node --test tests/
 */

import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import { pips } from '../src/lib/dice.ts';

const near = (a: number, b: number) => Math.abs(a - b) < 1e-9;

describe('a die face', () => {
  test('every face is centred on the die, with a thin border and with a picked die\'s thick one', () => {
    for (const size of [18, 22, 60]) {
      for (const border of [1.5, 3]) {
        for (let value = 1; value <= 6; value++) {
          // Back on the die's own box (the border added again), the pips' middle is the die's middle.
          const spots = pips(value, size, border);
          const middleX = spots.reduce((sum, p) => sum + p.left + border + p.size / 2, 0) / spots.length;
          const middleY = spots.reduce((sum, p) => sum + p.top + border + p.size / 2, 0) / spots.length;
          assert.ok(near(middleX, size / 2) && near(middleY, size / 2), `${value} on a ${size} die, border ${border}`);
        }
      }
    }
  });

  test('a face shows as many pips as its value', () => {
    for (let value = 1; value <= 6; value++) assert.equal(pips(value, 60, 1.5).length, value);
  });

  test('the pips sit where the website draws them: 28%, 50% and 72% of the face, 17% across', () => {
    const [corner] = pips(2, 100, 0);
    assert.ok(near(corner.left + corner.size / 2, 28) && near(corner.top + corner.size / 2, 28));
    assert.ok(near(corner.size, 17));
    const [middle] = pips(1, 100, 0);
    assert.ok(near(middle.left + middle.size / 2, 50));
  });
});
