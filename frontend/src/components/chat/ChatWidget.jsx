import React, { useState, useEffect, useRef } from 'react'
import { createPortal } from 'react-dom'
import { Send, ThumbsUp, ThumbsDown, Check, MessageCircle, ChevronRight } from 'lucide-react'
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

export default function ChatWidget({ user, lang, getContext, actions, sessionId, onOpenPortfolio, slotEl, fixedPos, collapsed, onToggleCollapsed }) {
  const [input, setInput] = useState('')
  const { messages, sending, send, sendFeedback, pending, confirm } = useChat({ user, lang, getContext, actions, sessionId })
  const bodyRef = useRef(null)
  const t = (en, de) => (lang === 'de' ? de : en)

  // Keep the conversation scrolled to the latest message (and to the confirm prompt).
  useEffect(() => {
    if (bodyRef.current) bodyRef.current.scrollTop = bodyRef.current.scrollHeight
  }, [messages, sending, pending])

  const quicks = lang === 'de'
    ? ['Plan optimieren', 'Warum dieser Plan?', 'Wie viel spare ich?']
    : ['Optimize my plan', 'Why this plan?', 'How much can I save?']

  const onSubmit = (e) => {
    e.preventDefault()
    const v = input
    setInput('')
    send(v)
  }

  const fixedStyle = fixedPos ? { '--chat-fixed-left': `${fixedPos.left}px`, '--chat-fixed-top': `${fixedPos.top}px` } : undefined

  // Collapsed: a slim rail (56px) instead of the full panel. Main content
  // reflows into the freed space through the same .page-split flex layout
  // that already sizes the reserved sidebar slot (see .page-split__sidebar /
  // body.chat-collapsed in components.css) — the actual panel and its
  // in-flow placeholder always agree on width, so nothing has to be
  // hand-synced across breakpoints the way the old floating-launcher +
  // body-margin approach did (see git history: "make chat window permanent").
  const content = collapsed ? (
    <div className="chat-sidebar chat-sidebar--collapsed" style={fixedStyle}>
      <button
        type="button"
        className="chat-collapse-rail"
        onClick={onToggleCollapsed}
        aria-label={t('Open assistant chat', 'Chat öffnen')}
        title={t('Open assistant chat', 'Chat öffnen')}
      >
        <MessageCircle size={20} />
        <span>{t('Chat', 'Chat')}</span>
      </button>
    </div>
  ) : (
    <div
      className="chat-sidebar"
      style={fixedStyle}
      aria-label={t('MoveOptimizer assistant', 'MoveOptimizer-Assistent')}
    >
      <div className="chat__header">
        <span className="chat__avatar">AI<span className="status-dot" /></span>
        <div>
          <div className="chat__title">{t('Mobility Assistant', 'Mobilitäts-Assistent')}</div>
          <div className="chat__status">● {t('Online', 'Online')}</div>
        </div>
        {onToggleCollapsed && (
          <button
            type="button"
            className="chat__collapse-btn"
            onClick={onToggleCollapsed}
            aria-label={t('Collapse chat', 'Chat einklappen')}
            title={t('Collapse chat', 'Chat einklappen')}
          >
            <ChevronRight size={16} />
          </button>
        )}
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

  // Portal into whichever page's sidebar slot is currently mounted, so this
  // component (and its useChat conversation state) never remounts on
  // navigation between views — only its DOM target changes.
  return slotEl ? createPortal(content, slotEl) : null
}