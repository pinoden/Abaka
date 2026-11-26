/**
 * One game, from its code: the invite (join, take a seat back, carry on a game on one
 * device), the waiting room, the starting throw, the turns and the results. The screen
 * watches the game over the live connection and draws whatever state the server sends;
 * every button sends the move the state offers (docs/API.md).
 */

import { router, useLocalSearchParams } from 'expo-router';
import { type ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { AccessibilityInfo, Pressable, Share, StyleSheet, Switch, Text, View } from 'react-native';

import { Board, lastMoveText } from '@/components/Board';
import { Chart } from '@/components/Chart';
import { Chat } from '@/components/Chat';
import { ClubRatings, PlayerChips } from '@/components/Club';
import { DieFace } from '@/components/Dice';
import { Races } from '@/components/Races';
import { ReactionBar } from '@/components/Reactions';
import { Shows } from '@/components/Shows';
import { Button, Card, Choice, colors, Field, Muted, Notice, Rich, Screen, Title } from '@/components/ui';
import { type ApiError, type Club, type Game, type Move, type Seat, type State } from '@/lib/api';
import { useApp } from '@/lib/app';
import { memberKey, offered } from '@/lib/clubs';
import { errorText } from '@/lib/errors';
import { nothingShown, type Show, showsFor } from '@/lib/shows';
import { fullCode, splitCode } from '@/lib/codes';
import { forgetGame, keyFor, saveGame, tokenFor, updateGame } from '@/lib/storage';

type Act = (op: string, fields?: Record<string, unknown>, move?: boolean) => Promise<void>;
type Pick = (dice: number[]) => void;
/** Reactions and chat: what a seated player of an online game sends to the table. */
type Talk = {
  react: (reaction: string, to: number | null) => Promise<unknown>;
  say: (text: string) => Promise<unknown>;
};

export default function GameScreen() {
  const params = useLocalSearchParams<{ code: string }>();
  // A game's full code (from "Open game"), or the code of a game this device remembers with its key.
  const opened = splitCode(String(params.code ?? ''));
  const code = opened.code;
  const { t, connection, online } = useApp();
  const [token, setToken] = useState<string | null | undefined>(undefined); // undefined: not read yet
  const [key, setKey] = useState<string | null>(opened.key || null);
  const [state, setState] = useState<State | null>(null);
  const [gone, setGone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [openedAt, setOpenedAt] = useState<number | null>(null); // the version this screen first drew
  const resuming = useRef(false);
  const leaving = useRef(false); // giving up the seat: what the server says meanwhile is not for the screen
  // Bubbles and effects playing over the screen, and what of the game's news it has taken in.
  const [shows, setShows] = useState<Show[]>([]);
  const news = useRef({ code, shown: nothingShown() });

  useEffect(() => {
    let live = true;
    Promise.all([tokenFor(code), keyFor(code)]).then(([savedToken, savedKey]) => {
      if (!live) return;
      setKey((typed) => typed ?? savedKey);
      setToken(savedToken);
    });
    return () => { live = false; };
  }, [code]);

  /** A seat taken (join, rejoin, resume): keep its token and the game's key, and watch the game with them. */
  const keepSeat = useCallback(async (seat: Seat) => {
    await saveGame({ code: seat.code, key: seat.state.key, local: seat.state.local, names: seat.state.names },
                   seat.token);
    setState(seat.state);
    setKey(seat.state.key);
    setToken(seat.token);
  }, []);

  // Neither a seat nor the key: the code alone opens nothing (Backlog item 31).
  const incomplete = token === null && !key;

  useEffect(() => {
    if (token === undefined || incomplete) return;
    return connection.startWatching(
      code,
      token ?? undefined,
      (next) => {
        if (leaving.current) return;
        setState(next); // the connection never hands over an older state after a newer one
        setOpenedAt((opened) => opened ?? next.version);
        if (news.current.code !== code) news.current = { code, shown: nothingShown() };
        const fresh = showsFor(next, news.current.shown, Date.now());
        if (fresh.length) setShows((playing) => [...playing, ...fresh]);
        // For a screen reader: what the bubble or the banner says (iOS reads no live regions).
        for (const show of fresh) {
          const words = show.kind === 'effect' ? [show.title, show.text] : [show.who, show.label];
          AccessibilityInfo.announceForAccessibility?.(words.filter(Boolean).join('. '));
        }
        // A game on one device opened from its code: carry on at once (no seat to pick).
        if (!next.seated && next.can.includes('resume') && !resuming.current) {
          resuming.current = true;
          connection.request<Seat>('resume', { code, key })
            .then(keepSeat, (e) => setError(errorText(e, t)))
            .finally(() => { resuming.current = false; });
        }
      },
      (e: ApiError) => {
        if (leaving.current) return;
        if (e.code === 'not_found') {
          setGone(true);
          forgetGame(code);
        } else {
          setError(errorText(e, t));
        }
      },
      key ?? undefined,
    );
    // t changes with the language; the connection watches again by itself then.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, token, key, incomplete, connection, keepSeat]);

  /** Join the game, or take a seat back. */
  const takeSeat = useCallback(async (op: string, fields: Record<string, unknown>) => {
    setBusy(true);
    setError(null);
    try {
      await keepSeat(await connection.request<Seat>(op, { code, key, ...fields }));
    } catch (e) {
      setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }, [code, key, connection, keepSeat, t]);

  const act: Act = useCallback(async (op, fields = {}, move = true) => {
    if (!state || !token) return;
    setBusy(true);
    try {
      await connection.act(op, { code, token, ...(move ? { version: state.version } : {}), ...fields });
      setError(null);
    } catch (e) {
      // An outdated move: the screen was behind, and the new state is on its way.
      if ((e as ApiError).code !== 'outdated') setError(errorText(e, t));
    } finally {
      setBusy(false);
    }
  }, [code, connection, state, t, token]);

  const talk: Talk = useMemo(() => ({
    react: (reaction, to) => connection.request('react', { code, token, reaction, ...(to === null ? {} : { to }) }),
    say: (text) => connection.request('say', { code, token, text }),
  }), [code, connection, token]);

  const showDone = useCallback((id: string) => setShows((playing) => playing.filter((show) => show.id !== id)), []);

  /** Online, the others see the dice picked to roll again. A pick is not a move. */
  const pick: Pick = useCallback((dice) => {
    if (token) connection.request('pick', { code, token, dice }).catch(() => {});
  }, [code, connection, token]);

  // What the home page lists: the game's players as they are now, and whether it is over.
  const seated = state?.seated ?? false;
  const over = state?.phase === 'over';
  const names = state?.names.join('\n') ?? '';
  useEffect(() => {
    if (seated) updateGame(code, { names: names.split('\n'), over });
  }, [code, seated, over, names]);

  /** To the home page. The seat is kept: the game is there under "Continue a game". */
  const goHome = () => router.dismissTo('/');

  /** Give up the seat in the waiting room (a game nobody is left in is closed). */
  const leave = async () => {
    if (!token) return goHome();
    setBusy(true);
    leaving.current = true;
    try {
      await connection.request('leave', { code, token });
      await forgetGame(code);
      goHome();
    } catch (e) {
      leaving.current = false;
      setError(errorText(e, t)); // the seat is still held: say so, and stay
      setBusy(false);
    }
  };

  let body: ReactNode;
  if (incomplete) {
    body = (
      <Card testID="incomplete">
        <Title>{t('This link is not complete')}</Title>
        <Muted>
          {t('A game opens only with its full link or code, such as Q47CH-8XJ4PN2R. Ask a player of the game to send it again.')}
        </Muted>
        <Button label={t('Go to start')} onPress={() => router.dismissTo('/')} />
      </Card>
    );
  } else if (gone) {
    body = (
      <Card testID="gone">
        <Title>{t('Game not found')}</Title>
        <Muted>{t('Game {code} has ended, or it is no longer kept. You can start a new one.', { code })}</Muted>
        <Button label={t('Go to start')} onPress={() => router.dismissTo('/')} />
      </Card>
    );
  } else if (!state) {
    body = <Muted>{t('Connecting…')}</Muted>;
  } else if (!state.seated) {
    // A seat this device held, taken back on another device.
    body = <Invite state={state} busy={busy} takeSeat={takeSeat} lost={!!token && !state.local} />;
  } else if (state.phase === 'waiting') {
    body = <WaitingRoom state={state} act={act} busy={busy} onLeave={leave} />;
  } else if (state.game) {
    body = <Table state={state} game={state.game} act={act} pick={pick} talk={talk} busy={busy}
                  openedAt={openedAt ?? state.version} />;
  }

  return (
    <Screen over={<Shows shows={shows} onDone={showDone} />}>
      <View style={styles.bar}>
        <Pressable accessibilityRole="button" testID="home" onPress={goHome} hitSlop={8}>
          <Text style={styles.barHome}>‹ {t('Home')}</Text>
        </Pressable>
        {/* The kind of game as the website's icons for it, so the code always fits; the words for screen readers. */}
        <Text testID="bar-code" style={styles.barTitle} numberOfLines={1}
              accessibilityLabel={!state ? code : state.local ? t('Same device · {code}', { code })
                : t('Online · {code}', { code })}>
          {state ? (state.local ? '👥 ' : '🌐 ') : ''}<Text style={styles.barCode}>{code}</Text>
        </Text>
        {/* The rules, and on their screen the language switch: as in the website's game menu. */}
        <Pressable accessibilityRole="button" accessibilityLabel={t('How to play')} testID="rules-button"
                   onPress={() => router.push('/rules')} hitSlop={6} style={styles.rulesButton}>
          <Text style={styles.rulesButtonText}>?</Text>
        </Pressable>
      </View>
      {!online && state ? <Notice tone="info" text={t('Connecting…')} /> : null}
      {error ? <Notice text={error} /> : null}
      {body}
    </Screen>
  );
}

/** No seat yet: join a waiting game, or take a seat back. */
function Invite({ state, busy, takeSeat, lost }: {
  state: State;
  busy: boolean;
  takeSeat: (op: string, fields: Record<string, unknown>) => void;
  lost: boolean;
}) {
  const { t, info, connection } = useApp();
  const [name, setName] = useState('');
  const [members, setMembers] = useState<string[]>([]); // a club game: the club's players
  const join = state.can.includes('join');
  const rejoin = state.can.includes('rejoin');
  const club = state.club;

  useEffect(() => {
    if (!club || !join) return;
    let asked = true;
    connection.request<{ club: Club }>('club', { club, games: 0 }).then(
      (answer) => { if (asked) setMembers(answer.club.names); },
      () => { /* no list to pick from: the name can still be typed */ },
    );
    return () => { asked = false; };
  }, [club, join, connection]);
  return (
    <Card testID="invite">
      {lost ? <Notice text={t('This game was opened in another tab or device, so this tab no longer controls it.')} /> : null}
      {join ? (
        <>
          <Title>{t('{host} invited you to play', { host: state.names[0] ?? '' })}</Title>
          <Muted>
            {state.capacity === 2
              ? t('Enter your name to join. The game starts right away.')
              : t('A game for {n} players; {k} joined so far: {names}. Enter your name to join.', {
                n: state.capacity, k: state.names.length, names: state.names.join(', '),
              })}
          </Muted>
          {/* A club game: the club's players not at the table yet. */}
          <PlayerChips names={offered(members, state.names)} hint={t('Pick a player or type a new name')}
                       on={(player) => memberKey(player) === memberKey(name)} onPick={setName} />
          <Field testID="join-name" label={t('Your name')} value={name} onChange={setName}
                 maxLength={info?.limits.name ?? 20} placeholder={t('Name')}
                 onSubmit={() => { if (!busy) takeSeat('join', { name }); }} />
          <Button testID="join" label={t('Join game')} disabled={busy} onPress={() => takeSeat('join', { name })} />
        </>
      ) : null}
      {rejoin ? (
        <>
          {!join ? <Title>{t('This game is full and already playing.')}</Title> : null}
          <Muted>{join ? t('Already joined and lost the page? Rejoin as:') : t('Are you one of the players? Rejoin as:')}</Muted>
          {state.names.map((player, seat) => (
            <Button key={seat} kind="secondary" testID={`rejoin-${seat}`} label={player} disabled={busy}
                    onPress={() => takeSeat('rejoin', { seat })} />
          ))}
        </>
      ) : null}
      {!join && !rejoin ? <Muted>{t('Connecting…')}</Muted> : null}
    </Card>
  );
}

function WaitingRoom({ state, act, busy, onLeave }: {
  state: State;
  act: Act;
  busy: boolean;
  onLeave: () => void;
}) {
  const { t, plural } = useApp();
  const joined = state.names.length;
  const share = async () => {
    try {
      await Share.share({ message: fullCode(state.code, state.key) });
    } catch {
      // Sharing is not offered here: the code is on the screen.
    }
  };
  return (
    <Card testID="waiting">
      <Title>{t('Invite your friends')}</Title>
      <Muted>{t('Give your friends the game code. They open it under "Open game".')}</Muted>
      {/* The full code: the code, and under it its key (the code alone opens nothing). */}
      <Text testID="game-code" selectable style={styles.code} accessibilityLabel={fullCode(state.code, state.key)}>
        {state.code}{'\n'}<Text style={styles.codeKey}>{state.key}</Text>
      </Text>
      <Button kind="secondary" label={t('Invite a friend')} onPress={share} />
      <Muted>
        {t('{joined} of {capacity} players are here. Waiting for {missing} more…', {
          joined, capacity: state.capacity, missing: state.capacity - joined,
        })}
      </Muted>
      {state.names.map((name, seat) => (
        <Text key={seat} style={styles.waitingName}>{seat === state.you ? `${name} · ${t('You')}` : name}</Text>
      ))}
      {state.can.includes('start_now') ? (
        <Button testID="start-now" disabled={busy}
                label={t('Start now with {players}', { players: plural('players_count', joined) })}
                onPress={() => act('start_now', {}, false)} />
      ) : null}
      <Button kind="quiet" testID="leave" label={state.you === 0 && joined === 1 ? t('Cancel') : t('Leave')}
              disabled={busy} onPress={onLeave} />
    </Card>
  );
}

/** The game: whose turn it is, the dice, the moves, the board; the results at the end. */
function Table({ state, game, act, pick, talk, busy, openedAt }: {
  state: State;
  game: Game;
  act: Act;
  pick: Pick;
  talk: Talk;
  busy: boolean;
  openedAt: number;
}) {
  const { t, rowName } = useApp();
  const myTurn = state.local || game.current === state.you;
  // The move being chosen is kept only for this throw: a new roll or turn starts afresh.
  const turn = `${game.number}.${game.current}.${game.rolls_left}.${game.dice.map((d) => d.value).join('')}`;
  // The column of row differences (a tester, 2026-11-26): off until the player turns it on, as on the web.
  const [showDiffs, setShowDiffs] = useState(false);
  const [choice, setChoice] = useState<{ turn: string; mode: 'score' | 'cross'; move: Move | null }>(
    { turn, mode: 'score', move: null });
  const current = choice.turn === turn ? choice : { turn, mode: 'score' as const, move: null };
  const target = state.moves && current.move ? current.move : null;
  const last = lastMoveText(game, state.local ? null : state.you, t, rowName);

  return (
    <>
      {state.phase === 'starting_throw' ? <StartingThrow state={state} game={game} act={act} busy={busy} /> : null}
      {state.phase === 'playing' ? (
        <Card testID="play">
          <StarterSummary state={state} game={game} />
          <Text testID="turn" style={[styles.turn, myTurn && !state.local && styles.turnMine]}>
            {myTurn && !state.local ? t('Your turn') : t('{name}’s turn', { name: state.names[game.current] })}
          </Text>
          <TurnLine state={state} game={game} myTurn={myTurn} />
          <DiceArea state={state} game={game} act={act} pick={pick} busy={busy} myTurn={myTurn}
                    openedAt={openedAt} turn={turn} />
          {state.moves ? (
            <Moves state={state} moves={state.moves} mode={current.mode} picked={current.move} busy={busy}
                   onMode={(mode) => setChoice({ turn, mode, move: null })}
                   onPick={(move) => setChoice({ turn, mode: current.mode, move })}
                   onConfirm={(move) => act(current.mode, { row: move.row, slot: move.slot })} />
          ) : null}
          {state.races ? <Races races={state.races} you={state.local ? null : state.you} /> : null}
        </Card>
      ) : null}
      {state.phase === 'over' ? <Results state={state} game={game} act={act} busy={busy} /> : null}
      {state.can.includes('react') ? <Card><ReactionBar state={state} react={talk.react} /></Card> : null}
      {state.can.includes('say') ? <Chat state={state} chat={state.chat} say={talk.say} /> : null}
      <Card testID="scoreboard" style={styles.boardCard}>
        {state.differences ? (
          <View style={styles.diffSwitch}>
            <Text style={styles.diffLabel}>{t('Row differences')}</Text>
            <Switch testID="differences-switch" value={showDiffs} onValueChange={setShowDiffs}
                    trackColor={{ true: colors.accent, false: colors.line }}
                    accessibilityHint={state.differences.hint} />
          </View>
        ) : null}
        <Board game={game} you={state.local ? null : state.you} target={target}
               differences={showDiffs ? state.differences : null} />
        {last ? <Text testID="last-move" style={styles.lastMove}>{last}</Text> : null}
        <TableScore state={state} />
        <Chart game={game} you={state.local ? null : state.you} />
      </Card>
    </>
  );
}

function TurnLine({ state, game, myTurn }: { state: State; game: Game; myTurn: boolean }) {
  const { t } = useApp();
  const name = state.names[game.current];
  if (game.dice.length === 0) {
    return <Muted>{myTurn ? t('Roll the dice to start the turn.') : t('Waiting for {name} to roll…', { name })}</Muted>;
  }
  return (
    <View style={styles.turnLine}>
      <Muted>{t('Roll {n} of 3', { n: 3 - game.rolls_left })}</Muted>
      {game.first_roll ? <Text style={styles.firstRoll}>{t('First roll: combinations score double')}</Text> : null}
    </View>
  );
}

function DiceArea({ state, game, act, pick, busy, myTurn, openedAt, turn }: {
  state: State;
  game: Game;
  act: Act;
  pick: Pick;
  busy: boolean;
  myTurn: boolean;
  openedAt: number;
  turn: string;
}) {
  const { t, plural } = useApp();
  const canReroll = state.can.includes('reroll');
  const [mine, setMine] = useState<{ turn: string; dice: number[] }>({ turn, dice: [] });
  const picked = !canReroll ? game.picked : mine.turn === turn ? mine.dice : [];
  // Dice rolled since this screen opened spin; dice already on the table when it opened do not.
  const rolledHere = state.version > openedAt;
  const spins = game.rolls_left === 2 ? game.dice.map((_, i) => i) : game.rerolled;

  if (game.dice.length === 0) {
    return state.can.includes('roll')
      ? <Button testID="roll" label={t('Roll dice')} disabled={busy} onPress={() => act('roll')} />
      : null;
  }

  const toggle = (i: number) => {
    const dice = picked.includes(i) ? picked.filter((d) => d !== i) : [...picked, i].sort();
    setMine({ turn, dice });
    if (state.can.includes('pick')) pick(dice);
  };

  return (
    <View style={styles.diceArea}>
      <View style={styles.dice} testID="dice">
        {game.dice.map((die, i) => (
          <DieFace
            key={i}
            testID={`die-${i}`}
            die={die}
            size={56}
            picked={picked.includes(i)}
            spinKey={rolledHere && spins.includes(i) ? state.version : null}
            label={die.joker ? t('{value} (joker)', { value: die.value }) : String(die.value)}
            onPress={canReroll ? () => toggle(i) : undefined}
          />
        ))}
      </View>
      {myTurn ? (
        canReroll ? (
          <>
            {picked.length === 0 ? (
              <Muted>
                {t('Tap the dice you want to roll again ({left} left), or choose a move below.', {
                  left: plural('rerolls_left', game.rolls_left),
                })}
              </Muted>
            ) : null}
            <View style={styles.buttons}>
              <View style={{ flex: 1 }}>
                <Button testID="reroll-picked" kind="secondary" disabled={busy || picked.length === 0}
                        label={picked.length ? plural('reroll_dice', picked.length) : t('Reroll picked')}
                        onPress={() => act('reroll', { dice: picked })} />
              </View>
              <View style={{ flex: 1 }}>
                <Button testID="reroll-all" kind="secondary" disabled={busy} label={t('Reroll all')}
                        onPress={() => act('reroll', { dice: [0, 1, 2, 3, 4] })} />
              </View>
            </View>
          </>
        ) : (
          <Muted>{t('No rerolls left. Choose where to write this roll.')}</Muted>
        )
      ) : (
        <Muted>{t('{name} is choosing a move. You will see it here as it happens.', { name: state.names[game.current] })}</Muted>
      )}
    </View>
  );
}

function Moves({ state, moves, mode, picked, busy, onMode, onPick, onConfirm }: {
  state: State;
  moves: { score: Move[]; cross: Move[] };
  mode: 'score' | 'cross';
  picked: Move | null;
  busy: boolean;
  onMode: (mode: 'score' | 'cross') => void;
  onPick: (move: Move) => void;
  onConfirm: (move: Move) => void;
}) {
  const { t } = useApp();
  const options = mode === 'score' ? moves.score : moves.cross;
  const can = state.can.includes(mode);
  return (
    <View style={styles.moves} testID="moves">
      <Choice<'score' | 'cross'>
        testID="move-kind"
        value={mode}
        onChange={onMode}
        options={[{ value: 'score', label: t('Score') }, { value: 'cross', label: t('Cross out') }]}
      />
      {options.length === 0 ? (
        mode === 'score'
          ? <Rich text={t('Nothing can be scored with these dice. Reroll, or switch to **Cross out**.')} />
          : <Muted>{t('There is nothing left to cross out.')}</Muted>
      ) : (
        <View style={styles.options}>
          {options.map((move) => {
            const on = picked?.row === move.row && picked.slot === move.slot;
            const best = mode === 'score' && move.best;
            return (
              <Pressable
                key={`${move.row}.${move.slot}`}
                testID={`option-${move.row}${best ? '-best' : ''}`}
                accessibilityRole="radio"
                accessibilityState={{ checked: on }}
                onPress={() => onPick(move)}
                style={[styles.option, best && styles.optionBest, on && styles.optionPicked]}>
                <Text style={[styles.optionText, best && styles.optionBestText, on && styles.optionPickedText]}>
                  {move.label}
                </Text>
              </Pressable>
            );
          })}
        </View>
      )}
      <Button
        testID="confirm"
        label={picked ? picked.action : mode === 'score' ? t('Choose a row above') : t('Choose a row to cross out')}
        disabled={busy || !picked || !can}
        onPress={() => picked && onConfirm(picked)}
      />
    </View>
  );
}

function StartingThrow({ state, game, act, busy }: { state: State; game: Game; act: Act; busy: boolean }) {
  const { t } = useApp();
  const st = game.starting_throw;
  const thrower = state.names[game.current];
  const latest = new Map(st.throws.map((th) => [th.seat, th]));
  return (
    <Card testID="starting-throw">
      <Title>{t('Who goes first?')}</Title>
      <Muted>
        {st.round > 1
          ? t('A tie for the lowest total: {names} throw again.', { names: st.throwing.map((s) => state.names[s]).join(', ') })
          : t('Everyone throws all five dice. The lowest total goes first.')}
      </Muted>
      {state.names.map((name, seat) => {
        const th = latest.get(seat);
        const inRound = st.throwing.includes(seat);
        // A player out of a tie's next round keeps the throw that put them out (dimmed), so
        // everyone can see how much they threw (Backlog item 16).
        const shown = th && (th.round === st.round || !inRound);
        return (
          <View key={seat} testID={`throw-${seat}`} style={[styles.throwRow, !inRound && styles.out]}>
            <Text style={styles.throwName} numberOfLines={1}>{name}</Text>
            {shown && th ? (
              <View style={styles.smallDice}>
                {th.dice.map((die, i) => <DieFace key={i} die={die} size={22} />)}
                <Text style={styles.throwTotal}>{th.total}</Text>
              </View>
            ) : (
              <Text style={styles.throwNote}>{inRound ? (seat === game.current ? t('throws next') : t('waiting')) : ''}</Text>
            )}
          </View>
        );
      })}
      {state.can.includes('throw') ? (
        <Button testID="start-throw" disabled={busy}
                label={state.local ? t('Throw for {name}', { name: thrower }) : t('Throw the dice')}
                onPress={() => act('throw')} />
      ) : (
        <Muted>{t('Waiting for {name} to throw…', { name: thrower })}</Muted>
      )}
    </Card>
  );
}

/** Until the first move: who threw the lowest, and every starting throw (Backlog item 16). */
function StarterSummary({ state, game }: { state: State; game: Game }) {
  const { t } = useApp();
  const st = game.starting_throw;
  if (game.last_move !== null || st.first_player === null) return null;
  const decisive = [...st.throws].reverse().find((th) => th.seat === st.first_player);
  const total = decisive?.total ?? 0;
  const text = !state.local && st.first_player === state.you
    ? t('You threw the lowest ({total}) and go first.', { total })
    : t('{name} threw the lowest ({total}) and goes first.', { name: state.names[st.first_player], total });
  const latest = new Map(st.throws.map((th) => [th.seat, th]));
  return (
    <View style={styles.summary} testID="starter">
      <Text style={styles.summaryText}>{text}</Text>
      {state.names.map((name, seat) => {
        const th = latest.get(seat);
        return th ? (
          <View key={seat} style={styles.throwRow}>
            <Text style={styles.throwName} numberOfLines={1}>{name}</Text>
            <View style={styles.smallDice}>
              {th.dice.map((die, i) => <DieFace key={i} die={die} size={18} />)}
              <Text style={styles.throwTotal}>{th.total}</Text>
            </View>
          </View>
        ) : null;
      })}
    </View>
  );
}

function Results({ state, game, act, busy }: { state: State; game: Game; act: Act; busy: boolean }) {
  const { t } = useApp();
  const club = state.club;
  const winners = game.winners;
  const title = winners.length > 1
    ? t('It’s a draw!')
    : !state.local && winners[0] === state.you
      ? t('You win!')
      : t('{name} wins!', { name: state.names[winners[0]] });
  const order = useMemo(
    () => game.players.map((p, seat) => ({ seat, name: p.name, total: p.total })).sort((a, b) => b.total - a.total),
    [game.players]);
  return (
    <Card testID="results">
      <Text style={styles.resultTitle}>{title}</Text>
      {order.map((p) => (
        <View key={p.seat} style={styles.resultRow}>
          <Text style={[styles.resultName, winners.includes(p.seat) && styles.winner]}>{p.name}</Text>
          <Text style={styles.resultScore}>{t('{score} pts', { score: p.total })}</Text>
        </View>
      ))}
      {state.club_result ? <ClubRatings result={state.club_result} /> : null}
      {state.can.includes('rematch') ? (
        <Button testID="rematch" label={t('Play again')} disabled={busy} onPress={() => act('rematch', {}, false)} />
      ) : null}
      {club ? (
        <Button kind="secondary" testID="club-table-button" label={t('Club table')}
                onPress={() => router.dismissTo({ pathname: '/club/[code]', params: { code: club } })} />
      ) : null}
      <Button kind="secondary" label={t('Home')} onPress={() => router.dismissTo('/')} />
    </Card>
  );
}

/** "Games at this table: 3 · 👑 Ann 2 · Bob 1", once a game here has finished. */
function TableScore({ state }: { state: State }) {
  const { t } = useApp();
  const { games, wins, draws } = state.table;
  if (!games) return null;
  const order = state.names.map((name, seat) => ({ name, wins: wins[seat] ?? 0, seat }))
    .sort((a, b) => b.wins - a.wins || a.seat - b.seat);
  const leader = order[0] && order[0].wins > 0 && (order.length === 1 || order[0].wins > order[1].wins) ? order[0].seat : null;
  const people = order.map((p) => `${p.seat === leader ? '👑 ' : ''}${p.name} ${p.wins}`).join(' · ');
  const tail = draws ? ` · ${t('draws: {n}', { n: draws })}` : '';
  const club = state.club ? ` · 🏆 ${t('club game')}` : '';
  return (
    <Text testID="table-score" style={styles.tableScore}>
      {`${t('Games at this table: {n}', { n: games })} · ${people}${tail}${club}`}
    </Text>
  );
}

const styles = StyleSheet.create({
  diffSwitch: { flexDirection: 'row', alignItems: 'center', justifyContent: 'flex-end', gap: 8, marginBottom: 4 },
  diffLabel: { fontSize: 13, color: colors.muted },
  bar: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  barHome: { fontSize: 16, color: colors.accent, fontWeight: '600' },
  barTitle: { flex: 1, fontSize: 15, color: colors.muted, textAlign: 'center' },
  barCode: { fontWeight: '700', color: colors.text, letterSpacing: 1 },
  rulesButton: {
    width: 34, height: 34, borderRadius: 17, borderWidth: 1, borderColor: colors.line,
    backgroundColor: colors.card, alignItems: 'center', justifyContent: 'center',
  },
  rulesButtonText: { fontSize: 17, fontWeight: '700', color: colors.accent },
  code: { fontSize: 34, fontWeight: '800', letterSpacing: 6, color: colors.text, textAlign: 'center' },
  codeKey: { fontSize: 24, fontWeight: '700', letterSpacing: 4, color: colors.accent },
  waitingName: { fontSize: 16, color: colors.text },
  turn: { fontSize: 20, fontWeight: '700', color: colors.text },
  turnMine: { color: colors.accent },
  turnLine: { flexDirection: 'row', flexWrap: 'wrap', alignItems: 'center', gap: 8 },
  firstRoll: {
    fontSize: 13, color: colors.gold, backgroundColor: colors.goldSoft, borderRadius: 8,
    paddingHorizontal: 8, paddingVertical: 2, overflow: 'hidden',
  },
  diceArea: { gap: 12 },
  dice: { flexDirection: 'row', justifyContent: 'space-between', paddingTop: 8, maxWidth: 340 },
  buttons: { flexDirection: 'row', gap: 10 },
  moves: { gap: 12, borderTopWidth: 1, borderTopColor: colors.line, paddingTop: 12 },
  options: { flexDirection: 'row', flexWrap: 'wrap', gap: 8 },
  option: {
    borderRadius: 999, borderWidth: 1, borderColor: colors.line, backgroundColor: colors.card,
    paddingHorizontal: 12, paddingVertical: 8,
  },
  optionBest: { backgroundColor: colors.goldSoft, borderColor: '#F0C36A' },
  optionPicked: { backgroundColor: colors.accent, borderColor: colors.accent },
  optionText: { fontSize: 14, color: colors.text },
  optionBestText: { color: '#7A5200', fontWeight: '700' },
  optionPickedText: { color: '#FFFFFF', fontWeight: '600' },
  throwRow: { flexDirection: 'row', alignItems: 'center', gap: 10, minHeight: 30 },
  out: { opacity: 0.45 },
  throwName: { width: 90, fontSize: 15, color: colors.text },
  throwNote: { fontSize: 14, color: colors.faint },
  smallDice: { flexDirection: 'row', alignItems: 'center', gap: 4 },
  throwTotal: { fontSize: 15, fontWeight: '700', color: colors.text, marginLeft: 6 },
  summary: { gap: 4, backgroundColor: colors.accentSoft, borderRadius: 10, padding: 10 },
  summaryText: { fontSize: 15, fontWeight: '600', color: colors.accent },
  resultTitle: { fontSize: 26, fontWeight: '800', color: colors.accent },
  resultRow: { flexDirection: 'row', justifyContent: 'space-between' },
  resultName: { fontSize: 16, color: colors.text },
  winner: { fontWeight: '800' },
  resultScore: { fontSize: 16, color: colors.muted },
  lastMove: { fontSize: 13, color: '#9A4D00' },
  tableScore: { fontSize: 14, color: colors.muted, lineHeight: 20 },
  boardCard: { paddingHorizontal: 10 },
});
