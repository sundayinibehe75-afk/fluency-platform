const testimonials = [
  { text: "I went from knowing zero German to holding basic conversations in just 3 months. The lessons are structured but never boring. Highly recommend!", author: 'Sarah M.', detail: 'Beginner → A2 Level' },
  { text: "Passed my Goethe B2 exam on the first try. The exam prep sessions were incredibly focused and exactly what I needed. Worth every penny.", author: 'James T.', detail: 'Goethe B2 Exam Prep' },
  { text: "The business German lessons helped me land a job at a German company. My tutor understood exactly what vocabulary and communication style I needed.", author: 'Priya K.', detail: 'Business German' },
]

export default function Testimonials() {
  return (
    <section id="testimonials">
      <div className="container">
        <p className="section-label">Student Reviews</p>
        <h2 className="section-title">What My Students Say</h2>
        <div className="testimonials-grid">
          {testimonials.map((t) => (
            <div className="testimonial-card" key={t.author}>
              <div className="stars">★★★★★</div>
              <p className="testimonial-text">"{t.text}"</p>
              <p className="testimonial-author">{t.author}</p>
              <p className="testimonial-detail">{t.detail}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
