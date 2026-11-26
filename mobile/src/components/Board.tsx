/**
 * The score table, as on the web (ui_components/scoreboard.py): each player's three cells
 * and the row bonus for every row, the column bonuses and the totals. Row names stay put
 * while the players' columns scroll sideways on a narrow phone.
 *
 * Cells as the server gives them (docs/API.md, `game`): null is empty, "X" is a settled
 * School cell (✓) or a crossed-out one (✕), and in a bonus cell a lost bonus (✕).
 */

import { type ComponentRef, useEffect, useRef } from 'react';
import { ScrollView, StyleSheet, Text, useWindowDimensions, View } from 'react-native';

import type { Cell, Differences, Game, Move } from '@/lib/api';
import { useApp } from '@/lib/app';
import { BONUS_W, CELL_W, cellWidths, COLUMN_PADDING, GAP, NAME_W } from '@/lib/board';

import { colors } from './ui';

const ROW_H = 30;
const HEAD_H = 56;
const SUB_H = 22;
const SECTION_H = 24;
const DIFF_W = 38;

const isSchool = (row: string) => row.startsWith('SCHOOL_');

export function Board({ game, you, target, differences }: {
  game: Game;
  /** This device's seat online (marked "You"), null on one device. */
  you: number | null;
  /** The move being chosen: its cell and the bonus cells it gives up are previewed. */
  target: Move | null;
  /** The difference row by row, as a last column (null: not shown). On a narrow phone it scrolls into view. */
  differences?: Differences | null;
}) {
  const { t, rowName } = useApp();
  const players = game.players;
  const { width: screenWidth } = useWindowDimensions();
  const { cell: cw, bonus: bw } = cellWidths(screenWidth, players.length);
  const cellW = { width: cw };
  const bonusW = { width: bw };
  const rows = Object.keys(players[0]?.rows ?? {});
  const school = rows.filter(isSchool);
  const combos = rows.filter((row) => !isSchool(row));
  const over = game.winners.length > 0;
  const active = over ? null : game.current;
  const last = game.last_move;
  // Switched on, the column of differences is scrolled into view (on a narrow phone it is past the edge).
  const scroller = useRef<ComponentRef<typeof ScrollView>>(null);
  const showing = !!differences;
  useEffect(() => {
    if (showing) scroller.current?.scrollToEnd({ animated: true });
  }, [showing]);

  const nameColumn = (
    <View style={{ width: NAME_W }}>
      <View style={{ height: HEAD_H + SUB_H }} />
      <Text numberOfLines={1} style={styles.section}>{t('School')}</Text>
      {school.map((row) => <Text key={row} numberOfLines={1} style={styles.rowName}>{rowName(row)}</Text>)}
      <Text numberOfLines={1} style={styles.section}>{t('Combinations')}</Text>
      {combos.map((row) => <Text key={row} numberOfLines={1} style={styles.rowName}>{rowName(row)}</Text>)}
      <Text numberOfLines={1} style={styles.section}>{t('Bonuses & total')}</Text>
      <Text numberOfLines={1} style={styles.rowName}>{t('Column bonus')}</Text>
      <Text style={[styles.rowName, styles.total]}>{t('Total')}</Text>
    </View>
  );

  const playerColumn = (seat: number) => {
    const p = players[seat];
    const on = seat === active;
    const aimed = on && target ? target : null;
    const cells = (row: string) => (
      <View key={row} style={styles.row}>
        {[0, 1, 2].map((slot) => {
          const isLast = last !== null && last.seat === seat && last.row === row && last.slot === slot;
          if (aimed && aimed.row === row && aimed.slot === slot) {
            return <Text key={slot} style={[styles.cell, cellW, styles.target]}>{aimed.preview}</Text>;
          }
          return <CellText key={slot} value={p.rows[row][slot]} school={isSchool(row)} last={isLast} width={cw} />;
        })}
        {aimed && aimed.row === row && aimed.bonus_lost
          ? <Text style={[styles.bonus, bonusW, styles.target]}>✕</Text>
          : <BonusText value={p.rows[row][3]} width={bw} />}
      </View>
    );
    return (
      <View key={seat} testID={`board-player-${seat}`} style={[styles.player, on && styles.activePlayer]}>
        <View style={[styles.head, { width: 3 * cw + bw }]}>
          <Text numberOfLines={1} style={[styles.playerName, on && styles.activeText]}>
            {on ? '● ' : ''}{p.name}
          </Text>
          {seat === you ? <Text style={styles.you}>{t('You')}</Text> : null}
          <Text style={styles.meta}>{t('{score} pts', { score: p.total })}</Text>
          <Text style={[styles.meta, p.school_balance < 0 && styles.negative]}>
            {t('balance {balance}', { balance: p.school_balance })}
          </Text>
        </View>
        <View style={[styles.row, { height: SUB_H }]}>
          {['I', 'II', 'III'].map((c) => <Text key={c} style={[styles.cell, cellW, styles.sub]}>{c}</Text>)}
          <Text style={[styles.bonus, bonusW, styles.sub]}>★</Text>
        </View>
        <View style={{ height: SECTION_H }} />
        {school.map(cells)}
        <View style={{ height: SECTION_H }} />
        {combos.map(cells)}
        <View style={{ height: SECTION_H }} />
        <View style={styles.row}>
          {p.column_bonus.map((value, column) =>
            aimed && aimed.column_bonus_lost && aimed.slot === column
              ? <Text key={column} style={[styles.cell, cellW, styles.target]}>✕</Text>
              : <BonusText key={column} value={value} width={cw} narrow />)}
          <View style={bonusW} />
        </View>
        <Text style={[styles.cell, styles.total, { width: 3 * cw + bw }]}>{p.total}</Text>
      </View>
    );
  };

  const diffColumn = differences ? (
    <View testID="board-differences" style={{ width: DIFF_W }}>
      <Text accessibilityLabel={differences.hint} style={[styles.diffHead, { height: HEAD_H + SUB_H, lineHeight: HEAD_H + SUB_H }]}>
        {differences.title}
      </Text>
      <View style={{ height: SECTION_H }} />
      {school.map((row) => <DiffText key={row} value={differences.rows[row] ?? null} />)}
      <View style={{ height: SECTION_H }} />
      {combos.map((row) => <DiffText key={row} value={differences.rows[row] ?? null} />)}
      <View style={{ height: SECTION_H }} />
      <DiffText value={players.some((p) => p.column_bonus.some((v) => v !== null)) ? differences.columns : null} />
      <DiffText value={differences.total} total />
    </View>
  ) : null;

  return (
    <View testID="board" style={styles.board}>
      {nameColumn}
      <ScrollView ref={scroller} horizontal showsHorizontalScrollIndicator={players.length > 2 || !!differences}>
        <View style={styles.players}>{players.map((_, seat) => playerColumn(seat))}{diffColumn}</View>
      </ScrollView>
    </View>
  );
}

