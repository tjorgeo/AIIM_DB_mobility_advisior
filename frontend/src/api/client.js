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

// Creates the essential account. The contract remains backwards-compatible with
// callers that also include onboarding data, but the current UI deliberately sends
// an empty onboarding first and offers the optional completion afterwards.
export async function submitOnboarding(profile) {
  let res
  try {
    res = await fetch('/api/register', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(profile),
    })
  } catch {
    return { ok: false, error: 'Keine Verbindung zum Server.' }
  }
  if (res.ok) return { ok: true, data: await res.json().catch(() => ({})) }
  let error = `Registrierung fehlgeschlagen (${res.status})`
  try {
    const body = await res.json()
    if (body?.detail) error = body.detail
  } catch {
    /* non-JSON error body — keep the generic message */
  }
  return { ok: false, error }
}

// Completes the optional mobility onboarding after the essential account has
// already been created. This route may also create the user's initial subscription
// holdings; later profile edits keep those holdings read-only.
export async function completeOnboarding(userId, profile) {
  const res = await fetch(`/api/onboarding/${encodeURIComponent(userId)}/complete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  if (res.ok) return { ok: true, data: await res.json() }
  let error = `Onboarding konnte nicht gespeichert werden (${res.status})`
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') error = body.detail
    else if (Array.isArray(body?.detail)) {
      error = body.detail.map((item) => item?.msg).filter(Boolean).join(' · ') || error
    }
  } catch {
    /* non-JSON error body — keep the generic message */
  }
  return { ok: false, error }
}

export async function getProfile(userId) {
  const res = await fetch(`/api/profile/${encodeURIComponent(userId)}`)
  return parseJson(res, 'Loading profile')
}

export async function updateProfile(userId, profile) {
  const res = await fetch(`/api/profile/${encodeURIComponent(userId)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(profile),
  })
  if (res.ok) return { ok: true, data: await res.json() }
  let error = `Profil konnte nicht gespeichert werden (${res.status})`
  try {
    const body = await res.json()
    if (typeof body?.detail === 'string') error = body.detail
    else if (Array.isArray(body?.detail)) {
      error = body.detail.map((item) => item?.msg).filter(Boolean).join(' · ') || error
    }
  } catch {
    /* non-JSON error body — keep the generic message */
  }
  return { ok: false, error }
}

// force=true bypasses the backend read-through cache and recomputes the analysis
// (e.g. after the user changes something and wants a fresh recommendation).
export async function analyze(userId, { force = false } = {}) {
  const res = await fetch('/api/analyze', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ user_id: userId, force }),
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
//
// timeoutMs guards against a stalled backend/LLM call that never resolves — without
// it a hang here would leave the chat widget's "typing…" indicator stuck forever
// instead of falling through to the scripted assistant.
export async function chat(sessionId, messages, { timeoutMs = 20000, lang = 'de' } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`/api/chat/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, lang }),
      signal: controller.signal,
    })
    return await parseJson(res, 'Chat')
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Chat timed out')
    throw err
  } finally {
    clearTimeout(timer)
  }
}

// Resolve a pending apply_change the Advisor paused for (see POST /confirm on the backend).
// `confirm=true` commits the previewed change, `false` cancels it. Returns { reply, trace_id }.
export async function confirmApply(sessionId, confirm, { lang = 'de', timeoutMs = 30000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`/api/chat/${sessionId}/confirm`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ confirm, lang }),
      signal: controller.signal,
    })
    return await parseJson(res, 'Confirm')
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Confirm timed out')
    throw err
  } finally {
    clearTimeout(timer)
  }
}

// Fetch the opening briefing (turn 0) for a session — the Advisor's first message, which
// replaces the old separately-generated memo. Works with or without an LLM key (the
// backend falls back to a deterministic template briefing). Idempotent server-side: the
// briefing is generated once per session and cached in the transcript.
export async function openingBriefing(sessionId, lang = 'de', { timeoutMs = 30000 } = {}) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    const res = await fetch(`/api/chat/${sessionId}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages: [], lang }),
      signal: controller.signal,
    })
    return await parseJson(res, 'Opening briefing')
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Briefing timed out')
    throw err
  } finally {
    clearTimeout(timer)
  }
}

// Streaming variant: POST /api/chat/stream returns Server-Sent Events. Calls
// onToken(text) for each token as it arrives and resolves to { traceId, gotTokens }.
// Throws on a non-OK response (e.g. 503 when no LLM key) so the caller can fall back
// to the non-streaming chat() and then to the scripted assistant.
//
// idleTimeoutMs resets on every chunk received (including the SSE keep-alive of a
// long reply), so a real answer never gets cut short — it only fires when the
// backend/LLM call stalls and nothing (not even an error event) ever arrives.
export async function streamChat(sessionId, messages, onToken, { idleTimeoutMs = 35000, lang = 'de' } = {}) {
  const controller = new AbortController()
  let timer = setTimeout(() => controller.abort(), idleTimeoutMs)
  const resetTimer = () => {
    clearTimeout(timer)
    timer = setTimeout(() => controller.abort(), idleTimeoutMs)
  }

  let res
  try {
    res = await fetch(`/api/chat/${sessionId}/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ messages, lang }),
      signal: controller.signal,
    })
  } catch (err) {
    clearTimeout(timer)
    if (err.name === 'AbortError') throw new Error('Chat stream timed out')
    throw err
  }
  if (!res.ok || !res.body) {
    clearTimeout(timer)
    const err = new Error(`Chat stream failed (${res.status})`)
    err.status = res.status
    throw err
  }

  const reader = res.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let traceId = null
  let gotTokens = false
  let pending = null  // set when the Advisor paused apply_change awaiting confirmation

  try {
    // Parse the SSE stream: events are separated by a blank line; each carries one
    // `data: <json>` line.
    for (;;) {
      const { done, value } = await reader.read()
      resetTimer()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      const events = buffer.split('\n\n')
      buffer = events.pop() ?? ''
      for (const evt of events) {
        const line = evt.trim()
        if (!line.startsWith('data:')) continue
        const payload = line.slice(5).trim()
        if (!payload) continue
        let ev
        try { ev = JSON.parse(payload) } catch { continue }
        if (ev.type === 'token') { gotTokens = true; onToken(ev.text) }
        else if (ev.type === 'done') { traceId = ev.trace_id || null }
        else if (ev.type === 'confirm_required') { pending = ev.payload || {}; traceId = ev.trace_id || traceId }
        else if (ev.type === 'error') {
          const err = new Error(ev.detail || 'Chat stream error')
          err.gotTokens = gotTokens
          throw err
        }
      }
    }
  } catch (err) {
    if (err.name === 'AbortError') {
      const timeoutErr = new Error('Chat stream timed out')
      timeoutErr.gotTokens = gotTokens
      throw timeoutErr
    }
    throw err
  } finally {
    clearTimeout(timer)
  }
  return { traceId, gotTokens, pending }
}

// Records a thumbs up/down on a chat reply as a Langfuse score. Best-effort:
// resolves to false on any failure so feedback UI never disrupts the chat.
export async function submitFeedback(traceId, value, comment) {
  try {
    const res = await fetch('/api/feedback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trace_id: traceId, value, comment }),
    })
    return res.ok
  } catch {
    return false
  }
}
