import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/LanguageContext'
import LanguageSwitcher from '../i18n/LanguageSwitcher'

export default function Nav() {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)
  const { t } = useT()

  async function handleLogout() {
    setMenuOpen(false)
    await logout()
  }

  function handleLinkClick() {
    setMenuOpen(false)
  }

  return (
    <nav>
      <Link to="/" className="nav-logo">Fluency <span>German</span></Link>
      <LanguageSwitcher />
      <button
        className="nav-hamburger"
        onClick={() => setMenuOpen(prev => !prev)}
        aria-label="Toggle navigation menu"
        aria-expanded={menuOpen}
      >
        ☰
      </button>
      <ul className={`nav-links${menuOpen ? ' nav-links--open' : ''}`}>
        <li><a href="/#about" onClick={handleLinkClick}>{t('nav.about')}</a></li>
        <li><a href="/#offerings" onClick={handleLinkClick}>{t('nav.lessons')}</a></li>
        <li><a href="/#pricing" onClick={handleLinkClick}>{t('nav.pricing')}</a></li>
        <li><a href="/#testimonials" onClick={handleLinkClick}>{t('nav.reviews')}</a></li>
        {user ? (
          <>
            <li>
              <Link to={user.role === 'admin' ? '/admin' : '/dashboard'} onClick={handleLinkClick}>
                {t('nav.dashboard')}
              </Link>
            </li>
            {user.role === 'student' && (
              <li><Link to="/notes" onClick={handleLinkClick}>{t('nav.notes')}</Link></li>
            )}
            <li><Link to="/messages" onClick={handleLinkClick}>{t('nav.messages')}</Link></li>
            <li>
              <button
                onClick={handleLogout}
                className="nav-cta"
                style={{ border: 'none', cursor: 'pointer', font: 'inherit' }}
              >
                {t('nav.logout')}
              </button>
            </li>
          </>
        ) : (
          <>
            <li><Link to="/login" onClick={handleLinkClick}>{t('nav.login')}</Link></li>
            <li><Link to="/register" onClick={handleLinkClick} className="nav-cta">{t('nav.register')}</Link></li>
          </>
        )}
      </ul>
    </nav>
  )
}