/** One row's difference: +12 in green, −8 in red, 0 in grey, nothing while nobody wrote there. */
function DiffText({ value, total }: { value: number | null; total?: boolean }) {
  const text = value === null ? '' : value > 0 ? `+${value}` : value < 0 ? `−${-value}` : '0';
  return (
    <Text numberOfLines={1} style={[styles.diff, total && styles.diffTotal,
      value !== null && value > 0 && styles.diffUp, value !== null && value < 0 && styles.negative]}>
      {text}
    </Text>
  );
}

function CellText({ value, school, last, width }: { value: Cell; school: boolean; last: boolean; width: number }) {
  let text = '';
  let style: object | null = null;
  if (value === 'X') {
    text = school ? '✓' : '✕';
    style = school ? styles.done : styles.crossed;
  } else if (value !== null) {
    text = String(value);
    style = value < 0 ? styles.negative : null;
  }
  return <Text numberOfLines={1} style={[styles.cell, { width }, style, last && styles.last]}>{text}</Text>;
}

function BonusText({ value, width, narrow }: { value: Cell; width: number; narrow?: boolean }) {
  const style = [narrow ? styles.cell : styles.bonus, { width }];
  if (value === null) return <Text style={style} />;
  if (value === 'X') return <Text style={[style, styles.crossed]}>✕</Text>;
  return <Text style={[style, styles.bonusValue]}>{value}</Text>;
}

