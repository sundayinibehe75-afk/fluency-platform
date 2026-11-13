import { useEffect, useState } from 'react'
import api from './useApi'

/** Provider and naira rate, for showing "≈ ₦…" next to dollar prices. */
export function usePaymentConfig() {
  const [config, setConfig] = useState(null)
  useEffect(() => {
    api.get('/payments/config').then((res) => setConfig(res.data)).catch(() => {})
  }, [])
  return config
}

/** "≈ ₦15,000" for a dollar price in cents, or '' when not charged in naira. */
export function nairaHint(config, usdCents) {
  if (!config || config.charge_currency !== 'NGN' || !config.ngn_per_usd) return ''
  const naira = Math.round((usdCents / 100) * config.ngn_per_usd)
  return `≈ ₦${naira.toLocaleString('en-NG')}`
}
