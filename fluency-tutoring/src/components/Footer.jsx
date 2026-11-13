import { useT } from '../i18n/LanguageContext'

export default function Footer() {
  const { t } = useT()
  return (
    <footer>
      <div className="footer-content">
        <div className="footer-main">
          <p>&copy; 2026 <span>Fluency German</span>. {t('footer.rights')}</p>
        </div>
        <div className="footer-social">
          <a href="https://wa.me/2349129534727" aria-label="WhatsApp" className="footer-social-link footer-social-link--whatsapp">WhatsApp</a>
        </div>
        <div className="footer-legal">
          <a href="#" className="footer-legal-link">{t('footer.privacy')}</a>
          <a href="#" className="footer-legal-link">{t('footer.terms')}</a>
        </div>
      </div>
    </footer>
  )
}
