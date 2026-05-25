import { useState, useEffect } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/dateUtils'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

export default function StudentDashboard() {
  const { user } = useAuth()
  const api = useApi()
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [cancellingId, setCancellingId] = useState(null)

  useEffect(() => {
    if (user) {
      fetchBookings()
    }
  }, [user])

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
    if (!window.confirm('Are you sure you want to cancel this booking?')) return
    try {
      setCancellingId(bookingId)
      await api.post(`/bookings/${bookingId}/cancel`)
      setBookings((prev) =>
        prev.map((b) => (b.id === bookingId ? { ...b, status: 'cancelled' } : b))
      )
    } catch (err) {
      console.error('Failed to cancel booking:', err)
      alert('Failed to cancel booking. Please try again.')
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

  function isMoreThan24hBefore(booking) {
    const startAt = new Date(booking.start_at || booking.slot_start_at)
    const diffMs = startAt - new Date()
    return diffMs > 24 * 60 * 60 * 1000
  }

  return (
    <>
      <Nav />
      <main className="dashboard-page">
        <div className="container">
          <h1 className="section-title" style={{ marginTop: '5rem', marginBottom: '2rem' }}>
            My Dashboard
          </h1>

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
                        <div className="dashboard-card-actions">
                          {isWithin10Min(booking) && (
                            <Link
                              to={`/lessons/${booking.id}`}
                              className="btn btn-primary btn-sm"
                            >
                              Join Lesson
                            </Link>
                          )}
                          {isMoreThan24hBefore(booking) && (
                            <button
                              onClick={() => handleCancel(booking.id)}
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
