/**
 * A game's full code: its code and its secret key, "K7M2Q-8XJ4PN2R" (Backlog item 31). The
 * code alone opens nothing, so this is what players share and type. As `split_code` and
 * `full_code` in abaka/rooms.py. No React Native imports here, so tests run it in Node.
 */

export const CODE_LENGTH = 5;
export const KEY_LENGTH = 8;

export function fullCode(code: string, key: string): string {
  return `${code}-${key}`;
}

/**
 * The code and the key in what a player typed or pasted: a full code (any case, with or
 * without the dash or spaces) or a game's link (its ?room=). The key is '' when only a code
 * was given.
 */
export function splitCode(text: string): { code: string; key: string } {
  let wanted = (text ?? '').trim();
  const link = /[?&]room=([^&#\s]*)/.exec(wanted);
  if (link) {
    try {
      wanted = decodeURIComponent(link[1]);
    } catch {
      wanted = link[1];
    }
  }
  const plain = wanted.toUpperCase().replace(/[^A-Z0-9]/g, '');
  if (plain.length === CODE_LENGTH + KEY_LENGTH) {
    return { code: plain.slice(0, CODE_LENGTH), key: plain.slice(CODE_LENGTH) };
  }
  return { code: plain, key: '' };
}
