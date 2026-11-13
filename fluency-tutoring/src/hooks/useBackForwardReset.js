import { useEffect } from 'react'

/**
 * Run `reset` when the browser shows this page again from its back/forward
 * cache, e.g. the student went to the payment page and pressed Back. Without
 * this the page comes back frozen exactly as it was left ("Opening
 * checkout...") and its buttons stay disabled.
 */
export function useBackForwardReset(reset) {
  useEffect(() => {
    function onPageShow(event) {
      if (event.persisted) reset()
    }
    window.addEventListener('pageshow', onPageShow)
    return () => window.removeEventListener('pageshow', onPageShow)
  }, [])
}
