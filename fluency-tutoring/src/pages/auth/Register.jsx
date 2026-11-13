import { useT } from '../../i18n/LanguageContext'
import { useState } from 'react'
import { useNavigate, Link, Navigate } from 'react-router-dom'
import { useApi } from '../../hooks/useApi'
import { useAuth } from '../../hooks/useAuth'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'
import { getErrorMessage } from '../../utils/errors'
import { nextPath } from '../../utils/nextPath'
import { GOALS, browserTimeZone } from '../../utils/profile'

export default function Register() {
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [cefrLevel, setCefrLevel] = useState('')
  const [goal, setGoal] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const api = useApi()
  const { user, login } = useAuth()
  const { t } = useT()
  const navigate = useNavigate()

  // If already logged in, redirect away
  if (user) {
    return <Navigate to={user.role === 'admin' ? '/admin' : nextPath('/dashboard')} replace />
  }

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
        learning_goal: goal || null,
        timezone: browserTimeZone(),
      })
      login(res.data.access_token)
      navigate(nextPath('/dashboard'))
    } catch (err) {
      if (err.response && err.response.data) {
        setError(getErrorMessage(err, 'Registration failed. Please try again.'))
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
          <p className="section-label">{t('register.label')}</p>
          <h2 className="section-title">{t('register.title')}</h2>
          <form onSubmit={handleSubmit}>
            <div className="form-row">
              <input
                type="text"
                placeholder={t('register.first')}
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                required
                aria-label="First name"
              />
              <input
                type="text"
                placeholder={t('register.last')}
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                required
                aria-label="Last name"
              />
            </div>
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
              placeholder={t('register.passwordMin')}
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
              <option value="" disabled>{t('register.level')}</option>
              {['A0', 'A1', 'A2', 'B1', 'B2', 'C1', 'C2'].map((level) => (
                <option key={level} value={level}>{t(`level.${level}`)}</option>
              ))}
            </select>
            <select value={goal} onChange={(e) => setGoal(e.target.value)} aria-label="Why are you learning German?">
              <option value="">{t('register.goal')}</option>
              {GOALS.map((g) => (
                <option key={g.value} value={g.value}>{t(`goal.${g.value}`)}</option>
              ))}
            </select>
            <button type="submit" className="btn btn-primary form-submit" disabled={loading}>
              {loading ? t('register.loading') : t('register.submit')}
            </button>
            {error && (
              <p style={{ color: '#cc0000', fontSize: '0.95rem', paddingTop: '0.5rem' }}>{error}</p>
            )}
          </form>
          <p style={{ marginTop: '1.5rem', color: '#666', fontSize: '0.95rem' }}>
            {t('register.haveAccount')} <Link to={`/login${window.location.search}`} style={{ color: '#cc0000', textDecoration: 'none', fontWeight: 600 }}>{t('register.login')}</Link>
          </p>
        </div>
      </section>
      <Footer />
    </>
  )
}
