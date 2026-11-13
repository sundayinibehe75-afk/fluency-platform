import { LANGUAGES, useT } from './LanguageContext'

export default function LanguageSwitcher() {
  const { lang, setLang, t } = useT()
  return (
    <label className="lang-switch" title={t('nav.language')}>
      <span aria-hidden="true">🌐</span>
      <span className="visually-hidden">{t('nav.language')}</span>
      <select value={lang} onChange={(e) => setLang(e.target.value)}>
        {LANGUAGES.map(([code, name]) => (
          <option key={code} value={code}>
            {name}
          </option>
        ))}
      </select>
    </label>
  )
}
