export default function About() {
  return (
    <section id="about">
      <div className="container">
        <div className="about-grid">
          <div className="about-image" role="img" aria-label="Emmanuel - German Tutor">
            <img
              src="/tutor-photo.jpg"
              alt="Emmanuel - Professional German Tutor"
              style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '8px' }}
              loading="lazy"
            />
          </div>
          <div className="about-text">
            <p className="section-label">About Me</p>
            <h2 className="section-title">Your Guide to the German Language</h2>
            <p>Hi, I'm Emmanuel — a professional German tutor with a passion for making the language approachable, practical, and even enjoyable. I've helped over 40 students reach their language goals on Preply alone.</p>
            <p>My lessons are tailored to your pace, your goals, and your learning style. Whether you need German for travel, work, university, or just personal growth, I've got you covered.</p>
            <p>I hold a Goethe B2 certification and specialize in helping students from complete beginners (A1) through to upper intermediate (B2) level.</p>
            <div className="about-badges">
              <span className="badge">⭐ 4.8 Rating (46 Reviews)</span>
              <span className="badge">A1 – B2 Levels</span>
              <span className="badge">Goethe B2 Certified</span>
              <span className="badge">Online Lessons</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
