import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

export default function Nav() {
  const { user, logout } = useAuth()
  const [menuOpen, setMenuOpen] = useState(false)

  async function handleLogout() {
    setMenuOpen(false)
    await logout()
  }

  function handleLinkClick() {
    setMenuOpen(false)
  }

  return (
    <nav>
      <Link to="/" className="nav-logo">Fluency <span>Tutoring</span></Link>
      <button
        className="nav-hamburger"
        onClick={() => setMenuOpen(prev => !prev)}
        aria-label="Toggle navigation menu"
        aria-expanded={menuOpen}
      >
        ☰
      </button>
      <ul className={`nav-links${menuOpen ? ' nav-links--open' : ''}`}>
        <li><a href="/#about" onClick={handleLinkClick}>About</a></li>
        <li><a href="/#offerings" onClick={handleLinkClick}>Lessons</a></li>
        <li><a href="/#pricing" onClick={handleLinkClick}>Pricing</a></li>
        <li><a href="/#testimonials" onClick={handleLinkClick}>Reviews</a></li>
        {user ? (
          <>
            <li><Link to="/dashboard" onClick={handleLinkClick}>Dashboard</Link></li>
            <li><Link to="/messages" onClick={handleLinkClick}>Messages</Link></li>
            <li>
              <button
                onClick={handleLogout}
                className="nav-cta"
                style={{ border: 'none', cursor: 'pointer', font: 'inherit' }}
              >
                Logout
              </button>
            </li>
          </>
        ) : (
          <>
            <li><Link to="/login" onClick={handleLinkClick}>Login</Link></li>
            <li><Link to="/register" onClick={handleLinkClick} className="nav-cta">Register</Link></li>
          </>
        )}
      </ul>
    </nav>
  )
}