/** "Last move: Bob scored 23 in Full house", as under the web's board. */
export function lastMoveText(game: Game, you: number | null,
                             t: (text: string, values?: Record<string, string | number>) => string,
                             rowName: (row: string) => string): string | null {
  const last = game.last_move;
  if (!last) return null;
  const value = game.players[last.seat].rows[last.row][last.slot];
  const name = rowName(last.row);
  let what: string;
  if (isSchool(last.row)) {
    what = value === 'X'
      ? t('wrote {name} (exactly three)', { name })
      : t('wrote {name} (balance now {value})', { name, value: String(value) });
  } else if (value === 'X') {
    what = t('crossed out {name}', { name });
  } else {
    what = t('scored {value} in {name}', { value: String(value), name });
  }
  const who = last.seat === you ? t('You') : game.players[last.seat].name;
  return t('Last move: {who} {what}', { who, what });
}

const styles = StyleSheet.create({
  board: { flexDirection: 'row' },
  players: { flexDirection: 'row', gap: GAP },
  player: { borderRadius: 10, paddingHorizontal: COLUMN_PADDING },
  activePlayer: { backgroundColor: colors.accentSoft },
  head: { height: HEAD_H, width: 3 * CELL_W + BONUS_W, justifyContent: 'center', paddingHorizontal: 2 },
  playerName: { fontSize: 14, fontWeight: '700', color: colors.text },
  activeText: { color: colors.accent },
  you: { fontSize: 11, color: colors.accent, fontWeight: '600' },
  meta: { fontSize: 11, color: colors.muted },
  section: {
    height: SECTION_H,
    fontSize: 11,
    fontWeight: '700',
    color: colors.muted,
    paddingTop: 8,
  },
  row: { flexDirection: 'row', height: ROW_H, alignItems: 'center' },
  rowName: { height: ROW_H, lineHeight: ROW_H, fontSize: 13, color: colors.text, paddingRight: 4 },
  cell: {
    width: CELL_W,
    height: ROW_H - 4,
    lineHeight: ROW_H - 4,
    marginVertical: 2,
    textAlign: 'center',
    fontSize: 13,
    color: colors.text,
    borderRadius: 6,
    overflow: 'hidden',
  },
  bonus: {
    width: BONUS_W,
    height: ROW_H - 4,
    lineHeight: ROW_H - 4,
    marginVertical: 2,
    textAlign: 'center',
    fontSize: 13,
    color: colors.muted,
    backgroundColor: '#F1F2FA',
    borderRadius: 6,
    overflow: 'hidden',
  },
  bonusValue: { color: colors.gold, fontWeight: '700' },
  sub: { height: SUB_H, lineHeight: SUB_H, fontSize: 11, color: colors.faint, backgroundColor: 'transparent' },
  done: { color: colors.green, fontWeight: '700' },
  crossed: { color: colors.faint },
  negative: { color: colors.red },
  last: { backgroundColor: colors.lastSoft, color: '#9A4D00', fontWeight: '700' },
  target: { backgroundColor: colors.accent, color: '#FFFFFF', fontWeight: '700' },
  total: { fontWeight: '700', fontSize: 15 },
  diffHead: { textAlign: 'right', fontSize: 15, fontWeight: '700', color: colors.muted, paddingRight: 2 },
  diff: { height: ROW_H, lineHeight: ROW_H, textAlign: 'right', fontSize: 12, fontWeight: '700', color: colors.faint,
    paddingRight: 2 },
  diffTotal: { fontSize: 14 },
  diffUp: { color: colors.green },
});
