/// <reference types="node" />
/**
 * Picked things say they are picked, on phones and on the web. React Native on a phone
 * reads `aria-checked` and `accessibilityState`, but not `aria-pressed`; the web build
 * (react-native-web) writes `aria-pressed` and `aria-checked` into the page, but not
 * `accessibilityState`. So an element with `aria-pressed` also needs `accessibilityState`,
 * or TalkBack and VoiceOver never hear that a die is picked (found on Android's emulator,
 * 2026-11-28). Pure source scan: no server, no screen.
 *
 *   node --test tests/
 */

import assert from 'node:assert/strict';
import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { test } from 'node:test';

const SRC = join(import.meta.dirname, '..', 'src');

function sources(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return sources(path);
    return /\.tsx?$/.test(name) ? [path] : [];
  });
}

/** Each JSX element's opening tag that has the attribute, as text. */
function tagsWith(text: string, attribute: string): string[] {
  const tags: string[] = [];
  let at = text.indexOf(attribute);
  while (at >= 0) {
    const start = text.lastIndexOf('<', at);
    const end = text.indexOf('>', at);
    tags.push(text.slice(start, end + 1));
    at = text.indexOf(attribute, at + attribute.length);
  }
  return tags;
}

test('an element pressed on the web also says so on phones', () => {
  const missing: string[] = [];
  let found = 0;
  for (const file of sources(SRC)) {
    for (const tag of tagsWith(readFileSync(file, 'utf8'), 'aria-pressed=')) {
      found += 1;
      if (!tag.includes('accessibilityState=')) missing.push(`${file.slice(SRC.length + 1)}: ${tag.split('\n')[0]}`);
    }
  }
  assert.ok(found >= 2, 'the dice and a club\'s players say whether they are picked');
  assert.deepEqual(missing, [], 'aria-pressed without accessibilityState: phones would not hear it');
});

test('nothing relies on accessibilityState alone where the web build needs an aria attribute', () => {
  const missing: string[] = [];
  for (const file of sources(SRC)) {
    for (const tag of tagsWith(readFileSync(file, 'utf8'), 'accessibilityState=')) {
      if (/accessibilityState=\{\{\s*(checked|selected)/.test(tag) && !/aria-(pressed|checked|selected)=/.test(tag)) {
        missing.push(`${file.slice(SRC.length + 1)}: ${tag.split('\n')[0]}`);
      }
    }
  }
  assert.deepEqual(missing, [], 'accessibilityState without an aria attribute: the web build would not say it');
});
