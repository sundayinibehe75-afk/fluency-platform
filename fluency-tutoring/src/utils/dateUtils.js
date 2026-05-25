/**
 * Convert a UTC ISO 8601 string to a Date in the user's local timezone.
 * @param {string} utcIsoString - ISO 8601 UTC datetime string
 * @returns {Date} Date object in local time
 */
export function toLocalTime(utcIsoString) {
  return new Date(utcIsoString)
}

/**
 * Format a UTC ISO 8601 string as a human-readable local date/time string.
 * @param {string} utcIsoString - ISO 8601 UTC datetime string
 * @returns {string} Formatted date string in user's locale
 */
export function formatDate(utcIsoString) {
  const date = new Date(utcIsoString)
  return date.toLocaleString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  })
}
