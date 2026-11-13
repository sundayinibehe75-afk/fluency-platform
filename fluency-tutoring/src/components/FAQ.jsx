import { useState } from 'react'
import { useT } from '../i18n/LanguageContext'

// Questions and answers live in src/i18n/strings.js (faq.q1 … faq.a7)
const FAQ_COUNT = 7

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState(null)
  const { t } = useT()
  const faqItems = Array.from({ length: FAQ_COUNT }, (_, i) => ({
    question: t(`faq.q${i + 1}`),
    answer: t(`faq.a${i + 1}`),
  }))

  function handleToggle(index) {
    setOpenIndex(prev => (prev === index ? null : index))
  }

  return (
    <section id="faq">
      <div className="container">
        <p className="section-label">{t('faq.label')}</p>
        <h2 className="section-title">{t('faq.title')}</h2>
        <div className="faq-accordion">
          {faqItems.map((item, index) => (
            <div
              key={index}
              className={`faq-item${openIndex === index ? ' faq-item--open' : ''}`}
            >
              <button
                className="faq-question"
                onClick={() => handleToggle(index)}
                aria-expanded={openIndex === index}
                aria-controls={`faq-answer-${index}`}
                id={`faq-question-${index}`}
              >
                <span>{item.question}</span>
                <span className="faq-icon">{openIndex === index ? '−' : '+'}</span>
              </button>
              <div
                id={`faq-answer-${index}`}
                className="faq-answer"
                role="region"
                aria-labelledby={`faq-question-${index}`}
              >
                <p>{item.answer}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
