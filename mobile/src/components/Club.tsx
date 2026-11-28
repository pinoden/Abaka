/**
 * The parts of a club on the app's screens, as on the web (abaka_ui.py): its table, its
 * latest games, the rating changes after a club game, and the club's players offered as
 * names. The rows are worked out in lib/clubs.ts.
 *
 * Names are players' own text: always plain <Text>.
 */

import { Pressable, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import type { ClubGame, ClubMember, ClubResult } from '@/lib/api';
import { useApp } from '@/lib/app';
import { type Change, gameLine, resultRows, tableRows } from '@/lib/clubs';

import { Card, colors, Muted, Title } from './ui';

const WIDE = 480; // from this width on, the table also shows the average and the best score

/** ▲12 in green, ▼3 in red, = in grey. */
export function ChangeText({ change }: { change: Change }) {
  const style = change.trend === 'up' ? styles.up : change.trend === 'down' ? styles.down : styles.same;
  return <Text style={style}>{change.text}</Text>;
}

/**
 * The club's players, to tap instead of typing a name. `on`: whether a name is in use
 * (it is shown picked); a tap calls `onPick` with it.
 */
export function PlayerChips({ names, on, onPick, hint }: {
  names: string[];
  on: (name: string) => boolean;
  onPick: (name: string) => void;
  hint: string;
}) {
  if (names.length === 0) return null;
  return (
    <View style={styles.chipsBox}>
      <Muted>{hint}</Muted>
      <View style={styles.chips}>
        {names.map((name) => {
          const picked = on(name);
          return (
            <Pressable
              key={name}
              testID="club-player"
              accessibilityRole="button"
              accessibilityState={{ selected: picked }}
              aria-pressed={picked}
              onPress={() => onPick(name)}
              style={({ pressed }) => [styles.chip, picked && styles.chipPicked, pressed && styles.pressed]}>
              <Text style={[styles.chipText, picked && styles.chipTextPicked]} numberOfLines={1}>{name}</Text>
            </Pressable>
          );
        })}
      </View>
    </View>
  );
}

export function ClubTable({ members }: { members: ClubMember[] }) {
  const { t } = useApp();
  const wide = useWindowDimensions().width >= WIDE;
  if (members.length === 0) {
    return (
      <Card testID="club-table">
        <Title>{t('Table')}</Title>
        <Muted>{t('No games yet. Start one, and the table fills in when it ends.')}</Muted>
      </Card>
    );
  }
  return (
    <Card testID="club-table">
      <Title>{t('Table')}</Title>
      <Muted>{t('Everyone starts at 1000. Beating a stronger player earns more.')}</Muted>
      <View>
        <View style={[styles.row, styles.headRow]}>
          <Text style={[styles.rank, styles.head]}>#</Text>
          <Text style={[styles.name, styles.head]}>{t('Player')}</Text>
          <Text style={[styles.rating, styles.head]}>{t('Rating')}</Text>
          <Text style={[styles.number, styles.head]} numberOfLines={1}>{t('Games')}</Text>
          <Text style={[styles.number, styles.head]} numberOfLines={1}>{t('Wins')}</Text>
          {wide ? <Text style={[styles.number, styles.head]} numberOfLines={1}>{t('Average')}</Text> : null}
          {wide ? <Text style={[styles.number, styles.head]} numberOfLines={1}>{t('Best')}</Text> : null}
        </View>
        {tableRows(members).map((row) => (
          <View key={row.name} testID="club-row" style={styles.row}>
            <Text style={styles.rank}>{row.rank}</Text>
            <Text style={styles.name} numberOfLines={1}>{row.name}</Text>
            <Text style={styles.rating}>
              <Text style={styles.bold}>{row.rating}</Text> <ChangeText change={row.change} />
            </Text>
            <Text style={styles.number}>{row.games}</Text>
            <Text style={styles.number}>{row.wins}</Text>
            {wide ? <Text style={styles.number}>{row.average}</Text> : null}
            {wide ? <Text style={styles.number}>{row.best}</Text> : null}
          </View>
        ))}
      </View>
    </Card>
  );
}

export function LatestGames({ games }: { games: ClubGame[] }) {
  const { t } = useApp();
  if (games.length === 0) return null;
  return (
    <Card testID="club-games">
      <Title>{t('Latest games')}</Title>
      {games.map((game) => {
        const line = gameLine(game);
        return (
          <Text key={game.id} testID="club-game" style={styles.gameLine}>
            <Text style={styles.day}>{line.day}  </Text>
            {line.players.map((p, i) => (
              <Text key={i} style={p.won ? styles.bold : null}>{i ? ' · ' : ''}{p.name} {p.score}</Text>
            ))}
          </Text>
        );
      })}
    </Card>
  );
}

/** On the results of a club game: each player's club rating now, and how it moved. */
export function ClubRatings({ result }: { result: ClubResult }) {
  const { t } = useApp();
  return (
    <View testID="club-result" style={styles.result}>
      <Text style={styles.resultTitle}>{t('Club rating · {name}', { name: result.club })}</Text>
      {resultRows(result).map((row, i) => (
        <View key={i} style={styles.resultRow}>
          <Text style={styles.resultName} numberOfLines={1}>{row.name}</Text>
          <Text style={styles.resultRating}>
            <Text style={styles.bold}>{row.rating}</Text> <ChangeText change={row.change} />
          </Text>
        </View>
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  up: { color: colors.green, fontWeight: '600' },
  down: { color: colors.red, fontWeight: '600' },
  same: { color: colors.faint },
  bold: { fontWeight: '700' },
  chipsBox: { gap: 6 },
  chips: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  chip: {
    borderRadius: 999, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.card,
    paddingHorizontal: 12, paddingVertical: 7, maxWidth: '100%', minHeight: 40, justifyContent: 'center',
  },
  chipPicked: { backgroundColor: colors.accentSoft, borderColor: colors.accent },
  chipText: { fontSize: 14, color: colors.text },
  chipTextPicked: { color: colors.accent, fontWeight: '600' },
  pressed: { opacity: 0.7 },
  row: { flexDirection: 'row', alignItems: 'center', minHeight: 32, gap: 6 },
  headRow: { borderBottomWidth: 1, borderBottomColor: colors.line },
  head: { fontSize: 11, color: colors.muted, fontWeight: '600' },
  rank: { width: 26, fontSize: 15, color: colors.text, textAlign: 'center' },
  name: { flex: 1, fontSize: 15, color: colors.text },
  rating: { width: 82, fontSize: 14, color: colors.text },
  number: { width: 50, fontSize: 14, color: colors.text, textAlign: 'right' },
  gameLine: { fontSize: 14, color: colors.text, lineHeight: 21 },
  day: { color: colors.faint },
  result: { gap: 4, backgroundColor: colors.goldSoft, borderRadius: 10, padding: 10 },
  resultTitle: { fontSize: 14, fontWeight: '700', color: colors.gold },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between', gap: 8 },
  resultName: { flexShrink: 1, fontSize: 15, color: colors.text },
  resultRating: { fontSize: 15, color: colors.text },
});
