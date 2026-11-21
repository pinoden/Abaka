/**
 * The app's building blocks, in the web app's colours (.streamlit/config.toml,
 * ui_components/style.py): cards, buttons, choices, text fields and notes.
 */

import type { ReactNode } from 'react';
import { Pressable, ScrollView, StyleSheet, Text, TextInput, View, type StyleProp, type ViewStyle } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

export const colors = {
  accent: '#4F46E5',     // indigo: the current player, picked choices, main buttons
  accentSoft: '#EEF0FF',
  accentLine: '#C7CBF5',
  background: '#F5F6FA',
  card: '#FFFFFF',
  line: '#E3E6EF',
  text: '#1C2033',
  muted: '#6B7089',
  faint: '#9AA0B5',
  gold: '#B7791F',       // the option with the most points
  goldSoft: '#FFF4DB',
  last: '#F59E0B',       // the cell of the latest move
  lastSoft: '#FFE8D1',
  red: '#E5484D',
  green: '#1F7A4A',
  joker: '#262B45',
  jokerPip: '#FBBF24',
};

/** A screen: safe area, scrolling, at most 560 wide (tablets and the web build). */
export function Screen({ children }: { children: ReactNode }) {
  return (
    <SafeAreaView style={styles.safe} edges={['top', 'left', 'right']}>
      <ScrollView contentContainerStyle={styles.scroll} keyboardShouldPersistTaps="handled">
        <View style={styles.column}>{children}</View>
      </ScrollView>
    </SafeAreaView>
  );
}

export function Card({ children, style, testID }: { children: ReactNode; style?: StyleProp<ViewStyle>; testID?: string }) {
  return <View testID={testID} style={[styles.card, style]}>{children}</View>;
}

export function Title({ children }: { children: ReactNode }) {
  return <Text style={styles.title}>{children}</Text>;
}

export function Muted({ children }: { children: ReactNode }) {
  return <Text style={styles.muted}>{children}</Text>;
}

/** Text with **bold** parts, as the web's Markdown labels have them. */
export function Rich({ text, style }: { text: string; style?: object }) {
  const parts = text.split('**');
  return (
    <Text style={[styles.body, style]}>
      {parts.map((part, i) => (i % 2 ? <Text key={i} style={styles.bold}>{part}</Text> : part))}
    </Text>
  );
}

type ButtonKind = 'primary' | 'secondary' | 'quiet';

export function Button({ label, onPress, kind = 'primary', disabled, testID }: {
  label: string;
  onPress: () => void;
  kind?: ButtonKind;
  disabled?: boolean;
  testID?: string;
}) {
  return (
    <Pressable
      testID={testID}
      accessibilityRole="button"
      disabled={disabled}
      onPress={onPress}
      style={({ pressed }) => [
        styles.button,
        kind === 'primary' && styles.primary,
        kind === 'secondary' && styles.secondary,
        kind === 'quiet' && styles.quiet,
        disabled && styles.disabled,
        pressed && !disabled && styles.pressed,
      ]}>
      <Text style={[styles.buttonText, kind === 'primary' ? styles.primaryText : styles.secondaryText]}>
        {label}
      </Text>
    </Pressable>
  );
}

/** Pick one of a few options (players count, Score / Cross out, language). */
export function Choice<T extends string | number>({ options, value, onChange, testID }: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (value: T) => void;
  testID?: string;
}) {
  return (
    <View testID={testID} style={styles.choice} accessibilityRole="radiogroup">
      {options.map((option) => {
        const picked = option.value === value;
        return (
          <Pressable
            key={String(option.value)}
            accessibilityRole="radio"
            accessibilityState={{ checked: picked }}
            onPress={() => onChange(option.value)}
            style={[styles.choiceItem, picked && styles.choicePicked]}>
            <Text style={[styles.choiceText, picked && styles.choiceTextPicked]}>{option.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function Field({ label, value, onChange, placeholder, maxLength, testID, autoCapitalize }: {
  label?: string;
  value: string;
  onChange: (text: string) => void;
  placeholder?: string;
  maxLength?: number;
  testID?: string;
  autoCapitalize?: 'none' | 'characters' | 'words';
}) {
  return (
    <View style={styles.field}>
      {label ? <Text style={styles.label}>{label}</Text> : null}
      <TextInput
        testID={testID}
        accessibilityLabel={label ?? placeholder}
        value={value}
        onChangeText={onChange}
        placeholder={placeholder}
        placeholderTextColor={colors.faint}
        maxLength={maxLength}
        autoCapitalize={autoCapitalize ?? 'words'}
        autoCorrect={false}
        style={styles.input}
      />
    </View>
  );
}

/** A line the player should not miss: a refusal, a lost connection. */
export function Notice({ text, tone = 'error' }: { text: string; tone?: 'error' | 'info' }) {
  return (
    <View accessibilityRole="alert" style={[styles.notice, tone === 'info' && styles.noticeInfo]}>
      <Text style={[styles.noticeText, tone === 'info' && styles.noticeInfoText]}>{text}</Text>
    </View>
  );
}

export const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: colors.background },
  scroll: { paddingHorizontal: 16, paddingVertical: 16 },
  column: { width: '100%', maxWidth: 560, alignSelf: 'center', gap: 16 },
  card: {
    backgroundColor: colors.card,
    borderRadius: 14,
    borderWidth: 1,
    borderColor: colors.line,
    padding: 16,
    gap: 12,
  },
  title: { fontSize: 18, fontWeight: '700', color: colors.text },
  body: { fontSize: 15, color: colors.text, lineHeight: 21 },
  bold: { fontWeight: '700' },
  muted: { fontSize: 14, color: colors.muted, lineHeight: 20 },
  button: {
    minHeight: 46,
    borderRadius: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
    alignItems: 'center',
    justifyContent: 'center',
    borderWidth: 1,
  },
  primary: { backgroundColor: colors.accent, borderColor: colors.accent },
  secondary: { backgroundColor: colors.card, borderColor: colors.line },
  quiet: { backgroundColor: 'transparent', borderColor: 'transparent' },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.8 },
  buttonText: { fontSize: 16, fontWeight: '600', textAlign: 'center' },
  primaryText: { color: '#FFFFFF' },
  secondaryText: { color: colors.accent },
  choice: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  choiceItem: {
    minHeight: 40,
    minWidth: 44,
    paddingHorizontal: 14,
    borderRadius: 10,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.card,
    alignItems: 'center',
    justifyContent: 'center',
  },
  choicePicked: { backgroundColor: colors.accentSoft, borderColor: colors.accent },
  choiceText: { fontSize: 15, color: colors.text },
  choiceTextPicked: { color: colors.accent, fontWeight: '600' },
  field: { gap: 6 },
  label: { fontSize: 14, color: colors.muted },
  input: {
    minHeight: 46,
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.line,
    backgroundColor: colors.card,
    paddingHorizontal: 12,
    fontSize: 16,
    color: colors.text,
  },
  notice: { backgroundColor: '#FDECEC', borderRadius: 12, padding: 12 },
  noticeText: { color: '#8C1D21', fontSize: 15 },
  noticeInfo: { backgroundColor: colors.accentSoft },
  noticeInfoText: { color: colors.accent },
});
