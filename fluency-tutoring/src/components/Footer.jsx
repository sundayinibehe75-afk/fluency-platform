export default function Footer() {
  return (
    <footer>
      <div className="footer-content">
        <div className="footer-main">
          <p>&copy; 2026 <span>Fluency Language Tutoring</span>. All rights reserved.</p>
        </div>
        <div className="footer-social">
          <a href="#" aria-label="Instagram" className="footer-social-link">Instagram</a>
          <a href="#" aria-label="Twitter / X" className="footer-social-link">Twitter/X</a>
          <a href="#" aria-label="LinkedIn" className="footer-social-link">LinkedIn</a>
          <a href="https://wa.me/1234567890" aria-label="WhatsApp" className="footer-social-link footer-social-link--whatsapp">WhatsApp</a>
        </div>
        <div className="footer-legal">
          <a href="#" className="footer-legal-link">Privacy Policy</a>
          <a href="#" className="footer-legal-link">Terms of Service</a>
        </div>
      </div>
    </footer>
  )
}
