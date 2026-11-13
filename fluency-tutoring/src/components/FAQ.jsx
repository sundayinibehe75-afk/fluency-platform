import { useState } from 'react'

const faqItems = [
  {
    question: 'What levels of German do you teach?',
    answer: 'I teach from complete beginner (A0) up to upper intermediate (B2). Each lesson is tailored to your current proficiency level and learning goals, whether you\'re preparing for a certification exam or building conversational fluency.'
  },
  {
    question: 'How do online lessons work?',
    answer: 'Lessons happen in the video classroom on this site, so there is nothing to install. Your Join button appears on your dashboard 10 minutes before the lesson. The classroom has screen sharing, a full-screen view and a chat beside the video, and after the lesson you will find your notes and homework under My Notes.'
  },
  {
    question: 'Can I reschedule or cancel a lesson?',
    answer: 'Yes. You can reschedule or cancel from your dashboard up to 12 hours before the lesson starts: a paid lesson is refunded in full, a plan lesson goes back to your plan, and a free trial can be booked again. With less than 12 hours\' notice the lesson counts as taken, because that time was kept for you.'
  },
  {
    question: 'What teaching methods do you use?',
    answer: 'I use a communicative approach that prioritises real-world conversation from day one. Lessons combine structured grammar instruction, vocabulary building, listening exercises, and interactive speaking practice tailored to your interests and goals.'
  },
  {
    question: 'How long are the lessons and how often should I take them?',
    answer: 'Lessons are 30 or 60 minutes: 30 minutes suits busy schedules and conversation practice, 60 minutes gives time for grammar and deeper work. For beginners, I recommend 2–3 sessions per week for steady progress. Intermediate learners often benefit from 1–2 sessions per week combined with self-study between lessons.'
  },
  {
    question: 'How do I pay, and do plans renew automatically?',
    answer: 'You pay securely by card through Paystack. Prices are in US dollars and charged in naira at the day\'s exchange rate; your bank converts it to your own currency. Monthly plans give you a month of lessons, valid for 30 days. They only renew if you tick "Renew automatically", and then you get an email 3 days before each renewal and can turn it off anytime in your dashboard.'
  },
  {
    question: 'Do you help with exam preparation (Goethe, telc)?',
    answer: 'Yes. I prepare students for the Goethe-Zertifikat and telc exams from A1 to B2. Lessons include practice with the exam format, timed exercises and targeted feedback on your writing and speaking.'
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
