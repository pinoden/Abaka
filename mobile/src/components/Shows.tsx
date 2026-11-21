/**
 * What plays over the game: bubbles for reactions and chat messages at the top, and
 * effects (fireworks, sparkles) with a banner in the lower part of the screen, so the dice
 * stay in view. As on the web (ui_components/effects.py, style.py). Which ones play, and
 * when, is decided in lib/shows.ts.
 *
 * Nothing here takes a touch. With "reduce motion" switched on in the phone's settings,
 * an effect is its banner alone.
 */

import { useEffect, useState } from 'react';
import {
  AccessibilityInfo, Animated, Easing, Platform, StyleSheet, Text, useWindowDimensions, View,
} from 'react-native';

import type { Show } from '@/lib/shows';

import { colors } from './ui';

const NATIVE = Platform.OS !== 'web';
const COLORS = ['#F59E0B', '#EF4444', '#10B981', '#3B82F6', '#A855F7', '#EC4899', '#FBBF24'];
const BURST_MS = 1100;

// Each effect's bursts: where on the screen (left %, top %) and when (s after its start).
// Bigger fireworks come in three waves, with a flash and a rain of sparkles.
const LOOKS = {
  grand_fireworks: {
    spokes: 16, reach: 120, stars: 18,
    bursts: [[50, 40, 0], [20, 28, 0.15], [80, 26, 0.3], [32, 58, 1.0], [68, 55, 1.2], [50, 20, 1.4], [12, 50, 1.6],
      [88, 48, 1.6], [26, 34, 2.2], [74, 36, 2.4], [50, 62, 2.7], [40, 18, 3.0], [60, 30, 3.2]],
  },
  fireworks: {
    spokes: 14, reach: 100, stars: 0,
    bursts: [[20, 30, 0], [78, 24, 0.35], [50, 18, 0.8], [30, 55, 1.3], [70, 52, 1.7], [50, 38, 2.2]],
  },
  sparkles: { spokes: 10, reach: 56, stars: 0, bursts: [[35, 26, 0], [65, 22, 0.3]] },
};

export function Shows({ shows, onDone }: { shows: Show[]; onDone: (id: string) => void }) {
  const [calm, setCalm] = useState(false); // the phone asks for reduced motion
  useEffect(() => {
    let asked = true;
    AccessibilityInfo.isReduceMotionEnabled().then((on) => { if (asked) setCalm(on); }, () => {});
    return () => { asked = false; };
  }, []);
  return (
    <>
      {shows.filter((show) => show.kind === 'effect').map((show) => (
        <Effect key={show.id} show={show} calm={calm} onDone={onDone} />
      ))}
      <View style={styles.bubbles}>
        {shows.filter((show) => show.kind !== 'effect').map((show) => (
          <Bubble key={show.id} show={show} onDone={onDone} />
        ))}
      </View>
    </>
  );
}

