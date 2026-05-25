import { useState, useEffect, useRef } from 'react'
import { useParams, Link } from 'react-router-dom'
import Daily from '@daily-co/daily-js'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { formatDate } from '../../utils/dateUtils'
import Nav from '../../components/Nav'

/**
 * Determines the lesson phase based on current time relative to booking times.
 * @param {string} startAt - ISO 8601 start time
 * @param {string} endAt - ISO 8601 end time
 * @returns {'waiting' | 'active' | 'ended'}
 */
function getLessonPhase(startAt, endAt) {
  const now = Date.now()
  const start = new Date(startAt).getTime()
  const end = new Date(endAt).getTime()
  const tenMinutes = 10 * 60 * 1000

  if (now < start - tenMinutes) {
    return 'waiting'
  }
  if (now >= end) {
    return 'ended'
  }
  return 'active'
}

/**
 * Formats milliseconds into a human-readable countdown string.
 * @param {number} ms - Milliseconds remaining
 * @returns {string}
 */
function formatCountdown(ms) {
  if (ms <= 0) return '0:00'
  const totalSeconds = Math.floor(ms / 1000)
  const hours = Math.floor(totalSeconds / 3600)
  const minutes = Math.floor((totalSeconds % 3600) / 60)
  const seconds = totalSeconds % 60
  const pad = (n) => String(n).padStart(2, '0')

  if (hours > 0) {
    return `${hours}:${pad(minutes)}:${pad(seconds)}`
  }
  return `${minutes}:${pad(seconds)}`
}

