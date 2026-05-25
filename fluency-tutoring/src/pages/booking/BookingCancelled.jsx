import { Link } from 'react-router-dom'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

export default function BookingCancelled() {
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
              background: '#fef2f2',
              borderRadius: '12px',
              border: '1px solid #fecaca',
            }}
          >
            <div style={{ fontSize: '3rem', marginBottom: '1rem' }}>✗</div>
            <h1 className="section-title" style={{ color: '#dc2626' }}>
              Payment was not completed
            </h1>
            <p style={{ color: 'var(--gray)', fontSize: '1.05rem', marginTop: '1rem' }}>
              Your payment was not processed. No charges have been made to your account.
            </p>
            <Link
              to="/booking"
              className="btn btn-primary"
              style={{ display: 'inline-block', marginTop: '2rem' }}
            >
              Try Again
            </Link>
          </div>
        </div>
      </section>
      <Footer />
    </>
  )
}