/** Runs from 0 to 1 over the show's time on screen, starting when the show starts. */
function useTimeline(show: Show, onDone: (id: string) => void): Animated.Value {
  const [timeline] = useState(() => new Animated.Value(0));
  useEffect(() => {
    const running = Animated.sequence([
      Animated.delay(Math.max(0, show.startAt - Date.now())),
      Animated.timing(timeline, { toValue: 1, duration: show.ms, easing: Easing.linear, useNativeDriver: NATIVE }),
    ]);
    running.start(({ finished }) => { if (finished) onDone(show.id); });
    return () => running.stop();
    // A show never changes once made; onDone is the screen's own.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [show.id]);
  return timeline;
}

function Bubble({ show, onDone }: { show: Show; onDone: (id: string) => void }) {
  const timeline = useTimeline(show, onDone);
  const opacity = timeline.interpolate({ inputRange: [0, 0.06, 0.88, 1], outputRange: [0, 1, 1, 0] });
  const rise = timeline.interpolate({ inputRange: [0, 0.06, 1], outputRange: [-12, 0, 0] });
  return (
    <Animated.View testID="bubble" accessibilityLiveRegion="polite"
                   style={[styles.bubble, show.toYou && styles.bubbleToYou, { opacity, transform: [{ translateY: rise }] }]}>
      {show.emoji ? <Text style={styles.bubbleEmoji}>{show.emoji}</Text> : null}
      <Text style={styles.bubbleText} numberOfLines={2}>
        <Text style={styles.bubbleWho}>{show.who}</Text>{'  '}{show.label}
      </Text>
    </Animated.View>
  );
}

function Effect({ show, calm, onDone }: { show: Show; calm: boolean; onDone: (id: string) => void }) {
  const timeline = useTimeline(show, onDone);
  const { width, height } = useWindowDimensions();
  const look = LOOKS[show.effect ?? 'sparkles'];
  const grand = show.effect === 'grand_fireworks';
  const part = (seconds: number) => Math.min(1, (seconds * 1000) / show.ms); // a moment as a share of the timeline
  const banner = timeline.interpolate({ inputRange: [0, part(0.25), 0.9, 1], outputRange: [0, 1, 1, 0] });
  const grow = timeline.interpolate({ inputRange: [0, part(0.25), 1], outputRange: [0.7, 1, 1] });
  return (
    <View testID={`effect-${show.effect}`} style={StyleSheet.absoluteFill}>
      {grand && !calm ? (
        <Animated.View style={[StyleSheet.absoluteFill, styles.flash, {
          opacity: timeline.interpolate({ inputRange: [0, part(0.12), part(0.7), 1], outputRange: [0, 0.4, 0, 0] }),
        }]} />
      ) : null}
      {calm ? null : look.bursts.map(([x, y, delay], b) => {
        const from = part(delay);
        const to = Math.min(1, from + BURST_MS / show.ms);
        const out = timeline.interpolate({ inputRange: [from, to], outputRange: [0, 1], extrapolate: 'clamp' });
        const glow = timeline.interpolate({
          inputRange: [from, from + (to - from) * 0.1, from + (to - from) * 0.7, to],
          outputRange: [0, 1, 1, 0],
          extrapolate: 'clamp',
        });
        return (
          <View key={b} style={{ position: 'absolute', left: (width * x) / 100, top: (height * y) / 100 }}>
            {Array.from({ length: look.spokes }, (_, k) => {
              const angle = (2 * Math.PI * k) / look.spokes;
              return (
                <Animated.View key={k} style={[styles.spark, {
                  backgroundColor: COLORS[(b + k) % COLORS.length],
                  opacity: glow,
                  transform: [
                    { translateX: out.interpolate({ inputRange: [0, 1], outputRange: [0, Math.cos(angle) * look.reach] }) },
                    { translateY: out.interpolate({ inputRange: [0, 1], outputRange: [0, Math.sin(angle) * look.reach + 18] }) },
                  ],
                }]} />
              );
            })}
          </View>
        );
      })}
      {calm ? null : Array.from({ length: look.stars }, (_, k) => {
        const from = part(0.3 + ((k * 0.41) % 3.2));
        const to = Math.min(1, from + part(2.2));
        return (
          <Animated.Text key={k} style={[styles.star, {
            left: `${(k * 37 + 5) % 100}%`,
            fontSize: 12 + ((k * 7) % 12),
            color: COLORS[k % COLORS.length],
            opacity: timeline.interpolate({
              inputRange: [from, from + (to - from) * 0.15, to], outputRange: [0, 1, 0], extrapolate: 'clamp',
            }),
            transform: [{
              translateY: timeline.interpolate({
                inputRange: [from, to], outputRange: [-20, height * 0.8], extrapolate: 'clamp',
              }),
            }],
          }]}>✦</Animated.Text>
        );
      })}
      <View style={styles.bannerPlace}>
        <Animated.View testID="effect-banner" accessibilityLiveRegion="polite"
                       style={[styles.banner, grand && styles.bannerGrand, { opacity: banner, transform: [{ scale: grow }] }]}>
          <Text style={[styles.bannerTitle, grand && styles.bannerTitleGrand]}>{show.title}</Text>
          {show.text ? <Text style={styles.bannerText}>{show.text}</Text> : null}
        </Animated.View>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  // At most a few at once: a burst of reactions from a full table must not cover the dice.
  bubbles: { position: 'absolute', top: 8, left: 12, right: 12, alignItems: 'center', gap: 6, maxHeight: 170, overflow: 'hidden' },
  bubble: {
    flexDirection: 'row', alignItems: 'center', gap: 8, maxWidth: 420,
    backgroundColor: '#FFFFFF', borderRadius: 999, borderWidth: 1, borderColor: colors.line,
    paddingVertical: 8, paddingHorizontal: 14,
    shadowColor: '#1C2033', shadowOpacity: 0.16, shadowRadius: 10, shadowOffset: { width: 0, height: 4 }, elevation: 6,
  },
  bubbleToYou: { borderColor: colors.accent, backgroundColor: colors.accentSoft },
  bubbleEmoji: { fontSize: 22 },
  bubbleText: { flexShrink: 1, fontSize: 15, color: colors.text },
  bubbleWho: { fontWeight: '700' },
  flash: { backgroundColor: '#FDE68A' },
  spark: { position: 'absolute', width: 7, height: 7, borderRadius: 4 },
  star: { position: 'absolute', top: 0 },
  bannerPlace: { position: 'absolute', left: 16, right: 16, bottom: '14%', alignItems: 'center' },
  banner: {
    alignItems: 'center', backgroundColor: '#FFFFFF', borderRadius: 18, borderWidth: 2, borderColor: '#F0C36A',
    paddingVertical: 12, paddingHorizontal: 22,
    shadowColor: '#1C2033', shadowOpacity: 0.2, shadowRadius: 16, shadowOffset: { width: 0, height: 6 }, elevation: 8,
  },
  bannerGrand: { paddingVertical: 16, paddingHorizontal: 28, borderColor: colors.last },
  bannerTitle: { fontSize: 22, fontWeight: '800', color: colors.gold, textAlign: 'center' },
  bannerTitleGrand: { fontSize: 30 },
  bannerText: { fontSize: 15, color: colors.text, textAlign: 'center', marginTop: 2 },
});
