/**
 * Format an amount in cents to a display currency string.
 * @param {number} cents - Amount in smallest currency unit (e.g. cents)
 * @param {string} [currency='USD'] - ISO 4217 currency code
 * @returns {string} Formatted currency string, e.g. "$45.00"
 */
export function formatCents(cents, currency = 'USD') {
  const amount = cents / 100
  return new Intl.NumberFormat(undefined, {
    style: 'currency',
    currency,
  }).format(amount)
}
