const plans = [
  {
    name: 'Single Session',
    price: '45',
    period: 'per 60-min lesson',
    features: ['One-on-one lesson', 'Custom lesson plan', 'Session notes provided', 'Flexible scheduling'],
    featured: false,
  },
  {
    name: 'Monthly Package',
    price: '160',
    period: '4 lessons / month',
    features: ['4 x 60-min lessons', 'Progress tracking', 'Homework & resources', 'WhatsApp support'],
    featured: true,
  },
  {
    name: 'Intensive Package',
    price: '280',
    period: '8 lessons / month',
    features: ['8 x 60-min lessons', 'Full curriculum plan', 'Exam prep included', 'Priority scheduling'],
    featured: false,
  },
]

export default function Pricing() {
  return (
    <section id="pricing">
      <div className="container">
        <p className="section-label">Pricing</p>
        <h2 className="section-title">Simple, Transparent Rates</h2>
        <p className="section-sub">No hidden fees. Choose the plan that works best for you.</p>
        <div className="pricing-grid">
          {plans.map((p) => (
            <div className={`pricing-card${p.featured ? ' featured' : ''}`} key={p.name}>
              {p.featured && <span className="featured-tag">Most Popular</span>}
              <h3>{p.name}</h3>
              <div className="price"><sup>$</sup>{p.price}</div>
              <p className="price-period">{p.period}</p>
              <ul className="pricing-features">
                {p.features.map((f) => <li key={f}>{f}</li>)}
              </ul>
              <a href="#contact" className="btn btn-primary">Get Started</a>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
