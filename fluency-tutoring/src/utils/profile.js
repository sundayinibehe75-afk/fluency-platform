export const GOALS = [
  { value: 'exam', label: 'Pass an exam (Goethe, telc, TestDaF)' },
  { value: 'work', label: 'German for work' },
  { value: 'study', label: 'Study in Germany' },
  { value: 'daily_life', label: 'Everyday life and travel' },
  { value: 'family', label: 'Family, partner or moving' },
  { value: 'other', label: 'Something else' },
]

export const LEVELS = [
  ['A0', 'A0 — No experience'],
  ['A1', 'A1 — Beginner'],
  ['A2', 'A2 — Elementary'],
  ['B1', 'B1 — Intermediate'],
  ['B2', 'B2 — Upper Intermediate'],
  ['C1', 'C1 — Advanced'],
  ['C2', 'C2 — Proficient'],
]

export function goalLabel(value) {
  return GOALS.find((g) => g.value === value)?.label || '—'
}

export function browserTimeZone() {
  try {
    return Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
  } catch {
    return 'UTC'
  }
}

export function allTimeZones() {
  try {
    return Intl.supportedValuesOf('timeZone')
  } catch {
    return [browserTimeZone(), 'UTC']
  }
}

/** Split vocabulary text ("der Zug - train" per line) into {word, meaning}. */
export function parseVocabulary(text) {
  return (text || '')
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const match = line.match(/^(.*?)\s+[-–—=:]\s+(.*)$/)
      return match ? { word: match[1], meaning: match[2] } : { word: line, meaning: '' }
    })
}
