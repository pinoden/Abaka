/// <reference types="node" />
/** A game's full code as players type or paste it: the same as the server reads it (abaka/rooms.py). */

import assert from 'node:assert/strict';
import { test } from 'node:test';

import { fullCode, splitCode } from '../src/lib/codes.ts';

test('a full code, a link, or a code alone', () => {
  const cases: [string, { code: string; key: string }][] = [
    ['K7M2Q-8XJ4PN2R', { code: 'K7M2Q', key: '8XJ4PN2R' }],
    [' k7m2q 8xj4 pn2r ', { code: 'K7M2Q', key: '8XJ4PN2R' }],
    ['K7M2Q8XJ4PN2R', { code: 'K7M2Q', key: '8XJ4PN2R' }],
    ['https://mipt-abaka.streamlit.app/?room=K7M2Q-8XJ4PN2R', { code: 'K7M2Q', key: '8XJ4PN2R' }],
    ['https://example.org/?lang=ru&room=k7m2q-8xj4pn2r#top', { code: 'K7M2Q', key: '8XJ4PN2R' }],
    ['https://example.org/?room=K7M2Q%2D8XJ4PN2R', { code: 'K7M2Q', key: '8XJ4PN2R' }],
    ['K7M2Q', { code: 'K7M2Q', key: '' }],
    ['https://mipt-abaka.streamlit.app/?room=K7M2Q', { code: 'K7M2Q', key: '' }],
    ['', { code: '', key: '' }],
  ];
  for (const [text, expected] of cases) assert.deepEqual(splitCode(text), expected, text);
  assert.equal(fullCode('K7M2Q', '8XJ4PN2R'), 'K7M2Q-8XJ4PN2R');
});
