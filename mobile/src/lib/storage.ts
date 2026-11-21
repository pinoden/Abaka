/**
 * What the app keeps on the device: the games it played (code, kind, names) and each
 * game's seat token, plus the language. Tokens are secrets, so on phones everything goes
 * in the system's secure storage (Keychain, Keystore). The web build, used for checks,
 * keeps it in the browser's storage.
 */

import * as SecureStore from 'expo-secure-store';
import { Platform } from 'react-native';

import type { Lang } from './api';

export const GAMES_KEPT = 10; // the newest games the device remembers, as on the web

export type SavedGame = { code: string; local: boolean; names: string[]; at: number };

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

/** Remember a game and this device's seat in it (newest first, at most GAMES_KEPT). */
export async function saveGame(game: Omit<SavedGame, 'at'>, token: string): Promise<void> {
  await write(tokenKey(game.code), token);
  const games = (await savedGames()).filter((g) => g.code !== game.code);
  const kept = [{ ...game, at: Date.now() }, ...games];
  for (const old of kept.slice(GAMES_KEPT)) await write(tokenKey(old.code), null);
  await write('abaka.games', JSON.stringify(kept.slice(0, GAMES_KEPT)));
}

export async function forgetGame(code: string): Promise<void> {
  await write(tokenKey(code), null);
  await write('abaka.games', JSON.stringify((await savedGames()).filter((g) => g.code !== code)));
}

export async function savedLanguage(): Promise<Lang | null> {
  const lang = await read('abaka.lang');
  return lang === 'en' || lang === 'ru' ? lang : null;
}

export async function saveLanguage(lang: Lang): Promise<void> {
  await write('abaka.lang', lang);
}
