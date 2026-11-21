/**
 * How to play: the rules as the website shows them, from the server (`rules`, docs/API.md),
 * in the app's language. The owner changes the rules from time to time, so the screen asks
 * for them each time it opens instead of keeping a copy.
 */

import { router } from 'expo-router';
import { useEffect, useState } from 'react';
import { Pressable, StyleSheet, Text, View } from 'react-native';

import { LanguageSwitch } from '@/components/LanguageSwitch';
import { Card, colors, Muted, Notice, Rich, Screen } from '@/components/ui';
import type { Rules, RulesBlock } from '@/lib/api';
import { useApp } from '@/lib/app';
import { errorText } from '@/lib/errors';

export default function RulesScreen() {
  const { t, lang, connection } = useApp();
  const [rules, setRules] = useState<Rules | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let asked = true;
    connection.request<{ rules: Rules }>('rules', { lang }).then(
      (answer) => {
        if (!asked) return;
        setRules(answer.rules);
        setError(null);
      },
      (e) => { if (asked) setError(errorText(e, t)); },
    );
    return () => { asked = false; };
  }, [connection, lang, t]);

  const back = () => (router.canGoBack() ? router.back() : router.dismissTo('/'));

  return (
    <Screen>
      <View style={styles.bar}>
        <Pressable accessibilityRole="button" testID="back" onPress={back} hitSlop={8}>
          <Text style={styles.barBack}>‹ {t('Back')}</Text>
        </Pressable>
        <View style={{ flex: 1 }} />
        <LanguageSwitch />
      </View>
      {error ? <Notice text={error} /> : null}
      {rules ? (
        <Card testID="rules">
          <Text accessibilityRole="header" style={styles.title}>{rules.title}</Text>
          {rules.blocks.map((block, i) => <Block key={i} block={block} />)}
        </Card>
      ) : error ? null : <Muted>{t('Connecting…')}</Muted>}
    </Screen>
  );
}

function Block({ block }: { block: RulesBlock }) {
  if (block.heading !== undefined) {
    return <Text accessibilityRole="header" style={styles.heading}>{block.heading}</Text>;
  }
  if (block.text !== undefined) return <Rich text={block.text} />;
  if (block.table) {
    const { head, rows } = block.table;
    return (
      <View testID="rules-table" style={styles.table}>
        <View style={[styles.row, styles.headRow]}>
          {head.map((cell, i) => <Text key={i} style={[styles.cell, WIDTHS[i], styles.head]}>{cell}</Text>)}
        </View>
        {rows.map((row, r) => (
          <View key={r} style={[styles.row, r % 2 === 1 && styles.shaded]}>
            {row.map((cell, i) => (
              <Text key={i} style={[styles.cell, WIDTHS[i], i === 0 && styles.rowName]}>{cell}</Text>
            ))}
          </View>
        ))}
      </View>
    );
  }
  return null; // a kind of block this app does not know yet
}

// The table's columns: the row, what it needs (the longest), what it scores.
const WIDTHS = [{ flex: 1 }, { flex: 1.5 }, { flex: 1.2 }];

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  barBack: { fontSize: 16, color: colors.accent, fontWeight: '600' },
  title: { fontSize: 22, fontWeight: '800', color: colors.text },
  heading: { fontSize: 17, fontWeight: '700', color: colors.text, marginTop: 4 },
  table: { borderWidth: 1, borderColor: colors.line, borderRadius: 10, overflow: 'hidden' },
  row: { flexDirection: 'row', gap: 8, paddingHorizontal: 8, paddingVertical: 6 },
  headRow: { backgroundColor: colors.accentSoft },
  shaded: { backgroundColor: '#FAFAFD' },
  cell: { fontSize: 13, lineHeight: 18, color: colors.text },
  head: { fontWeight: '700', color: colors.accent },
  rowName: { fontWeight: '600' },
});
