import { useState, useEffect } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/dateUtils'
import { formatCents } from '../../utils/formatCurrency'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

const TABS = ['Overview', 'Bookings', 'Students', 'Availability', 'Tutor Profile', 'Reviews']

function OverviewTab() {
  return (
    <div className="admin-overview">
      <div className="admin-stats-grid">
        <div className="admin-stat-card">
          <h3>Total Bookings</h3>
          <p className="admin-stat-value">—</p>
          <span className="admin-stat-note">Stats endpoint coming soon</span>
        </div>
        <div className="admin-stat-card">
          <h3>Revenue</h3>
          <p className="admin-stat-value">—</p>
          <span className="admin-stat-note">Stats endpoint coming soon</span>
        </div>
        <div className="admin-stat-card">
          <h3>Upcoming Lessons</h3>
          <p className="admin-stat-value">—</p>
          <span className="admin-stat-note">Stats endpoint coming soon</span>
        </div>
        <div className="admin-stat-card">
          <h3>Total Students</h3>
          <p className="admin-stat-value">—</p>
          <span className="admin-stat-note">Stats endpoint coming soon</span>
        </div>
      </div>
    </div>
  )
}

function BookingsTab() {
  const api = useApi()
  const [bookings, setBookings] = useState([])
  const [loading, setLoading] = useState(true)
  const [cancellingId, setCancellingId] = useState(null)

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
            <th>Status</th>
            <th>Amount</th>
            <th>Actions</th>
          </tr>
        </thead>
        <tbody>
          {bookings.map((booking) => (
            <tr key={booking.id}>
              <td>{booking.student_name || 'Student'}</td>
              <td>{formatDate(booking.start_at || booking.slot_start_at)}</td>
              <td>
                <span className={`admin-status admin-status--${booking.status}`}>
                  {booking.status}
                </span>
              </td>
              <td>{formatCents(booking.price_cents, booking.currency)}</td>
              <td>
                {booking.status === 'confirmed' && (
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
          ))}
        </tbody>
      </table>
    </div>
  )
}

function StudentsTab() {
  return (
    <div className="admin-placeholder">
      <p>Student management coming soon</p>
    </div>
  )
}

function AvailabilityTab() {
  const api = useApi()
  const [startDate, setStartDate] = useState('')
  const [startTime, setStartTime] = useState('09:00')
  const [duration, setDuration] = useState(60)
  const [recurrence, setRecurrence] = useState(false)
  const [weeksAhead, setWeeksAhead] = useState(4)
  const [loading, setLoading] = useState(false)
  const [message, setMessage] = useState('')
  const [slots, setSlots] = useState([])
  const [slotsLoading, setSlotsLoading] = useState(true)

  const tutorId = '00000000-0000-0000-0000-000000000001'

  useEffect(() => {
    fetchSlots()
  }, [])

  async function fetchSlots() {
    try {
      setSlotsLoading(true)
      const res = await api.get(`/availability?tutor_id=${tutorId}`)
      setSlots(res.data)
    } catch (err) {
      console.error('Failed to fetch slots:', err)
    } finally {
      setSlotsLoading(false)
    }
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setMessage('')
    setLoading(true)

    const startAt = new Date(`${startDate}T${startTime}:00Z`).toISOString()
    const endAt = new Date(new Date(`${startDate}T${startTime}:00Z`).getTime() + duration * 60000).toISOString()

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
      setMessage(`✅ Created ${res.data.length} slot(s) successfully!`)
      setStartDate('')
      fetchSlots()
    } catch (err) {
      const detail = err.response?.data?.detail?.detail || err.response?.data?.detail || 'Failed to create slots'
      setMessage(`❌ ${detail}`)
    } finally {
      setLoading(false)
    }
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
          <label htmlFor="start-time">Start Time (UTC)</label>
          <input
            id="start-time"
            type="time"
            value={startTime}
            onChange={(e) => setStartTime(e.target.value)}
            required
          />
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

      <h3 style={{ marginBottom: '1rem' }}>Current Availability ({slots.length} slots)</h3>
      {slotsLoading ? (
        <p>Loading slots...</p>
      ) : slots.length === 0 ? (
        <p style={{ color: 'var(--gray)' }}>No available slots. Add some above.</p>
      ) : (
        <div style={{ maxHeight: '300px', overflowY: 'auto' }}>
          {slots.map(slot => (
            <div key={slot.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '0.5rem 0', borderBottom: '1px solid var(--border)' }}>
              <span>{formatDate(slot.start_at)} — {slot.duration_minutes} min</span>
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

  // Use tutor ID 1 as default; in production this would come from config
  const tutorId = '1'

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
      const detail = err.response?.data?.detail || 'Failed to update profile.'
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

  // Use tutor ID 1 as default
  const tutorId = '1'

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
