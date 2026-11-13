import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { getErrorMessage } from '../utils/errors'
import { nairaHint, usePaymentConfig } from '../hooks/usePaymentConfig'

// Shown if the prices can't be loaded; the server's /api/plans is the source of truth
const FALLBACK = [
  { product_key: 'single_session', price_cents: 1000, lessons_per_month: null, is_plan: false },
  { product_key: 'plan_2x', price_cents: 7600, lessons_per_month: 8, is_plan: true },
  { product_key: 'plan_3x', price_cents: 10800, lessons_per_month: 12, is_plan: true },
  { product_key: 'plan_4x', price_cents: 14000, lessons_per_month: 16, is_plan: true },
  { product_key: 'plan_5x', price_cents: 17000, lessons_per_month: 20, is_plan: true },
]

function dollars(cents) {
  const value = cents / 100
  return Number.isInteger(value) ? String(value) : value.toFixed(2)
}

export default function Pricing() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [prices, setPrices] = useState(FALLBACK)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState('')
  const payConfig = usePaymentConfig()
  const autoRenew = payConfig ? payConfig.auto_renew : false

  useEffect(() => {
    api.get('/plans').then((res) => res.data?.length && setPrices(res.data)).catch(() => {})
  }, [])

  const single = prices.find((p) => p.product_key === 'single_session')
  const plans = prices.filter((p) => p.is_plan)

  function go(path) {
    if (!user) navigate(`/register?next=${encodeURIComponent(path)}`)
    else navigate(path)
  }

  async function choosePlan(plan) {
    setError('')
    if (!user) return navigate('/register')
    if (user.role !== 'student') return setError('Plans are for student accounts.')
    try {
      setBusy(plan.product_key)
      const res = await api.post('/subscriptions/checkout', { product_key: plan.product_key })
      window.location.href = res.data.session_url
    } catch (err) {
      setError(getErrorMessage(err, 'Could not start checkout. Please try again.'))
      setBusy(null)
    }
  }

  return (
    <section id="pricing">
      <div className="container">
        <p className="section-label">Pricing</p>
        <h2 className="section-title">Simple, Transparent Rates</h2>
        <p className="section-sub">
          All lessons are 60 minutes, one-to-one. Start with a free trial lesson.
        </p>

        <div className="pricing-grid">
          <div className="pricing-card">
            <h3>Free Trial</h3>
            <div className="price"><sup>$</sup>0</div>
            <p className="price-period">one 60-min lesson</p>
            <ul className="pricing-features">
              <li>Meet your tutor</li>
              <li>Level check and goals</li>
              <li>One per student</li>
            </ul>
            <button className="btn btn-primary" onClick={() => go('/booking?type=trial')}>
              Book free trial
            </button>
          </div>

          {single && (
            <div className="pricing-card">
              <h3>Single Lesson</h3>
              <div className="price"><sup>$</sup>{dollars(single.price_cents)}</div>
              <p className="price-period">per 60-min lesson</p>
              {nairaHint(payConfig, single.price_cents) && (
                <span className="price-naira">{nairaHint(payConfig, single.price_cents)}, charged in naira</span>
              )}
              <ul className="pricing-features">
                <li>Pay as you go</li>
                <li>Custom lesson plan</li>
                <li>Free cancellation 12h+ before</li>
              </ul>
              <button className="btn btn-primary" onClick={() => go('/booking?type=single')}>
                Book a lesson
              </button>
            </div>
          )}
        </div>

        <h3 className="pricing-plans-title">Monthly plans</h3>
        <p className="section-sub pricing-plans-sub">
          Choose how many lessons a week and pick your own times.{' '}
          {autoRenew
            ? 'Renews monthly until you cancel. Unused lessons expire at the end of each month.'
            : 'Pay once for a month of lessons, with no automatic charges. Unused lessons expire after 30 days, and we remind you before they do.'}
        </p>
        {error && <p className="pricing-error" role="alert">{error}</p>}
        <div className="pricing-grid pricing-grid--plans">
          {plans.map((p) => {
            const perWeek = Math.round(p.lessons_per_month / 4)
            const perLesson = p.price_cents / p.lessons_per_month
            return (
              <div className={`pricing-card${perWeek === 3 ? ' featured' : ''}`} key={p.product_key}>
                {perWeek === 3 && <span className="featured-tag">Most Popular</span>}
                <h3>{perWeek}× a week</h3>
                <div className="price"><sup>$</sup>{dollars(p.price_cents)}</div>
                <p className="price-period">per month · {p.lessons_per_month} lessons</p>
                {nairaHint(payConfig, p.price_cents) && (
                  <span className="price-naira">{nairaHint(payConfig, p.price_cents)}, charged in naira</span>
                )}
                <ul className="pricing-features">
                  <li>${dollars(perLesson)} per lesson</li>
                  <li>Reschedule up to 12h before</li>
                  <li>{autoRenew ? 'Cancel anytime' : 'No automatic renewal'}</li>
                </ul>
                <button
                  className="btn btn-primary"
                  onClick={() => choosePlan(p)}
                  disabled={busy !== null}
                >
                  {busy === p.product_key ? 'Opening checkout…' : autoRenew ? 'Choose plan' : 'Buy this month'}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
