/// <reference types="node" />
/**
 * What plays over the game's screen, and when (src/lib/shows.ts): the website's rules for
 * reactions, effects and new chat messages. Pure logic: no server, no screen.
 *
 *   node --test tests/
 */

import assert from 'node:assert/strict';
import { describe, test } from 'node:test';

import type { ChatMessage, GameEvent, State } from '../src/lib/api.ts';
import { BUBBLE_MS, DICE_LAND_MS, EFFECT_MS, nothingShown, showsFor } from '../src/lib/shows.ts';

const NOW = 1_000_000; // the device's clock, ms
const SERVER_NOW = 5000; // the server's clock, s

/** A watcher's state: `events` are the new ones, `chat` is the whole chat. */
function state(events: Partial<GameEvent>[] = [], chat: Partial<ChatMessage>[] = [], more: Partial<State> = {}): State {
  return {
    code: 'ABCDE', seated: true, you: 0, local: false, names: ['Ann', 'Bob', 'Cy'], now: SERVER_NOW,
    events: events.map((e) => ({ at: SERVER_NOW, seat: 1, ...e })),
    chat: chat.map((m) => ({ at: SERVER_NOW, seat: 1, text: 'hi', ...m })),
    ...more,
  } as State;
}

const reaction = (id: number, more: Partial<GameEvent> = {}): Partial<GameEvent> =>
  ({ id, kind: 'reaction', reaction: 'lucky', emoji: '🍀', label: 'Lucky!', who: 'Bob → you', to_you: true, ...more });
const effect = (id: number, more: Partial<GameEvent> = {}): Partial<GameEvent> =>
  ({ id, kind: 'effect', effect: 'sparkles', what: 'FULL', title: 'Full house!', text: 'Bob · first roll', ...more });

/** A screen that has opened the game and seen it as it was. */
function opened(events: Partial<GameEvent>[] = [], chat: Partial<ChatMessage>[] = []) {
  const shown = nothingShown();
  assert.deepEqual(showsFor(state(events, chat), shown, NOW), []);
  return shown;
}

describe('what plays over the game', () => {
  test('what happened before the screen opened the game is not news', () => {
    const shown = nothingShown();
    assert.deepEqual(showsFor(state([reaction(10), effect(11)], [{ id: 12 }]), shown, NOW), []);
    assert.deepEqual([shown.events, shown.chat], [11, 12]);
    // Nor does the same news come again (a reconnect hands the recent events over once more).
    assert.deepEqual(showsFor(state([reaction(10), effect(11)], [{ id: 12 }]), shown, NOW), []);
  });

  test('an invite shows nothing of the game, and taking the seat is the opening', () => {
    const shown = nothingShown();
    assert.deepEqual(showsFor(state([], [], { seated: false, you: null }), shown, NOW), []);
    assert.equal(shown.events, null);
    // The seat is taken back in the middle of a game: its chat so far is not announced.
    assert.deepEqual(showsFor(state([reaction(10)], [{ id: 12 }]), shown, NOW), []);
    assert.equal(showsFor(state([reaction(13)], [{ id: 12 }, { id: 14 }]), shown, NOW).length, 2);
  });

  test('a reaction is a bubble with the server’s words, at once', () => {
    const shown = opened();
    const [bubble] = showsFor(state([reaction(10)]), shown, NOW);
    assert.deepEqual(bubble, {
      id: 'reaction-10', kind: 'reaction', startAt: NOW, ms: BUBBLE_MS,
      emoji: '🍀', who: 'Bob → you', label: 'Lucky!', toYou: true,
    });
  });

  test('a throw’s effect waits for the dice to land; a bonus comes at once', () => {
    const thrown = showsFor(state([effect(10, { effect: 'grand_fireworks', what: 'ABAKA', title: 'Abaka!' })]), opened(), NOW);
    assert.deepEqual(thrown.map((s) => [s.effect, s.title, s.startAt - NOW, s.ms]),
      [['grand_fireworks', 'Abaka!', DICE_LAND_MS, EFFECT_MS.grand_fireworks]]);
    const bonus = showsFor(state([effect(10, { what: 'BONUS', title: 'Bonus!' })]), opened(), NOW);
    assert.deepEqual(bonus.map((s) => [s.effect, s.startAt - NOW]), [['sparkles', 0]]);
  });

  test('an effect that arrives while another plays waits for it to end', () => {
    const shown = opened();
    // A full house thrown and written at once: its sparkles, then the bonus it earned.
    const [first, second] = showsFor(state([effect(10), effect(11, { what: 'BONUS' })]), shown, NOW);
    assert.equal(first.startAt, NOW + DICE_LAND_MS);
    assert.equal(second.startAt, first.startAt + EFFECT_MS.sparkles);
    // One more, half a second later, queues behind both; a reaction never waits.
    const later = showsFor(state([effect(12, { effect: 'fireworks' }), reaction(13)]), shown, NOW + 500);
    assert.deepEqual(later.map((s) => s.startAt), [second.startAt + EFFECT_MS.sparkles, NOW + 500]);
    // Once they are over, the next one starts as the dice land again.
    const [fresh] = showsFor(state([effect(14)]), shown, NOW + 60000);
    assert.equal(fresh.startAt, NOW + 60000 + DICE_LAND_MS);
  });

  test('old news is skipped: an event first seen 15 s after it happened', () => {
    const shown = opened();
    const shows = showsFor(state([reaction(10, { at: SERVER_NOW - 16 }), reaction(11, { at: SERVER_NOW - 14 })]), shown, NOW);
    assert.deepEqual(shows.map((s) => s.id), ['reaction-11']);
    assert.equal(shown.events, 11); // and it stays skipped
  });

  test('an effect or a kind this app does not know', () => {
    const shown = opened();
    const shows = showsFor(state([
      effect(10, { effect: 'meteor_shower', title: 'Meteors!' }), // a newer server's effect: its banner, with sparkles
      { id: 11, kind: 'tournament' }, // a newer server's kind of event: nothing
    ]), shown, NOW);
    assert.deepEqual(shows.map((s) => [s.kind, s.effect, s.title]), [['effect', 'sparkles', 'Meteors!']]);
  });

  test('tears: a great throw with nowhere to write it, as the dice land, for as long as fireworks', () => {
    const shown = opened();
    const shows = showsFor(state([effect(10, { effect: 'tears', what: 'ABAKA', title: 'Abaka, and nowhere to write it 😭' })]),
      shown, NOW);
    assert.deepEqual(shows.map((s) => [s.effect, s.title, s.startAt - NOW, s.ms]),
      [['tears', 'Abaka, and nowhere to write it 😭', 450, 4500]]);
  });

  test('other players’ new messages are announced, the latest three, cut short', () => {
    const shown = opened([], [{ id: 5 }]);
    const long = 'x'.repeat(200);
    const chat = [{ id: 5 }, { id: 6, text: 'one' }, { id: 7, seat: 0, text: 'mine' }, { id: 8, text: 'two' },
      { id: 9, seat: 2, text: long }, { id: 10, text: 'four' }];
    const shows = showsFor(state([], chat), shown, NOW);
    assert.deepEqual(shows.map((s) => [s.kind, s.who, s.label!.length === 80 ? 'long' : s.label]),
      [['message', 'Bob', 'two'], ['message', 'Cy', 'long'], ['message', 'Bob', 'four']]);
    assert.equal(shows[1].label!.length, 80);
    assert.ok(shows[1].label!.endsWith('…'));
    assert.deepEqual(showsFor(state([], chat), shown, NOW), []); // each once
  });
});
