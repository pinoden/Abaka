/**
 * What a phone lets the hand feel: a short knock when the dice are thrown, a longer one
 * when fireworks play. Nothing on the web, and never an error: a phone without a motor, or
 * with touch feedback switched off, just stays still.
 */

import * as Haptics from 'expo-haptics';
import { Platform } from 'react-native';

const quiet = () => { /* no motor, or feedback switched off */ };

/** The dice leave the hand (Throw, Roll dice, Reroll). */
export function feelThrow(): void {
  if (Platform.OS === 'web') return;
  try {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(quiet);
  } catch {
    quiet();
  }
}

/** Fireworks, sparkles or tears begin on this screen. */
export function feelEffect(): void {
  if (Platform.OS === 'web') return;
  try {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(quiet);
  } catch {
    quiet();
  }
}
