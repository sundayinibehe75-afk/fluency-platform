import { useState, useEffect, useRef, useCallback } from 'react'
import { Navigate } from 'react-router-dom'
import { useAuth } from '../../hooks/useAuth'
import { useApi } from '../../hooks/useApi'
import { formatDate } from '../../utils/dateUtils'
import Nav from '../../components/Nav'
import Footer from '../../components/Footer'

export default function Inbox() {
  const { user } = useAuth()
  const api = useApi()

  const [threads, setThreads] = useState([])
  const [threadsLoading, setThreadsLoading] = useState(true)
  const [selectedThread, setSelectedThread] = useState(null)
  const [messages, setMessages] = useState([])
  const [messagesLoading, setMessagesLoading] = useState(false)
  const [page, setPage] = useState(1)
  const [hasMore, setHasMore] = useState(false)
  const [messageBody, setMessageBody] = useState('')
  const [sending, setSending] = useState(false)
  const [error, setError] = useState(null)

  const messagesEndRef = useRef(null)

  // Fetch threads
  useEffect(() => {
    if (user) {
      fetchThreads()
    }
  }, [user])

  async function fetchThreads() {
    try {
      setThreadsLoading(true)
      const response = await api.get('/messages/threads')
      setThreads(response.data)
    } catch (err) {
      console.error('Failed to fetch threads:', err)
      setError('Failed to load message threads.')
    } finally {
      setThreadsLoading(false)
    }
  }

  // Fetch messages for a thread
  const fetchMessages = useCallback(async (userId, pageNum = 1, append = false) => {
    try {
      setMessagesLoading(true)
      const response = await api.get(`/messages/threads/${userId}?page=${pageNum}`)
      const data = response.data

      if (append) {
        setMessages((prev) => [...data, ...prev])
      } else {
        setMessages(data)
      }

      // If we got 50 messages, there might be more
      setHasMore(data.length === 50)
    } catch (err) {
      console.error('Failed to fetch messages:', err)
      setError('Failed to load messages.')
    } finally {
      setMessagesLoading(false)
    }
  }, [api])

  // Select a thread
  function handleSelectThread(thread) {
    setSelectedThread(thread)
    setPage(1)
    setMessages([])
    setHasMore(false)
    setError(null)
    fetchMessages(thread.other_user_id, 1)

    // Update unread count locally
    setThreads((prev) =>
      prev.map((t) =>
        t.other_user_id === thread.other_user_id
          ? { ...t, unread_count: 0 }
          : t
      )
    )
  }

  // Load more (older) messages
  function handleLoadMore() {
    if (selectedThread && hasMore) {
      const nextPage = page + 1
      setPage(nextPage)
      fetchMessages(selectedThread.other_user_id, nextPage, true)
    }
  }

  // Send a message
  async function handleSend(e) {
    e.preventDefault()
    if (!messageBody.trim() || !selectedThread || sending) return

    try {
      setSending(true)
      setError(null)
      const response = await api.post('/messages', {
        recipient_id: selectedThread.other_user_id,
        body: messageBody.trim(),
      })

      setMessages((prev) => [...prev, response.data])
      setMessageBody('')

      // Update thread preview
      setThreads((prev) =>
        prev.map((t) =>
          t.other_user_id === selectedThread.other_user_id
            ? {
                ...t,
                last_message_preview: messageBody.trim().slice(0, 100),
                last_message_at: response.data.sent_at,
              }
            : t
        )
      )

      // Scroll to bottom
      setTimeout(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      }, 100)
    } catch (err) {
      console.error('Failed to send message:', err)
      if (err.response?.status === 403) {
        setError('You can only message your assigned tutor.')
      } else {
        setError('Failed to send message. Please try again.')
      }
    } finally {
      setSending(false)
    }
  }

  // Scroll to bottom when messages load
  useEffect(() => {
    if (messages.length > 0 && page === 1) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
    }
  }, [messages, page])

  if (!user) {
    return <Navigate to="/login" replace />
  }

  function formatThreadTime(isoString) {
    const date = new Date(isoString)
    const now = new Date()
    const diffMs = now - date
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24))

    if (diffDays === 0) {
      return date.toLocaleTimeString(undefined, { hour: '2-digit', minute: '2-digit' })
    } else if (diffDays === 1) {
      return 'Yesterday'
    } else if (diffDays < 7) {
      return date.toLocaleDateString(undefined, { weekday: 'short' })
    }
    return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
  }

  return (
    <>
      <Nav />
      <main className="inbox-page">
        <div className="inbox-container">
          <h1 className="section-title inbox-title">Messages</h1>

          {error && (
            <div className="inbox-error" role="alert">
              {error}
            </div>
          )}

          <div className="inbox-split">
            {/* Thread List Panel */}
            <aside className="inbox-threads" aria-label="Message threads">
              {threadsLoading ? (
                <div className="inbox-loading">
                  <div className="loading-spinner" aria-label="Loading threads"></div>
                  <p>Loading threads...</p>
                </div>
              ) : threads.length === 0 ? (
                <div className="inbox-empty">
                  <p>No messages yet.</p>
                </div>
              ) : (
                <ul className="thread-list">
                  {threads.map((thread) => (
                    <li key={thread.other_user_id}>
                      <button
                        className={`thread-item ${
                          selectedThread?.other_user_id === thread.other_user_id
                            ? 'thread-item--active'
                            : ''
                        }`}
                        onClick={() => handleSelectThread(thread)}
                        aria-label={`Thread with ${thread.other_user_name}${
                          thread.unread_count > 0
                            ? `, ${thread.unread_count} unread`
                            : ''
                        }`}
                      >
                        <div className="thread-item-header">
                          <span className="thread-item-name">
                            {thread.other_user_name}
                          </span>
                          <span className="thread-item-time">
                            {formatThreadTime(thread.last_message_at)}
                          </span>
                        </div>
                        <div className="thread-item-body">
                          <span className="thread-item-preview">
                            {thread.last_message_preview}
                          </span>
                          {thread.unread_count > 0 && (
                            <span className="thread-item-badge" aria-label={`${thread.unread_count} unread messages`}>
                              {thread.unread_count}
                            </span>
                          )}
                        </div>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </aside>

            {/* Message View Panel */}
            <section className="inbox-messages" aria-label="Message conversation">
              {!selectedThread ? (
                <div className="inbox-placeholder">
                  <p>Select a conversation to view messages</p>
                </div>
              ) : (
                <>
                  <div className="inbox-messages-header">
                    <h2 className="inbox-messages-title">
                      {selectedThread.other_user_name}
                    </h2>
                  </div>

                  <div className="inbox-messages-list">
                    {messagesLoading && messages.length === 0 ? (
                      <div className="inbox-loading">
                        <div className="loading-spinner" aria-label="Loading messages"></div>
                        <p>Loading messages...</p>
                      </div>
                    ) : (
                      <>
                        {hasMore && (
                          <div className="inbox-load-more">
                            <button
                              onClick={handleLoadMore}
                              disabled={messagesLoading}
                              className="btn-load-more"
                            >
                              {messagesLoading ? 'Loading...' : 'Load older messages'}
                            </button>
                          </div>
                        )}

                        {messages.map((msg) => (
                          <div
                            key={msg.id}
                            className={`message-bubble ${
                              msg.sender_id === user.id
                                ? 'message-bubble--sent'
                                : 'message-bubble--received'
                            }`}
                          >
                            <div className="message-bubble-body">{msg.body}</div>
                            <div className="message-bubble-meta">
                              <span className="message-bubble-time">
                                {formatDate(msg.sent_at)}
                              </span>
                              {msg.sender_id === user.id && msg.is_read && (
                                <span className="message-bubble-read" aria-label="Read">✓</span>
                              )}
                            </div>
                          </div>
                        ))}

                        <div ref={messagesEndRef} />
                      </>
                    )}
                  </div>

                  <form className="inbox-send-form" onSubmit={handleSend}>
                    <label htmlFor="message-input" className="visually-hidden">
                      Type a message
                    </label>
                    <textarea
                      id="message-input"
                      className="inbox-send-textarea"
                      value={messageBody}
                      onChange={(e) => setMessageBody(e.target.value)}
                      placeholder="Type a message..."
                      maxLength={5000}
                      rows={2}
                      disabled={sending}
                      aria-label="Message text"
                    />
                    <button
                      type="submit"
                      className="inbox-send-btn"
                      disabled={!messageBody.trim() || sending}
                      aria-label="Send message"
                    >
                      {sending ? 'Sending...' : 'Send'}
                    </button>
                  </form>
                </>
              )}
            </section>
          </div>
        </div>
      </main>
      <Footer />
    </>
  )
}
