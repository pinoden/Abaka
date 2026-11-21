/**
 * What every screen shares: the language, the one connection to the server, and the
 * board's rows as the server names them (`info`, in the current language).
 */

import { getLocales } from 'expo-localization';
import { createContext, type ReactNode, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { AppState } from 'react-native';

import { Connection, type Info, type Lang } from './api';
import { serverUrl } from './server';
import { savedLanguage, saveLanguage } from './storage';
import { plural, translate } from './texts';

type T = (text: string, values?: Record<string, string | number>) => string;

type AppValue = {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: T;
  plural: (name: Parameters<typeof plural>[1], n: number) => string;
  connection: Connection;
  /** The board's rows and the limits, from the server (null until it answers). */
  info: Info | null;
  /** Whether the connection to the server is open. */
  online: boolean;
  /** A row's name in the current language. */
  rowName: (row: string) => string;
};

const AppContext = createContext<AppValue | null>(null);

function deviceLanguage(): Lang {
  try {
    return getLocales()[0]?.languageCode === 'ru' ? 'ru' : 'en';
  } catch {
    return 'en';
  }
}

export function AppProvider({ children }: { children: ReactNode }) {
  const [connection] = useState(() => new Connection(serverUrl()));
  const [lang, setLangState] = useState<Lang>(deviceLanguage);
  const [info, setInfo] = useState<Info | null>(null);
  const [online, setOnline] = useState(false);
  const infoLang = useRef<Lang | null>(null);

  const loadInfo = useCallback(() => {
    const asked = connection.language();
    connection.request<Info>('info').then((answer) => {
      if (connection.language() === asked) {
        infoLang.current = asked;
        setInfo(answer);
      }
    }, () => { /* offline: asked again when the connection opens */ });
  }, [connection]);

  useEffect(() => {
    savedLanguage().then((saved) => { if (saved) setLangState(saved); });
  }, []);

  useEffect(() => {
    connection.setLanguage(lang);
    connection.rewatch(); // the watched game's texts in the new language
    loadInfo();
  }, [connection, lang, loadInfo]);

  useEffect(() => {
    const stopListening = connection.listen((up) => {
      setOnline(up);
      if (up && infoLang.current !== connection.language()) loadInfo();
    });
    const listener = AppState.addEventListener('change', (status) => {
      if (status === 'active') connection.wake();
    });
    return () => {
      stopListening();
      listener.remove();
    };
  }, [connection, loadInfo]);

  const value = useMemo<AppValue>(() => {
    const names = new Map((info?.rows ?? []).map((r) => [r.row, r.name]));
    return {
      lang,
      setLang: (next: Lang) => {
        setLangState(next);
        saveLanguage(next);
      },
      t: (text, values) => translate(lang, text, values),
      plural: (name, n) => plural(lang, name, n),
      connection,
      info,
      online,
      rowName: (row) => names.get(row) ?? row,
    };
  }, [lang, info, online, connection]);

  return <AppContext.Provider value={value}>{children}</AppContext.Provider>;
}

export function useApp(): AppValue {
  const value = useContext(AppContext);
  if (!value) throw new Error('useApp outside AppProvider');
  return value;
}
