/**
 * Home, as on the web (abaka_ui.py): continue a game this device played, start a game on
 * one device or online, or open a game by its code.
 */

import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { LanguageSwitch } from '@/components/LanguageSwitch';
import { Button, Card, Choice, colors, Field, Muted, Notice, Screen, Title } from '@/components/ui';
import { gamesToContinue, type Seat } from '@/lib/api';
import { useApp } from '@/lib/app';
import { errorText } from '@/lib/errors';
import { forgetGame, type SavedGame, savedGames, saveGame, updateGame } from '@/lib/storage';

const GAMES_SHOWN = 4; // as on the web (MY_GAMES_SHOWN)
const PLAYER_COUNTS = [2, 3, 4, 5];

export default function Home() {
  const { t, connection, info, online } = useApp();
  const [games, setGames] = useState<SavedGame[]>([]);
  const [count, setCount] = useState(2);
  const [names, setNames] = useState(['', '', '', '', '']);
  const [myName, setMyName] = useState('');
  const [capacity, setCapacity] = useState(2);
  const [code, setCode] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const nameLength = info?.limits.name ?? 20;

  // The games to continue: at once what the device remembers, then what the server says
  // (a game that ended or was closed elsewhere is not offered any more).
  useFocusEffect(useCallback(() => {
    let shown = true;
    (async () => {
      const saved = await savedGames();
      if (shown) setGames(saved.filter((game) => !game.over).slice(0, GAMES_SHOWN));
      const now = await gamesToContinue(connection, saved.map((game) => game.code), GAMES_SHOWN);
      if (!now) return;
      for (const code of now.gone) await forgetGame(code);
      for (const code of now.over) {
        const game = saved.find((g) => g.code === code);
        if (game) await updateGame(code, { names: game.names, over: true });
      }
      for (const state of now.open) await updateGame(state.code, { names: state.names, over: false });
      if (shown) {
        setGames(now.open.map((state) => ({ code: state.code, local: state.local, names: state.names, at: 0 })));
      }
    })();
    return () => { shown = false; };
  }, [connection]));

  const start = async (op: 'create' | 'create_local', fields: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      const seat = await connection.request<Seat>(op, fields);
      await saveGame({ code: seat.code, local: seat.state.local, names: seat.state.names }, seat.token);
      router.push({ pathname: '/game/[code]', params: { code: seat.code } });
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  const open = () => {
    const wanted = code.trim().toUpperCase().replace(/\s+/g, '');
    if (wanted) router.push({ pathname: '/game/[code]', params: { code: wanted } });
  };

  return (
    <Screen>
      <View style={styles.top}>
        <View style={{ flex: 1 }}>
          <Text style={styles.logo}>Abaka</Text>
          <Muted>{t('The dice game of combinations. Play with friends on one screen or online.')}</Muted>
        </View>
        <LanguageSwitch />
      </View>

      {error ? <Notice text={error} /> : null}

      {games.length > 0 ? (
        <Card testID="card-my-games">
          <Title>{t('Continue a game')}</Title>
          <Muted>{t('Your games are saved after every move.')}</Muted>
          {games.map((game) => (
            <Button
              key={game.code}
              kind="secondary"
              testID={`continue-${game.code}`}
              label={t('{code} · {kind} · {names}', {
                code: game.code,
                kind: game.local ? t('Same device') : t('Online'),
                names: game.names.join(', '),
              })}
              onPress={() => router.push({ pathname: '/game/[code]', params: { code: game.code } })}
            />
          ))}
        </Card>
      ) : null}

      <Card testID="card-local">
        <Title>{t('Same device')}</Title>
        <Muted>{t('Take turns on this screen.')}</Muted>
        <Text style={styles.label}>{t('Players')}</Text>
        <Choice
          testID="local-count"
          value={count}
          onChange={setCount}
          options={PLAYER_COUNTS.map((n) => ({ value: n, label: String(n) }))}
        />
        {names.slice(0, count).map((name, i) => (
          <Field
            key={i}
            testID={`local-name-${i}`}
            value={name}
            maxLength={nameLength}
            placeholder={t('Player {i}', { i: i + 1 })}
            onChange={(text) => setNames(names.map((old, j) => (j === i ? text : old)))}
          />
        ))}
        <Button
          testID="start-local"
          label={t('Start game')}
          disabled={busy}
          onPress={() => start('create_local', { names: names.slice(0, count) })}
        />
      </Card>

      <Card testID="card-online">
        <Title>{t('Online')}</Title>
        <Muted>{t('Each player on their own device. Invite friends with a link.')}</Muted>
        <Field testID="online-name" label={t('Your name')} value={myName} onChange={setMyName}
               maxLength={nameLength} placeholder={t('Name')} />
        <Text style={styles.label}>{t('Players')}</Text>
        <Choice
          testID="online-count"
          value={capacity}
          onChange={setCapacity}
          options={PLAYER_COUNTS.map((n) => ({ value: n, label: String(n) }))}
        />
        <Button
          testID="create-online"
          label={t('Create game')}
          disabled={busy}
          onPress={() => start('create', { name: myName, players: capacity })}
        />
      </Card>

      <Card testID="card-open">
        <Title>{t('or open a game by its code')}</Title>
        <Muted>{t("Join a friend's game, or continue a saved game.")}</Muted>
        <Field testID="open-code" label={t('Game code')} value={code} onChange={setCode}
               placeholder={t('e.g. Q47CH')} maxLength={8} autoCapitalize="characters" />
        <Button testID="open-game" kind="secondary" label={t('Open game')} disabled={!code.trim()} onPress={open} />
      </Card>

      {!online && busy ? <Muted>{t('Connecting…')}</Muted> : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  logo: { fontSize: 30, fontWeight: '800', color: colors.accent, letterSpacing: 0.5 },
  label: { fontSize: 14, color: colors.muted },
});
