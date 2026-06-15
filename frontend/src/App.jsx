import React from 'react'
import { useAuth } from './context/AuthContext.jsx'
import Login from './pages/Login.jsx'
import Dashboard from './pages/Dashboard.jsx'

export default function App() {
  const { currentUser } = useAuth()

  // Keying on the auth state remounts the active view, so each one fades in
  // (CSS `viewIn`) — a smooth hand-off from sign-in into the dashboard.
  return (
    <div className="app-view" key={currentUser ? `dash-${currentUser.id}` : 'login'}>
      {currentUser ? <Dashboard /> : <Login />}
    </div>
  )
}
