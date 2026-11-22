/**
 * The score table's sizes (src/components/Board.tsx): each player's three cells and the row
 * bonus, next to the row names. Two players' columns fit the screen; with three to five the
 * columns scroll sideways under the row names, as on the web.
 *
 * No React Native imports here: tests/board.test.ts runs this file in Node.
 */

export const CELL_W = 26;
export const BONUS_W = 28;
export const NAME_W = 96;
export const GAP = 6; // between players' columns
export const COLUMN_PADDING = 2; // each side of a player's column

// What the board has: the screen's column (at most 560 wide, 16 of padding each side), less
// the card's padding and border (src/components/ui.tsx).
const SCREEN_MAX = 560;
const SCREEN_PADDING = 16;
const CARD_INSET = 17;

// Narrower cells for two players on a small phone, down to 360 wide (a common Android width),
// but not below these: a cell must still hold "160" (Abaka on the first roll).
const CELL_MIN = 22;
const BONUS_MIN = 24;

/** The width the board has inside its card. */
export function boardRoom(screenWidth: number): number {
  return Math.min(screenWidth - 2 * SCREEN_PADDING, SCREEN_MAX) - 2 * CARD_INSET;
}

/** How wide the whole table is with these cells. */
export function boardWidth(players: number, cell: number, bonus: number): number {
  return NAME_W + players * (2 * COLUMN_PADDING + 3 * cell + bonus) + GAP * (players - 1);
}

/** The cells' widths: the usual ones, or narrower so two players' columns fit the screen. */
export function cellWidths(screenWidth: number, players: number): { cell: number; bonus: number } {
  if (players > 2) return { cell: CELL_W, bonus: BONUS_W };
  const room = boardRoom(screenWidth) - NAME_W - GAP * (players - 1) - 2 * COLUMN_PADDING * players;
  const fit = Math.min(1, room / (players * (3 * CELL_W + BONUS_W)));
  return { cell: Math.max(CELL_MIN, Math.floor(CELL_W * fit)), bonus: Math.max(BONUS_MIN, Math.floor(BONUS_W * fit)) };
}
