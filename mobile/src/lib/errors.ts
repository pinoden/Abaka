import { ApiError } from './api';

/** What to tell the player about a refused request (docs/API.md, Errors). */
export function errorText(error: unknown, t: (text: string) => string): string {
  if (error instanceof ApiError) {
    if (error.code === 'offline') return t('Cannot reach the server. Check your connection.');
    if (error.code === 'protocol') return t('This app and the server do not match. Update the app, or try again later.');
    return error.message;
  }
  return t('Something went wrong on the server. Please try again.');
}
