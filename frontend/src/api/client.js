// Thin wrappers around the backend contract (proxied via vite to :8000).
// All UI-facing failures are surfaced as thrown errors so callers can render
// graceful states — no console logging in the consumer app.

async function parseJson(res, context) {
  if (!res.ok) {
    const err = new Error(`${context} failed (${res.status})`)
    err.status = res.status
    throw err
  }
  return res.json()
}

export async function getPersonas() {
  const res = await fetch('/api/personas')
  return parseJson(res, 'Loading profiles')
}

// Authenticate against the real database users. Unlike the other helpers this
// resolves (rather than throws) on a 401 so the sign-in form can show the
// backend's message inline.
export async function login(identifier, password) {
  const res = await fetch('/api/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ identifier, password }),
  })
  if (res.ok) return { ok: true, user: await res.json() }
  let error = `Sign in failed (${res.status})`
  try {
    const body = await res.json()
    if (body?.detail) error = body.detail
  } catch {
    /* non-JSON error body — keep the generic message */
  }
  return { ok: false, error }
}

export async function analyze(userId) {
  const res = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId }),
  })
  return parseJson(res, 'Analysis')
}

export async function approve(sessionId, scenarioId) {
  const res = await fetch(`/api/recommendations/${sessionId}/approve`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario_id: scenarioId }),
  })
  return parseJson(res, 'Approval')
}

// Optional endpoint owned by the backend team. Until it exists this throws,
// and the chat widget falls back to its scripted assistant.
export async function chat(userId, messages) {
  const res = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, messages }),
  })
  return parseJson(res, 'Chat')
}
