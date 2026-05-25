import { createContext, useState, useEffect, useContext } from 'react'
import { AuthContext } from './AuthContext'
import axios from 'axios'

export const NotificationContext = createContext(null)

export function NotificationProvider({ children }) {
  const { user } = useContext(AuthContext)
  const [unreadCount, setUnreadCount] = useState(0)

  useEffect(() => {
    if (!user) {
      setUnreadCount(0)
      return
    }

    let intervalId = null

    const fetchUnread = async () => {
      try {
        const token = localStorage.getItem('token')
        const res = await axios.get('/api/messages/threads', {
          headers: { Authorization: `Bearer ${token}` },
        })
        const threads = res.data
        const total = threads.reduce(
          (sum, thread) => sum + (thread.unread_count || 0),
          0
        )
        setUnreadCount(total)
      } catch {
        // Silently ignore polling errors
      }
    }

    fetchUnread()
    intervalId = setInterval(fetchUnread, 30000)

    return () => {
      if (intervalId) clearInterval(intervalId)
    }
  }, [user])

  return (
    <NotificationContext.Provider value={{ unreadCount }}>
      {children}
    </NotificationContext.Provider>
  )
}
