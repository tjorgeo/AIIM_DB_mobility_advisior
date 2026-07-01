import React from 'react'
import { Lightbulb, CheckCircle } from 'lucide-react'
import { euro } from '../lib/format'

export default function Insights({ inefficiencies, lang }) {
  const t = (en, de) => (lang === 'de' ? de : en)
  const items = inefficiencies || []

  return (
    <section className="card section">
      <div className="section__head">
        <h2 className="section__title">
          <span className="section__title-ico"><Lightbulb size={20} /></span>
          {t('Savings opportunities', 'Sparpotenziale')}
        </h2>
      </div>

      {items.length > 0 ? (
        <div className="insights">
          {items.map((it, i) => (
            <div className="insight" key={i}>
              <span className="insight__icon"><Lightbulb size={18} /></span>
              <div>
                <div className="insight__title">
                  {it.service}
                  {it.annual_waste_eur > 0 && (
                    <span className="pill pill--save">
                      {t('Up to', 'Bis zu')} {euro(it.annual_waste_eur, { lang })}/{t('yr', 'Jahr')}
                    </span>
                  )}
                </div>
                <p className="insight__text">{it.details}</p>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="insight insight--good">
          <span className="insight__icon"><CheckCircle size={18} /></span>
          <div>
            <div className="insight__title">{t('Your plan looks efficient', 'Dein Tarif ist effizient')}</div>
            <p className="insight__text">
              {t(
                'We didn’t find any major waste in your current setup. Nicely optimized!',
                'Wir haben keine größeren Ineffizienzen gefunden. Gut optimiert!',
              )}
            </p>
          </div>
        </div>
      )}
    </section>
  )
}
