import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { toLocalTime, formatDate } from '../../utils/dateUtils'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

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
  }, [user])

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
      // Step 1: Create booking
      const bookingRes = await api.post('/bookings', { slot_id: slot.id })
      const bookingId = bookingRes.data.id

      // Step 2: Create checkout session
      const checkoutRes = await api.post('/payments/checkout', { booking_id: bookingId })
      const sessionUrl = checkoutRes.data.session_url

      // Step 3: Redirect to Stripe Checkout
      window.location.href = sessionUrl
    } catch (err) {
      const detail = err.response?.data?.detail || 'Something went wrong. Please try again.'
      setError(detail)
      setSelectedSlot(null)
      setBooking(false)
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
          <h1 className="section-title">Choose a Time Slot</h1>

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
              Processing your booking...
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
