import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import api from '../../hooks/useApi'
import { getErrorMessage } from '../../utils/errors'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

/**
 * Students land here after paying. With Paystack the URL carries
 * ?reference=..., and we confirm the payment with the server straight away
 * (the webhook does the same; whichever comes first counts).
 */
export default function BookingSuccess() {
  const [params] = useSearchParams()
  const reference = params.get('reference') || params.get('trxref')
  const [state, setState] = useState(reference ? 'checking' : 'done')
  const [message, setMessage] = useState('')

  useEffect(() => {
    if (!reference) return
    api
      .get(`/payments/paystack/verify?reference=${encodeURIComponent(reference)}`)
      .then((res) => setState(res.data.status === 'success' ? 'done' : 'failed'))
      .catch((err) => {
        setMessage(getErrorMessage(err, 'We could not confirm your payment yet.'))
        setState('failed')
      })
  }, [reference])

  const ok = state === 'done'
  return (
    <>
      <Nav />
      <section style={{ paddingTop: '7rem', textAlign: 'center' }}>
        <div className="container">
          <div className={`payment-result ${ok ? 'payment-result--ok' : state === 'failed' ? 'payment-result--bad' : ''}`}>
            {state === 'checking' && (
              <>
                <div className="payment-result-icon">⏳</div>
                <h1 className="section-title">Confirming your payment…</h1>
              </>
            )}
            {ok && (
              <>
                <div className="payment-result-icon">✓</div>
                <h1 className="section-title" style={{ color: '#16a34a' }}>Your lesson is confirmed!</h1>
                <p>You will receive a confirmation email with the lesson details shortly.</p>
              </>
            )}
            {state === 'failed' && (
              <>
                <div className="payment-result-icon">!</div>
                <h1 className="section-title" style={{ color: '#b91c1c' }}>Payment not confirmed</h1>
                <p>
                  {message || 'The payment did not go through.'} If money left your account, don't
                  pay again: it can take a few minutes to arrive. Check your dashboard shortly or
                  send us a message.
                </p>
              </>
            )}
            <Link to="/dashboard" className="btn btn-primary" style={{ display: 'inline-block', marginTop: '2rem' }}>
              Go to Dashboard
            </Link>
          </div>
        </div>
      </section>
      <Footer />
    </>
  )
}
