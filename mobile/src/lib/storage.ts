/**
 * What the app keeps on the device: the games it played (code, kind, names) and each
 * game's seat token, the clubs it opened, plus the language. Tokens are secrets, so on phones everything goes
 * in the system's secure storage (Keychain, Keystore). The web build, used for checks,
 * keeps it in the browser's storage.
 */

import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import type { Lang } from './api';

export const GAMES_KEPT = 10; // the newest games the device remembers, as on the web
export const CLUBS_KEPT = 6; // the clubs it remembers, as on the web (MY_CLUBS_KEPT)

export type SavedClub = { code: string; name: string };

/**
 * `over`: the game had ended when the device last saw it (the home page lists the others).
 * `key`: the game's secret key, without which its code opens nothing (Backlog item 31).
 */
export type SavedGame = { code: string; key?: string; local: boolean; names: string[]; at: number; over?: boolean };

// Changes to the list of games happen one after another: each reads the list and writes
// it back, and two at once would lose one of them.
let changes: Promise<unknown> = Promise.resolve();

function inTurn<T>(change: () => Promise<T>): Promise<T> {
  const result = changes.then(change, change);
  changes = result.catch(() => {});
  return result;
}

async function read(key: string): Promise<string | null> {
  if (Platform.OS === 'web') {
    try {
      return globalThis.localStorage?.getItem(key) ?? null;
    } catch {
      return null;
    }
  }
  try {
    return await SecureStore.getItemAsync(key);
  } catch {
    return null;
  }
}

async function write(key: string, value: string | null): Promise<void> {
  try {
    if (Platform.OS === 'web') {
      if (value === null) globalThis.localStorage?.removeItem(key);
      else globalThis.localStorage?.setItem(key, value);
    } else if (value === null) {
      await SecureStore.deleteItemAsync(key);
    } else {
      await SecureStore.setItemAsync(key, value);
    }
  } catch {
    // Storage refused (a private browser window): the game still plays, it is just not kept.
  }
}

const tokenKey = (code: string) => `abaka.token.${code}`;

/**
 * This device's secret (Backlog item 37): the server keeps a seat for the device that took
 * it, so a lost token is no lost seat, and nobody else with the game's link can take it.
 */
export async function savedDevice(): Promise<string | null> {
  return read('abaka.device');
}

export async function saveDevice(secret: string): Promise<void> {
  await write('abaka.device', secret);
}

export async function savedGames(): Promise<SavedGame[]> {
  try {
    const games = JSON.parse((await read('abaka.games')) ?? '[]');
    return Array.isArray(games) ? games : [];
  } catch {
    return [];
  }
}

export async function tokenFor(code: string): Promise<string | null> {
  return read(tokenKey(code));
}

/** The key of a game the device remembers, or null. */
export async function keyFor(code: string): Promise<string | null> {
  return (await savedGames()).find((g) => g.code === code)?.key ?? null;
}

/** Remember a game and this device's seat in it (newest first, at most GAMES_KEPT). */
export function saveGame(game: Omit<SavedGame, 'at'>, token: string): Promise<void> {
  return inTurn(async () => {
    await write(tokenKey(game.code), token);
    const games = (await savedGames()).filter((g) => g.code !== game.code);
    const kept = [{ ...game, at: Date.now() }, ...games];
    for (const old of kept.slice(GAMES_KEPT)) await write(tokenKey(old.code), null);
    await write('abaka.games', JSON.stringify(kept.slice(0, GAMES_KEPT)));
  });
}

/** Bring up to date what the device remembers about a game: its players, whether it is over. */
export function updateGame(code: string, now: Pick<SavedGame, 'names' | 'over'>): Promise<void> {
  return inTurn(async () => {
    const games = await savedGames();
    const game = games.find((g) => g.code === code);
    if (!game || (game.over === now.over && game.names.join('\n') === now.names.join('\n'))) return;
    game.names = now.names;
    game.over = now.over;
    await write('abaka.games', JSON.stringify(games));
  });
}

export function forgetGame(code: string): Promise<void> {
  return inTurn(async () => {
    await write(tokenKey(code), null);
    await write('abaka.games', JSON.stringify((await savedGames()).filter((g) => g.code !== code)));
  });
}

export async function savedClubs(): Promise<SavedClub[]> {
  try {
    const clubs = JSON.parse((await read('abaka.clubs')) ?? '[]');
    return Array.isArray(clubs) ? clubs : [];
  } catch {
    return [];
  }
}

/** Remember a club this device opened (newest first, at most CLUBS_KEPT). */
export function saveClub(club: SavedClub): Promise<void> {
  return inTurn(async () => {
    const clubs = (await savedClubs()).filter((c) => c.code !== club.code);
    await write('abaka.clubs', JSON.stringify([{ code: club.code, name: club.name }, ...clubs].slice(0, CLUBS_KEPT)));
  });
}

export function forgetClub(code: string): Promise<void> {
  return inTurn(async () => {
    await write('abaka.clubs', JSON.stringify((await savedClubs()).filter((c) => c.code !== code)));
  });
}

export async function savedLanguage(): Promise<Lang | null> {
  const lang = await read('abaka.lang');
  return lang === 'en' || lang === 'ru' ? lang : null;
}

export async function saveLanguage(lang: Lang): Promise<void> {
  await write('abaka.lang', lang);
}
