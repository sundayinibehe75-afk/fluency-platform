import { useEffect, useMemo, useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/dateUtils'
import { parseVocabulary } from '../../utils/profile'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

const TABS = ['Lessons', 'My words']

export default function LessonNotes() {
  const { user } = useAuth()
  const api = useApi()
  const [notes, setNotes] = useState([])
  const [loading, setLoading] = useState(true)
  const [tab, setTab] = useState('Lessons')
  const [query, setQuery] = useState('')
  const [hideMeaning, setHideMeaning] = useState(false)
  const [revealed, setRevealed] = useState(() => new Set())

  useEffect(() => {
    if (user?.role !== 'student') return
    api
      .get('/notes/me')
      .then((res) => setNotes(res.data))
      .catch((err) => console.error('Failed to load notes:', err))
      .finally(() => setLoading(false))
  }, [user])

  // Every word from every lesson, newest first, without duplicates
  const words = useMemo(() => {
    const seen = new Set()
    const list = []
    for (const note of notes) {
      for (const item of parseVocabulary(note.vocabulary)) {
        const key = item.word.toLowerCase()
        if (seen.has(key)) continue
        seen.add(key)
        list.push({ ...item, lesson: note.lesson_start })
      }
    }
    return list
  }, [notes])

  if (!user) return <Navigate to="/login?next=/notes" replace />
  if (user.role !== 'student') return <Navigate to="/admin" replace />

  const q = query.trim().toLowerCase()
  const shownWords = words.filter(
    (w) => !q || w.word.toLowerCase().includes(q) || w.meaning.toLowerCase().includes(q)
  )

  function toggle(word) {
    setRevealed((prev) => {
      const next = new Set(prev)
      next.has(word) ? next.delete(word) : next.add(word)
      return next
    })
  }

  return (
    <>
      <Nav />
      <main className="dashboard-page">
        <div className="container">
          <h1 className="section-title" style={{ marginTop: '5rem', marginBottom: '1.5rem' }}>
            My Notes
          </h1>

          <div className="admin-tabs">
            {TABS.map((t) => (
              <button
                key={t}
                className={`admin-tab-btn ${tab === t ? 'admin-tab-btn--active' : ''}`}
                onClick={() => setTab(t)}
                aria-pressed={tab === t}
              >
                {t}
                {t === 'My words' && words.length > 0 && ` (${words.length})`}
              </button>
            ))}
          </div>

          {loading ? (
            <p>Loading your notes...</p>
          ) : notes.length === 0 ? (
            <p className="dashboard-empty">
              No notes yet. After each lesson your tutor adds a summary, homework and new words here.{' '}
              <Link to="/booking" className="dashboard-link">Book a lesson</Link>
            </p>
          ) : tab === 'Lessons' ? (
            <div className="notes-list">
              {notes.map((note) => (
                <article key={note.booking_id} className="notes-card">
                  <h2 className="notes-card-date">{formatDate(note.lesson_start)}</h2>
                  {note.summary && (
                    <>
                      <h3>What we covered</h3>
                      <p className="notes-text">{note.summary}</p>
                    </>
                  )}
                  {note.homework && (
                    <>
                      <h3>Homework</h3>
                      <p className="notes-text notes-homework">{note.homework}</p>
                    </>
                  )}
                  {note.vocabulary && (
                    <>
                      <h3>New words</h3>
                      <ul className="notes-words">
                        {parseVocabulary(note.vocabulary).map((w, i) => (
                          <li key={i}>
                            <strong>{w.word}</strong>
                            {w.meaning && <span> — {w.meaning}</span>}
                          </li>
                        ))}
                      </ul>
                    </>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <div>
              <div className="words-toolbar">
                <input
                  type="search"
                  className="admin-search"
                  placeholder="Search words"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                <label className="words-practice">
                  <input
                    type="checkbox"
                    checked={hideMeaning}
                    onChange={(e) => {
                      setHideMeaning(e.target.checked)
                      setRevealed(new Set())
                    }}
                  />
                  Practice mode (hide meanings)
                </label>
              </div>
              {shownWords.length === 0 ? (
                <p className="dashboard-empty">No words found.</p>
              ) : (
                <ul className="words-list">
                  {shownWords.map((w) => {
                    const hidden = hideMeaning && !revealed.has(w.word)
                    return (
                      <li key={w.word}>
                        <button
                          type="button"
                          className="words-item"
                          onClick={() => hideMeaning && toggle(w.word)}
                          aria-label={hidden ? `Show meaning of ${w.word}` : w.word}
                        >
                          <strong>{w.word}</strong>
                          <span className={hidden ? 'words-hidden' : ''}>
                            {hidden ? 'tap to show' : w.meaning || '—'}
                          </span>
                        </button>
                      </li>
                    )
                  })}
                </ul>
              )}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  )
}
