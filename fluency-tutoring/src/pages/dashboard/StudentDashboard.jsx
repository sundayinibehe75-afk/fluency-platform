import { useState, useEffect } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/dateUtils'
import { formatCents } from '../../utils/formatCurrency'
import { GOALS, LEVELS, allTimeZones, browserTimeZone, goalLabel } from '../../utils/profile'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'
import { getErrorMessage } from '../../utils/errors'

const TYPE_LABELS = { trial: 'Free trial', plan: 'Plan', single: 'Single' }

export function LessonTypeBadge({ type }) {
  const t = type || 'single'
  return <span className={`lesson-type lesson-type--${t}`}>{TYPE_LABELS[t] || t}</span>
}

function hoursUntil(booking) {
  return (new Date(booking.start_at || booking.slot_start_at) - new Date()) / 36e5
}

function PlanCard({ account, onCancel, onResume, busy }) {
  if (!account) return null
  const { plan } = account
  return (
    <section className="dashboard-section plan-card">
      <div className="plan-card-main">
        <div>
          <h2 className="dashboard-section-title">My Plan</h2>
          {plan ? (
            <>
              <p className="plan-card-name">
                {plan.label}
                {plan.price_cents != null && <> · {formatCents(plan.price_cents)}/month</>}
              </p>
              <p className="plan-card-meta">
                {plan.cancel_at_period_end
                  ? `Cancelled. Your plan ends on ${formatDate(plan.current_period_end)} and won't renew.`
                  : plan.current_period_end
                    ? `Renews on ${formatDate(plan.current_period_end)}.`
                    : 'Active.'}
                {plan.status === 'past_due' && ' Your last payment failed. Please update your card with Stripe.'}
              </p>
            </>
          ) : (
            <p className="plan-card-meta">
              {account.credits_remaining > 0
                ? 'Your prepaid lessons are below.'
                : 'No lessons left.'}{' '}
              <Link to="/#pricing" className="dashboard-link">Buy a month of lessons</Link>
            </p>
          )}
        </div>
        <div className="plan-card-credits">
          <span className="plan-card-number">{account.credits_remaining}</span>
          <span>lesson{account.credits_remaining === 1 ? '' : 's'} left</span>
          {account.credits_expire_at && account.credits_remaining > 0 && (
            <small>use by {formatDate(account.credits_expire_at)}</small>
          )}
        </div>
      </div>
      <div className="dashboard-card-actions">
        {account.credits_remaining > 0 && (
          <Link to="/booking?type=plan" className="btn btn-primary btn-sm">Book with plan</Link>
        )}
        {account.trial_available && (
          <Link to="/booking?type=trial" className="btn btn-outline-dark btn-sm">Book free trial</Link>
        )}
        {plan && !plan.cancel_at_period_end && (
          <button className="btn btn-cancel btn-sm" onClick={onCancel} disabled={busy}>
            Cancel plan
          </button>
        )}
        {plan && plan.cancel_at_period_end && (
          <button className="btn btn-outline-dark btn-sm" onClick={onResume} disabled={busy}>
            Keep my plan
          </button>
        )}
      </div>
      <p className="plan-card-rules">
        Unused lessons expire at the end of each month. Cancel or reschedule a lesson at least 12
        hours before it starts to keep the lesson.
      </p>
    </section>
  )
}

