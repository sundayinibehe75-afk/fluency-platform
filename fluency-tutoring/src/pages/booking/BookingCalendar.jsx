import { useState, useEffect } from 'react'
import { useNavigate, useSearchParams, Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { toLocalTime, formatDate } from '../../utils/dateUtils'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'
import { getErrorMessage } from '../../utils/errors'

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

  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [selectedSlot, setSelectedSlot] = useState(null)
  const [booking, setBooking] = useState(false)

  useEffect(() => {
    if (!user) {
      navigate('/login')
      return
    }
    fetchSlots()
    if (user.role === 'student' && !rescheduleId) fetchAccount()
  }, [user])

  async function fetchAccount() {
    try {
      const res = await api.get('/subscriptions/me')
      setAccount(res.data)
      const wanted = params.get('type')
      const options = availableTypes(res.data)
      setBookingType(options.includes(wanted) ? wanted : options[0])
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
      const res = await api.get(`/availability?tutor_id=${TUTOR_ID}`)
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
        await api.post(`/bookings/${rescheduleId}/reschedule`, { new_slot_id: slot.id })
        navigate(user.role === 'admin' ? '/admin' : '/dashboard?moved=1')
        return
      }

      const type = bookingType || 'single'
      const bookingRes = await api.post('/bookings', { slot_id: slot.id, booking_type: type })

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
              Pick the new time for your lesson. Your old time is released.{' '}
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
                    onChange={() => setBookingType(type)}
                  />
                  {type === 'plan' && <>Use a plan lesson <small>({account.credits_remaining} left)</small></>}
                  {type === 'trial' && <>Free trial lesson <small>(one per student)</small></>}
                  {type === 'single' && <>Single lesson <small>($10, pay now)</small></>}
                </label>
              ))}
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
                        key={slot.id}
                        className={`booking-slot-btn ${selectedSlot?.id === slot.id ? 'selected' : ''}`}
                        onClick={() => handleSlotSelect(slot)}
                        disabled={booking}
                        aria-label={`Book slot at ${formatTime(slot.start_at)}`}
                      >
                        {formatTime(slot.start_at)}
                        <span className="booking-slot-duration">
                          {slot.duration_minutes} min
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
