/**
 * Where a die's pips go (src/components/Dice.tsx), as the website draws them
 * (ui_components/style.py, `die_uri`): centres on a 3 x 3 grid at 28%, 50% and 72% of the
 * face, each pip 17% of it across.
 *
 * No React Native imports here: tests/dice.test.ts runs this file in Node.
 */

const GRID = [0.28, 0.5, 0.72];
const PIP = 0.17;

// Each value's pips as (row, column) on the grid.
const PIPS: Record<number, [number, number][]> = {
  1: [[1, 1]],
  2: [[0, 0], [2, 2]],
  3: [[0, 0], [1, 1], [2, 2]],
  4: [[0, 0], [0, 2], [2, 0], [2, 2]],
  5: [[0, 0], [0, 2], [1, 1], [2, 0], [2, 2]],
  6: [[0, 0], [1, 0], [2, 0], [0, 2], [1, 2], [2, 2]],
};

export type Pip = { top: number; left: number; size: number };

/**
 * The pips of a die `size` across with a border `border` wide. A child placed with `top`
 * and `left` is measured from inside the border, so the border is taken off: otherwise
 * every pip sits the border's width right of and below where it belongs (more on a picked
 * die, whose border is thicker).
 */
export function pips(value: number, size: number, border: number): Pip[] {
  const across = size * PIP;
  return (PIPS[value] ?? []).map(([row, col]) => ({
    top: size * GRID[row] - across / 2 - border,
    left: size * GRID[col] - across / 2 - border,
    size: across,
  }));
}
