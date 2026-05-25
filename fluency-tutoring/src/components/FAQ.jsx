import { useState } from 'react'

const faqItems = [
  {
    question: 'What levels of German do you teach?',
    answer: 'I teach all levels from complete beginner (A0) to advanced (C2). Each lesson is tailored to your current proficiency level and learning goals, whether you\'re preparing for a certification exam or building conversational fluency.'
  },
  {
    question: 'How do online lessons work?',
    answer: 'Lessons take place via a built-in video call directly on this platform — no extra software needed. Simply log in, navigate to your lesson room at the scheduled time, and join the session. I provide all materials digitally during the lesson.'
  },
  {
    question: 'Can I reschedule or cancel a lesson?',
    answer: 'Yes! You can cancel or reschedule a lesson free of charge up to 24 hours before the scheduled start time. Cancellations within 24 hours of the lesson are non-refundable to respect the reserved time slot.'
  },
  {
    question: 'What teaching methods do you use?',
    answer: 'I use a communicative approach that prioritises real-world conversation from day one. Lessons combine structured grammar instruction, vocabulary building, listening exercises, and interactive speaking practice tailored to your interests and goals.'
  },
  {
    question: 'How long are the lessons and how often should I take them?',
    answer: 'Standard lessons are 60 minutes. For beginners, I recommend 2–3 sessions per week for steady progress. Intermediate and advanced learners often benefit from 1–2 sessions per week combined with self-study between lessons.'
  },
  {
    question: 'Do you help with exam preparation (Goethe, TestDaF, telc)?',
    answer: 'Absolutely. I have extensive experience preparing students for all major German language exams including Goethe-Zertifikat (A1–C2), TestDaF, and telc. Lessons include practice with exam formats, timed exercises, and targeted feedback.'
  }
]

export default function FAQ() {
  const [openIndex, setOpenIndex] = useState(null)

  function handleToggle(index) {
    setOpenIndex(prev => (prev === index ? null : index))
  }

  return (
    <section id="faq">
      <div className="container">
        <p className="section-label">FAQ</p>
        <h2 className="section-title">Frequently Asked Questions</h2>
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
