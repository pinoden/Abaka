/**
 * Home, as on the web (abaka_ui.py): continue a game this device played, start a game on
 * one device or online, open a game by its code, and the clubs.
 */

import { router, useFocusEffect } from 'expo-router';
import { useCallback, useState } from 'react';
import { StyleSheet, Text, View } from 'react-native';

import { LanguageSwitch } from '@/components/LanguageSwitch';
import { Button, Card, Choice, colors, Field, Muted, Notice, Screen, Title } from '@/components/ui';
import { type Club, gamesToContinue } from '@/lib/api';
import { useApp } from '@/lib/app';
import { fullCode, splitCode } from '@/lib/codes';
import { errorText } from '@/lib/errors';
import { startGame } from '@/lib/start';
import {
  forgetGame, type SavedClub, savedClubs, saveClub, type SavedGame, savedGames, updateGame,
} from '@/lib/storage';

const GAMES_SHOWN = 4; // as on the web (MY_GAMES_SHOWN)
const PLAYER_COUNTS = [2, 3, 4, 5];

export default function Home() {
  const { t, connection, info, online } = useApp();
  const [games, setGames] = useState<SavedGame[]>([]);
  const [count, setCount] = useState(2);
  // The computer plays the last seats (Backlog item 33): none to all but one.
  const [computers, setComputers] = useState(0);
  const people = count - Math.min(computers, count - 1);
  // How well the computer plays (Backlog item 34). The server names the levels; these are for an older one.
  const levels = info?.computer_levels
    ?? [{ id: 'easy', label: t('Easy') }, { id: 'medium', label: t('Medium') }, { id: 'hard', label: t('Hard') }];
  const [chosenLevel, setLevel] = useState<string | null>(null);
  const level = chosenLevel ?? info?.computer_level_suggested ?? 'medium';
  const [names, setNames] = useState(['', '', '', '', '']);
  const [myName, setMyName] = useState('');
  const [capacity, setCapacity] = useState(2);
  const [code, setCode] = useState('');
  const [openError, setOpenError] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [clubs, setClubs] = useState<SavedClub[]>([]);
  const [clubName, setClubName] = useState('');
  const [clubCode, setClubCode] = useState('');
  const nameLength = info?.limits.name ?? 20;

  useFocusEffect(useCallback(() => {
    let shown = true;
    savedClubs().then((saved) => { if (shown) setClubs(saved); });
    return () => { shown = false; };
  }, []));

  // The games to continue: at once what the device remembers, then what the server says
  // (a game that ended or was closed elsewhere is not offered any more).
  useFocusEffect(useCallback(() => {
    let shown = true;
    (async () => {
      const saved = await savedGames();
      if (shown) setGames(saved.filter((game) => !game.over).slice(0, GAMES_SHOWN));
      const now = await gamesToContinue(connection, saved.map((game) => ({ code: game.code, key: game.key })),
                                        GAMES_SHOWN);
      if (!now) return;
      for (const code of now.gone) await forgetGame(code);
      for (const code of now.over) {
        const game = saved.find((g) => g.code === code);
        if (game) await updateGame(code, { names: game.names, over: true });
      }
      for (const state of now.open) await updateGame(state.code, { names: state.names, over: false });
      if (shown) {
        setGames(now.open.map((state) => ({ code: state.code, key: state.key, local: state.local, names: state.names,
                                            at: 0 })));
      }
    })();
    return () => { shown = false; };
  }, [connection]));

  const start = async (op: 'create' | 'create_local', fields: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await startGame(connection, op, fields);
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  };

  const openClub = (wanted: string) => {
    const code = wanted.replace(/\s+/g, '').toUpperCase();
    if (code) router.push({ pathname: '/club/[code]', params: { code } });
  };

  const createClub = async () => {
    setBusy(true);
    setError(null);
    try {
      const { club } = await connection.request<{ club: Club }>('create_club', { name: clubName });
      await saveClub({ code: club.code, name: club.name });
      setClubName('');
      openClub(club.code);
    } catch (e) {
      setError(errorText(e, t)); // for example "Give the club a name."
    } finally {
      setBusy(false);
    }
  };

  /** A game by its full code (or a pasted link): its code alone opens nothing (Backlog item 31). */
  const open = () => {
    const wanted = splitCode(code);
    if (!wanted.code) return;
    if (!wanted.key) {
      setOpenError(
        t("That is only the first part of a game's code. The full code looks like Q47CH-8XJ4PN2R: ask a player of the game for it."),
      );
      return;
    }
    setOpenError(null);
    router.push({ pathname: '/game/[code]', params: { code: fullCode(wanted.code, wanted.key) } });
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
        <Muted>{t('Take turns on this screen, or play against the computer.')}</Muted>
        <Text style={styles.label}>{t('Players')}</Text>
        <Choice
          testID="local-count"
          value={count}
          onChange={setCount}
          options={PLAYER_COUNTS.map((n) => ({ value: n, label: String(n) }))}
        />
        <Text style={styles.label}>{t('Computer players')}</Text>
        <Choice
          testID="local-computers"
          value={count - people}
          onChange={setComputers}
          options={Array.from({ length: count }, (_, n) => ({ value: n, label: String(n) }))}
        />
        {count > people ? (
          <>
            <Text style={styles.label}>{t('Level')}</Text>
            <Choice
              testID="local-level"
              value={level}
              onChange={setLevel}
              options={levels.map((l) => ({ value: l.id, label: l.label }))}
            />
          </>
        ) : null}
        {names.slice(0, people).map((name, i) => (
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
          onPress={() => start('create_local', {
            names: [...names.slice(0, people), ...Array(count - people).fill('')],
            computers: Array.from({ length: count - people }, (_, n) => people + n),
            ...(count > people ? { level } : {}),
          })}
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
        <Muted>{t("The full code, or the game's link. Join a friend's game, or continue a saved game.")}</Muted>
        <Field testID="open-code" label={t('Game code')} value={code} onChange={(text) => { setCode(text); setOpenError(null); }}
               placeholder={t('e.g. Q47CH-8XJ4PN2R')} maxLength={300} autoCapitalize="characters"
               onSubmit={() => { if (code.trim()) open(); }} />
        {openError ? <Notice testID="open-error" text={openError} /> : null}
        <Button testID="open-game" kind="secondary" label={t('Open game')} disabled={!code.trim()} onPress={open} />
      </Card>

      <Card testID="card-clubs">
        <Title>{t('Clubs')}</Title>
        <Muted>{t('A leaderboard for your group of friends. Games started from a club count for its table.')}</Muted>
        {clubs.map((club) => (
          <Button key={club.code} kind="secondary" testID={`my-club-${club.code}`} label={`🏆 ${club.name}`}
                  onPress={() => openClub(club.code)} />
        ))}
        <Field testID="club-name" label={t('Club name')} value={clubName} onChange={setClubName}
               placeholder={t('e.g. Friday dice')} maxLength={info?.limits.club_name ?? 30}
               onSubmit={() => { if (!busy) createClub(); }} />
        <Button testID="create-club" kind="secondary" label={t('Create club')} disabled={busy} onPress={createClub} />
        <Field testID="find-club-code" label={t('Club code')} value={clubCode} onChange={setClubCode}
               placeholder={t('e.g. K7PX2M')} maxLength={8} autoCapitalize="characters"
               onSubmit={() => { if (clubCode.trim()) openClub(clubCode); }} />
        <Button testID="open-club" kind="secondary" label={t('Open club')} disabled={!clubCode.trim()}
                onPress={() => openClub(clubCode)} />
      </Card>

      <Button kind="quiet" testID="rules-home" label={t('How to play')} onPress={() => router.push('/rules')} />

      {!online && busy ? <Muted>{t('Connecting…')}</Muted> : null}
    </Screen>
  );
}

const styles = StyleSheet.create({
  top: { flexDirection: 'row', alignItems: 'flex-start', gap: 12 },
  logo: { fontSize: 30, fontWeight: '800', color: colors.accent, letterSpacing: 0.5 },
  label: { fontSize: 14, color: colors.muted },
});
