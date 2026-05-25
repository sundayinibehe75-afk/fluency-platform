import { useState } from 'react'
import { useParams, Navigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useApi } from '../../hooks/useApi'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

const MAX_COMMENT_LENGTH = 1000

function StarRating({ rating, hoverRating, onSelect, onHover, onLeave, disabled }) {
  return (
    <div className="star-rating" role="group" aria-label="Rating">
      {[1, 2, 3, 4, 5].map((star) => {
        const isFilled = star <= (hoverRating || rating)
        return (
          <button
            key={star}
            type="button"
            className={`star-btn ${isFilled ? 'star-btn--filled' : ''}`}
            onClick={() => onSelect(star)}
            onMouseEnter={() => onHover(star)}
            onMouseLeave={onLeave}
            disabled={disabled}
            aria-label={`${star} star${star !== 1 ? 's' : ''}`}
            aria-pressed={star === rating}
          >
            <svg
              width="32"
              height="32"
              viewBox="0 0 24 24"
              fill={isFilled ? '#f5a623' : 'none'}
              stroke={isFilled ? '#f5a623' : '#ccc'}
              strokeWidth="2"
              aria-hidden="true"
            >
              <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
            </svg>
          </button>
        )
      })}
    </div>
  )
}

export default function ReviewForm() {
  const { bookingId } = useParams()
  const { user } = useAuth()
  const api = useApi()

  const [rating, setRating] = useState(0)
  const [hoverRating, setHoverRating] = useState(0)
  const [comment, setComment] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState(null)
  const [formDisabled, setFormDisabled] = useState(false)

  if (!user) {
    return <Navigate to="/login" replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    if (rating === 0 || submitting || formDisabled) return

    try {
      setSubmitting(true)
      setError(null)
      await api.post('/reviews', {
        booking_id: bookingId,
        rating,
        comment: comment.trim() || null,
      })
      setSuccess(true)
      setFormDisabled(true)
    } catch (err) {
      if (err.response?.status === 409) {
        setError("You've already reviewed this lesson.")
        setFormDisabled(true)
      } else if (err.response?.status === 403) {
        setError("You don't have permission to review this booking.")
        setFormDisabled(true)
      } else {
        setError('Something went wrong. Please try again.')
      }
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <>
      <Nav />
      <main className="review-page">
        <div className="container">
          <div className="review-form-wrapper">
            <h1 className="section-title" style={{ marginTop: '5rem', marginBottom: '1rem' }}>
              Leave a Review
            </h1>
            <p className="review-subtitle">
              How was your lesson? Your feedback helps improve the learning experience.
            </p>

            {success ? (
              <div className="review-success" role="status">
                <svg
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="#4caf50"
                  strokeWidth="2"
                  aria-hidden="true"
                >
                  <circle cx="12" cy="12" r="10" />
                  <path d="M9 12l2 2 4-4" />
                </svg>
                <h2>Thank you for your review!</h2>
                <p>Your feedback has been submitted successfully.</p>
              </div>
            ) : (
              <form className="review-form" onSubmit={handleSubmit} noValidate>
                {error && (
                  <div className="review-error" role="alert">
                    {error}
                  </div>
                )}

                <div className="review-field">
                  <label className="review-label" id="rating-label">
                    Rating <span className="required">*</span>
                  </label>
                  <StarRating
                    rating={rating}
                    hoverRating={hoverRating}
                    onSelect={(star) => !formDisabled && setRating(star)}
                    onHover={(star) => !formDisabled && setHoverRating(star)}
                    onLeave={() => setHoverRating(0)}
                    disabled={formDisabled}
                  />
                  {rating > 0 && (
                    <span className="rating-text" aria-live="polite">
                      {rating} of 5 stars
                    </span>
                  )}
                </div>

                <div className="review-field">
                  <label htmlFor="review-comment" className="review-label">
                    Comment <span className="optional">(optional)</span>
                  </label>
                  <textarea
                    id="review-comment"
                    className="review-textarea"
                    value={comment}
                    onChange={(e) => setComment(e.target.value.slice(0, MAX_COMMENT_LENGTH))}
                    placeholder="Share your experience..."
                    maxLength={MAX_COMMENT_LENGTH}
                    rows={5}
                    disabled={formDisabled}
                    aria-describedby="comment-counter"
                  />
                  <span id="comment-counter" className="review-char-counter" aria-live="polite">
                    {comment.length}/{MAX_COMMENT_LENGTH}
                  </span>
                </div>

                <button
                  type="submit"
                  className="btn btn-primary review-submit-btn"
                  disabled={rating === 0 || submitting || formDisabled}
                >
                  {submitting ? 'Submitting...' : 'Submit Review'}
                </button>
              </form>
            )}
          </div>
        </div>
      </main>
      <Footer />
    </>
  )
}
