/**
 * A club, as on the web (abaka_ui.py, the club page): its table, the latest games, a new
 * club game on one device or online, and the club's code to share. Games started here
 * count for the club's table. The screen asks the server again each time it comes into
 * view, so the table is up to date after a club game.
 */

import { router, useFocusEffect, useLocalSearchParams } from 'expo-router';
import { useCallback, useState } from 'react';
import { Share, StyleSheet, Text, View } from 'react-native';

import { ClubTable, LatestGames, PlayerChips } from '@/components/Club';
import { LanguageSwitch } from '@/components/LanguageSwitch';
import { BackLink, Button, Card, Choice, colors, Field, Muted, Notice, Screen, Title } from '@/components/ui';
import type { ApiError, Club } from '@/lib/api';
import { useApp } from '@/lib/app';
import { inBoxes, memberKey, togglePlayer } from '@/lib/clubs';
import { errorText } from '@/lib/errors';
import { startGame } from '@/lib/start';
import { forgetClub, saveClub } from '@/lib/storage';

const PLAYER_COUNTS = [2, 3, 4, 5];

export default function ClubScreen() {
  const params = useLocalSearchParams<{ code: string }>();
  const code = String(params.code ?? '').replace(/\s+/g, '').toUpperCase();
  const { t, connection } = useApp();
  const [club, setClub] = useState<Club | null>(null);
  const [gone, setGone] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useFocusEffect(useCallback(() => {
    let shown = true;
    connection.request<{ club: Club }>('club', { club: code }).then(
      ({ club: now }) => {
        if (!shown) return;
        setClub(now);
        setGone(false);
        setError(null);
        saveClub({ code: now.code, name: now.name });
      },
      (e: ApiError) => {
        if (!shown) return;
        if (e.code === 'not_found') {
          setGone(true);
          forgetClub(code);
        } else {
          setError(errorText(e, t));
        }
      },
    );
    return () => { shown = false; };
  }, [code, connection, t]));

  let body;
  if (gone) {
    body = (
      <Card testID="club-gone">
        <Title>{t('No club with that code. Check it and try again.')}</Title>
        <Button label={t('Go to start')} onPress={() => router.dismissTo('/')} />
      </Card>
    );
  } else if (!club) {
    body = <Muted>{t('Connecting…')}</Muted>;
  } else {
    body = (
      <>
        <Card testID="club">
          <Text style={styles.clubName}>🏆 {club.name}</Text>
          <Muted>{t('Games started here count for the table.')}</Muted>
        </Card>
        <ClubTable members={club.members} />
        <LatestGames games={club.games} />
        <NewClubGame club={club} onError={setError} />
        <ShareClub code={club.code} />
      </>
    );
  }

  return (
    <Screen>
      <View style={styles.bar}>
        <BackLink testID="home" label={t('Home')} onPress={() => router.dismissTo('/')} />
        <Text style={styles.barTitle} numberOfLines={1}>🏆 {code}</Text>
        <LanguageSwitch />
      </View>
      {error ? <Notice text={error} /> : null}
      {body}
    </Screen>
  );
}

/** A game that counts for the club: on one device, or online. The club's players can be tapped instead of typed. */
function NewClubGame({ club, onError }: { club: Club; onError: (error: string | null) => void }) {
  const { t, connection, info } = useApp();
  const [mode, setMode] = useState<'local' | 'online'>('local');
  const [count, setCount] = useState(2);
  const [boxes, setBoxes] = useState(['', '', '', '', '']);
  const [myName, setMyName] = useState('');
  const [capacity, setCapacity] = useState(2);
  const [busy, setBusy] = useState(false);
  const nameLength = info?.limits.name ?? 20;
  const known = club.names;

  const start = async (op: 'create' | 'create_local', fields: Record<string, unknown>) => {
    setBusy(true);
    onError(null);
    try {
      await startGame(connection, op, { ...fields, club: club.code });
    } catch (e) {
      onError(errorText(e, t)); // for example "Each player needs a different name."
    } finally {
      setBusy(false);
    }
  };

  const shown = boxes.slice(0, count);
  const counts = PLAYER_COUNTS.map((n) => ({ value: n, label: String(n) }));
  return (
    <Card testID="club-new-game">
      <Title>{t('New club game')}</Title>
      <Muted>
        {known.length
          ? t('Pick the club\'s players, or type a new name.')
          : t('Type the names the same way each time; capital letters do not matter.')}
      </Muted>
      <Choice testID="club-mode" value={mode} onChange={setMode}
              options={[{ value: 'local', label: t('Same device') }, { value: 'online', label: t('Online') }]} />
      {mode === 'local' ? (
        <>
          <Text style={styles.label}>{t('Players')}</Text>
          <Choice testID="club-local-count" value={count} onChange={setCount} options={counts} />
          <PlayerChips names={known} hint={t('Pick a player or type a new name')}
                       on={(name) => inBoxes(shown, name)}
                       onPick={(name) => setBoxes([...togglePlayer(shown, name), ...boxes.slice(count)])} />
          {shown.map((name, i) => (
            <Field key={i} testID={`club-name-${i}`} value={name} maxLength={nameLength}
                   placeholder={t('Player {i}', { i: i + 1 })}
                   onChange={(text) => setBoxes(boxes.map((old, j) => (j === i ? text : old)))} />
          ))}
          <Button testID="club-start-local" label={t('Start game')} disabled={busy}
                  onPress={() => start('create_local', { names: shown })} />
        </>
      ) : (
        <>
          <PlayerChips names={known} hint={t('Pick a player or type a new name')}
                       on={(name) => memberKey(name) === memberKey(myName)}
                       onPick={setMyName} />
          <Field testID="club-host" label={t('Your name')} value={myName} onChange={setMyName}
                 maxLength={nameLength} placeholder={t('Name')} />
          <Text style={styles.label}>{t('Players')}</Text>
          <Choice testID="club-online-count" value={capacity} onChange={setCapacity} options={counts} />
          <Button testID="club-create-online" label={t('Create game')} disabled={busy}
                  onPress={() => start('create', { name: myName, players: capacity })} />
        </>
      )}
    </Card>
  );
}

function ShareClub({ code }: { code: string }) {
  const { t } = useApp();
  const share = async () => {
    try {
      await Share.share({ message: code });
    } catch {
      // Sharing is not offered here: the code is on the screen.
    }
  };
  return (
    <Card testID="club-share">
      <Muted>{t('Give your friends the club code. They open it under "Open club".')}</Muted>
      <Text testID="club-code" selectable style={styles.code}>{code}</Text>
      <Button kind="secondary" label={t('Invite a friend')} onPress={share} />
    </Card>
  );
}

const styles = StyleSheet.create({
  bar: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  barTitle: { flex: 1, fontSize: 15, color: colors.muted, textAlign: 'center' },
  clubName: { fontSize: 22, fontWeight: '800', color: colors.text },
  label: { fontSize: 14, color: colors.muted },
  code: { fontSize: 30, fontWeight: '800', letterSpacing: 5, color: colors.text, textAlign: 'center' },
});
