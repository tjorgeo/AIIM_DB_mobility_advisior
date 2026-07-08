import { useState, useRef, useCallback, useEffect } from 'react'
import { chat as apiChat, submitFeedback } from '../../api/client'
import { euro, co2 } from '../../lib/format'

// Pick the recommended scenario (or the first) from an analysis result.
function pickRec(result) {
  const s = result?.summary?.scenarios || []
  return s.find((x) => x.id === result.summary.recommended_scenario) || s[0] || null
}

export function greetingText(user, lang) {
  const name = user.firstName
  return lang === 'de'
    ? `Hi ${name} 👋 Ich bin dein MoveOptimizer-Assistent. Ich werte gerade deine Fahrten aus — dein persönlicher Plan erscheint gleich hier.`
    : `Hi ${name} 👋 I'm your MoveOptimizer assistant. I'm reviewing your travel now — your personalized plan will appear here in a moment.`
}

// Frontend-only scripted assistant — used whenever POST /api/chat is unavailable.
async function scriptedReply(text, { user, lang, getContext, actions }) {
  const t = (en, de) => (lang === 'de' ? de : en)
  const q = text.toLowerCase()
  const has = (...words) => words.some((w) => q.includes(w))

  const summarize = (rec) => {
    if (!rec) return t('I couldn’t build a plan just now — please try again in a moment.', 'Ich konnte gerade keinen Plan erstellen — bitte versuche es gleich erneut.')
    if (rec.annual_savings > 0) {
      return t(
        `Done! Switching to “${rec.label}” would save you ${euro(rec.annual_savings, { lang })} a year and cut about ${co2(rec.co2_savings_kg, lang)} of CO₂. Want me to switch you to it?`,
        `Fertig! Mit „${rec.label}“ sparst du ${euro(rec.annual_savings, { lang })} pro Jahr und vermeidest rund ${co2(rec.co2_savings_kg, lang)} CO₂. Soll ich darauf umstellen?`,
      )
    }
    return t(
      `Good news — your current setup is already efficient. “${rec.label}” at ${euro(rec.annual_cost, { lang })}/yr is the best fit, no changes needed.`,
      `Gute Nachricht — dein Tarif ist bereits effizient. „${rec.label}“ für ${euro(rec.annual_cost, { lang })}/Jahr passt am besten, keine Änderung nötig.`,
    )
  }

  // Accept / switch
  if (has('switch', 'approve', 'accept', 'do it', 'go ahead', 'sounds good', 'yes', 'ja', 'wechsel', 'annehm', 'umstell')) {
    let rec = getContext().recommendation
    if (!rec) rec = pickRec(await actions.optimize())
    if (!rec) return summarize(rec)
    const ok = await actions.approve(rec.id)
    return ok
      ? t(`Switched you to “${rec.label}” ✓ Your new plan is saved. Anything else?`, `Auf „${rec.label}“ umgestellt ✓ Dein neuer Tarif ist gespeichert. Sonst noch etwas?`)
      : t('Hmm, I couldn’t save that just now. Please try again.', 'Hmm, das konnte ich gerade nicht speichern. Bitte versuche es erneut.')
  }

  // Why / explain
  if (has('why', 'explain', 'reason', 'how come', 'warum', 'erklär')) {
    const rec = getContext().recommendation || pickRec(await actions.optimize())
    if (!rec) return summarize(rec)
    const changes = (rec.changes || []).map((c) => `${String(c.action).toUpperCase()} ${c.item}`).join(', ')
    return t(
      `“${rec.label}” fits how you actually travel. ${changes ? `The move: ${changes}. ` : ''}It lands at ${euro(rec.annual_cost, { lang })}/yr${rec.annual_savings > 0 ? `, saving ${euro(rec.annual_savings, { lang })}` : ''}.`,
      `„${rec.label}“ passt zu deinem Reiseverhalten. ${changes ? `Die Änderung: ${changes}. ` : ''}Kosten: ${euro(rec.annual_cost, { lang })}/Jahr${rec.annual_savings > 0 ? `, Ersparnis ${euro(rec.annual_savings, { lang })}` : ''}.`,
    )
  }

  // How much / savings / cost
  if (has('how much', 'save', 'saving', 'cost', 'price', 'cheap', 'spar', 'kost', 'günstig')) {
    const rec = getContext().recommendation || pickRec(await actions.optimize())
    return summarize(rec)
  }

  // CO2 / environment
  if (has('co2', 'carbon', 'emission', 'environment', 'green', 'umwelt', 'klima')) {
    const rec = getContext().recommendation || pickRec(await actions.optimize())
    if (!rec) return summarize(rec)
    return t(
      `Your recommended plan cuts roughly ${co2(rec.co2_savings_kg, lang)} of CO₂ per year. Small switch, real impact 🌱`,
      `Dein empfohlener Tarif spart rund ${co2(rec.co2_savings_kg, lang)} CO₂ pro Jahr. Kleine Umstellung, echte Wirkung 🌱`,
    )
  }

  // Optimize / analyze / run
  if (has('optimi', 'analy', 'optimier', 'check', 'review', 'plan', 'recommend', 'empfehl', 'tarif')) {
    return summarize(pickRec(await actions.optimize()))
  }

  // Greeting
  if (has('hi', 'hello', 'hey', 'hallo', 'servus', 'guten')) {
    return t(
      `Hi ${user.firstName}! I can analyze your travel and find the cheapest, greenest plan for you. Shall I take a look?`,
      `Hi ${user.firstName}! Ich kann deine Fahrten analysieren und den günstigsten, grünsten Tarif finden. Soll ich nachsehen?`,
    )
  }

  // Help / default
  return t(
    'I can optimize your mobility plan, explain why it’s recommended, show how much you’d save, or switch you over. Just ask — or tap a suggestion below.',
    'Ich kann deinen Mobilitätsplan optimieren, die Empfehlung erklären, deine Ersparnis zeigen oder dich umstellen. Frag einfach — oder tippe unten auf einen Vorschlag.',
  )
}

