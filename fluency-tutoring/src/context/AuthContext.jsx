import { createContext, useState, useEffect, useCallback } from 'react'
import axios from 'axios'

export const AuthContext = createContext(null)

function decodeJwtPayload(token) {
  try {
    const base64Url = token.split('.')[1]
    const base64 = base64Url.replace(/-/g, '+').replace(/_/g, '/')
    const jsonPayload = decodeURIComponent(
      atob(base64)
        .split('')
        .map((c) => '%' + ('00' + c.charCodeAt(0).toString(16)).slice(-2))
        .join('')
    )
    return JSON.parse(jsonPayload)
  } catch {
    return null
  }
}

function validStoredToken() {
  try {
    const stored = localStorage.getItem('token')
    if (!stored) return null
    const decoded = decodeJwtPayload(stored)
    if (decoded && decoded.exp && decoded.exp * 1000 > Date.now()) return stored
    localStorage.removeItem('token') // invalid or expired
  } catch {
    // storage unavailable
  }
  return null
}

export function AuthProvider({ children }) {
  // Read the saved login synchronously, so pages that need a user don't
  // redirect away on the first render after a page refresh.
  const [token, setToken] = useState(() => validStoredToken())
  const [user, setUser] = useState(() => (token ? decodeJwtPayload(token) : null))

  const login = useCallback((newToken) => {
    localStorage.setItem('token', newToken)
    const decoded = decodeJwtPayload(newToken)
    setToken(newToken)
    setUser(decoded)
  }, [])

  const logout = useCallback(async () => {
    try {
      const currentToken = localStorage.getItem('token')
      if (currentToken) {
        await axios.post('/api/auth/logout', null, {
          headers: { Authorization: `Bearer ${currentToken}` },
        })
      }
    } catch {
      // Ignore errors during logout request
    } finally {
      localStorage.removeItem('token')
      setToken(null)
      setUser(null)
    }
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}
