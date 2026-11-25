/** Starting a game from a screen (home, a club): the request, the seat kept on the device, the game opened. */

import { router } from 'expo-router';

import type { Connection, Seat } from './api';
import { saveGame } from './storage';

/** Start a game, online (`create`) or on one device (`create_local`), keep this device's seat in it, and open it. */
export async function startGame(connection: Connection, op: 'create' | 'create_local',
                                fields: Record<string, unknown>): Promise<void> {
  const seat = await connection.request<Seat>(op, fields);
  await saveGame({ code: seat.code, key: seat.state.key, local: seat.state.local, names: seat.state.names },
                 seat.token);
  router.push({ pathname: '/game/[code]', params: { code: seat.code } });
}