export function useChat({ user, lang, getContext, actions, advisorMemo }) {
  const [messages, setMessages] = useState(() => [{ role: 'assistant', content: greetingText(user, lang) }])
  const [sending, setSending] = useState(false)
  const messagesRef = useRef(messages)
  useEffect(() => { messagesRef.current = messages }, [messages])

  // Optional `traceId` on assistant messages enables thumbs feedback (only set
  // for real LLM replies from /api/chat, not scripted fallbacks).
  const push = (role, content, traceId = null) =>
    setMessages((m) => [...m, { role, content, traceId, feedback: null }])

  // When the analysis finishes, the advisor delivers the personalized memo
  // straight into the chat (once).
  const advisorPostedRef = useRef(false)
  useEffect(() => {
    if (!advisorMemo || advisorPostedRef.current) return
    advisorPostedRef.current = true
    const intro = lang === 'de' ? 'Hier ist dein persönlicher Plan 📋\n\n' : 'Here’s your personalized plan 📋\n\n'
    setMessages((m) => [...m, { role: 'assistant', content: intro + advisorMemo }])
  }, [advisorMemo, lang])

  const send = useCallback(async (raw) => {
    const text = String(raw || '').trim()
    if (!text || sending) return
    push('user', text)
    setSending(true)

    const history = [...messagesRef.current, { role: 'user', content: text }]
    try {
      const data = await apiChat(user.id, history)
      if (!data || !data.reply) throw new Error('no reply')
      push('assistant', data.reply, data.trace_id || null)
    } catch {
      const reply = await scriptedReply(text, { user, lang, getContext, actions })
      push('assistant', reply)
    } finally {
      setSending(false)
    }
  }, [sending, user, lang, getContext, actions])

  // Send thumbs feedback for one assistant message (by index) and remember the
  // choice locally so the UI can reflect it. Best-effort; ignores failures.
  const sendFeedback = useCallback((index, value) => {
    setMessages((m) => {
      const msg = m[index]
      if (!msg || !msg.traceId || msg.feedback === value) return m
      submitFeedback(msg.traceId, value)
      return m.map((x, i) => (i === index ? { ...x, feedback: value } : x))
    })
  }, [])

  return { messages, sending, send, sendFeedback }
}
