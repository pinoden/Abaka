/**
 * The app's texts in English and Russian, as on the web: the code is written with English
 * texts in t("..."), and the Russian versions come from abaka/i18n.py, exported into
 * ../texts.json by tools/export_texts.py (never edit that file by hand). A new text gets
 * its Russian version in abaka/i18n.py; tests/test_mobile_texts.py checks every t("...")
 * here has one.
 *
 * Texts the server sends (move labels, row names, error messages) are already in the
 * request's language.
 */

import texts from '../texts.json';

import type { Lang } from './api';

const RU: Record<string, string> = texts.ru;
type PluralName = keyof typeof texts.plurals;

/** `text` (an English template) in `lang`, with {values} filled in. */
export function translate(lang: Lang, text: string, values?: Record<string, string | number>): string {
  let out = lang === 'ru' ? (RU[text] ?? text) : text;
  if (values) {
    out = out.replace(/\{(\w+)\}/g, (match, name: string) =>
      name in values ? String(values[name]) : match);
  }
  return out;
}

/** A plural form worked out on the server's side: "2 rerolls", "Перебросить 3 кубика". */
export function plural(lang: Lang, name: PluralName, n: number): string {
  const forms = texts.plurals[name][lang] as Record<string, string>;
  return forms[String(n)] ?? String(n);
}