function ProfileCard() {
  const api = useApi()
  const [profile, setProfile] = useState(null)
  const [editing, setEditing] = useState(false)
  const [form, setForm] = useState({})
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    api.get('/users/me').then((res) => setProfile(res.data)).catch(() => {})
  }, [])

  if (!profile) return null

  const browserZone = browserTimeZone()
  const zoneDiffers = profile.timezone !== browserZone

  function start() {
    setForm({
      cefr_level: profile.cefr_level || '',
      learning_goal: profile.learning_goal || '',
      goal_note: profile.goal_note || '',
      timezone: profile.timezone,
    })
    setError('')
    setEditing(true)
  }

  async function save(patch) {
    try {
      setSaving(true)
      const res = await api.patch('/users/me', patch)
      setProfile(res.data)
      setEditing(false)
    } catch (err) {
      setError(getErrorMessage(err, 'Could not save. Please try again.'))
    } finally {
      setSaving(false)
    }
  }

  function submit(e) {
    e.preventDefault()
    save({
      cefr_level: form.cefr_level || null,
      learning_goal: form.learning_goal || null,
      goal_note: form.goal_note.trim() || null,
      timezone: form.timezone,
    })
  }

  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  return (
    <section className="dashboard-section plan-card profile-card">
      <h2 className="dashboard-section-title">My Learning Profile</h2>
      {!editing ? (
        <>
          <dl className="profile-grid">
            <div><dt>Level</dt><dd>{profile.cefr_level || '—'}</dd></div>
            <div><dt>Goal</dt><dd>{goalLabel(profile.learning_goal)}</dd></div>
            <div><dt>Time zone</dt><dd>{profile.timezone}</dd></div>
          </dl>
          {profile.goal_note && <p className="plan-card-meta">“{profile.goal_note}”</p>}
          {zoneDiffers && (
            <p className="profile-zone-hint">
              Your device is set to {browserZone}.{' '}
              <button className="link-button" onClick={() => save({ timezone: browserZone })} disabled={saving}>
                Use {browserZone} for my emails
              </button>
            </p>
          )}
          <div className="dashboard-card-actions">
            <button className="btn btn-outline-dark btn-sm" onClick={start}>Edit</button>
          </div>
        </>
      ) : (
        <form onSubmit={submit} className="profile-form">
          <label>
            Level
            <select value={form.cefr_level} onChange={set('cefr_level')}>
              <option value="">Not sure</option>
              {LEVELS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </label>
          <label>
            Goal
            <select value={form.learning_goal} onChange={set('learning_goal')}>
              <option value="">—</option>
              {GOALS.map((g) => <option key={g.value} value={g.value}>{g.label}</option>)}
            </select>
          </label>
          <label className="profile-form-wide">
            Tell your tutor more (optional)
            <textarea
              rows={2}
              maxLength={500}
              value={form.goal_note}
              onChange={set('goal_note')}
              placeholder="e.g. Goethe B1 exam in March, I want to speak more confidently at work"
            />
          </label>
          <label>
            Time zone (for emails)
            <select value={form.timezone} onChange={set('timezone')}>
              {allTimeZones().map((z) => <option key={z} value={z}>{z}</option>)}
            </select>
          </label>
          {error && <p className="pricing-error profile-form-wide">{error}</p>}
          <div className="dashboard-card-actions profile-form-wide">
            <button type="submit" className="btn btn-primary btn-sm" disabled={saving}>
              {saving ? 'Saving…' : 'Save'}
            </button>
            <button type="button" className="btn btn-outline-dark btn-sm" onClick={() => setEditing(false)}>
              Cancel
            </button>
          </div>
        </form>
      )}
    </section>
  )
}

