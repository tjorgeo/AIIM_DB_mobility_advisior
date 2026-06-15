import React, { useState } from 'react'

export default function AdvisorNote({ memo, lang }) {
  const t = (en, de) => (lang === 'de' ? de : en)
  const [open, setOpen] = useState(false)
  if (!memo) return null

  return (
    <section className="card advisor">
      <div className="advisor__head">
        <span className="advisor__avatar">AI</span>
        <div>
          <div className="advisor__title">{t('Your advisor', 'Dein Berater')}</div>
          <div className="advisor__sub">● {t('Personalized memo', 'Persönliches Memo')}</div>
        </div>
      </div>

      <div className={`advisor__body${open ? ' advisor__body--open' : ''}`}>{memo}</div>

      <button className="advisor__more" onClick={() => setOpen((o) => !o)}>
        {open ? t('Show less', 'Weniger anzeigen') : t('Read full memo', 'Ganzes Memo lesen')}
      </button>
    </section>
  )
}
