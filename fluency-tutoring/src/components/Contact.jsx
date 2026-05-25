import { useState } from 'react'

const FORMSPREE_ID = 'mreojgka'

export default function Contact() {
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
      } else {
        setStatus('Something went wrong. Please try again or email me directly.')
        setStatusColor('#cc0000')
      }
    } catch {
      setStatus('Network error. Please check your connection and try again.')
      setStatusColor('#cc0000')
    }
  }

  return (
    <section id="contact">
      <div className="container">
        <p className="section-label">Get in Touch</p>
        <h2 className="section-title">Ready to Start Learning?</h2>
        <div className="contact-grid">
          <div className="contact-info">
            <h3>Let's talk about your goals</h3>
            <p>Fill out the form and I'll get back to you within 24 hours to schedule your free introductory lesson and discuss what you'd like to achieve.</p>
            <div className="contact-detail"><span>📧</span><a href="mailto:fluencylangtutoring@gmail.com" style={{ color: 'inherit', textDecoration: 'none' }}>fluencylangtutoring@gmail.com</a></div>
            <div className="contact-detail"><span>🕐</span><span>Response within 24 hours</span></div>
            <div className="contact-detail"><span>🌍</span><span>Online lessons via Zoom / Google Meet</span></div>
          </div>
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
              <option value="c1">Advanced (C1)</option>
              <option value="c2">Proficient (C2)</option>
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
    </section>
  )
}
