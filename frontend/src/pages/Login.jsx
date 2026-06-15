import React, { useState } from 'react'
import { ArrowRight, Wallet, Leaf, Route, AlertCircle } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { DEMO_PASSWORD } from '../data/personas'

const FEATURES = [
  { icon: Wallet, text: 'See exactly what your mobility costs — and where it leaks.' },
  { icon: Route, text: 'Get a personalized plan tuned to how you actually travel.' },
  { icon: Leaf, text: 'Cut spend and CO₂ in a single, clear recommendation.' },
]

export default function Login() {
  const { login, loginAs, personas } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')

  const handleSubmit = (e) => {
    e.preventDefault()
    const res = login(email, password)
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
              <label className="field__label" htmlFor="email">Email</label>
              <input
                id="email"
                className="field__input"
                type="email"
                autoComplete="username"
                placeholder="you@dbmove.de"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setError('') }}
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

            <button className="btn btn--primary btn--block" type="submit">
              Sign in <ArrowRight size={16} />
            </button>

            <p className="login__hint">
              Demo access — password <code>{DEMO_PASSWORD}</code> for any profile below.
            </p>
          </form>

          <div className="login__divider">or jump straight in</div>

          <div className="demo__grid">
            {personas.map((p) => (
              <button
                key={p.id}
                type="button"
                className="demo-persona"
                onClick={() => loginAs(p.id)}
              >
                <span className="avatar">{p.initials}</span>
                <span>
                  <span className="demo-persona__name">{p.name}</span><br />
                  <span className="demo-persona__role">{p.tagline}</span>
                </span>
                <ArrowRight className="demo-persona__go" size={18} />
              </button>
            ))}
          </div>
        </div>
      </main>
    </div>
  )
}
