import React, { createContext, useContext, useState, useCallback } from 'react'
import { login as apiLogin } from '../api/client'

const STORAGE_KEY = 'moveoptimizer.session'

const AuthContext = createContext(null)

function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const user = JSON.parse(raw)
    // Only restore a usable session; drops stale id-only sessions from the
    // previous persona-based login.
    return user && user.id ? user : null
  } catch {
    return null
  }
}

function persist(user) {
  try {
    if (user) localStorage.setItem(STORAGE_KEY, JSON.stringify(user))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* storage unavailable — session simply won't persist */
  }
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(loadSession)

  const login = useCallback(async (identifier, password) => {
    const res = await apiLogin(identifier, password)
    if (res.ok) {
      setCurrentUser(res.user)
      persist(res.user)
    }
    return res
  }, [])

  const logout = useCallback(() => {
    setCurrentUser(null)
    persist(null)
  }, [])

  const value = { currentUser, login, logout }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
