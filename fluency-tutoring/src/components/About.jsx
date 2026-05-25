export default function About() {
  return (
    <section id="about">
      <div className="container">
        <div className="about-grid">
          <div className="about-image" role="img" aria-label="Students learning in a classroom">
            <img
              src="https://images.unsplash.com/photo-1434030216411-0b793f4b4173?w=600&q=80"
              alt="Students studying together in a bright classroom"
              style={{ width: '100%', height: '100%', objectFit: 'cover', borderRadius: '8px' }}
              loading="lazy"
            />
          </div>
          <div className="about-text">
            <p className="section-label">About Me</p>
            <h2 className="section-title">Your Guide to the German Language</h2>
            <p>Hi, I'm a professional German tutor with years of experience helping students reach their language goals. I specialize in making German approachable, practical, and even enjoyable.</p>
            <p>My lessons are tailored to your pace, your goals, and your learning style. Whether you need German for travel, work, university, or just personal growth, I've got you covered.</p>
            <p>I hold a formal qualification in German language instruction and have worked with students from A1 beginners all the way to C2 advanced level.</p>
            <div className="about-badges">
              <span className="badge">Native-level Fluency</span>
              <span className="badge">A1 – C2 Levels</span>
              <span className="badge">Certified Tutor</span>
              <span className="badge">Online & In-Person</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  )
}
