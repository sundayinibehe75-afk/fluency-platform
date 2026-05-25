const offerings = [
  { icon: '🎯', title: 'Beginner German', desc: 'Start from zero with a structured, encouraging approach. Build vocabulary, pronunciation, and basic grammar from day one.' },
  { icon: '📈', title: 'Intermediate & Advanced', desc: 'Push past plateaus with targeted grammar work, reading comprehension, and real-world conversation practice.' },
  { icon: '💼', title: 'Business German', desc: 'Master professional vocabulary, email writing, and workplace communication for German-speaking environments.' },
  { icon: '📝', title: 'Exam Preparation', desc: 'Targeted prep for Goethe-Zertifikat, TestDaF, DSH, and other German language certifications.' },
  { icon: '🗣️', title: 'Conversation Practice', desc: 'Improve fluency and confidence through guided conversation sessions on topics that interest you.' },
  { icon: '✈️', title: 'Travel German', desc: 'Learn the essentials for navigating Germany, Austria, or Switzerland — fast, practical, and fun.' },
]

export default function Offerings() {
  return (
    <section id="offerings">
      <div className="container">
        <p className="section-label">What I Offer</p>
        <h2 className="section-title">Lessons Built Around You</h2>
        <p className="section-sub">Every student is different. I offer a range of lesson formats to fit your schedule, goals, and learning style.</p>
        <div className="offerings-grid">
          {offerings.map((o) => (
            <div className="offering-card" key={o.title}>
              <div className="offering-icon" aria-hidden="true">{o.icon}</div>
              <h3>{o.title}</h3>
              <p>{o.desc}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
