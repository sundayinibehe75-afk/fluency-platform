import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { getErrorMessage } from '../utils/errors'
import { nairaHint, usePaymentConfig } from '../hooks/usePaymentConfig'
import { useBackForwardReset } from '../hooks/useBackForwardReset'

// Shown if the prices can't be loaded; the server's /api/plans is the source of truth
const FALLBACK = [
  { product_key: 'single_session', price_cents: 1000, lessons_per_month: null, lesson_minutes: 60, is_plan: false },
  { product_key: 'plan_2x', price_cents: 7600, lessons_per_month: 8, lesson_minutes: 60, is_plan: true },
  { product_key: 'plan_3x', price_cents: 10800, lessons_per_month: 12, lesson_minutes: 60, is_plan: true },
  { product_key: 'plan_4x', price_cents: 14000, lessons_per_month: 16, lesson_minutes: 60, is_plan: true },
  { product_key: 'plan_5x', price_cents: 17000, lessons_per_month: 20, lesson_minutes: 60, is_plan: true },
  { product_key: 'single_session_30', price_cents: 600, lessons_per_month: null, lesson_minutes: 30, is_plan: false },
  { product_key: 'plan_2x_30', price_cents: 4600, lessons_per_month: 8, lesson_minutes: 30, is_plan: true },
  { product_key: 'plan_3x_30', price_cents: 6500, lessons_per_month: 12, lesson_minutes: 30, is_plan: true },
  { product_key: 'plan_4x_30', price_cents: 8400, lessons_per_month: 16, lesson_minutes: 30, is_plan: true },
  { product_key: 'plan_5x_30', price_cents: 10200, lessons_per_month: 20, lesson_minutes: 30, is_plan: true },
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
  useBackForwardReset(() => setBusy(null))
  // Paystack: the student chooses whether the plan renews. Stripe: always renews.
  const studentChooses = payConfig?.provider === 'paystack'
  const [renewChoice, setRenewChoice] = useState(false)
  const autoRenew = studentChooses ? renewChoice : payConfig ? payConfig.auto_renew : false

  useEffect(() => {
    api.get('/plans').then((res) => res.data?.length && setPrices(res.data)).catch(() => {})
  }, [])

  const [length, setLength] = useState(60)
  const ofLength = (p) => (p.lesson_minutes || 60) === length
  const single = prices.find((p) => !p.is_plan && ofLength(p))
  const plans = prices.filter((p) => p.is_plan && ofLength(p))

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
      const res = await api.post('/subscriptions/checkout', { product_key: plan.product_key, auto_renew: studentChooses && renewChoice })
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
          One-to-one lessons of 30 or 60 minutes. Start with a free 60-minute trial lesson.
        </p>

        <div className="pricing-length" role="group" aria-label="Lesson length">
          {[30, 60].map((m) => (
            <button
              key={m}
              type="button"
              className={`pricing-length-btn ${length === m ? 'selected' : ''}`}
              onClick={() => setLength(m)}
              aria-pressed={length === m}
            >
              {m}-minute lessons
            </button>
          ))}
        </div>

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
              <p className="price-period">per {length}-min lesson</p>
              {nairaHint(payConfig, single.price_cents) && (
                <span className="price-naira">{nairaHint(payConfig, single.price_cents)}, charged in naira</span>
              )}
              <ul className="pricing-features">
                <li>Pay as you go</li>
                <li>Custom lesson plan</li>
                <li>Free cancellation 12h+ before</li>
              </ul>
              <button className="btn btn-primary" onClick={() => go(`/booking?type=single&minutes=${length}`)}>
                Book a lesson
              </button>
            </div>
          )}
        </div>

        <h3 className="pricing-plans-title">Monthly plans</h3>
        <p className="section-sub pricing-plans-sub">
          Choose how many lessons a week and pick your own times.{' '}
          {studentChooses
            ? 'Pay for a month of lessons. Unused lessons expire after 30 days, and we remind you before they do.'
            : autoRenew
              ? 'Renews monthly until you cancel. Unused lessons expire at the end of each month.'
              : 'Pay once for a month of lessons, with no automatic charges. Unused lessons expire after 30 days, and we remind you before they do.'}
        </p>
        {studentChooses && (
          <label className="pricing-renew">
            <input type="checkbox" checked={renewChoice} onChange={(e) => setRenewChoice(e.target.checked)} />
            <span>
              <strong>Renew automatically each month</strong>
              <small>Your card is charged when the month ends. We email you 3 days before, and you can turn it off anytime in your dashboard.</small>
            </span>
          </label>
        )}
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
                <p className="price-period">per month · {p.lessons_per_month} × {length} min</p>
                {nairaHint(payConfig, p.price_cents) && (
                  <span className="price-naira">{nairaHint(payConfig, p.price_cents)}, charged in naira</span>
                )}
                <ul className="pricing-features">
                  <li>${dollars(perLesson)} per lesson</li>
                  <li>Reschedule up to 12h before</li>
                  <li>{autoRenew ? 'Renews monthly, cancel anytime' : 'No automatic renewal'}</li>
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
