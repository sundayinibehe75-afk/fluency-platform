import { useState } from 'react'
import { useNavigate, Link } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
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
      const res = await api.post('/auth/login', { email, password })
      login(res.data.access_token)
      // Redirect based on role
      const payload = JSON.parse(atob(res.data.access_token.split('.')[1]))
      if (payload.role === 'admin') {
        navigate('/admin')
      } else {
        navigate('/dashboard')
      }
    } catch (err) {
      if (err.response && err.response.status === 401) {
        setError('Invalid email or password. Please try again.')
      } else if (err.response && err.response.data) {
        setError('Invalid email or password. Please try again.')
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
          <p className="section-label">Welcome Back</p>
          <h2 className="section-title">Log In</h2>
          <form onSubmit={handleSubmit}>
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
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              aria-label="Password"
            />
            <button type="submit" className="btn btn-primary form-submit" disabled={loading}>
              {loading ? 'Logging in...' : 'Log In'}
            </button>
            {error && (
              <p style={{ color: '#cc0000', fontSize: '0.95rem', paddingTop: '0.5rem' }}>{error}</p>
            )}
          </form>
          <p style={{ marginTop: '1.5rem', color: '#666', fontSize: '0.95rem' }}>
            Don't have an account? <Link to="/register" style={{ color: '#cc0000', textDecoration: 'none', fontWeight: 600 }}>Register</Link>
          </p>
          <p style={{ marginTop: '0.75rem', color: '#666', fontSize: '0.95rem' }}>
            <Link to="/reset-password" style={{ color: '#cc0000', textDecoration: 'none', fontWeight: 600 }}>Forgot your password?</Link>
          </p>
        </div>
      </section>
      <Footer />
    </>
  )
}
