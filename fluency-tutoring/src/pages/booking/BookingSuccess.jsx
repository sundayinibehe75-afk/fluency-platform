import { Link, useSearchParams } from 'react-router-dom'
import { formatDate } from '../../utils/dateUtils'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

export default function BookingSuccess() {
  const [searchParams] = useSearchParams()
  const lessonDate = searchParams.get('date')

  return (
    <>
      <Nav />
      <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
        <div className="container">
          <div
            style={{
              maxWidth: '500px',
              margin: '0 auto',
              padding: '3rem 2rem',
              background: '#f0fdf4',
              borderRadius: '12px',
              border: '1px solid #bbf7d0',
            }}
          >
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✓</div>
            <h1 className="section-title" style={{ color: '#16a34a' }}>
              Your lesson is confirmed!
            </h1>
            {lessonDate && (
              <p style={{ color: 'var(--gray)', fontSize: '1.05rem', marginTop: '1rem' }}>
                Lesson scheduled for: <strong>{formatDate(lessonDate)}</strong>
              </p>
            )}
            <p style={{ color: 'var(--gray)', fontSize: '1rem', marginTop: '1rem' }}>
              You will receive a confirmation email with the lesson details shortly.
            </p>
            <Link
              to="/dashboard"
              className="btn btn-primary"
              style={{ display: 'inline-block', marginTop: '2rem' }}
            >
              Go to Dashboard
            </Link>
          </div>
        </div>
      </section>
      <Footer />
    </>
  )
}
