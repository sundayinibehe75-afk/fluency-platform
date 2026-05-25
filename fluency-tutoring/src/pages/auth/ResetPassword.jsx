import { useState } from 'react'
import { useSearchParams, Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  return (
    <>
      <Nav />
      <section id="contact" style={{ paddingTop: '7rem' }}>
        <div className="container" style={{ maxWidth: '500px' }}>
          {token ? <ConfirmForm token={token} /> : <RequestForm />}
        </div>
      </section>
      <Footer />
    </>
  )
}

function RequestForm() {
  const [email, setEmail] = useState('')
  const [submitted, setSubmitted] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const api = useApi()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      await api.post('/auth/reset-password/request', { email })
      setSubmitted(true)
    } catch (err) {
      if (err.response && err.response.data) {
        setError(err.response.data.detail || 'Something went wrong. Please try again.')
      } else {
        setError('Network error. Please check your connection and try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (submitted) {
    return (
      <>
        <p className="section-label">Check Your Email</p>
        <h2 className="section-title">Reset Link Sent</h2>
        <p style={{ color: '#666', lineHeight: '1.7', marginTop: '1rem' }}>
          If an account exists with that email address, we've sent a password reset link.
          Please check your inbox and follow the instructions.
        </p>
        <p style={{ marginTop: '1.5rem', color: '#666', fontSize: '0.95rem' }}>
          <Link to="/login" style={{ color: '#cc0000', textDecoration: 'none', fontWeight: 600 }}>Back to Login</Link>
        </p>
      </>
    )
  }

  return (
    <>
      <p className="section-label">Forgot Password?</p>
      <h2 className="section-title">Reset Your Password</h2>
      <p style={{ color: '#666', lineHeight: '1.7', marginBottom: '1.5rem' }}>
        Enter your email address and we'll send you a link to reset your password.
      </p>
      <form onSubmit={handleSubmit}>
        <input
          type="email"
          placeholder="Email Address"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
          aria-label="Email address"
        />
        <button type="submit" className="btn btn-primary form-submit" disabled={loading}>
          {loading ? 'Sending...' : 'Send Reset Link'}
        </button>
        {error && (
          <p style={{ color: '#cc0000', fontSize: '0.95rem', paddingTop: '0.5rem' }}>{error}</p>
        )}
      </form>
      <p style={{ marginTop: '1.5rem', color: '#666', fontSize: '0.95rem' }}>
        Remember your password? <Link to="/login" style={{ color: '#cc0000', textDecoration: 'none', fontWeight: 600 }}>Log in</Link>
      </p>
    </>
  )
}

function ConfirmForm({ token }) {
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [success, setSuccess] = useState(false)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const api = useApi()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')

    if (password !== confirmPassword) {
      setError('Passwords do not match.')
      return
    }

    setLoading(true)

    try {
      await api.post('/auth/reset-password/confirm', { token, new_password: password })
      setSuccess(true)
    } catch (err) {
      if (err.response && err.response.data) {
        setError(err.response.data.detail || 'Invalid or expired token. Please request a new reset link.')
      } else {
        setError('Network error. Please check your connection and try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  if (success) {
    return (
      <>
        <p className="section-label">Success</p>
        <h2 className="section-title">Password Updated</h2>
        <p style={{ color: '#666', lineHeight: '1.7', marginTop: '1rem' }}>
          Your password has been reset successfully. You can now log in with your new password.
        </p>
        <Link to="/login" className="btn btn-primary" style={{ marginTop: '1.5rem' }}>
          Go to Login
        </Link>
      </>
    )
  }

  return (
    <>
      <p className="section-label">Almost Done</p>
      <h2 className="section-title">Set New Password</h2>
      <form onSubmit={handleSubmit}>
        <input
          type="password"
          placeholder="New Password (min. 8 characters)"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          required
          minLength={8}
          aria-label="New password, minimum 8 characters"
        />
        <input
          type="password"
          placeholder="Confirm New Password"
          value={confirmPassword}
          onChange={(e) => setConfirmPassword(e.target.value)}
          required
          minLength={8}
          aria-label="Confirm new password"
        />
        <button type="submit" className="btn btn-primary form-submit" disabled={loading}>
          {loading ? 'Updating...' : 'Reset Password'}
        </button>
        {error && (
          <p style={{ color: '#cc0000', fontSize: '0.95rem', paddingTop: '0.5rem' }}>{error}</p>
        )}
      </form>
    </>
  )
}
