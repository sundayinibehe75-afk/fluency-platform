import { Link } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth'
import { useT } from '../i18n/LanguageContext'

export default function Hero() {
  const { user } = useAuth()
  const { t, lang } = useT()
  const trial = '/booking?type=trial'
  return (
    <section
      id="hero"
      style={{
        backgroundImage: 'linear-gradient(rgba(0, 0, 0, 0.65), rgba(0, 0, 0, 0.65)), url("https://images.unsplash.com/photo-1467269204594-9661b134dd2b?w=1600&q=80")',
        backgroundSize: 'cover',
        backgroundPosition: 'center',
      }}
    >
      <div className="hero-content">
        <h1>{t('hero.title1')}<br /><span>{t('hero.title2')}</span></h1>
        <p>{t('hero.text')}</p>
        <Link to={user ? trial : `/register?next=${encodeURIComponent(trial)}`} className="btn btn-primary">
          {t('hero.cta')}
        </Link>
        <a href="#offerings" className="btn btn-outline">{t('hero.cta2')}</a>
        {lang !== 'en' && <p className="hero-lesson-language">{t('hero.lessonLanguage')}</p>}
      </div>
    </section>
  )
}
