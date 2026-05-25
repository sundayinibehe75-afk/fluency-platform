import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

export default function Register() {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [cefrLevel, setCefrLevel] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const api = useApi()
  const { login } = useAuth()
  const navigate = useNavigate()

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await api.post('/auth/register', {
        first_name: firstName,
        last_name: lastName,
        email,
        password,
        cefr_level: cefrLevel || null,
      })
      login(res.data.access_token)
      navigate('/dashboard')
    } catch (err) {
      if (err.response && err.response.data) {
        const data = err.response.data
        setError(data.detail || data.error || 'Registration failed. Please try again.')
      } else {
        setError('Network error. Please check your connection and try again.')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <>
      <Nav />
      <section id="contact" style={{ paddingTop: '7rem' }}>
        <div className="container" style={{ maxWidth: '500px' }}>
          <p className="section-label">Join Us</p>
          <h2 className="section-title">Create Your Account</h2>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <input
                type="text"
                placeholder="First Name"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
                aria-label="First name"
              />
              <input
                type="text"
                placeholder="Last Name"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
                aria-label="Last name"
              />
            </div>
            <input
              type="email"
              placeholder="Email Address"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              aria-label="Email address"
            />
            <input
              type="password"
              placeholder="Password (min. 8 characters)"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={8}
              aria-label="Password, minimum 8 characters"
            />
            <select
              value={cefrLevel}
              onChange={(e) => setCefrLevel(e.target.value)}
              required
              aria-label="CEFR level"
            >
              <option value="" disabled>Select Your CEFR Level</option>
              <option value="A0">A0 — No experience</option>
              <option value="A1">A1 — Beginner</option>
              <option value="A2">A2 — Elementary</option>
              <option value="B1">B1 — Intermediate</option>
              <option value="B2">B2 — Upper Intermediate</option>
              <option value="C1">C1 — Advanced</option>
              <option value="C2">C2 — Proficient</option>
            </select>
            <button type="submit" className="btn btn-primary form-submit" disabled={loading}>
              {loading ? 'Creating Account...' : 'Register'}
            </button>
            {error && (
              <p style={{ color: '#cc0000', fontSize: '0.95rem', paddingTop: '0.5rem' }}>{error}</p>
            )}
          </form>
          <p style={{ marginTop: '1.5rem', color: '#666', fontSize: '0.95rem' }}>
            Already have an account? <Link to="/login" style={{ color: '#cc0000', textDecoration: 'none', fontWeight: 600 }}>Log in</Link>
          </p>
        </div>
      </section>
      <Footer />
    </>
  )
}
