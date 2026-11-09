import { useState, useEffect } from 'react'
import { Link, Navigate, useSearchParams } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/dateUtils'
import { formatCents } from '../../utils/formatCurrency'
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
              No monthly plan. <Link to="/#pricing" className="dashboard-link">See plans</Link>
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

export default function StudentDashboard() {
  const { user } = useAuth()
  const api = useApi()
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [cancellingId, setCancellingId] = useState(null)
  const [account, setAccount] = useState(null)
  const [planBusy, setPlanBusy] = useState(false)
  const [params] = useSearchParams()
  const notice = params.get('booked')
    ? 'Your lesson is booked. A confirmation email is on its way.'
    : params.get('moved')
      ? 'Your lesson has been moved. We have emailed you the new time.'
      : params.get('plan') === 'success'
        ? 'Thank you! Your plan is active. Your lessons may take a moment to appear.'
        : null

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

  const upcoming = bookings.filter((b) => {
    const startAt = new Date(b.start_at || b.slot_start_at)
    return b.status === 'confirmed' && startAt > now
  })

  const past = bookings.filter((b) => {
    const startAt = new Date(b.start_at || b.slot_start_at)
    return b.status === 'completed' || startAt < now
  })

  function isWithin10Min(booking) {
    const startAt = new Date(booking.start_at || booking.slot_start_at)
    const diffMs = startAt - new Date()
    return diffMs <= 10 * 60 * 1000 && diffMs > 0
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
