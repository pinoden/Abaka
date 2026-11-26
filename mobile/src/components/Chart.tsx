/**
 * The scores by move, under the score table, as on the web (ui_components/chart.py): a line
 * per player, like the chart of a chess game (a tester, 2026-11-26). The points come from the
 * server (`game.history`).
 *
 * Drawn with plain views, each piece of a line a thin bar turned to its slope, so the app
 * needs no drawing package (Expo Go has only its bundled native modules). At most 225 moves,
 * so a few hundred small views.
 */

import { useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import type { Game } from '@/lib/api';
import { useApp } from '@/lib/app';

import { colors } from './ui';

// One colour per seat, the same on the web (ui_components/chart.py).
export const SEAT_COLORS = ['#4F46E5', '#F59E0B', '#10B981', '#E5484D', '#A855F7'];
const HEIGHT = 130;
const LABELS_W = 40;
const PAD = 6;

export function Chart({ game, you }: { game: Game; you: number | null }) {
  const { t } = useApp();
  const [width, setWidth] = useState(0);
  const history = game.history ?? [];
  if (history.length < 2) return null;
  const values = history.flatMap((point) => point.totals);
  const low = Math.min(0, ...values);
  const high = Math.max(0, ...values) === low ? low + 1 : Math.max(0, ...values);
  const first = history[0].move;
  const last = history[history.length - 1].move;
  const x = (move: number) => ((move - first) * width) / (last - first);
  const y = (value: number) => PAD + ((high - value) * (HEIGHT - 2 * PAD)) / (high - low);
  const seats = game.players.map((_, seat) => seat).filter((seat) => seat !== you);
  if (you !== null) seats.push(you); // the viewer's line on top
  const levels = [...new Set([low, 0, high])];

  return (
    <View testID="score-chart" style={styles.chart}>
      <Text style={styles.title}>{t('Scores by move')}</Text>
      <View style={styles.plotRow}>
        <View style={{ width: LABELS_W, height: HEIGHT }}>
          {levels.map((value) => (
            <Text key={value} style={[styles.yLabel, { top: y(value) - 7 }]}>{value}</Text>
          ))}
        </View>
        <View style={styles.plot} onLayout={(e) => setWidth(e.nativeEvent.layout.width)}>
          {levels.map((value) => (
            <View key={value} style={[styles.level, value === 0 && styles.zero, { top: y(value) }]} />
          ))}
          {width > 0 ? seats.map((seat) => history.slice(1).map((point, i) => {
            const before = history[i];
            const x1 = x(before.move);
            const y1 = y(before.totals[seat]);
            const x2 = x(point.move);
            const y2 = y(point.totals[seat]);
            const length = Math.hypot(x2 - x1, y2 - y1);
            const thick = seat === you ? 3 : 2;
            return (
              <View key={`${seat}-${i}`} style={{
                position: 'absolute', left: (x1 + x2) / 2 - length / 2, top: (y1 + y2) / 2 - thick / 2,
                width: length + 1, height: thick, borderRadius: thick / 2,
                backgroundColor: SEAT_COLORS[seat % SEAT_COLORS.length],
                transform: [{ rotate: `${Math.atan2(y2 - y1, x2 - x1)}rad` }],
              }} />
            );
          })) : null}
        </View>
      </View>
      <View style={[styles.xLabels, { marginLeft: LABELS_W }]}>
        <Text style={styles.axis}>{first}</Text>
        <Text style={styles.axis}>{t('move {n}', { n: last })}</Text>
      </View>
      <View style={styles.keys}>
        {game.players.map((p, seat) => (
          <View key={seat} style={styles.key}>
            <View style={[styles.swatch, { backgroundColor: SEAT_COLORS[seat % SEAT_COLORS.length] }]} />
            <Text numberOfLines={1} style={styles.keyText}>
              {seat === you ? t('You') : p.name} <Text style={styles.keyTotal}>{history[history.length - 1].totals[seat]}</Text>
            </Text>
          </View>
        ))}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  chart: { marginTop: 14, paddingTop: 10, borderTopWidth: 1, borderTopColor: colors.line },
  title: { fontSize: 11, fontWeight: '700', color: colors.muted, textTransform: 'uppercase', marginBottom: 4 },
  plotRow: { flexDirection: 'row' },
  plot: { flex: 1, height: HEIGHT, overflow: 'hidden' },
  level: { position: 'absolute', left: 0, right: 0, height: 1, backgroundColor: '#EEF0F6' },
  zero: { backgroundColor: '#D9DCE8' },
  yLabel: { position: 'absolute', right: 6, fontSize: 11, color: colors.faint },
  xLabels: { flexDirection: 'row', justifyContent: 'space-between', marginTop: 2 },
  axis: { fontSize: 11, color: colors.faint },
  keys: { flexDirection: 'row', flexWrap: 'wrap', columnGap: 14, rowGap: 4, marginTop: 6 },
  key: { flexDirection: 'row', alignItems: 'center', gap: 6, maxWidth: '100%' },
  swatch: { width: 14, height: 3, borderRadius: 2 },
  keyText: { fontSize: 12, color: colors.text, flexShrink: 1 },
  keyTotal: { fontWeight: '700' },
});
