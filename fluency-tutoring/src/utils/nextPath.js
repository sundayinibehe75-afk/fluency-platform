/** Where to go after login/register: a ?next=/path on the current URL, if safe. */
export function nextPath(fallback) {
  const next = new URLSearchParams(window.location.search).get('next')
  return next && next.startsWith('/') && !next.startsWith('//') ? next : fallback
}
