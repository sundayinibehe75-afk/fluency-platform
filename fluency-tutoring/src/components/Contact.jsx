import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/LanguageContext'

const WHATSAPP_NUMBER = '2349129534727'

/**
 * Contact: messages go through the site's own inbox (so every conversation
 * stays in one place, under Fluency German) or WhatsApp. Visitors create a
 * free account first and land straight in Messages.
 */
export default function Contact() {
  const { user } = useAuth()
  const { t } = useT()
  const whatsapp = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(t('contact.whatsappText'))}`
  const messagesLink = user ? '/messages' : `/register?next=${encodeURIComponent('/messages')}`

  return (
    <section id="contact">
      <div className="container" style={{ textAlign: 'center' }}>
        <p className="section-label">{t('contact.label')}</p>
        <h2 className="section-title">{t('contact.title')}</h2>
        <p className="section-sub" style={{ margin: '0 auto 2rem' }}>
          {t('contact.text', { account: user ? '' : t('contact.account') })}
        </p>
        <div className="contact-actions">
          <Link to={messagesLink} className="btn btn-primary">
            {t('contact.message')}
          </Link>
          <a href={whatsapp} target="_blank" rel="noopener noreferrer" className="btn btn-whatsapp">
            {t('contact.whatsapp')}
          </a>
        </div>
        <div style={{ marginTop: '1.5rem', color: 'var(--gray)', fontSize: '0.95rem' }}>
          <span>{t('contact.response')}</span>
        </div>
      </div>
    </section>
  )
}
