import type { Lang } from '@/lib/api';
import { useApp } from '@/lib/app';

import { Choice } from './ui';

/** EN / RU, kept on the device. */
export function LanguageSwitch() {
  const { lang, setLang } = useApp();
  return (
    <Choice<Lang>
      testID="language"
      value={lang}
      onChange={setLang}
      options={[{ value: 'en', label: 'EN' }, { value: 'ru', label: 'RU' }]}
    />
  );
}
