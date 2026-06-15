import React, { useState, useEffect, useRef } from 'react'
import { MessageCircle, X, Send } from 'lucide-react'
import { useChat } from './useChat'

export default function ChatWidget({ user, lang, getContext, actions }) {
  const [open, setOpen] = useState(false)
  const [teaser, setTeaser] = useState(false)
  const [input, setInput] = useState('')
  const { messages, sending, send } = useChat({ user, lang, getContext, actions })
  const bodyRef = useRef(null)
  const t = (en, de) => (lang === 'de' ? de : en)

  // One-time greeting teaser on the launcher.
  useEffect(() => {
    if (open) return undefined
    const id = setTimeout(() => setTeaser(true), 1400)
    return () => clearTimeout(id)
  }, [open])

  // Keep the conversation scrolled to the latest message.
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, sending, open])

  const quicks = lang === 'de'
    ? ['Plan optimieren', 'Warum dieser Plan?', 'Wie viel spare ich?']
    : ['Optimize my plan', 'Why this plan?', 'How much can I save?']

  const onSubmit = (e) => {
    e.preventDefault()
    const v = input
    setInput('')
    send(v)
  }

  if (!open) {
    return (
      <>
        {teaser && (
          <div className="chat-teaser">
            <button className="chat-teaser__close" onClick={() => setTeaser(false)} aria-label={t('Dismiss', 'Schließen')}>×</button>
            <p className="chat-teaser__text">
              {t(`Hi ${user.firstName} 👋 Want to optimize your mobility?`, `Hi ${user.firstName} 👋 Mobilität optimieren?`)}
            </p>
          </div>
        )}
        <button className="chat-launcher" onClick={() => { setOpen(true); setTeaser(false) }} aria-label={t('Open assistant', 'Assistent öffnen')}>
          <MessageCircle size={26} />
          <span className="chat-launcher__badge" />
        </button>
      </>
    )
  }

  return (
    <div className="chat-panel" role="dialog" aria-label={t('MoveOptimizer assistant', 'MoveOptimizer-Assistent')}>
      <div className="chat__header">
        <span className="chat__avatar">AI<span className="status-dot" /></span>
        <div>
          <div className="chat__title">{t('Mobility Assistant', 'Mobilitäts-Assistent')}</div>
          <div className="chat__status">● {t('Online', 'Online')}</div>
        </div>
        <button className="chat__close" onClick={() => setOpen(false)} aria-label={t('Close', 'Schließen')}><X size={18} /></button>
      </div>

      <div className="chat__body" ref={bodyRef}>
        {messages.map((m, i) => (
          <div className={`msg msg--${m.role}`} key={i}>{m.content}</div>
        ))}
        {sending && (
          <div className="typing"><span className="typing__dot" /><span className="typing__dot" /><span className="typing__dot" /></div>
        )}
      </div>

      <div className="chat__quick">
        {quicks.map((qr) => (
          <button className="quick-chip" key={qr} onClick={() => send(qr)} disabled={sending}>{qr}</button>
        ))}
      </div>

      <form className="chat__composer" onSubmit={onSubmit}>
        <input
          className="chat__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t('Ask anything…', 'Frag mich etwas…')}
          aria-label={t('Message', 'Nachricht')}
        />
        <button className="chat__send" type="submit" disabled={!input.trim() || sending} aria-label={t('Send', 'Senden')}>
          <Send size={18} />
        </button>
      </form>
    </div>
  )
}
