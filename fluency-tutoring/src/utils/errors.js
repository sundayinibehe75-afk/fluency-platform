/**
 * Turn an API error into a message that is safe to show on the page.
 *
 * The backend returns errors in a few shapes:
 *   { detail: "text" }                          — plain message
 *   { detail: { error: "CODE", detail: "text" } } — most app errors
 *   { detail: [{ msg: "text", loc: [...] }] }    — validation errors (422)
 * Rendering the object or array directly would crash React and leave a
 * blank page, so always pass errors through this helper.
 */
export function getErrorMessage(err, fallback = 'Something went wrong. Please try again.') {
  const data = err?.response?.data
  if (!data) return fallback
  const detail = data.detail
  if (typeof detail === 'string') return detail
  if (detail && typeof detail.detail === 'string') return detail.detail
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d) => (typeof d?.msg === 'string' ? d.msg.replace(/^Value error, /, '') : null))
      .filter(Boolean)
      .join(' ') || fallback
  }
  if (typeof data === 'string' && data.length < 200) return data
  return fallback
}
