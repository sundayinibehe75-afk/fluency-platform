import { useT } from '../i18n/LanguageContext'

export default function About() {
  const { t } = useT()
  return (
    <section id="about">
      <div className="container">
        <div className="about-grid">
          <div className="about-image" role="img" aria-label="Emmanuel Sunday - German Tutor">
            <img
              src="/tutor-photo.jpg"
              alt={t('about.photoAlt')}
              style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '50%' }}
              loading="lazy"
            />
          </div>
          <div className="about-text">
            <p className="section-label">{t('about.label')}</p>
            <h2 className="section-title">{t('about.title')}</h2>
            <p style={{ fontWeight: 600, color: 'var(--black)', marginBottom: '0.5rem' }}>
              {t('about.lead')}
            </p>
            <p>{t('about.p1')}</p>
            <p>{t('about.p2')}</p>
            <p>{t('about.p3')}</p>
            <div className="about-badges">
              <span className="badge">{t('about.badgeRating')}</span>
              <span className="badge">{t('about.badgeLevels')}</span>
              <span className="badge">{t('about.badgeCert')}</span>
              <span className="badge">{t('about.badgePro')}</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