export default function LessonRoom() {
  const { id } = useParams()
  const api = useApi()
  const { user } = useAuth()

  const [booking, setBooking] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [forbidden, setForbidden] = useState(false)
  const [phase, setPhase] = useState(null)
  const [countdown, setCountdown] = useState('')

  const videoContainerRef = useRef(null)
  const callFrameRef = useRef(null)
  const countdownIntervalRef = useRef(null)

  // Fetch booking detail
  useEffect(() => {
    async function fetchBooking() {
      setLoading(true)
      setError(null)
      try {
        const res = await api.get(`/bookings/${id}`)
        const data = res.data

        // Ownership check: booking must belong to current user (student or tutor)
        if (user && data.student_id !== user.id && data.tutor_id !== user.id) {
          setForbidden(true)
          setLoading(false)
          return
        }

        setBooking(data)
        setPhase(getLessonPhase(data.start_at, data.end_at))
      } catch (err) {
        if (err.response?.status === 403) {
          setForbidden(true)
        } else if (err.response?.status === 404) {
          setError('Booking not found.')
        } else {
          setError('Unable to load lesson details. Please try again.')
        }
      } finally {
        setLoading(false)
      }
    }

    if (user) {
      fetchBooking()
    }
  }, [id, user])

  // Phase transition timer — re-evaluate phase every second
  useEffect(() => {
    if (!booking) return

    function tick() {
      const currentPhase = getLessonPhase(booking.start_at, booking.end_at)
      setPhase(currentPhase)

      if (currentPhase === 'waiting') {
        const start = new Date(booking.start_at).getTime()
        const tenMinBefore = start - 10 * 60 * 1000
        const remaining = tenMinBefore - Date.now()
        setCountdown(formatCountdown(remaining))
      }
    }

    tick()
    countdownIntervalRef.current = setInterval(tick, 1000)

    return () => {
      if (countdownIntervalRef.current) {
        clearInterval(countdownIntervalRef.current)
      }
    }
  }, [booking])

  // Embed Daily.co video when phase becomes active
  useEffect(() => {
    if (phase !== 'active' || !booking?.video_room_url || !videoContainerRef.current) return
    if (callFrameRef.current) return // Already joined

    const frame = Daily.createFrame(videoContainerRef.current, {
      url: booking.video_room_url,
      showLeaveButton: true,
      iframeStyle: {
        width: '100%',
        height: '100%',
        border: '0',
        borderRadius: '8px',
      },
    })

    frame.join({ url: booking.video_room_url })
    callFrameRef.current = frame

    return () => {
      if (callFrameRef.current) {
        callFrameRef.current.destroy()
        callFrameRef.current = null
      }
    }
  }, [phase, booking])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (callFrameRef.current) {
        callFrameRef.current.destroy()
        callFrameRef.current = null
      }
    }
  }, [])

  // --- Render states ---

  if (loading) {
    return (
      <>
        <Nav />
        <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
          <div className="container">
            <p style={{ color: 'var(--gray)', fontSize: '1.1rem' }}>Loading lesson...</p>
          </div>
        </section>
      </>
    )
  }

  if (forbidden) {
    return (
      <>
        <Nav />
        <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
          <div className="container">
            <h1 style={{ color: '#dc2626', marginBottom: '1rem' }}>403 — Access Denied</h1>
            <p style={{ color: 'var(--gray)', fontSize: '1.05rem' }}>
              You do not have permission to access this lesson.
            </p>
            <Link to="/dashboard" style={{ color: 'var(--primary)', marginTop: '1rem', display: 'inline-block' }}>
              Return to Dashboard
            </Link>
          </div>
        </section>
      </>
    )
  }

  if (error) {
    return (
      <>
        <Nav />
        <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
          <div className="container">
            <div
              role="alert"
              style={{
                background: '#fef2f2',
                border: '1px solid #fecaca',
                borderRadius: '8px',
                padding: '1rem',
                color: '#dc2626',
              }}
            >
              {error}
            </div>
          </div>
        </section>
      </>
    )
  }

  if (phase === 'waiting') {
    return (
      <>
        <Nav />
        <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
          <div className="container">
            <p className="section-label">Waiting Room</p>
            <h1 className="section-title">Your Lesson Starts Soon</h1>
            <p style={{ color: 'var(--gray)', fontSize: '1.05rem', marginBottom: '1.5rem' }}>
              Scheduled for {formatDate(booking.start_at)}
            </p>
            <div
              style={{
                background: '#f0f9ff',
                border: '1px solid #bae6fd',
                borderRadius: '12px',
                padding: '2rem',
                display: 'inline-block',
              }}
            >
              <p style={{ color: '#0369a1', fontSize: '0.9rem', marginBottom: '0.5rem' }}>
                The video room will open in
              </p>
              <p
                style={{
                  fontSize: '2.5rem',
                  fontWeight: 'bold',
                  color: '#0369a1',
                  fontVariantNumeric: 'tabular-nums',
                }}
                aria-live="polite"
                aria-label={`Time remaining: ${countdown}`}
              >
                {countdown}
              </p>
            </div>
          </div>
        </section>
      </>
    )
  }

  if (phase === 'ended') {
    return (
      <>
        <Nav />
        <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
          <div className="container">
            <h1 className="section-title">Session Ended</h1>
            <p style={{ color: 'var(--gray)', fontSize: '1.05rem', marginBottom: '2rem' }}>
              Your lesson on {formatDate(booking.start_at)} has concluded. Thank you for attending!
            </p>
            <Link
              to={`/reviews/${booking.id}`}
              style={{
                display: 'inline-block',
                background: 'var(--primary)',
                color: '#fff',
                padding: '0.75rem 2rem',
                borderRadius: '8px',
                textDecoration: 'none',
                fontWeight: '600',
              }}
            >
              Leave a Review
            </Link>
          </div>
        </section>
      </>
    )
  }

  // phase === 'active'
  return (
    <>
      <Nav />
      <section
        style={{
          paddingTop: '5rem',
          height: 'calc(100vh - 5rem)',
          display: 'flex',
          flexDirection: 'column',
        }}
      >
        <div
          ref={videoContainerRef}
          style={{
            flex: 1,
            width: '100%',
            background: '#111',
            borderRadius: '0',
            overflow: 'hidden',
          }}
          aria-label="Video lesson room"
        />
      </section>
    </>
  )
}
