import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import api from '../hooks/useApi'
import { useAuth } from '../hooks/useAuth'
import { getErrorMessage } from '../utils/errors'
import { nairaHint, usePaymentConfig } from '../hooks/usePaymentConfig'
import { useBackForwardReset } from '../hooks/useBackForwardReset'
import { useT } from '../i18n/LanguageContext'

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
  const { t } = useT()
  const naira = (cents) => nairaHint(payConfig, cents) && t('pricing.naira', { amount: nairaHint(payConfig, cents) })
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
    if (user.role !== 'student') return setError(t('pricing.err.studentOnly'))
    try {
      setBusy(plan.product_key)
      const res = await api.post('/subscriptions/checkout', { product_key: plan.product_key, auto_renew: studentChooses && renewChoice })
      window.location.href = res.data.session_url
    } catch (err) {
      setError(getErrorMessage(err, t('pricing.err.checkout')))
      setBusy(null)
    }
  }

  return (
    <section id="pricing">
      <div className="container">
        <p className="section-label">{t('pricing.label')}</p>
        <h2 className="section-title">{t('pricing.title')}</h2>
        <p className="section-sub">{t('pricing.sub')}</p>

        <div className="pricing-length" role="group" aria-label={t('pricing.lengthGroup')}>
          {[30, 60].map((m) => (
            <button
              key={m}
              type="button"
              className={`pricing-length-btn ${length === m ? 'selected' : ''}`}
              onClick={() => setLength(m)}
              aria-pressed={length === m}
            >
              {t('pricing.lengthButton', { m })}
            </button>
          ))}
        </div>

        <div className="pricing-grid">
          <div className="pricing-card">
            <h3>{t('pricing.trial.title')}</h3>
            <div className="price"><sup>$</sup>0</div>
            <p className="price-period">{t('pricing.trial.period')}</p>
            <ul className="pricing-features">
              <li>{t('pricing.trial.f1')}</li>
              <li>{t('pricing.trial.f2')}</li>
              <li>{t('pricing.trial.f3')}</li>
            </ul>
            <button className="btn btn-primary" onClick={() => go('/booking?type=trial')}>
              {t('pricing.trial.cta')}
            </button>
          </div>

          {single && (
            <div className="pricing-card">
              <h3>{t('pricing.single.title')}</h3>
              <div className="price"><sup>$</sup>{dollars(single.price_cents)}</div>
              <p className="price-period">{t('pricing.single.period', { m: length })}</p>
              {naira(single.price_cents) && <span className="price-naira">{naira(single.price_cents)}</span>}
              <ul className="pricing-features">
                <li>{t('pricing.single.f1')}</li>
                <li>{t('pricing.single.f2')}</li>
                <li>{t('pricing.single.f3')}</li>
              </ul>
              <button className="btn btn-primary" onClick={() => go(`/booking?type=single&minutes=${length}`)}>
                {t('pricing.single.cta')}
              </button>
            </div>
          )}
        </div>

        <h3 className="pricing-plans-title">{t('pricing.plans.title')}</h3>
        <p className="section-sub pricing-plans-sub">
          {t('pricing.plans.intro')}{' '}
          {t(studentChooses ? 'pricing.plans.choose' : autoRenew ? 'pricing.plans.renews' : 'pricing.plans.once')}
        </p>
        {studentChooses && (
          <label className="pricing-renew">
            <input type="checkbox" checked={renewChoice} onChange={(e) => setRenewChoice(e.target.checked)} />
            <span>
              <strong>{t('pricing.renew.title')}</strong>
              <small>{t('pricing.renew.note')}</small>
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
                {perWeek === 3 && <span className="featured-tag">{t('pricing.popular')}</span>}
                <h3>{t('pricing.plan.perWeek', { n: perWeek })}</h3>
                <div className="price"><sup>$</sup>{dollars(p.price_cents)}</div>
                <p className="price-period">{t('pricing.plan.period', { n: p.lessons_per_month, m: length })}</p>
                {naira(p.price_cents) && <span className="price-naira">{naira(p.price_cents)}</span>}
                <ul className="pricing-features">
                  <li>{t('pricing.plan.perLesson', { price: `$${dollars(perLesson)}` })}</li>
                  <li>{t('pricing.plan.reschedule')}</li>
                  <li>{t(autoRenew ? 'pricing.plan.renews' : 'pricing.plan.noRenew')}</li>
                </ul>
                <button
                  className="btn btn-primary"
                  onClick={() => choosePlan(p)}
                  disabled={busy !== null}
                >
                  {t(busy === p.product_key ? 'pricing.plan.opening' : autoRenew ? 'pricing.plan.choose' : 'pricing.plan.buy')}
                </button>
              </div>
            )
          })}
        </div>
      </div>
    </section>
  )
}
