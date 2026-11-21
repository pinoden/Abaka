/**
 * What plays over the game's screen, and when: bubbles for reactions and for other
 * players' chat messages, and effects (fireworks, sparkles) with their banners. The rules
 * are the website's (ui_components/effects.py, chat.py):
 *
 * - what happened before this screen opened the game is not news;
 * - an event first seen more than 15 s after it happened is skipped;
 * - a throw's effect waits 0.45 s for the dice to land;
 * - an effect that arrives while another plays waits for it to end, so two never overlap.
 *
 * No React Native imports here: tests/shows.test.ts runs this file in Node.
 */

import type { State } from './api';

export type Show = {
  /** Unique on a screen (an event's or a message's id, with its kind). */
  id: string;
  kind: 'reaction' | 'message' | 'effect';
  /** When it starts, on this device's clock (ms), and how long it stays. */
  startAt: number;
  ms: number;
  // A bubble: "🍀 **Ann → you** Lucky!", or "💬 **Ann** a message".
  emoji?: string;
  who?: string;
  label?: string;
  toYou?: boolean;
  // An effect and its banner.
  effect?: 'grand_fireworks' | 'fireworks' | 'sparkles';
  title?: string;
  text?: string;
};

/** What a screen has already taken in. One per game screen; `showsFor` keeps it up to date. */
export type Shown = {
  /** The latest event id and chat message id seen (null: the screen has seen no state yet). */
  events: number | null;
  chat: number | null;
  /** When the last effect scheduled so far ends (ms). */
  effectsEnd: number;
};

export const BUBBLE_MS = 3500;
export const EFFECT_MS = { grand_fireworks: 6000, fireworks: 4500, sparkles: 2800 };
export const DICE_LAND_MS = 450; // the dice's spin (components/Dice.tsx)
export const STALE_SECONDS = 15;
const MESSAGES_ANNOUNCED = 3; // of a burst of chat messages, the latest few get a bubble
const MESSAGE_SHOWN = 80; // characters of a message in its bubble

export function nothingShown(): Shown {
  return { events: null, chat: null, effectsEnd: 0 };
}

/**
 * What to play for a state a watcher was just handed (its `events` are new, its `chat` is
 * the whole chat): the new shows, with their start times. `shown` is brought up to date.
 */
export function showsFor(state: State, shown: Shown, now: number): Show[] {
  if (!state.seated) return []; // an invite: nothing of the game is on the screen yet
  const events = state.events ?? [];
  const chat = state.chat ?? [];
  const latestEvent = Math.max(shown.events ?? 0, ...events.map((e) => e.id));
  const latestMessage = Math.max(shown.chat ?? 0, ...chat.map((m) => m.id));
  if (shown.events === null || shown.chat === null) {
    // The screen has just opened the game (or taken its seat): what happened before is not news.
    shown.events = latestEvent;
    shown.chat = latestMessage;
    return [];
  }
  const shows: Show[] = [];
  for (const event of events) {
    if (event.id <= shown.events || state.now - event.at > STALE_SECONDS) continue;
    if (event.kind === 'reaction') {
      shows.push({
        id: `reaction-${event.id}`, kind: 'reaction', startAt: now, ms: BUBBLE_MS,
        emoji: event.emoji ?? '', who: event.who ?? '', label: event.label ?? event.reaction ?? '',
        toYou: event.to_you === true,
      });
    } else if (event.kind === 'effect') {
      // An effect this app does not know yet still has its banner: sparkles go with it.
      const effect = event.effect === 'grand_fireworks' || event.effect === 'fireworks' ? event.effect : 'sparkles';
      // A throw's effect starts as the dice land; a bonus at once (the move clears the dice).
      const startAt = Math.max(now + (event.what === 'BONUS' ? 0 : DICE_LAND_MS), shown.effectsEnd);
      shown.effectsEnd = startAt + EFFECT_MS[effect];
      shows.push({
        id: `effect-${event.id}`, kind: 'effect', startAt, ms: EFFECT_MS[effect], effect,
        title: event.title ?? '', text: event.text ?? '',
      });
    }
  }
  // Other players' new messages, so a phone that shows the dice still hears about them.
  const others = chat.filter((m) => m.id > (shown.chat ?? 0) && (state.local || m.seat !== state.you));
  for (const message of others.slice(-MESSAGES_ANNOUNCED)) {
    const text = message.text.length <= MESSAGE_SHOWN ? message.text : message.text.slice(0, MESSAGE_SHOWN - 1) + '…';
    shows.push({
      id: `message-${message.id}`, kind: 'message', startAt: now, ms: BUBBLE_MS,
      emoji: '💬', who: state.names[message.seat] ?? '?', label: text,
    });
  }
  shown.events = latestEvent;
  shown.chat = latestMessage;
  return shows;
}
