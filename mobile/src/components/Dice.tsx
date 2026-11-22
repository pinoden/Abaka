/**
 * Dice, drawn like the web's (ui_components/style.py): white with dark pips, the joker
 * dark with gold pips, the pips where the web puts them (src/lib/dice.ts). A picked die is
 * lifted and marked ↻. Dice that were just rolled spin for 0.45 s, as on the web (dice.py).
 */

import { useEffect, useState } from 'react';
import { Animated, Easing, Platform, Pressable, StyleSheet, Text, View } from 'react-native';

import type { Die } from '@/lib/api';
import { pips } from '@/lib/dice';

import { colors } from './ui';

const SPIN_MS = 450;

export function DieFace({ die, size, picked, spinKey, onPress, label, testID }: {
  die: Die;
  size: number;
  picked?: boolean;
  /** Changes when this die was rolled again: it spins. */
  spinKey?: string | number | null;
  onPress?: () => void;
  label?: string;
  testID?: string;
}) {
  const [spin] = useState(() => new Animated.Value(1)); // 1: at rest
  useEffect(() => {
    if (spinKey == null) return;
    spin.setValue(0);
    Animated.timing(spin, {
      toValue: 1,
      duration: SPIN_MS,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: Platform.OS !== 'web',
    }).start();
  }, [spinKey, spin]);

  const border = picked ? 3 : 1.5;
  const face = (
    <Animated.View
      style={[
        styles.die,
        {
          width: size,
          height: size,
          borderRadius: size * 0.2,
          backgroundColor: die.joker ? colors.joker : '#FFFFFF',
          borderColor: picked ? colors.accent : die.joker ? colors.joker : '#DADDE8',
          borderWidth: border,
          transform: [
            { translateY: picked ? -6 : 0 },
            { rotate: spin.interpolate({ inputRange: [0, 1], outputRange: ['-200deg', '0deg'] }) },
          ],
        },
      ]}>
      {pips(die.value, size, border).map((pip, i) => (
        <View
          key={i}
          style={{
            position: 'absolute',
            width: pip.size,
            height: pip.size,
            borderRadius: pip.size / 2,
            backgroundColor: die.joker ? colors.jokerPip : colors.joker,
            top: pip.top,
            left: pip.left,
          }}
        />
      ))}
      {picked ? <Text style={[styles.mark, { fontSize: size * 0.22 }]}>↻</Text> : null}
    </Animated.View>
  );
  if (!onPress) {
    return <View testID={testID} accessibilityLabel={label}>{face}</View>;
  }
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      accessibilityLabel={label}
      accessibilityState={{ selected: !!picked }}
      onPress={onPress}
      hitSlop={4}>
      {face}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  die: { overflow: 'hidden' },
  mark: { position: 'absolute', right: 2, top: -1, color: colors.accent, fontWeight: '700' },
});
