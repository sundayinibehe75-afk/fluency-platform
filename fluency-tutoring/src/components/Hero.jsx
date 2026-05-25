export default function Hero() {
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
        <h1>Learn German with<br /><span>Confidence & Fluency</span></h1>
        <p>Personalized one-on-one German lessons for all levels. Whether you're a complete beginner or looking to polish your skills, I'll guide you every step of the way.</p>
        <a href="#contact" className="btn btn-primary">Book a Free Intro Lesson</a>
        <a href="#offerings" className="btn btn-outline">See What I Offer</a>
      </div>
    </section>
  )
}
