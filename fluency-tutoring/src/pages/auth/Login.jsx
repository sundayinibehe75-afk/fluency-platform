import { useT } from '../../i18n/LanguageContext'
import { useState } from 'react'
import { Link, Navigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'
import { nextPath } from '../../utils/nextPath'

export default function Login() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const api = useApi()
  const { user, login } = useAuth()
  const { t } = useT()

  // If already logged in, redirect away
  if (user) {
    return <Navigate to={user.role === 'admin' ? '/admin' : nextPath('/dashboard')} replace />
  }

  async function handleSubmit(e) {
    e.preventDefault()
    setError('')
    setLoading(true)

    try {
      const res = await api.post('/auth/login', { email, password })
      login(res.data.access_token)
      // The existing guard at the top of this component will handle the
      // redirect once React re-renders with the updated user state.
    } catch (err) {
      if (err.response && err.response.status === 429) {
        setError('Too many login attempts. Please wait a minute and try again.')
      } else if (err.response && err.response.status === 401) {
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
          <p className="section-label">{t('login.label')}</p>
          <h2 className="section-title">{t('login.title')}</h2>
          <form onSubmit={handleSubmit}>
            <input
              type="email"
              placeholder={t('auth.email')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              aria-label="Email address"
            />
            <input
              type="password"
              placeholder={t('auth.password')}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              aria-label="Password"
            />
            <button type="submit" className="btn btn-primary form-submit" disabled={loading}>
              {loading ? t('login.loading') : t('login.submit')}
            </button>
            {error && (
              <p style={{ color: '#cc0000', fontSize: '0.95rem', paddingTop: '0.5rem' }}>{error}</p>
            )}
          </form>
          <p style={{ marginTop: '1.5rem', color: '#666', fontSize: '0.95rem' }}>
            {t('login.noAccount')} <Link to={`/register${window.location.search}`} style={{ color: '#cc0000', textDecoration: 'none', fontWeight: 600 }}>{t('login.register')}</Link>
          </p>
          <p style={{ marginTop: '0.75rem', color: '#666', fontSize: '0.95rem' }}>
            <Link to="/reset-password" style={{ color: '#cc0000', textDecoration: 'none', fontWeight: 600 }}>{t('login.forgot')}</Link>
          </p>
        </div>
      </section>
      <Footer />
    </>
  )
}
