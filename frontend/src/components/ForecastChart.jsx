import React from 'react'
import { TrendingUp } from 'lucide-react'

export default function ForecastChart({ forecaster, lang }) {
  const t = (en, de) => (lang === 'de' ? de : en)
  const bars = forecaster.forecast_6mo || []
  const max = Math.max(...bars.map((b) => b.total_trips), 1)
  const conf = Math.round((forecaster.confidence_score || 0) * 100)

  return (
    <section className="card section">
      <div className="section__head">
        <h2 className="section__title">
          <span className="section__title-ico"><TrendingUp size={20} /></span>
          {t('Your next 6 months', 'Deine nächsten 6 Monate')}
        </h2>
        <span className="section__hint">{conf}% {t('confidence', 'Konfidenz')}</span>
      </div>

      {forecaster.trend && <p className="forecast__meta">“{forecaster.trend}”</p>}

      <div className="chart">
        <div className="chart__bars">
          {bars.map((m, i) => (
            <div className="chart__group" key={i}>
              <div className="chart__bar" style={{ height: `${Math.max((m.total_trips / max) * 100, 4)}%` }}>
                <span className="chart__val">{m.total_trips}</span>
              </div>
              <span className="chart__label">{String(m.month).split(' ')[0].slice(0, 3)}</span>
            </div>
          ))}
        </div>
      </div>
    </section>
  )
}
