import React, { createContext, useContext, useState, useCallback } from 'react'
import { PERSONAS, DEMO_PASSWORD, findPersonaByEmail, findPersonaById } from '../data/personas'

const STORAGE_KEY = 'moveoptimizer.session'

const AuthContext = createContext(null)

function loadSession() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const id = JSON.parse(raw)?.id
    return findPersonaById(id)
  } catch {
    return null
  }
}

function persist(persona) {
  try {
    if (persona) localStorage.setItem(STORAGE_KEY, JSON.stringify({ id: persona.id }))
    else localStorage.removeItem(STORAGE_KEY)
  } catch {
    /* storage unavailable — session simply won't persist */
  }
}

export function AuthProvider({ children }) {
  const [currentUser, setCurrentUser] = useState(loadSession)

  const loginAs = useCallback((personaId) => {
    const persona = findPersonaById(personaId)
    if (!persona) return { ok: false, error: 'Profile not found.' }
    setCurrentUser(persona)
    persist(persona)
    return { ok: true }
  }, [])

  const login = useCallback((email, password) => {
    const persona = findPersonaByEmail(email)
    if (!persona) return { ok: false, error: 'No account matches that email.' }
    if (password !== DEMO_PASSWORD) return { ok: false, error: 'Incorrect password. Try the demo password.' }
    setCurrentUser(persona)
    persist(persona)
    return { ok: true }
  }, [])

  const logout = useCallback(() => {
    setCurrentUser(null)
    persist(null)
  }, [])

  const value = { currentUser, login, loginAs, logout, personas: PERSONAS }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
