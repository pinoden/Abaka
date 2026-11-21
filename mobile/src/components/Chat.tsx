/**
 * The chat of an online game, as on the web (ui_components/chat.py): the game's messages,
 * latest at the bottom, and a box to write one. The server deletes the chat with the move
 * that ends the game, and never saves it.
 *
 * Messages are other players' text: always drawn as plain text.
 */

import { type ComponentRef, useEffect, useRef, useState } from 'react';
import { ScrollView, StyleSheet, Text, TextInput, View } from 'react-native';

import type { ChatMessage, State } from '@/lib/api';
import { useApp } from '@/lib/app';
import { errorText } from '@/lib/errors';

import { Button, Card, colors, Muted } from './ui';

const NOTE_MS = 3000;

export function Chat({ state, chat, say }: {
  state: State;
  chat: ChatMessage[];
  /** Send a message; rejects with the server's refusal (too fast, or the game has just ended). */
  say: (text: string) => Promise<unknown>;
}) {
  const { t, info } = useApp();
  const [text, setText] = useState('');
  const [sending, setSending] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const list = useRef<ComponentRef<typeof ScrollView>>(null);

  useEffect(() => {
    if (!note) return;
    const timer = setTimeout(() => setNote(null), NOTE_MS);
    return () => clearTimeout(timer);
  }, [note]);

  const send = async () => {
    const message = text.trim();
    if (!message || sending) return;
    setSending(true);
    try {
      await say(message);
      setText(''); // kept if it was not sent, to try again
    } catch (e) {
      setNote(errorText(e, t));
    } finally {
      setSending(false);
    }
  };

  return (
    <Card testID="chat" style={styles.card}>
      <View style={styles.head}>
        <Text style={styles.title}>{t('Chat')}</Text>
        <Text style={styles.sub}>{t('Deleted when the game ends')}</Text>
      </View>
      {chat.length === 0 ? (
        <Muted>{t('No messages yet. Say hi!')}</Muted>
      ) : (
        <ScrollView ref={list} style={styles.messages} nestedScrollEnabled
                    onContentSizeChange={() => list.current?.scrollToEnd({ animated: false })}>
          {chat.map((message) => {
            const mine = !state.local && message.seat === state.you;
            return (
              <Text key={message.id} testID="chat-message" style={[styles.message, mine && styles.mine]}>
                <Text style={styles.who}>{mine ? t('You') : state.names[message.seat] ?? '?'}</Text>
                {'  '}{message.text}
              </Text>
            );
          })}
        </ScrollView>
      )}
      <View style={styles.row}>
        <TextInput
          testID="chat-text"
          accessibilityLabel={t('Message')}
          value={text}
          onChangeText={setText}
          onSubmitEditing={send}
          submitBehavior="submit"
          returnKeyType="send"
          placeholder={t('Message')}
          placeholderTextColor={colors.faint}
          maxLength={info?.limits.message ?? 200}
          style={styles.input}
        />
        <Button testID="chat-send" kind="secondary" label={t('Send')} disabled={sending || !text.trim()} onPress={send} />
      </View>
      {note ? <Muted>{note}</Muted> : null}
    </Card>
  );
}

const styles = StyleSheet.create({
  card: { gap: 8 },
  head: { flexDirection: 'row', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 },
  title: { fontSize: 15, fontWeight: '700', color: colors.text },
  sub: { flexShrink: 1, fontSize: 12, color: colors.faint, textAlign: 'right' },
  messages: { maxHeight: 132 },
  message: { fontSize: 15, lineHeight: 21, color: colors.text, paddingVertical: 1 },
  mine: { color: colors.muted },
  who: { fontWeight: '700' },
  row: { flexDirection: 'row', alignItems: 'center', gap: 8 },
  input: {
    flex: 1, minHeight: 44, borderRadius: 12, borderWidth: 1, borderColor: colors.line,
    backgroundColor: colors.card, paddingHorizontal: 12, fontSize: 16, color: colors.text,
  },
});
