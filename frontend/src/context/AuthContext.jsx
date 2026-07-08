import React, { createContext, useContext, useState, useCallback, useEffect } from 'react'
import { login as apiLogin, getPersonas } from '../api/client'

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

  // Setzt die Session direkt aus einem User-Objekt (z. B. nach der Registrierung),
  // ohne erneuten Login-Roundtrip.
  const setSession = useCallback((user) => {
    if (!user || !user.id) return
    setCurrentUser(user)
    persist(user)
  }, [])

  // Demo-Personas aus der DB laden (die 6 Seed-User mit echten Daten). Registrierte
  // User (user_id beginnt mit "user_") werden ausgefiltert.
  const [personas, setPersonas] = useState([])
  useEffect(() => {
    let cancelled = false
    getPersonas()
      .then((rows) => {
        if (cancelled || !Array.isArray(rows)) return
        const demo = rows
          .filter((p) => p.user_id && !p.user_id.startsWith('user_'))
          .map((p) => {
            const first = p.first_name || ''
            const last = p.last_name || ''
            const initials = `${first[0] || ''}${last[0] || ''}`.toUpperCase() || 'U'
            const occ = p.preferences?.occupation
            const tagline = [occ, p.home_city].filter(Boolean).join(' · ') || p.home_city || ''
            return { id: p.user_id, name: p.name || `${first} ${last}`.trim(), firstName: first, initials, tagline }
          })
        setPersonas(demo)
      })
      .catch(() => { /* Personas optional — der Formular-Login bleibt möglich */ })
    return () => { cancelled = true }
  }, [])

  // Direkt als Demo-Persona einloggen (kein Passwort nötig).
  const loginAs = useCallback((personaId) => {
    const p = personas.find((x) => x.id === personaId)
    if (!p) return
    const user = { id: p.id, name: p.name, firstName: p.firstName, initials: p.initials }
    setCurrentUser(user)
    persist(user)
  }, [personas])

  const value = { currentUser, login, logout, setSession, personas, loginAs }
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}