export default function StudentDashboard() {
  const { user } = useAuth()
  const api = useApi()
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [cancellingId, setCancellingId] = useState(null)
  const [payingId, setPayingId] = useState(null)
  const [account, setAccount] = useState(null)
  const [planBusy, setPlanBusy] = useState(false)
  const [params] = useSearchParams()
  const payReference = params.get('reference') || params.get('trxref')
  const [packageNotice, setPackageNotice] = useState('')

  // Back from paying for a lesson package: confirm it and refresh the lessons
  useEffect(() => {
    if (!payReference || !user) return
    api
      .get(`/payments/paystack/verify?reference=${encodeURIComponent(payReference)}`)
      .then((res) => {
        setPackageNotice(
          res.data.status === 'success'
            ? 'Payment received. Your lessons for this month have been added. 🎉'
            : 'The payment did not go through. No lessons were added.'
        )
        fetchAccount()
      })
      .catch((err) => setPackageNotice(getErrorMessage(err, 'We could not confirm your payment yet. Please check again in a few minutes.')))
  }, [payReference, user])

  const notice = packageNotice || (params.get('booked')
    ? 'Your lesson is booked. A confirmation email is on its way.'
    : params.get('weekly')
      ? `Booked ${params.get('weekly')} weekly lesson(s).` +
        (Number(params.get('skipped')) > 0
          ? ` ${params.get('skipped')} week(s) had no free slot at that time; we've emailed you the dates.`
          : ' A confirmation email is on its way.')
    : params.get('moved')
      ? 'Your lesson has been moved. We have emailed you the new time.'
      : params.get('plan') === 'success'
        ? 'Thank you! Your plan is active. Your lessons may take a moment to appear.'
        : null)

  useEffect(() => {
    if (user) {
      fetchBookings()
      if (user.role === 'student') fetchAccount()
    }
  }, [user])

  async function fetchAccount() {
    try {
      const res = await api.get('/subscriptions/me')
      setAccount(res.data)
    } catch (err) {
      console.error('Failed to fetch plan:', err)
    }
  }

  async function changePlan(action) {
    if (
      action === 'cancel' &&
      !window.confirm(
        'Cancel your plan? It will not renew. You keep your remaining lessons until the end of this month.'
      )
    )
      return
    try {
      setPlanBusy(true)
      const res = await api.post(`/subscriptions/me/${action}`)
      setAccount(res.data)
    } catch (err) {
      alert(getErrorMessage(err, 'Something went wrong. Please try again.'))
    } finally {
      setPlanBusy(false)
    }
  }

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

  async function handleCancel(booking) {
    const late = hoursUntil(booking) < 12
    const type = booking.booking_type || 'single'
    const paid = booking.status === 'confirmed'
    let message = 'Cancel this booking?'
    if (paid && type === 'single') {
      message = late
        ? 'This lesson starts in less than 12 hours, so it will not be refunded. Cancel anyway?'
        : 'Cancel this lesson? You will receive a full refund.'
    } else if (paid && type === 'plan') {
      message = late
        ? 'This lesson starts in less than 12 hours, so the lesson credit will be used. Cancel anyway?'
        : 'Cancel this lesson? The lesson goes back to your plan.'
    } else if (paid && type === 'trial') {
      message = late
        ? 'This trial starts in less than 12 hours, so it will count as used. Cancel anyway?'
        : 'Cancel your free trial? You can book it again.'
    }
    if (!window.confirm(message)) return
    try {
      setCancellingId(booking.id)
      await api.post(`/bookings/${booking.id}/cancel`)
      setBookings((prev) =>
        prev.map((b) => (b.id === booking.id ? { ...b, status: 'cancelled' } : b))
      )
      fetchAccount()
    } catch (err) {
      console.error('Failed to cancel booking:', err)
      alert(getErrorMessage(err, 'Failed to cancel booking. Please try again.'))
    } finally {
      setCancellingId(null)
    }
  }

  if (!user) {
    return <Navigate to="/login" replace />
  }

  const now = new Date()

  // A lesson stays "upcoming" until it ends, so the Join button is still
  // there for a student who arrives a few minutes late.
  const endOf = (b) => new Date(b.end_at || b.start_at || b.slot_start_at)

  const upcoming = bookings
    .filter((b) => b.status === 'confirmed' && endOf(b) > now)
    .sort((a, b) => new Date(a.start_at) - new Date(b.start_at))

  const past = bookings.filter((b) => !upcoming.includes(b) && (b.status === 'completed' || endOf(b) < now))

  // Single lessons the student started booking but has not paid for yet
  const awaitingPayment = bookings
    .filter((b) => b.status === 'pending_payment' && new Date(b.start_at) > now)
    .sort((a, b) => new Date(a.start_at) - new Date(b.start_at))

  async function completePayment(booking) {
    setPayingId(booking.id)
    try {
      // Re-booking the same slot renews the hold on it, then a new payment starts
      const res = await api.post('/bookings', { slot_id: booking.slot_id, booking_type: 'single' })
      const checkout = await api.post('/payments/checkout', { booking_id: res.data.id })
      window.location.href = checkout.data.session_url
    } catch (err) {
      alert(getErrorMessage(err, 'Could not start the payment. Please book the lesson again.'))
      setPayingId(null)
    }
  }

  function isWithin10Min(booking) {
    // Joinable from 10 minutes before the start until the lesson ends
    const startAt = new Date(booking.start_at || booking.slot_start_at)
    return startAt - new Date() <= 10 * 60 * 1000 && endOf(booking) > new Date()
  }

  return (
    <>
      <Nav />
      <main className="dashboard-page">
        <div className="container">
          <h1 className="section-title" style={{ marginTop: '5rem', marginBottom: '2rem' }}>
            My Dashboard
          </h1>

          {notice && <p className="dashboard-notice" role="status">{notice}</p>}

          <ProfileCard />

          <PlanCard
            account={account}
            busy={planBusy}
            onCancel={() => changePlan('cancel')}
            onResume={() => changePlan('resume')}
          />

          {loading ? (
            <div className="dashboard-loading">
              <div className="loading-spinner" aria-label="Loading bookings"></div>
              <p>Loading your bookings...</p>
            </div>
          ) : (
            <>
              {awaitingPayment.length > 0 && (
                <section className="dashboard-section">
                  <h2 className="dashboard-section-title">Waiting for payment</h2>
                  <p className="dashboard-empty">
                    These lessons are held for you for 15 minutes while you pay.
                  </p>
                  <div className="dashboard-cards">
                    {awaitingPayment.map((booking) => (
                      <div key={booking.id} className="dashboard-card">
                        <div className="dashboard-card-header">
                          <span className="dashboard-card-date">{formatDate(booking.start_at)}</span>
                          <span className="dashboard-status dashboard-status--pending_payment">not paid</span>
                        </div>
                        <div className="dashboard-card-actions">
                          <button
                            onClick={() => completePayment(booking)}
                            disabled={payingId === booking.id}
                            className="btn btn-primary btn-sm"
                          >
                            {payingId === booking.id ? 'Opening payment...' : 'Complete payment'}
                          </button>
                          <button
                            onClick={() => handleCancel(booking)}
                            disabled={cancellingId === booking.id}
                            className="btn btn-cancel btn-sm"
                          >
                            {cancellingId === booking.id ? 'Removing...' : 'Remove'}
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </section>
              )}

              <section className="dashboard-section">
                <h2 className="dashboard-section-title">Upcoming Lessons</h2>
                {upcoming.length === 0 ? (
                  <p className="dashboard-empty">
                    No upcoming lessons.{' '}
                    <Link to="/booking" className="dashboard-link">Book a lesson</Link>
                  </p>
                ) : (
                  <div className="dashboard-cards">
                    {upcoming.map((booking) => (
                      <div key={booking.id} className="dashboard-card">
                        <div className="dashboard-card-header">
                          <span className="dashboard-card-date">
                            {formatDate(booking.start_at || booking.slot_start_at)}
                          </span>
                          <span className={`dashboard-status dashboard-status--${booking.status}`}>
                            {booking.status}
                          </span>
                        </div>
                        <LessonTypeBadge type={booking.booking_type} />
                        <div className="dashboard-card-actions">
                          {isWithin10Min(booking) && (
                            <Link
                              to={`/lessons/${booking.id}`}
                              className="btn btn-primary btn-sm"
                            >
                              Join Lesson
                            </Link>
                          )}
                          {hoursUntil(booking) >= 12 && (
                            <Link
                              to={`/booking?reschedule=${booking.id}`}
                              className="btn btn-outline-dark btn-sm"
                            >
                              Reschedule
                            </Link>
                          )}
                          {hoursUntil(booking) > 0 && (
                            <button
                              onClick={() => handleCancel(booking)}
                              disabled={cancellingId === booking.id}
                              className="btn btn-cancel btn-sm"
                            >
                              {cancellingId === booking.id ? 'Cancelling...' : 'Cancel'}
                            </button>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>

              <section className="dashboard-section">
                <h2 className="dashboard-section-title">Past Lessons</h2>
                {past.length === 0 ? (
                  <p className="dashboard-empty">No past lessons yet.</p>
                ) : (
                  <div className="dashboard-cards">
                    {past.map((booking) => (
                      <div key={booking.id} className="dashboard-card">
                        <div className="dashboard-card-header">
                          <span className="dashboard-card-date">
                            {formatDate(booking.start_at || booking.slot_start_at)}
                          </span>
                          <span className={`dashboard-status dashboard-status--${booking.status}`}>
                            {booking.status}
                          </span>
                        </div>
                        <div className="dashboard-card-actions">
                          {booking.has_notes && (
                            <Link to="/notes" className="btn btn-outline-dark btn-sm">
                              Notes &amp; homework
                            </Link>
                          )}
                          {booking.status === 'completed' && !booking.has_review && (
                            <Link
                              to={`/reviews/${booking.id}`}
                              className="btn btn-outline-dark btn-sm"
                            >
                              Leave Review
                            </Link>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </section>
            </>
          )}
        </div>
      </main>
      <Footer />
    </>
  )
}
