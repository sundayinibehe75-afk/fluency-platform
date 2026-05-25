import { useState, useEffect } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import { formatDate } from '../../utils/dateUtils'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

function StarRating({ rating, max = 5 }) {
  const stars = []
  for (let i = 1; i <= max; i++) {
    stars.push(i <= rating ? '★' : '☆')
  }
  return <span className="stars">{stars.join('')}</span>
}

export default function TutorProfile() {
  const { id } = useParams()
  const api = useApi()
  const { user } = useAuth()
  const navigate = useNavigate()

  const [tutor, setTutor] = useState(null)
  const [loading, setLoading] = useState(true)
  const [notFound, setNotFound] = useState(false)

  useEffect(() => {
    async function fetchTutor() {
      try {
        const res = await api.get(`/tutors/${id}`)
        setTutor(res.data)
      } catch (err) {
        if (err.response && err.response.status === 404) {
          setNotFound(true)
        }
      } finally {
        setLoading(false)
      }
    }
    fetchTutor()
  }, [id])

  function handleBookLesson() {
    if (user) {
      navigate('/booking')
    } else {
      navigate('/register')
    }
  }

  if (loading) {
    return (
      <>
        <Nav />
        <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
          <div className="container">
            <p style={{ color: 'var(--gray)', fontSize: '1.1rem' }}>Loading tutor profile...</p>
          </div>
        </section>
        <Footer />
      </>
    )
  }

  if (notFound) {
    return (
      <>
        <Nav />
        <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
          <div className="container">
            <h2 className="section-title">Tutor Not Found</h2>
            <p style={{ color: 'var(--gray)', fontSize: '1.05rem' }}>
              The tutor you are looking for does not exist or has been removed.
            </p>
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
          {/* Profile Header */}
          <div className="tutor-profile-header">
            <div className="tutor-photo-container">
              {tutor.photo_url ? (
                <img
                  src={tutor.photo_url}
                  alt={`${tutor.display_name} profile photo`}
                  className="tutor-photo"
                  loading="lazy"
                />
              ) : (
                <div className="tutor-photo-placeholder" aria-label="Tutor photo placeholder">
                  👤
                </div>
              )}
            </div>
            <div className="tutor-info">
              <h1 className="section-title" style={{ marginBottom: '0.5rem' }}>
                {tutor.display_name}
              </h1>
              <div className="tutor-rating-summary">
                <StarRating rating={Math.round(tutor.avg_rating)} />
                <span style={{ marginLeft: '0.5rem', color: 'var(--gray)', fontSize: '1rem' }}>
                  {tutor.avg_rating.toFixed(1)} ({tutor.review_count} {tutor.review_count === 1 ? 'review' : 'reviews'})
                </span>
              </div>
              {tutor.years_experience != null && (
                <p style={{ color: 'var(--gray)', marginTop: '0.5rem' }}>
                  {tutor.years_experience} {tutor.years_experience === 1 ? 'year' : 'years'} of experience
                </p>
              )}
              <button
                onClick={handleBookLesson}
                className="btn btn-primary"
                style={{ marginTop: '1.5rem' }}
              >
                Book a Lesson
              </button>
            </div>
          </div>

          {/* Bio */}
          {tutor.bio && (
            <div style={{ marginTop: '3rem' }}>
              <p className="section-label">About</p>
              <p style={{ color: 'var(--gray)', lineHeight: '1.8', maxWidth: '700px' }}>
                {tutor.bio}
              </p>
            </div>
          )}

          {/* Details Grid */}
          <div className="tutor-details-grid">
            {tutor.spoken_languages.length > 0 && (
              <div>
                <p className="section-label">Languages Spoken</p>
                <div className="about-badges">
                  {tutor.spoken_languages.map((lang) => (
                    <span key={lang} className="badge">{lang}</span>
                  ))}
                </div>
              </div>
            )}

            {tutor.specialisms.length > 0 && (
              <div>
                <p className="section-label">Specialisms</p>
                <div className="about-badges">
                  {tutor.specialisms.map((spec) => (
                    <span key={spec} className="badge">{spec}</span>
                  ))}
                </div>
              </div>
            )}

            {tutor.cefr_levels_taught.length > 0 && (
              <div>
                <p className="section-label">CEFR Levels Taught</p>
                <div className="about-badges">
                  {tutor.cefr_levels_taught.map((level) => (
                    <span key={level} className="badge">{level}</span>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Recent Reviews */}
          {tutor.recent_reviews && tutor.recent_reviews.length > 0 && (
            <div style={{ marginTop: '3rem' }}>
              <p className="section-label">Recent Reviews</p>
              <h2 className="section-title" style={{ fontSize: '1.5rem' }}>
                What Students Say
              </h2>
              <div className="tutor-reviews-list">
                {tutor.recent_reviews.map((review, index) => (
                  <div key={index} className="tutor-review-card">
                    <div className="tutor-review-header">
                      <span className="tutor-review-author">{review.first_name}</span>
                      <StarRating rating={review.rating} />
                    </div>
                    {review.comment && (
                      <p className="tutor-review-comment">{review.comment}</p>
                    )}
                    <p className="tutor-review-date">{formatDate(review.submitted_at)}</p>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      </section>
      <Footer />
    </>
  )
}
