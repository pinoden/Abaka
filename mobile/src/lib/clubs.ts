/**
 * Clubs on the app's screens, as on the web (abaka_ui.py: the club page, the results of a
 * club game, the name picker): the table's rows, the latest games, the rating changes, and
 * which of the club's players a name box offers.
 *
 * No React Native imports here: tests/clubs.test.ts runs this file in Node.
 */

import type { ClubGame, ClubMember, ClubResult } from './api';

/**
 * Who a name is in a club: the same name, whatever its capitals and spacing. The server's
 * rule (abaka/rooms.py, member_key) uses Python's casefold; lower case is the same but for
 * a few letters, such as ß. The server decides: this only chooses what to offer.
 */
export function memberKey(name: string): string {
  return name.split(/\s+/).filter(Boolean).join(' ').toLowerCase();
}

/**
 * Python's round(): a half goes to the even neighbour (2.5 -> 2, 3.5 -> 4), so the app shows
 * the numbers the website shows.
 */
export function roundHalfEven(x: number): number {
  const r = Math.round(x);
  return Math.abs(x % 1) === 0.5 && r % 2 !== 0 ? r - 1 : r;
}

export type Change = { text: string; trend: 'up' | 'down' | 'same' };

/** A rating's change as the website shows it: ▲12, ▼3, or = for none. */
export function changeText(change: number): Change {
  const n = roundHalfEven(change);
  if (n > 0) return { text: `▲${n}`, trend: 'up' };
  if (n < 0) return { text: `▼${-n}`, trend: 'down' };
  return { text: '=', trend: 'same' };
}

export type TableRow = {
  rank: string;
  name: string;
  rating: number;
  change: Change;
  games: number;
  wins: number;
  average: number;
  best: number;
};

const MEDALS = ['🥇', '🥈', '🥉'];

/** The club's table in the server's order (best first), with a medal for the first three. */
export function tableRows(members: ClubMember[]): TableRow[] {
  return members.map((m, i) => ({
    rank: MEDALS[i] ?? String(i + 1),
    name: m.name,
    rating: roundHalfEven(m.rating),
    change: changeText(m.change),
    games: m.games,
    wins: m.wins,
    average: m.games ? roundHalfEven(m.points / m.games) : 0,
    best: m.best,
  }));
}

/** A finished game in the club's list: its day (on this device's clock), and its players by score, winners marked. */
export function gameLine(game: ClubGame): { day: string; players: { name: string; score: number; won: boolean }[] } {
  const best = Math.max(...game.players.map((p) => p.score));
  const date = new Date(game.at * 1000);
  const day = `${String(date.getDate()).padStart(2, '0')}.${String(date.getMonth() + 1).padStart(2, '0')}`;
  const players = [...game.players].sort((a, b) => b.score - a.score)
    .map((p) => ({ name: p.name, score: p.score, won: p.score === best }));
  return { day, players };
}

/** The results of a club game: each player's rating now and its change, by score. */
export function resultRows(result: ClubResult): { name: string; rating: number; change: Change }[] {
  return [...result.players].sort((a, b) => b.score - a.score)
    .map((p) => ({ name: p.name, rating: roundHalfEven(p.rating), change: changeText(p.change) }));
}

/** The club's players a name box offers: the ones not at the table already. */
export function offered(names: string[], taken: string[]): string[] {
  const seated = new Set(taken.map(memberKey));
  return names.filter((name) => !seated.has(memberKey(name)));
}

/** Whether `name` is one of `boxes` (ignoring capitals and spaces). */
export function inBoxes(boxes: string[], name: string): boolean {
  const key = memberKey(name);
  return key !== '' && boxes.some((box) => memberKey(box) === key);
}

/**
 * A game on one device, the boxes of names: tapping a club player puts them in the first
 * empty box, or takes them out of the box they are in. Unchanged if every box is full.
 */
export function togglePlayer(boxes: string[], name: string): string[] {
  const key = memberKey(name);
  const at = boxes.findIndex((box) => key !== '' && memberKey(box) === key);
  if (at >= 0) return boxes.map((box, i) => (i === at ? '' : box));
  const free = boxes.findIndex((box) => !box.trim());
  return free < 0 ? boxes : boxes.map((box, i) => (i === free ? name : box));
}
