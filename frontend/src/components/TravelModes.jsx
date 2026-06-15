import React from 'react'
import { TrainFront, Bus, Car, Bike, Compass } from 'lucide-react'
import { number } from '../lib/format'

const MODE_META = {
  train: { Icon: TrainFront, en: 'Train', de: 'Bahn', cls: 'mode--train' },
  bus: { Icon: Bus, en: 'Bus', de: 'Bus', cls: 'mode--bus' },
  car: { Icon: Car, en: 'Car-sharing', de: 'Carsharing', cls: 'mode--car' },
  scooter: { Icon: Bike, en: 'Scooter', de: 'Roller', cls: 'mode--scooter' },
}

export default function TravelModes({ analyst, lang }) {
  const t = (en, de) => (lang === 'de' ? de : en)
  const entries = Object.entries(analyst.mode_breakdown || {})
    .map(([mode, v]) => ({ mode, ...v }))
    .sort((a, b) => (b.trips || 0) - (a.trips || 0))
  const total = entries.reduce((s, e) => s + (e.trips || 0), 0) || 1
  const top = entries[0]
  const topMeta = top ? MODE_META[top.mode] : null

  return (
    <section className="card section">
      <div className="section__head">
        <h2 className="section__title">
          <span className="section__title-ico"><Compass size={20} /></span>
          {t('How you travel', 'So bist du unterwegs')}
        </h2>
        {top && (
          <span className="section__hint">
            {t('Mostly by', 'Meist mit')} {topMeta ? t(topMeta.en, topMeta.de) : top.mode}
          </span>
        )}
      </div>

      <div className="modes">
        {entries.map((e) => {
          const meta = MODE_META[e.mode] || { Icon: Compass, en: e.mode, de: e.mode, cls: '' }
          const Icon = meta.Icon
          const pct = Math.round((e.trips / total) * 100)
          return (
            <div className={`mode ${meta.cls}`} key={e.mode}>
              <span className="mode__icon"><Icon size={18} /></span>
              <div className="mode__main">
                <div className="mode__head">
                  <span className="mode__label">{t(meta.en, meta.de)}</span>
                  <span className="mode__count">
                    {number(e.trips, lang)} {t('trips', 'Fahrten')} · {pct}%
                  </span>
                </div>
                <div className="mode__bar">
                  <div className="mode__fill" style={{ width: `${Math.max(pct, 2)}%` }} />
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </section>
  )
}
