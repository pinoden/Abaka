/**
 * Where the game server is. The live server for apps comes with Backlog item 25, stage B;
 * until then the app plays on a server run for development:
 *
 * - EXPO_PUBLIC_ABAKA_SERVER, set when the app is started or built (for example
 *   `EXPO_PUBLIC_ABAKA_SERVER=http://192.168.1.20:8501 npx expo start`);
 * - otherwise the computer running Expo's development server, port 8501, where
 *   `streamlit run abaka_server.py` serves the API;
 * - otherwise (a web build) the page's own host, port 8501.
 *
 * The web build, used for checks (tools/app_check.py), also takes `?server=` in its
 * address, but only a server on the same computer: a link must never send players' moves
 * to someone else's server.
 */

import Constants from 'expo-constants';

export const DEV_PORT = 8501;

const LOOPBACK = /^http:\/\/(127\.0\.0\.1|localhost)(:\d+)?$/;

export function serverUrl(): string {
  const asked = new URLSearchParams(globalThis.location?.search ?? '').get('server')?.replace(/\/+$/, '');
  if (asked && LOOPBACK.test(asked)) return asked;
  const configured = process.env.EXPO_PUBLIC_ABAKA_SERVER;
  if (configured) return configured.replace(/\/+$/, '');
  const devHost = Constants.expoConfig?.hostUri?.split(':')[0];
  if (devHost) return `http://${devHost}:${DEV_PORT}`;
  const pageHost = globalThis.location?.hostname;
  return `http://${pageHost || 'localhost'}:${DEV_PORT}`;
}
