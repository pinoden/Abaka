/**
 * Reactions, as on the web (ui_components/effects.py): a row of buttons every seated
 * player of an online game has ("Lucky! 🍀", "GG 🤝"...). With three or more players, one
 * can be aimed at a single player. Every screen shows it as a bubble (Shows.tsx).
 *
 * The buttons come from the server (`info.reaction_list`), so a reaction it adds later
 * appears here by itself.
 */

import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import type { State } from '@/lib/api';
import { useApp } from '@/lib/app';
import { errorText } from '@/lib/errors';

import { Choice, colors, Muted } from './ui';

const EVERYONE = -1;
const NOTE_MS = 2500;

export function ReactionBar({ state, react }: {
  state: State;
  /** Send a reaction to everyone (`to` null) or to one seat; rejects with the server's refusal. */
  react: (reaction: string, to: number | null) => Promise<unknown>;
}) {
  const { t, info } = useApp();
  const [to, setTo] = useState(EVERYONE);
  const [note, setNote] = useState<string | null>(null);
  const others = state.names.map((name, seat) => ({ name, seat })).filter((p) => p.seat !== state.you);
  // Until the server's list arrives, the reactions it names, without their emoji.
  const buttons = info?.reaction_list ?? (info?.reactions ?? []).map((id) => ({ id, emoji: '', label: id }));

  useEffect(() => {
    if (!note) return;
    const timer = setTimeout(() => setNote(null), NOTE_MS);
    return () => clearTimeout(timer);
  }, [note]);

  const send = (reaction: string) => {
    const aimed = others.some((p) => p.seat === to) ? to : null;
    // Too soon after the last one: the server says so, and nothing was sent.
    react(reaction, aimed).catch((e) => setNote(errorText(e, t)));
  };

  if (buttons.length === 0) return null;
  return (
    <View testID="reactions" style={styles.box}>
      {others.length >= 2 ? (
        <Choice
          testID="react-to"
          value={others.some((p) => p.seat === to) ? to : EVERYONE}
          onChange={setTo}
          options={[{ value: EVERYONE, label: t('Everyone') }, ...others.map((p) => ({ value: p.seat, label: p.name }))]}
        />
      ) : null}
      <View style={styles.row}>
        {buttons.map((button) => (
          <Pressable
            key={button.id}
            testID={`react-${button.id}`}
            accessibilityRole="button"
            accessibilityLabel={button.label}
            onPress={() => send(button.id)}
            style={({ pressed }) => [styles.button, pressed && styles.pressed]}>
            <Text style={styles.label}>{button.emoji ? `${button.emoji} ${button.label}` : button.label}</Text>
          </Pressable>
        ))}
      </View>
      {note ? <Muted>{note}</Muted> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: 8 },
  row: { flexDirection: 'row', flexWrap: 'wrap', gap: 6 },
  button: {
    borderRadius: 999, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.card,
    paddingHorizontal: 10, paddingVertical: 6,
  },
  pressed: { opacity: 0.6 },
  label: { fontSize: 13, color: colors.text },
});
