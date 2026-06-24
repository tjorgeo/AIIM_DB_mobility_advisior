import React, { useState } from 'react'
import { ArrowRight, Wallet, Leaf, Route, AlertCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'

const FEATURES = [
  { icon: Wallet, text: 'See exactly what your mobility costs — and where it leaks.' },
  { icon: Route, text: 'Get a personalized plan tuned to how you actually travel.' },
  { icon: Leaf, text: 'Cut spend and CO₂ in a single, clear recommendation.' },
]

export default function Login() {
  const { login } = useAuth()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    const res = await login(identifier, password)
    setSubmitting(false)
    if (!res.ok) setError(res.error)
  }

  return (
    <div className="login">
      <aside className="login__brand">
        <div className="brand-mark brand-mark--invert">DB</div>

        <div>
          <h1 className="login__headline">Smarter mobility, less spend.</h1>
          <p className="login__tagline">
            MoveOptimizer is your personal advisor for Deutsche Bahn travel — it studies your
            journeys and finds the subscription mix that saves you the most.
          </p>
        </div>

        <ul className="login__features">
          {FEATURES.map(({ icon: Icon, text }, i) => (
            <li className="login__feature" key={i}>
              <span className="login__feature-ico"><Icon size={18} /></span>
              <span>{text}</span>
            </li>
          ))}
        </ul>
      </aside>

      <main className="login__panel">
        <div className="login__card">
          <h2 className="login__title">Welcome back</h2>
          <p className="login__subtitle">Sign in to see your personalized mobility plan.</p>

          <form className="login__form" onSubmit={handleSubmit} noValidate>
            <div className="field">
              <label className="field__label" htmlFor="identifier">Username or email</label>
              <input
                id="identifier"
                className="field__input"
                type="text"
                autoComplete="username"
                placeholder="your username or you@dbmove.de"
                value={identifier}
                onChange={(e) => { setIdentifier(e.target.value); setError('') }}
              />
            </div>

            <div className="field">
              <label className="field__label" htmlFor="password">Password</label>
              <input
                id="password"
                className="field__input"
                type="password"
                autoComplete="current-password"
                placeholder="••••••••"
                value={password}
                onChange={(e) => { setPassword(e.target.value); setError('') }}
              />
            </div>

            {error && (
              <div className="login__error" role="alert">
                <AlertCircle size={16} />
                <span>{error}</span>
              </div>
            )}

            <button className="btn btn--primary btn--block" type="submit" disabled={submitting}>
              {submitting ? 'Signing in…' : <>Sign in <ArrowRight size={16} /></>}
            </button>

            <p className="login__hint">
              Demo access — sign in with your username or email and the shared
              password <code>mobility</code>.
            </p>
          </form>
        </div>
      </main>
    </div>
  )
}
