import { useState } from 'react'

const FORMSPREE_ID = 'mreojgka'

export function ContactModal({ isOpen, onClose }) {
  const [status, setStatus] = useState('')
  const [statusColor, setStatusColor] = useState('')

  async function handleSubmit(e) {
    e.preventDefault()
    const data = new FormData(e.target)
    try {
      const res = await fetch(`https://formspree.io/f/${FORMSPREE_ID}`, {
        method: 'POST',
        body: data,
        headers: { Accept: 'application/json' },
      })
      if (res.ok) {
        setStatus("Message sent! I'll be in touch within 24 hours.")
        setStatusColor('#2a9d2a')
        e.target.reset()
        setTimeout(() => onClose(), 2000)
      } else {
        setStatus('Something went wrong. Please try again or email me directly.')
        setStatusColor('#cc0000')
      }
    } catch {
      setStatus('Network error. Please check your connection and try again.')
      setStatusColor('#cc0000')
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <button className="modal-close" onClick={onClose} aria-label="Close contact form">&times;</button>
        <p className="section-label">Get in Touch</p>
        <h2 className="section-title" style={{ fontSize: '1.6rem' }}>Send Me a Message</h2>
        <form onSubmit={handleSubmit}>
          <div className="form-row">
            <input type="text" name="name" placeholder="Your Name" required aria-label="Your name" />
            <input type="email" name="email" placeholder="Your Email" required aria-label="Your email" />
          </div>
          <select name="level" required defaultValue="" aria-label="Your current German level">
            <option value="" disabled>Your Current German Level</option>
            <option value="none">No experience (A0)</option>
            <option value="a1">Beginner (A1)</option>
            <option value="a2">Elementary (A2)</option>
            <option value="b1">Intermediate (B1)</option>
            <option value="b2">Upper Intermediate (B2)</option>
          </select>
          <select name="interest" required defaultValue="" aria-label="What are you interested in">
            <option value="" disabled>What are you interested in?</option>
            <option value="general">General German</option>
            <option value="business">Business German</option>
            <option value="exam">Exam Preparation</option>
            <option value="conversation">Conversation Practice</option>
            <option value="travel">Travel German</option>
          </select>
          <textarea name="message" placeholder="Tell me a bit about your goals or any questions you have..." aria-label="Message"></textarea>
          <button type="submit" className="btn btn-primary form-submit">Send Message</button>
          {status && <p style={{ color: statusColor, fontSize: '0.95rem', paddingTop: '0.5rem' }}>{status}</p>}
        </form>
      </div>
    </div>
  )
}

export default function Contact() {
  const [modalOpen, setModalOpen] = useState(false)

  return (
    <>
      <section id="contact">
        <div className="container" style={{ textAlign: 'center' }}>
          <p className="section-label">Get in Touch</p>
          <h2 className="section-title">Ready to Start Learning?</h2>
          <p className="section-sub" style={{ margin: '0 auto 2rem' }}>
            Have questions or want to book your free introductory lesson? Reach out and I'll get back to you within 24 hours.
          </p>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap' }}>
            <button onClick={() => setModalOpen(true)} className="btn btn-primary">
              Send a Message
            </button>
            <a href="mailto:fluencylangtutoring@gmail.com" className="btn btn-outline" style={{ color: 'var(--black)', borderColor: 'var(--border)' }}>
              Email Me Directly
            </a>
          </div>
          <div style={{ marginTop: '1.5rem', color: 'var(--gray)', fontSize: '0.95rem' }}>
            <span>📧 fluencylangtutoring@gmail.com</span>
            <span style={{ margin: '0 1rem' }}>•</span>
            <span>🕐 Response within 24 hours</span>
          </div>
        </div>
      </section>
      <ContactModal isOpen={modalOpen} onClose={() => setModalOpen(false)} />
    </>
  )
}
