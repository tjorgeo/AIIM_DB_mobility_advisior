import React, { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { MessageCircle, X, Send, ThumbsUp, ThumbsDown, Maximize2, Minimize2, Check } from 'lucide-react'
import { useChat } from './useChat'
import Markdown from './Markdown'

// One-line, human-readable summary of a pending change's constraints (drop/keep/prefer/
// exclude) for the confirmation prompt. Category slugs are de-underscored; falls back to ''.
function describeConstraints(c, lang) {
  if (!c) return ''
  const label = (s) => String(s).replace(/_/g, ' ')
  const parts = []
  if (c.drop?.length) parts.push(`${lang === 'de' ? 'Kündigen' : 'Cancel'}: ${c.drop.map(label).join(', ')}`)
  if (c.keep?.length) parts.push(`${lang === 'de' ? 'Behalten' : 'Keep'}: ${c.keep.map(label).join(', ')}`)
  if (c.prefer_plans?.length) parts.push(`${lang === 'de' ? 'Bevorzugen' : 'Prefer'}: ${c.prefer_plans.join(', ')}`)
  if (c.exclude_plans?.length) parts.push(`${lang === 'de' ? 'Ausschließen' : 'Exclude'}: ${c.exclude_plans.join(', ')}`)
  return parts.join(' · ')
}

export default function ChatWidget({ user, lang, getContext, actions, sessionId, onOpenPortfolio }) {
  const [open, setOpen] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const [unread, setUnread] = useState(0)
  const [teaserDismissed, setTeaserDismissed] = useState(false)
  const [input, setInput] = useState('')
  const { messages, sending, send, sendFeedback, pending, confirm } = useChat({ user, lang, getContext, actions, sessionId })
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

  // Reserve room for the panel so it never overlaps page content — every page's
  // main content is centered with `margin: 0 auto`, so shrinking body's available
  // width (see the .chat-open/.chat-expanded rules in components.css) reflows the
  // whole page left instead of leaving it to sit underneath the fixed-position
  // panel. Cleaned up on unmount since body is shared, outside this component's
  // own DOM subtree.
  useEffect(() => {
    document.body.classList.toggle('chat-open', open)
    document.body.classList.toggle('chat-expanded', open && expanded)
    return () => { document.body.classList.remove('chat-open', 'chat-expanded') }
  }, [open, expanded])

  // Keep the conversation scrolled to the latest message (and to the confirm prompt).
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, sending, open, pending])

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
    <div className={`chat-panel${expanded ? ' chat-panel--expanded' : ''}`} role="dialog" aria-label={t('MoveOptimizer assistant', 'MoveOptimizer-Assistent')}>
      <div className="chat__header">
        <span className="chat__avatar">AI<span className="status-dot" /></span>
        <div>
          <div className="chat__title">{t('Mobility Assistant', 'Mobilitäts-Assistent')}</div>
          <div className="chat__status">● {t('Online', 'Online')}</div>
        </div>
        <button
          className="chat__close"
          onClick={() => setExpanded((v) => !v)}
          aria-label={expanded ? t('Shrink window', 'Fenster verkleinern') : t('Enlarge window', 'Fenster vergrößern')}
        >
          {expanded ? <Minimize2 size={16} /> : <Maximize2 size={16} />}
        </button>
        <button className="chat__close" onClick={() => setOpen(false)} aria-label={t('Close', 'Schließen')}><X size={18} /></button>
      </div>

      <div className="chat__body" ref={bodyRef}>
        {messages.map((m, i) => (
          <div className={`msg msg--${m.role}`} key={i}>
            {m.role === 'assistant' ? <Markdown text={m.content} /> : m.content}
            {m.role === 'assistant' && m.action === 'open-portfolio' && onOpenPortfolio && (
              <button
                className="msg__action"
                onClick={onOpenPortfolio}
              >
                {t('View portfolio', 'Portfolio ansehen')} →
              </button>
            )}
            {m.role === 'assistant' && m.traceId && (
              <div className="msg__feedback">
                <button
                  className={`msg__thumb${m.feedback === 1 ? ' msg__thumb--on' : ''}`}
                  onClick={() => sendFeedback(i, 1)}
                  aria-label={t('Helpful', 'Hilfreich')}
                  aria-pressed={m.feedback === 1}
                  disabled={m.feedback !== null}
                >
                  <ThumbsUp size={13} />
                </button>
                <button
                  className={`msg__thumb${m.feedback === 0 ? ' msg__thumb--on' : ''}`}
                  onClick={() => sendFeedback(i, 0)}
                  aria-label={t('Not helpful', 'Nicht hilfreich')}
                  aria-pressed={m.feedback === 0}
                  disabled={m.feedback !== null}
                >
                  <ThumbsDown size={13} />
                </button>
              </div>
            )}
          </div>
        ))}
        {sending && (
          <div className="typing"><span className="typing__dot" /><span className="typing__dot" /><span className="typing__dot" /></div>
        )}
      </div>

      {pending ? (
        <div className="chat__confirm" role="group" aria-label={t('Confirm change', 'Änderung bestätigen')}>
          <div className="chat__confirm-text">
            <strong>{t('Apply this change to your plan?', 'Diese Änderung in deinen Plan übernehmen?')}</strong>
            {describeConstraints(pending.constraints, lang) && (
              <span className="chat__confirm-detail">{describeConstraints(pending.constraints, lang)}</span>
            )}
          </div>
          <div className="chat__confirm-actions">
            <button className="chat__confirm-btn chat__confirm-btn--yes" onClick={() => confirm(true)} disabled={sending}>
              <Check size={15} /> {t('Apply', 'Übernehmen')}
            </button>
            <button className="chat__confirm-btn chat__confirm-btn--no" onClick={() => confirm(false)} disabled={sending}>
              {t('Cancel', 'Abbrechen')}
            </button>
          </div>
        </div>
      ) : (
        <div className="chat__quick">
          {quicks.map((qr) => (
            <button className="quick-chip" key={qr} onClick={() => send(qr)} disabled={sending}>{qr}</button>
          ))}
        </div>
      )}

      <form className="chat__composer" onSubmit={onSubmit}>
        <input
          className="chat__input"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={pending
            ? t('Please confirm or cancel above…', 'Bitte oben bestätigen oder abbrechen…')
            : t('Ask anything…', 'Frag mich etwas…')}
          aria-label={t('Message', 'Nachricht')}
          disabled={!!pending}
        />
        <button className="chat__send" type="submit" disabled={!input.trim() || sending || !!pending} aria-label={t('Send', 'Senden')}>
          <Send size={18} />
        </button>
      </form>
    </div>
  )

  // Portal to <body> so fixed positioning resolves against the viewport
  // (not the transformed .app-view wrapper) — keeps the bubble pinned.
  return createPortal(content, document.body)
}