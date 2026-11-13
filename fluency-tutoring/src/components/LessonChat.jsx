import { useEffect, useRef, useState } from 'react'
import { useApi } from '../hooks/useApi'
import { getErrorMessage } from '../utils/errors'

const POLL_MS = 4000

/**
 * Chat beside the video. It is the same conversation as the Messages page,
 * so everything written during the lesson stays there afterwards.
 */
export default function LessonChat({ otherUserId, otherName, myId, open, onUnread }) {
  const api = useApi()
  const [messages, setMessages] = useState([])
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState('')
  const listRef = useRef(null)
  const seenRef = useRef(0)

  async function load() {
    if (!otherUserId) return
    try {
      const res = await api.get(`/messages/threads/${otherUserId}?latest=true`)
      setMessages(res.data)
    } catch {
      // keep the last messages; the next poll tries again
    }
  }

  useEffect(() => {
    load()
    const id = setInterval(load, POLL_MS)
    return () => clearInterval(id)
  }, [otherUserId])

  // Unread count while the panel is closed
  useEffect(() => {
    const fromOther = messages.filter((m) => m.sender_id !== myId).length
    if (open) {
      seenRef.current = fromOther
      onUnread?.(0)
    } else {
      onUnread?.(Math.max(0, fromOther - seenRef.current))
    }
  }, [messages, open])

  // Keep the newest message in view
  useEffect(() => {
    if (open && listRef.current) listRef.current.scrollTop = listRef.current.scrollHeight
  }, [messages, open])

  async function send(e) {
    e.preventDefault()
    const body = text.trim()
    if (!body || !otherUserId) return
    setSending(true)
    setError('')
    try {
      const res = await api.post('/messages', { recipient_id: otherUserId, body })
      setMessages((prev) => [...prev, res.data])
      setText('')
    } catch (err) {
      setError(getErrorMessage(err, 'Message not sent. Please try again.'))
    } finally {
      setSending(false)
    }
  }

  if (!open) return null

  return (
    <aside className="lesson-chat" aria-label="Lesson chat">
      <div className="lesson-chat-head">
        Chat with {otherName || '…'}
        <small>Saved in Messages after the lesson</small>
      </div>
      <div className="lesson-chat-list" ref={listRef}>
        {messages.length === 0 ? (
          <p className="lesson-chat-empty">No messages yet. Say hallo! 👋</p>
        ) : (
          messages.map((m) => (
            <div key={m.id} className={`lesson-chat-msg ${m.sender_id === myId ? 'mine' : 'theirs'}`}>
              <span>{m.body}</span>
              <time>
                {new Date(m.sent_at).toLocaleTimeString(undefined, { hour: 'numeric', minute: '2-digit' })}
              </time>
            </div>
          ))
        )}
      </div>
      {error && <p className="lesson-chat-error">{error}</p>}
      <form className="lesson-chat-form" onSubmit={send}>
        <input
          type="text"
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Write a message…"
          maxLength={5000}
          aria-label="Message"
        />
        <button type="submit" disabled={sending || !text.trim()}>Send</button>
      </form>
    </aside>
  )
}
