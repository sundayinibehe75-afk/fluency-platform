import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'

const WHATSAPP = 'https://wa.me/2349129534727?text=' +
  encodeURIComponent("Hi! I'm interested in German lessons. Can we chat?")

/**
 * Contact: messages go through the site's own inbox (so every conversation
 * stays in one place, under Fluency German) or WhatsApp. Visitors create a
 * free account first and land straight in Messages.
 */
export default function Contact() {
  const { user } = useAuth()
  const messagesLink = user ? '/messages' : `/register?next=${encodeURIComponent('/messages')}`

  return (
    <section id="contact">
      <div className="container" style={{ textAlign: 'center' }}>
        <p className="section-label">Get in Touch</p>
        <h2 className="section-title">Ready to Start Learning?</h2>
        <p className="section-sub" style={{ margin: '0 auto 2rem' }}>
          Have questions or want to book your free introductory lesson? Send me a message here
          {user ? '' : ' (it takes a minute to create your free account)'} or on WhatsApp, and
          I'll get back to you within 24 hours.
        </p>
        <div className="contact-actions">
          <Link to={messagesLink} className="btn btn-primary">
            Send me a message
          </Link>
          <a href={WHATSAPP} target="_blank" rel="noopener noreferrer" className="btn btn-whatsapp">
            Chat on WhatsApp
          </a>
        </div>
        <div style={{ marginTop: '1.5rem', color: 'var(--gray)', fontSize: '0.95rem' }}>
          <span>🕐 Response within 24 hours</span>
        </div>
      </div>
    </section>
  )
}
