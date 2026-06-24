import React, { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { MessageCircle, X, Send } from 'lucide-react'
import { useChat } from './useChat'

export default function ChatWidget({ user, lang, getContext, actions, advisorMemo }) {
  const [open, setOpen] = useState(false)
  const [unread, setUnread] = useState(0)
  const [teaserDismissed, setTeaserDismissed] = useState(false)
  const [input, setInput] = useState('')
  const { messages, sending, send } = useChat({ user, lang, getContext, actions, advisorMemo })
  const bodyRef = useRef(null)
  const prevLenRef = useRef(messages.length)
  const t = (en, de) => (lang === 'de' ? de : en)

  // Count assistant messages that arrive while the panel is closed → unread.
  useEffect(() => {
    if (messages.length > prevLenRef.current) {
      const added = messages.slice(prevLenRef.current)
      const assistantAdded = added.filter((m) => m.role === 'assistant').length
      if (!open && assistantAdded > 0) {
        setUnread((u) => u + assistantAdded)
        setTeaserDismissed(false)
      }
    }
    prevLenRef.current = messages.length
  }, [messages, open])

  // Opening the chat clears the notification.
  useEffect(() => { if (open) setUnread(0) }, [open])

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

  const showTeaser = !open && unread > 0 && !teaserDismissed

  const content = !open ? (
    <>
      {showTeaser && (
        <div className="chat-teaser" role="button" tabIndex={0} onClick={() => setOpen(true)}>
          <button
            className="chat-teaser__close"
            onClick={(e) => { e.stopPropagation(); setTeaserDismissed(true) }}
            aria-label={t('Dismiss', 'Schließen')}
          >×</button>
          <span className="chat-teaser__title">{t('New message from your advisor', 'Neue Nachricht von deinem Berater')}</span>
          <span className="chat-teaser__text">{t('Your personalized mobility plan is ready 📋', 'Dein persönlicher Mobilitätsplan ist fertig 📋')}</span>
        </div>
      )}
      <button
        className={`chat-launcher${unread > 0 ? ' chat-launcher--alert' : ''}`}
        onClick={() => setOpen(true)}
        aria-label={unread > 0 ? t('Open assistant — new message', 'Assistent öffnen — neue Nachricht') : t('Open assistant', 'Assistent öffnen')}
      >
        <MessageCircle size={26} />
        {unread > 0
          ? <span className="chat-launcher__count">{unread}</span>
          : <span className="chat-launcher__badge" />}
      </button>
    </>
  ) : (
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

  // Portal to <body> so fixed positioning resolves against the viewport
  // (not the transformed .app-view wrapper) — keeps the bubble pinned.
  return createPortal(content, document.body)
}
