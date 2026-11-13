import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import { STRINGS } from './strings'

/**
 * Site language. English is the default; a student can switch the public
 * pages (home, pricing, FAQ, sign-up, login) to their own language. The
 * choice is remembered on their device. Missing translations fall back to
 * English, so a page never shows a blank.
 */
export const LANGUAGES = [
  ['en', 'English'],
  ['fr', 'Français'],
  ['es', 'Español'],
  ['it', 'Italiano'],
  ['pt', 'Português'],
]

const STORAGE_KEY = 'fg_lang'
const LanguageContext = createContext(null)

function savedLanguage() {
  try {
    const value = localStorage.getItem(STORAGE_KEY)
    return LANGUAGES.some(([code]) => code === value) ? value : 'en'
  } catch {
    return 'en'
  }
}

export function LanguageProvider({ children }) {
  const [lang, setLangState] = useState(savedLanguage)

  useEffect(() => {
    document.documentElement.lang = lang
  }, [lang])

  const value = useMemo(() => {
    function setLang(code) {
      setLangState(code)
      try {
        localStorage.setItem(STORAGE_KEY, code)
      } catch {
        /* private mode: the choice lasts for this visit */
      }
    }
    // t('pricing.period', { m: 30 }) -> "per 30-min lesson"
    function t(key, vars) {
      let text = STRINGS[lang]?.[key] ?? STRINGS.en[key] ?? key
      if (vars) {
        for (const [name, val] of Object.entries(vars)) text = text.replaceAll(`{${name}}`, String(val))
      }
      return text
    }
    return { lang, setLang, t }
  }, [lang])

  return <LanguageContext.Provider value={value}>{children}</LanguageContext.Provider>
}

export function useT() {
  const ctx = useContext(LanguageContext)
  if (ctx) return ctx
  // Outside the provider (e.g. tests): English
  return { lang: 'en', setLang: () => {}, t: (key) => STRINGS.en[key] ?? key }
}
