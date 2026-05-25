import { useContext } from 'react'
import { NotificationContext } from '../context/NotificationContext'

export function useUnreadCount() {
  const context = useContext(NotificationContext)
  if (!context) {
    throw new Error('useUnreadCount must be used within a NotificationProvider')
  }
  return context.unreadCount
}
