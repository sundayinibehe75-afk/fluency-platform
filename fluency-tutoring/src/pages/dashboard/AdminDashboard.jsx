import { Fragment, useState, useEffect } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/dateUtils'
import { formatCents } from '../../utils/formatCurrency'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'
import { getErrorMessage } from '../../utils/errors'
import { LessonTypeBadge } from './StudentDashboard'
import { goalLabel } from '../../utils/profile'

const TUTOR_ID = import.meta.env.VITE_TUTOR_ID || '00000000-0000-0000-0000-000000000001'

const TABS = ['Overview', 'Bookings', 'Students', 'Availability', 'Time Off', 'Tutor Profile', 'Reviews']

const PLAN_NAMES = { plan_2x: '2× a week', plan_3x: '3× a week', plan_4x: '4× a week', plan_5x: '5× a week' }

function OverviewTab() {
  const api = useApi()
  const [stats, setStats] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api
      .get('/admin/stats')
      .then((res) => setStats(res.data))
      .catch((err) => setError(getErrorMessage(err, 'Could not load the numbers.')))
  }, [])

  if (error) return <p className="admin-form-message">{error}</p>
  if (!stats) return <p>Loading...</p>

  const cards = [
    ['Income', formatCents(stats.income_this_month_cents), `${stats.month_label}, after refunds`],
    ['Lessons taught', stats.lessons_taught_this_month, stats.month_label],
    ['Next 7 days', stats.upcoming_next_7_days, 'lessons booked'],
    ['Active plans', stats.active_plans,
      Object.entries(stats.plans_by_type).map(([k, n]) => `${n} × ${PLAN_NAMES[k] || k}`).join(', ') || 'none yet'],
    ['Students', stats.students, `${stats.new_students_this_month} new this month`],
    ['Free trials', stats.trials_this_month, 'this month'],
    ['Trial → plan', stats.trial_students ? `${Math.round((100 * stats.trial_to_plan) / stats.trial_students)}%` : '—',
      `${stats.trial_to_plan} of ${stats.trial_students} trial students bought a plan`],
    ['Late cancellations', stats.late_cancellations_this_month, 'this month (under 12h)'],
  ]

  return (
    <div className="admin-overview">
      <div className="admin-stats-grid">
        {cards.map(([title, value, note]) => (
          <div className="admin-stat-card" key={title}>
            <h3>{title}</h3>
            <p className="admin-stat-value">{value}</p>
            <span className="admin-stat-note">{note}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function NotesEditor({ booking, onSaved, onClose }) {
  const api = useApi()
  const [form, setForm] = useState(null)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')

  useEffect(() => {
    api
      .get(`/bookings/${booking.id}/notes`)
      .then((res) =>
        setForm({
          summary: res.data.summary || '',
          homework: res.data.homework || '',
          vocabulary: res.data.vocabulary || '',
        })
      )
      .catch((err) => setMessage(getErrorMessage(err, 'Could not load notes.')))
  }, [booking.id])

  async function save(e) {
    e.preventDefault()
    try {
      setSaving(true)
      await api.put(`/bookings/${booking.id}/notes`, form)
      setMessage(booking.has_notes ? 'Saved.' : 'Saved. The student has been emailed.')
      onSaved()
    } catch (err) {
      setMessage(getErrorMessage(err, 'Could not save.'))
    } finally {
      setSaving(false)
    }
  }

  if (!form) return <p className="admin-muted">{message || 'Loading...'}</p>
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  return (
    <form onSubmit={save} className="notes-editor">
      <label>
        What we covered
        <textarea rows={3} value={form.summary} onChange={set('summary')} placeholder="Topics, grammar, what went well, what to practise" />
      </label>
      <label>
        Homework
        <textarea rows={2} value={form.homework} onChange={set('homework')} placeholder="e.g. Write 5 sentences in the Perfekt" />
      </label>
      <label>
        New words <small className="admin-muted">(one per line: der Bahnhof - train station)</small>
        <textarea rows={4} value={form.vocabulary} onChange={set('vocabulary')} />
      </label>
      <div className="dashboard-card-actions">
        <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
          {saving ? 'Saving…' : 'Save notes'}
        </button>
        <button type="button" className="btn btn-outline-dark btn-sm" onClick={onClose}>Close</button>
        {message && <span className="admin-muted">{message}</span>}
      </div>
    </form>
  )
}

function BookingsTab() {
  const api = useApi()
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [cancellingId, setCancellingId] = useState(null)
  const [notesId, setNotesId] = useState(null)

  useEffect(() => {
    fetchBookings()
  }, [])

  async function fetchBookings() {
    try {
      setLoading(true)
      const response = await api.get('/bookings')
      setBookings(response.data)
    } catch (err) {
      console.error('Failed to fetch bookings:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleCancel(bookingId) {
    if (
      !window.confirm(
        'Cancel this booking? The student gets a full refund, or the lesson back if it was a plan lesson.'
      )
    )
      return
    try {
      setCancellingId(bookingId)
      await api.post(`/bookings/${bookingId}/cancel`)
      setBookings((prev) =>
        prev.map((b) => (b.id === bookingId ? { ...b, status: 'cancelled' } : b))
      )
    } catch (err) {
      console.error('Failed to cancel booking:', err)
      alert(getErrorMessage(err, 'Failed to cancel booking. Please try again.'))
    } finally {
      setCancellingId(null)
    }
  }

  if (loading) {
    return <p>Loading bookings...</p>
  }

  if (bookings.length === 0) {
    return <p>No bookings found.</p>
  }

  return (
    <div className="admin-table-wrapper">
      <table className="admin-table">
        <thead>
          <tr>
            <th>Student</th>
            <th>Date/Time</th>
            <th>Type</th>
            <th>Status</th>
            <th>Amount</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {bookings.map((booking) => (
            <Fragment key={booking.id}>
            <tr>
              <td>{booking.student_name || 'Student'}</td>
              <td>{formatDate(booking.start_at || booking.slot_start_at)}</td>
              <td><LessonTypeBadge type={booking.booking_type} /></td>
              <td>
                <span className={`admin-status admin-status--${booking.status}`}>
                  {booking.status}
                </span>
                {booking.late_cancellation && <small className="admin-late"> late</small>}
              </td>
              <td>{formatCents(booking.price_cents, booking.currency)}</td>
              <td>
                {booking.status === 'confirmed' &&
                  new Date(booking.start_at) - new Date() <= 10 * 60 * 1000 &&
                  new Date(booking.end_at) > new Date() && (
                    <Link to={`/lessons/${booking.id}`} className="btn btn-primary btn-sm">
                      Join
                    </Link>
                  )}{' '}
                {booking.status === 'confirmed' && new Date(booking.start_at) > new Date() && (
                  <Link to={`/booking?reschedule=${booking.id}`} className="btn btn-outline-dark btn-sm">
                    Move
                  </Link>
                )}{' '}
                {['confirmed', 'completed'].includes(booking.status) &&
                  new Date(booking.start_at) <= new Date() && (
                    <button
                      className={`btn btn-sm ${booking.has_notes ? 'btn-outline-dark' : 'btn-primary'}`}
                      onClick={() => setNotesId(notesId === booking.id ? null : booking.id)}
                    >
                      {booking.has_notes ? 'Edit notes' : 'Add notes'}
                    </button>
                  )}{' '}
                {booking.status === 'confirmed' && new Date(booking.start_at) > new Date() && (
                  <button
                    onClick={() => handleCancel(booking.id)}
                    disabled={cancellingId === booking.id}
                    className="btn btn-cancel btn-sm"
                  >
                    {cancellingId === booking.id ? 'Cancelling...' : 'Cancel'}
                  </button>
                )}
              </td>
            </tr>
            {notesId === booking.id && (
              <tr>
                <td colSpan={6}>
                  <NotesEditor
                    booking={booking}
                    onSaved={() =>
                      setBookings((prev) => prev.map((b) => (b.id === booking.id ? { ...b, has_notes: true } : b)))
                    }
                    onClose={() => setNotesId(null)}
                  />
                </td>
              </tr>
            )}
            </Fragment>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function inDays(days) {
  const d = new Date(Date.now() + days * 864e5)
  return d.toISOString().slice(0, 10)
}

function endOfDayIso(dateStr) {
  // The chosen date, until 23:59 local time
  return new Date(`${dateStr}T23:59:00`).toISOString()
}

function StudentCredits({ student, onChanged }) {
  const api = useApi()
  const [grants, setGrants] = useState([])
  const [lessons, setLessons] = useState(1)
  const [expires, setExpires] = useState(inDays(30))
  const [note, setNote] = useState('')
  const [message, setMessage] = useState('')

  useEffect(() => {
    load()
  }, [student.id])

  async function load() {
    try {
      const res = await api.get(`/admin/students/${student.id}/credits`)
      setGrants(res.data)
    } catch (err) {
      setMessage(getErrorMessage(err, 'Could not load credits.'))
    }
  }

  async function add(e) {
    e.preventDefault()
    setMessage('')
    try {
      await api.post(`/admin/students/${student.id}/credits`, {
        lessons: Number(lessons),
        expires_at: endOfDayIso(expires),
        note: note || null,
      })
      setNote('')
      setMessage(`Added ${lessons} lesson(s).`)
      load()
      onChanged()
    } catch (err) {
      setMessage(getErrorMessage(err, 'Could not add lessons.'))
    }
  }

  async function extend(grant) {
    const value = window.prompt('New expiry date (YYYY-MM-DD):', grant.expires_at.slice(0, 10))
    if (!value) return
    try {
      await api.patch(`/admin/credits/${grant.id}`, { expires_at: endOfDayIso(value) })
      load()
      onChanged()
    } catch (err) {
      alert(getErrorMessage(err, 'Could not extend.'))
    }
  }

  const now = new Date()
  return (
    <div className="admin-credits">
      <form onSubmit={add} className="admin-credits-form">
        <label>
          Add lessons
          <input type="number" min="1" max="100" value={lessons} onChange={(e) => setLessons(e.target.value)} required />
        </label>
        <label>
          Use by
          <input type="date" value={expires} onChange={(e) => setExpires(e.target.value)} required />
        </label>
        <label className="admin-credits-note">
          Note (optional)
          <input type="text" value={note} maxLength={500} onChange={(e) => setNote(e.target.value)} placeholder="e.g. make-up lesson" />
        </label>
        <button type="submit" className="btn btn-primary btn-sm">Add</button>
      </form>
      {message && <p className="admin-form-message">{message}</p>}
      {grants.length === 0 ? (
        <p className="admin-muted">No lesson credits yet.</p>
      ) : (
        <table className="admin-table admin-table--compact">
          <thead>
            <tr><th>From</th><th>Used</th><th>Left</th><th>Expires</th><th>Note</th><th></th></tr>
          </thead>
          <tbody>
            {grants.map((g) => {
              const expired = new Date(g.expires_at) <= now
              return (
                <tr key={g.id} className={expired ? 'admin-row-muted' : ''}>
                  <td>{g.source === 'subscription' ? 'Plan' : 'Added by you'}</td>
                  <td>{g.used}/{g.total}</td>
                  <td>{expired ? 0 : g.remaining}</td>
                  <td>{formatDate(g.expires_at)}{expired && ' (expired)'}</td>
                  <td>{g.note || ''}</td>
                  <td>
                    <button className="btn btn-outline-dark btn-sm" onClick={() => extend(g)}>
                      Extend
                    </button>
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      )}
    </div>
  )
}

function StudentsTab() {
  const api = useApi()
  const [students, setStudents] = useState([])
  const [loading, setLoading] = useState(true)
  const [openId, setOpenId] = useState(null)
  const [filter, setFilter] = useState('')

  useEffect(() => {
    load()
  }, [])

  async function load() {
    try {
      const res = await api.get('/admin/students')
      setStudents(res.data)
    } catch (err) {
      console.error('Failed to fetch students:', err)
    } finally {
      setLoading(false)
    }
  }

  if (loading) return <p>Loading students...</p>
  if (students.length === 0) return <p>No students yet.</p>

  const q = filter.trim().toLowerCase()
  const shown = students.filter(
    (s) => !q || `${s.first_name} ${s.last_name} ${s.email}`.toLowerCase().includes(q)
  )

  return (
    <div>
      <input
        className="admin-search"
        type="search"
        placeholder="Search students"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
      />
      <div className="admin-table-wrapper">
        <table className="admin-table">
          <thead>
            <tr><th>Student</th><th>Plan</th><th>Lessons left</th><th>Free trial</th><th></th></tr>
          </thead>
          <tbody>
            {shown.map((s) => (
              <Fragment key={s.id}>
                <tr>
                  <td>
                    {s.first_name} {s.last_name}
                    {s.cefr_level && <span className="lesson-type lesson-type--single" style={{ marginLeft: '0.4rem' }}>{s.cefr_level}</span>}
                    <br /><small className="admin-muted">{s.email}</small>
                    {(s.learning_goal || s.goal_note) && (
                      <><br /><small>{goalLabel(s.learning_goal)}{s.goal_note ? ` — “${s.goal_note}”` : ''}</small></>
                    )}
                    <br /><small className="admin-muted">{s.timezone}</small>
                  </td>
                  <td>
                    {s.plan ? s.plan.label : '—'}
                    {s.plan?.cancel_at_period_end && <small className="admin-muted"> (ends {formatDate(s.plan.current_period_end)})</small>}
                  </td>
                  <td>
                    {s.credits_remaining}
                    {s.credits_remaining > 0 && s.credits_expire_at && (
                      <small className="admin-muted"> · by {formatDate(s.credits_expire_at)}</small>
                    )}
                  </td>
                  <td>{s.trial_available ? 'Not used' : 'Used'}</td>
                  <td>
                    <button className="btn btn-outline-dark btn-sm" onClick={() => setOpenId(openId === s.id ? null : s.id)}>
                      {openId === s.id ? 'Close' : 'Lessons'}
                    </button>
                  </td>
                </tr>
                {openId === s.id && (
                  <tr>
                    <td colSpan={5}><StudentCredits student={s} onChanged={load} /></td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

function TimeOffTab() {
  const api = useApi()
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [message, setMessage] = useState('')
  const [busy, setBusy] = useState(false)

  function range() {
    // Whole days in your local time: from the start of "from" to the end of "to"
    return {
      tutor_id: TUTOR_ID,
      start_at: new Date(`${from}T00:00:00`).toISOString(),
      end_at: new Date(new Date(`${to}T00:00:00`).getTime() + 864e5).toISOString(),
    }
  }

  async function submit(action) {
    if (!from || !to) return setMessage('Choose both dates.')
    if (to < from) return setMessage('The last day must be on or after the first day.')
    setBusy(true)
    setMessage('')
    try {
      const res = await api.post(`/availability/${action}`, range())
      const { changed, booked_lessons_in_range: booked } = res.data
      if (action === 'block') {
        setMessage(
          `Blocked ${changed} free slot(s).` +
            (booked
              ? ` ${booked} lesson(s) are already booked in these days. Move or cancel them in the Bookings tab.`
              : '')
        )
      } else {
        setMessage(`Reopened ${changed} slot(s).`)
      }
    } catch (err) {
      setMessage(getErrorMessage(err, 'Something went wrong.'))
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{ maxWidth: '500px' }}>
      <h3 style={{ marginBottom: '0.5rem' }}>Time off</h3>
      <p className="admin-muted" style={{ marginBottom: '1.5rem' }}>
        Students can't book free slots on these days. Booked lessons stay as they are.
      </p>
      <div className="admin-form-group">
        <label htmlFor="off-from">First day off</label>
        <input id="off-from" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
      </div>
      <div className="admin-form-group">
        <label htmlFor="off-to">Last day off</label>
        <input id="off-to" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
      </div>
      <button className="btn btn-primary" disabled={busy} onClick={() => submit('block')}>
        Block these days
      </button>{' '}
      <button className="btn btn-outline-dark" disabled={busy} onClick={() => submit('unblock')}>
        Reopen these days
      </button>
      {message && <p className="admin-form-message" style={{ marginTop: '1rem' }}>{message}</p>}
    </div>
  )
}

function AvailabilityTab() {
  const api = useApi()
  const [startDate, setStartDate] = useState('')
  const [times, setTimes] = useState(['09:00'])
  const [duration, setDuration] = useState(60)
  const [recurrence, setRecurrence] = useState(false)
  const [weeksAhead, setWeeksAhead] = useState(4)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [slots, setSlots] = useState([])
  const [slotsLoading, setSlotsLoading] = useState(true)

  const tutorId = TUTOR_ID

  useEffect(() => {
    fetchSlots()
  }, [])

  async function fetchSlots() {
    try {
      setSlotsLoading(true)
      const res = await api.get(`/availability/all?tutor_id=${tutorId}`)
      setSlots(res.data)
    } catch (err) {
      console.error('Failed to fetch slots:', err)
    } finally {
      setSlotsLoading(false)
    }
  }

  function addTime() {
    setTimes(prev => [...prev, '10:00'])
  }

  // Spell out the chosen time (e.g. "Wed 11 Nov, 6:08 PM") so AM/PM mix-ups
  // are visible before saving
  function slotPreview(date, time) {
    if (!date || !time) return { text: '', past: false }
    const d = new Date(`${date}T${time}:00`)
    if (Number.isNaN(d.getTime())) return { text: '', past: false }
    const past = d <= new Date()
    const text = d.toLocaleString(undefined, {
      weekday: 'short', day: 'numeric', month: 'short', hour: 'numeric', minute: '2-digit', hour12: true,
    })
    return { text: past ? `${text} (already passed)` : text, past }
  }

  function removeTime(index) {
    setTimes(prev => prev.filter((_, i) => i !== index))
  }

  function updateTime(index, value) {
    setTimes(prev => prev.map((t, i) => i === index ? value : t))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setMessage('')
    setLoading(true)

    let totalCreated = 0
    let errors = []

    for (const time of times) {
      // Times are entered in the tutor's own local time (the browser's time zone)
      const start = new Date(`${startDate}T${time}:00`)
      if (start <= new Date()) {
        errors.push(`${time}: this time has already passed (check AM/PM)`)
        continue
      }
      const startAt = start.toISOString()
      const endAt = new Date(start.getTime() + duration * 60000).toISOString()

      const body = {
        tutor_id: tutorId,
        start_at: startAt,
        end_at: endAt,
        duration_minutes: duration,
      }

      if (recurrence) {
        body.recurrence = { pattern: 'weekly', weeks_ahead: weeksAhead }
      }

      try {
        const res = await api.post('/availability', body)
        totalCreated += res.data.length
      } catch (err) {
        const detail = getErrorMessage(err, 'Failed')
        errors.push(`${time}: ${detail}`)
      }
    }

    if (totalCreated > 0) {
      setMessage(
        `✅ Created ${totalCreated} slot(s).` + (errors.length ? ` Not created: ${errors.join('; ')}` : '')
      )
      fetchSlots()
    } else if (errors.length > 0) {
      setMessage(`❌ ${errors.join('; ')}`)
    }

    setLoading(false)
  }

  async function handleDelete(slotId) {
    if (!window.confirm('Delete this slot?')) return
    try {
      await api.delete(`/availability/${slotId}`)
      setSlots(prev => prev.filter(s => s.id !== slotId))
    } catch (err) {
      alert('Failed to delete slot')
    }
  }

  return (
    <div>
      <h3 style={{ marginBottom: '1.5rem' }}>Add Availability</h3>
      <form onSubmit={handleSubmit} style={{ maxWidth: '500px', marginBottom: '2rem' }}>
        <div className="admin-form-group">
          <label htmlFor="start-date">Date</label>
          <input
            id="start-date"
            type="date"
            value={startDate}
            onChange={(e) => setStartDate(e.target.value)}
            required
          />
        </div>
        <div className="admin-form-group">
          <label>Time slots (your local time: {Intl.DateTimeFormat().resolvedOptions().timeZone})</label>
          {times.map((time, index) => (
            <div key={index} style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.5rem', alignItems: 'center' }}>
              <input
                type="time"
                value={time}
                onChange={(e) => updateTime(index, e.target.value)}
                required
                style={{ flex: 1 }}
              />
              <span className={`slot-preview${slotPreview(startDate, time).past ? ' slot-preview--past' : ''}`}>
                {slotPreview(startDate, time).text}
              </span>
              {times.length > 1 && (
                <button type="button" onClick={() => removeTime(index)} className="btn btn-cancel btn-sm">✕</button>
              )}
            </div>
          ))}
          <button type="button" onClick={addTime} style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer', fontWeight: 600, fontSize: '0.9rem', padding: '0.25rem 0' }}>
            + Add another time
          </button>
        </div>
        <div className="admin-form-group">
          <label htmlFor="duration">Duration (minutes)</label>
          <select id="duration" value={duration} onChange={(e) => setDuration(Number(e.target.value))}>
            <option value={30}>30 min</option>
            <option value={45}>45 min</option>
            <option value={60}>60 min</option>
            <option value={90}>90 min</option>
          </select>
        </div>
        <div className="admin-form-group">
          <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
            <input
              type="checkbox"
              checked={recurrence}
              onChange={(e) => setRecurrence(e.target.checked)}
              style={{ width: 'auto' }}
            />
            Repeat weekly
          </label>
        </div>
        {recurrence && (
          <div className="admin-form-group">
            <label htmlFor="weeks-ahead">For how many weeks?</label>
            <select id="weeks-ahead" value={weeksAhead} onChange={(e) => setWeeksAhead(Number(e.target.value))}>
              {[1,2,3,4,5,6,7,8].map(w => (
                <option key={w} value={w}>{w} week{w > 1 ? 's' : ''}</option>
              ))}
            </select>
          </div>
        )}
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? 'Creating...' : 'Add Slot(s)'}
        </button>
        {message && <p style={{ marginTop: '1rem', fontSize: '0.95rem' }}>{message}</p>}
      </form>

      <h3 style={{ marginBottom: '1rem' }}>Upcoming slots ({slots.length})</h3>
      {slotsLoading ? (
        <p>Loading slots...</p>
      ) : slots.length === 0 ? (
        <p style={{ color: 'var(--gray)' }}>No available slots. Add some above.</p>
      ) : (
        <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
          {slots.map(slot => (
            <div key={slot.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid var(--border)' }}>
              <span>
                {formatDate(slot.start_at)} — {slot.duration_minutes} min{' '}
                {slot.status !== 'available' && (
                  <span className={`admin-status admin-status--${slot.status}`}>{slot.status}</span>
                )}
              </span>
              <button onClick={() => handleDelete(slot.id)} className="btn btn-cancel btn-sm">Delete</button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function TutorProfileTab() {
  const api = useApi()
  const [profile, setProfile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [message, setMessage] = useState('')
  const [form, setForm] = useState({
    display_name: '',
    bio: '',
    spoken_languages: '',
    specialisms: '',
    cefr_levels_taught: '',
    years_experience: '',
  })

  const tutorId = TUTOR_ID

  useEffect(() => {
    fetchProfile()
  }, [])

  async function fetchProfile() {
    try {
      setLoading(true)
      const response = await api.get(`/tutors/${tutorId}`)
      const data = response.data
      setProfile(data)
      setForm({
        display_name: data.display_name || '',
        bio: data.bio || '',
        spoken_languages: Array.isArray(data.spoken_languages)
          ? data.spoken_languages.join(', ')
          : '',
        specialisms: Array.isArray(data.specialisms)
          ? data.specialisms.join(', ')
          : '',
        cefr_levels_taught: Array.isArray(data.cefr_levels_taught)
          ? data.cefr_levels_taught.join(', ')
          : '',
        years_experience: data.years_experience != null ? String(data.years_experience) : '',
      })
    } catch (err) {
      console.error('Failed to fetch tutor profile:', err)
      setMessage('Failed to load tutor profile.')
    } finally {
      setLoading(false)
    }
  }

  function handleChange(e) {
    const { name, value } = e.target
    setForm((prev) => ({ ...prev, [name]: value }))
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setMessage('')
    setSaving(true)
    try {
      const payload = {
        display_name: form.display_name,
        bio: form.bio,
        spoken_languages: form.spoken_languages
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        specialisms: form.specialisms
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        cefr_levels_taught: form.cefr_levels_taught
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean),
        years_experience: form.years_experience ? parseInt(form.years_experience, 10) : null,
      }
      await api.patch(`/tutors/${tutorId}`, payload)
      setMessage('Profile updated successfully.')
    } catch (err) {
      console.error('Failed to update tutor profile:', err)
      const detail = getErrorMessage(err, 'Failed to update profile.')
      setMessage(detail)
    } finally {
      setSaving(false)
    }
  }

  if (loading) {
    return <p>Loading tutor profile...</p>
  }

  return (
    <div className="admin-tutor-form">
      {message && <p className="admin-form-message">{message}</p>}
      <form onSubmit={handleSubmit}>
        <div className="admin-form-group">
          <label htmlFor="display_name">Display Name</label>
          <input
            id="display_name"
            name="display_name"
            type="text"
            value={form.display_name}
            onChange={handleChange}
            required
          />
        </div>
        <div className="admin-form-group">
          <label htmlFor="bio">Bio</label>
          <textarea
            id="bio"
            name="bio"
            value={form.bio}
            onChange={handleChange}
            rows={4}
          />
        </div>
        <div className="admin-form-group">
          <label htmlFor="spoken_languages">Spoken Languages (comma-separated)</label>
          <input
            id="spoken_languages"
            name="spoken_languages"
            type="text"
            value={form.spoken_languages}
            onChange={handleChange}
          />
        </div>
        <div className="admin-form-group">
          <label htmlFor="specialisms">Specialisms (comma-separated)</label>
          <input
            id="specialisms"
            name="specialisms"
            type="text"
            value={form.specialisms}
            onChange={handleChange}
          />
        </div>
        <div className="admin-form-group">
          <label htmlFor="cefr_levels_taught">CEFR Levels Taught (comma-separated)</label>
          <input
            id="cefr_levels_taught"
            name="cefr_levels_taught"
            type="text"
            value={form.cefr_levels_taught}
            onChange={handleChange}
          />
        </div>
        <div className="admin-form-group">
          <label htmlFor="years_experience">Years of Experience</label>
          <input
            id="years_experience"
            name="years_experience"
            type="number"
            min="0"
            value={form.years_experience}
            onChange={handleChange}
          />
        </div>
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Saving...' : 'Update Profile'}
        </button>
      </form>
    </div>
  )
}

function ReviewsTab() {
  const api = useApi()
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(true)
  const [togglingId, setTogglingId] = useState(null)

  const tutorId = TUTOR_ID

  useEffect(() => {
    fetchReviews()
  }, [])

  async function fetchReviews() {
    try {
      setLoading(true)
      const response = await api.get(`/reviews?tutor_id=${tutorId}`)
      setReviews(response.data)
    } catch (err) {
      console.error('Failed to fetch reviews:', err)
    } finally {
      setLoading(false)
    }
  }

  async function handleToggleVisibility(review) {
    try {
      setTogglingId(review.id)
      await api.patch(`/reviews/${review.id}/visibility`, {
        is_hidden: !review.is_hidden,
      })
      setReviews((prev) =>
        prev.map((r) =>
          r.id === review.id ? { ...r, is_hidden: !r.is_hidden } : r
        )
      )
    } catch (err) {
      console.error('Failed to toggle review visibility:', err)
      alert('Failed to update review visibility.')
    } finally {
      setTogglingId(null)
    }
  }

  if (loading) {
    return <p>Loading reviews...</p>
  }

  if (reviews.length === 0) {
    return <p>No reviews found.</p>
  }

  return (
    <div className="admin-reviews">
      {reviews.map((review) => (
        <div key={review.id} className="admin-review-card">
          <div className="admin-review-header">
            <span className="admin-review-rating">
              {'★'.repeat(review.rating)}{'☆'.repeat(5 - review.rating)}
            </span>
            <span className="admin-review-date">
              {formatDate(review.submitted_at)}
            </span>
          </div>
          {review.comment && (
            <p className="admin-review-comment">{review.comment}</p>
          )}
          <div className="admin-review-actions">
            <button
              onClick={() => handleToggleVisibility(review)}
              disabled={togglingId === review.id}
              className={`btn btn-sm ${review.is_hidden ? 'btn-primary' : 'btn-cancel'}`}
            >
              {togglingId === review.id
                ? 'Updating...'
                : review.is_hidden
                  ? 'Unhide'
                  : 'Hide'}
            </button>
            {review.is_hidden && (
              <span className="admin-review-hidden-badge">Hidden</span>
            )}
          </div>
        </div>
      ))}
    </div>
  )
}

export default function AdminDashboard() {
  const { user } = useAuth()
  const [activeTab, setActiveTab] = useState('Overview')

  // Redirect non-admin users to home
  if (!user || user.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  function renderTabContent() {
    switch (activeTab) {
      case 'Overview':
        return <OverviewTab />
      case 'Bookings':
        return <BookingsTab />
      case 'Students':
        return <StudentsTab />
      case 'Availability':
        return <AvailabilityTab />
      case 'Time Off':
        return <TimeOffTab />
      case 'Tutor Profile':
        return <TutorProfileTab />
      case 'Reviews':
        return <ReviewsTab />
      default:
        return null
    }
  }

  return (
    <>
      <Nav />
      <main className="admin-dashboard-page">
        <div className="container">
          <h1 className="section-title" style={{ marginTop: '5rem', marginBottom: '2rem' }}>
            Admin Dashboard
          </h1>

          <div className="admin-tabs">
            {TABS.map((tab) => (
              <button
                key={tab}
                className={`admin-tab-btn ${activeTab === tab ? 'admin-tab-btn--active' : ''}`}
                onClick={() => setActiveTab(tab)}
                aria-pressed={activeTab === tab}
              >
                {tab}
              </button>
            ))}
          </div>

          <div className="admin-tab-content">
            {renderTabContent()}
          </div>
        </div>
      </main>
      <Footer />
    </>
  )
}
