/**
 * The races for the shared bonuses, at the foot of the play card, as on the web
 * (ui_components/races.py): the cells each player has left in column I and II, and the rows
 * where two or more players are one cell from the bonus. On a phone the board is below the
 * dice, so this saves scrolling down and counting.
 *
 * The server works it all out and sends the words (`state.races`, abaka/races.py); this only
 * lays them out.
 */

import { StyleSheet, Text, View } from 'react-native';

import type { Races as RacesData } from '@/lib/api';

import { colors } from './ui';

export function Races({ races, you }: { races: RacesData; you: number | null }) {
  return (
    <View testID="races" style={styles.box}>
      {races.columns.length ? (
        <View style={styles.table}>
          <View style={styles.line}>
            <Text style={[styles.label, styles.title]}>{races.title}</Text>
            {races.heads.map((head, seat) => (
              <Text key={seat} numberOfLines={1} style={[styles.cell, styles.head, seat === you && styles.you]}>
                {head}
              </Text>
            ))}
          </View>
          {races.columns.map((column) => {
            const fewest = Math.min(...column.left);
            return (
              <View key={column.column} testID={`race-column-${column.column}`} style={styles.line}>
                <Text style={styles.label}>{column.label}</Text>
                {column.left.map((left, seat) => (
                  <Text key={seat} testID={`race-left-${column.column}-${seat}`}
                        style={[styles.cell, styles.count, left === fewest && styles.lead,
                                !column.open[seat] && styles.off]}>
                    {column.open[seat] ? `${left}` : `${left} ✕`}
                  </Text>
                ))}
              </View>
            );
          })}
        </View>
      ) : null}
      {races.rows.map((row) => (
        <View key={row.rows.join()} style={styles.row}>
          <Text testID="race-row" style={styles.rowText}>{row.text}</Text>
        </View>
      ))}
      {races.note ? <Text style={styles.note}>{races.note}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  box: { gap: 6, backgroundColor: colors.background, borderRadius: 12, padding: 10 },
  table: { gap: 2 },
  line: { flexDirection: 'row', alignItems: 'center' },
  label: { width: '40%', fontSize: 14, fontWeight: '600', color: colors.muted },
  title: { fontSize: 11, fontWeight: '700', color: colors.faint, textTransform: 'uppercase', letterSpacing: 0.6 },
  cell: { flex: 1, textAlign: 'center' },
  head: { fontSize: 12, fontWeight: '700', color: colors.muted },
  you: { color: colors.accent },
  count: { fontSize: 14, color: colors.text, fontVariant: ['tabular-nums'] },
  lead: { fontWeight: '800' },
  off: { color: colors.faint },
  row: { backgroundColor: colors.goldSoft, borderRadius: 9, paddingHorizontal: 9, paddingVertical: 6 },
  rowText: { fontSize: 14, fontWeight: '600', color: '#8A5A00' },
  note: { fontSize: 12, color: colors.faint, lineHeight: 16 },
});
