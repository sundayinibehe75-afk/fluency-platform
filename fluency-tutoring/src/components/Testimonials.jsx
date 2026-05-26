const testimonials = [
  {
    text: "I passed my B2 exam! Emmanuel is a lovely teacher. He is patient, kind and gently improves my mistakes. 10/10",
    author: 'Amy',
    detail: 'Exam Preparation — B2',
    rating: 5,
  },
  {
    text: "I passed my A1 test with a 57 out of 60, sehr gut. I couldn't have done it without Emmanuel. If you're still reading this, please give him a try — you won't be disappointed.",
    author: 'Ola',
    detail: 'Beginner → A1 Certified',
    rating: 5,
  },
  {
    text: "Emmanuel is truly an exceptional tutor. Concepts are clearly explained, incredibly engaging and has a unique way of breaking down concepts. My confidence in speaking and understanding German has grown tremendously.",
    author: 'Moureen',
    detail: 'General German',
    rating: 5,
  },
  {
    text: "I've been learning with Emmanuel for over 4 months and it has been great. Our conversations are becoming stronger and I am really enjoying my weekly lessons. Highly recommend!",
    author: 'Hayden',
    detail: 'Conversation Practice',
    rating: 5,
  },
  {
    text: "Emmanuel is truly a one of a kind tutor. He takes the time to explain every detail to make sure you have solid understanding. Very dynamic and interactive classes full of knowledge.",
    author: 'Felix',
    detail: 'Beginner German',
    rating: 5,
  },
  {
    text: "In just two lessons, I've made more progress than I ever expected. His teaching style makes learning German both fun and engaging. Thank you, Emmanuel!",
    author: 'Carla',
    detail: 'General German',
    rating: 5,
  },
]

export default function Testimonials() {
  return (
    <section id="testimonials">
      <div className="container">
        <p className="section-label">Student Reviews</p>
        <h2 className="section-title">What My Students Say</h2>
        <p className="section-sub" style={{ color: '#ccc', marginBottom: '0.5rem' }}>
          4.8 ★ average from 46 verified reviews on Preply
        </p>
        <div className="testimonials-grid">
          {testimonials.map((t) => (
            <div className="testimonial-card" key={t.author}>
              <div className="stars">{'★'.repeat(t.rating)}</div>
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
