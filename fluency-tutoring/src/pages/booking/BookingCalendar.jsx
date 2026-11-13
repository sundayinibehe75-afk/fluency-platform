import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { nairaHint, usePaymentConfig } from '../../hooks/usePaymentConfig'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { toLocalTime, formatDate } from '../../utils/dateUtils'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'
import { getErrorMessage } from '../../utils/errors'
import { useBackForwardReset } from '../../hooks/useBackForwardReset'

// Hardcoded tutor_id for v1 single-tutor setup — will be dynamic in v2
const TUTOR_ID = import.meta.env.VITE_TUTOR_ID || '00000000-0000-0000-0000-000000000001'

function groupSlotsByDate(slots) {
  const groups = {}
  for (const slot of slots) {
    const localDate = toLocalTime(slot.start_at)
    const dateKey = localDate.toLocaleDateString(undefined, {
      year: 'numeric',
      month: 'short',
      day: 'numeric',
      weekday: 'short',
    })
    if (!groups[dateKey]) {
      groups[dateKey] = []
    }
    groups[dateKey].push(slot)
  }
  return groups
}

function formatTime(utcIsoString) {
  const date = new Date(utcIsoString)
  return date.toLocaleTimeString(undefined, {
    hour: '2-digit',
    minute: '2-digit',
  })
}

export default function BookingCalendar() {
  const api = useApi()
  const { user } = useAuth()
  const navigate = useNavigate()
  const [params] = useSearchParams()
  const rescheduleId = params.get('reschedule')

  // How this lesson is paid: 'trial' (free), 'plan' (uses a credit) or 'single' ($10)
  const [account, setAccount] = useState(null)
  const [bookingType, setBookingType] = useState(null)
  const [weekly, setWeekly] = useState(false)
  const payConfig = usePaymentConfig()

  // Lesson length: 30 or 60 minutes (the free trial is always 60)
  const [minutes, setMinutes] = useState(params.get('minutes') === '30' ? 30 : 60)
  const [lockedLength, setLockedLength] = useState(false) // rescheduling keeps the length
  const [singlePrices, setSinglePrices] = useState({ 30: 600, 60: 1000 })
  const lessonMinutes = bookingType === 'trial' ? 60 : minutes

  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [booking, setBooking] = useState(false)
  useBackForwardReset(() => {
    setBooking(false)
    setSelectedSlot(null)
  })

  useEffect(() => {
    if (!user) {
      navigate('/login')
      return
    }
    if (user.role === 'student' && !rescheduleId) fetchAccount()
    if (rescheduleId) fetchRescheduleLength()
    api.get('/plans').then((res) => {
      const byLength = {}
      for (const p of res.data || []) {
        if (!p.is_plan) byLength[p.lesson_minutes || 60] = p.price_cents
      }
      if (byLength[30] || byLength[60]) setSinglePrices((prev) => ({ ...prev, ...byLength }))
    }).catch(() => {})
  }, [user])

  useEffect(() => {
    if (user) fetchSlots()
  }, [user, lessonMinutes])

  async function fetchRescheduleLength() {
    try {
      const res = await api.get(`/bookings/${rescheduleId}`)
      if (res.data.duration_minutes === 30 || res.data.duration_minutes === 60) {
        setMinutes(res.data.duration_minutes)
        setLockedLength(true)
      }
    } catch {
      /* keep the default */
    }
  }

  // Plan lessons can only book the length they were bought for
  function planLengths(acc) {
    const byLength = acc?.credits_by_length || { 60: acc?.credits_remaining || 0 }
    return [30, 60].filter((m) => (byLength[m] || byLength[String(m)] || 0) > 0)
  }

  function chooseType(type, acc = account) {
    setBookingType(type)
    if (type === 'plan') {
      const lengths = planLengths(acc)
      if (lengths.length && !lengths.includes(minutes)) setMinutes(lengths[0])
    }
  }

  async function fetchAccount() {
    try {
      const res = await api.get('/subscriptions/me')
      setAccount(res.data)
      const wanted = params.get('type')
      const options = availableTypes(res.data)
      chooseType(options.includes(wanted) ? wanted : options[0], res.data)
    } catch {
      setBookingType('single')
    }
  }

  function availableTypes(acc) {
    const types = []
    if (acc?.credits_remaining > 0) types.push('plan')
    if (acc?.trial_available) types.push('trial')
    types.push('single')
    return types
  }

  async function fetchSlots() {
    setLoading(true)
    setError(null)
    try {
      const res = await api.get(`/availability?tutor_id=${TUTOR_ID}&minutes=${lessonMinutes}`)
      setSlots(res.data)
    } catch (err) {
      setError('Unable to load available slots. Please try again later.')
    } finally {
      setLoading(false)
    }
  }

  async function handleSlotSelect(slot) {
    setSelectedSlot(slot)
    setBooking(true)
    setError(null)

    try {
      if (rescheduleId) {
        await api.post(`/bookings/${rescheduleId}/reschedule`, { new_slot_id: slot.id, start_at: slot.start_at })
        navigate(user.role === 'admin' ? '/admin' : '/dashboard?moved=1')
        return
      }

      const type = bookingType || 'single'

      if (type === 'plan' && weekly) {
        const res = await api.post('/bookings/weekly', {
          slot_id: slot.id,
          start_at: slot.start_at,
          minutes: lessonMinutes,
        })
        navigate(`/dashboard?weekly=${res.data.booked.length}&skipped=${res.data.skipped.length}`)
        return
      }
      const bookingRes = await api.post('/bookings', {
        slot_id: slot.id,
        booking_type: type,
        start_at: slot.start_at,
        minutes: lessonMinutes,
      })

      if (type !== 'single') {
        // Free trial and plan lessons are confirmed straight away
        navigate('/dashboard?booked=1')
        return
      }

      // Single lesson: pay with Stripe Checkout
      const checkoutRes = await api.post('/payments/checkout', { booking_id: bookingRes.data.id })
      window.location.href = checkoutRes.data.session_url
    } catch (err) {
      const detail = getErrorMessage(err)
      setError(detail)
      setSelectedSlot(null)
      setBooking(false)
      if (!rescheduleId) fetchAccount()
    }
  }

  const groupedSlots = groupSlotsByDate(slots)

  if (loading) {
    return (
      <>
        <Nav />
        <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
          <div className="container">
            <p style={{ color: 'var(--gray)', fontSize: '1.1rem' }}>Loading available slots...</p>
          </div>
        </section>
        <Footer />
      </>
    )
  }

  return (
    <>
      <Nav />
      <section style={{ paddingTop: '7rem' }}>
        <div className="container">
          <p className="section-label">Book a Lesson</p>
          <h1 className="section-title">
            {rescheduleId ? 'Choose a New Time' : 'Choose a Time Slot'}
          </h1>

          {rescheduleId && (
            <p className="booking-mode-note">
              Pick the new time for your {lockedLength ? `${minutes}-minute ` : ''}lesson. Your old time is released.{' '}
              <Link to={user?.role === 'admin' ? '/admin' : '/dashboard'} className="dashboard-link">Keep the current time</Link>
            </p>
          )}

          {!rescheduleId && account && (
            <fieldset className="booking-mode">
              <legend>How would you like to book?</legend>
              {availableTypes(account).map((type) => (
                <label key={type} className={`booking-mode-option ${bookingType === type ? 'selected' : ''}`}>
                  <input
                    type="radio"
                    name="booking-type"
                    value={type}
                    checked={bookingType === type}
                    onChange={() => chooseType(type)}
                  />
                  {type === 'plan' && <>Use a plan lesson <small>({account.credits_remaining} left)</small></>}
                  {type === 'trial' && <>Free trial lesson <small>(60 min, one per student)</small></>}
                  {type === 'single' && (
                    <>
                      Single lesson{' '}
                      <small>
                        (${(singlePrices[minutes] / 100).toFixed(0)}
                        {nairaHint(payConfig, singlePrices[minutes]) ? `, ${nairaHint(payConfig, singlePrices[minutes])} in naira` : ''}, pay now)
                      </small>
                    </>
                  )}
                </label>
              ))}
              {bookingType !== 'trial' && (
                <div className="booking-length" role="group" aria-label="Lesson length">
                  <span>Lesson length</span>
                  {[30, 60].map((m) => {
                    const allowed = bookingType !== 'plan' || planLengths(account).includes(m)
                    return (
                      <button
                        key={m}
                        type="button"
                        className={`booking-length-btn ${minutes === m ? 'selected' : ''}`}
                        onClick={() => setMinutes(m)}
                        disabled={!allowed || booking}
                        title={allowed ? '' : `You have no ${m}-minute plan lessons`}
                      >
                        {m} min
                      </button>
                    )
                  })}
                </div>
              )}
              {bookingType === 'plan' && account.credits_remaining > 1 && (
                <label className="booking-weekly">
                  <input type="checkbox" checked={weekly} onChange={(e) => setWeekly(e.target.checked)} />
                  Book this time every week while my plan lessons last
                </label>
              )}
              {!account.plan && account.credits_remaining === 0 && (
                <p className="booking-mode-note">
                  Taking lessons every week? <Link to="/#pricing" className="dashboard-link">See monthly plans</Link>
                </p>
              )}
            </fieldset>
          )}

          {error && (
            <div
              role="alert"
              style={{
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                padding: '1rem',
                marginBottom: '2rem',
                color: '#dc2626',
              }}
            >
              {error}
            </div>
          )}

          {booking && (
            <div
              style={{
                background: '#f0f9ff',
                border: '1px solid #bae6fd',
                borderRadius: '8px',
                padding: '1rem',
                marginBottom: '2rem',
                color: '#0369a1',
              }}
            >
              {rescheduleId ? 'Moving your lesson...' : 'Processing your booking...'}
            </div>
          )}

          {Object.keys(groupedSlots).length === 0 ? (
            <p style={{ color: 'var(--gray)', fontSize: '1.05rem', textAlign: 'center' }}>
              No available slots at the moment. Please check back later.
            </p>
          ) : (
            <div className="booking-calendar-grid">
              {Object.entries(groupedSlots).map(([dateLabel, dateSlots]) => (
                <div key={dateLabel} className="booking-date-group">
                  <h3 className="booking-date-heading">{dateLabel}</h3>
                  <div className="booking-slots-row">
                    {dateSlots.map((slot) => (
                      <button
                        key={`${slot.id}-${slot.start_at}`}
                        className={`booking-slot-btn ${
                          selectedSlot?.id === slot.id && selectedSlot?.start_at === slot.start_at ? 'selected' : ''
                        }`}
                        onClick={() => handleSlotSelect(slot)}
                        disabled={booking}
                        aria-label={`Book slot at ${formatTime(slot.start_at)}`}
                      >
                        {formatTime(slot.start_at)}
                        <span className="booking-slot-duration">
                          to {formatTime(slot.end_at)}
                        </span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
      <Footer />
    </>
  )
}
