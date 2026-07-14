import React from 'react'
import { TrainFront, Bus, Car, Bike, Zap, Footprints, Compass } from 'lucide-react'
import { number } from '../lib/format'

// Keyed on the raw production transport_mode (see backend/database/init/01_create_table.sql's
// transport_mode CHECK constraint) — mode_breakdown no longer groups regional_train/
// long_distance_train into one "train" figure or car/car_sharing/ride_hailing/taxi into
// one "car" figure, so every raw mode gets its own entry here.
const MODE_META = {
  public_transport: { Icon: Bus, en: 'Public transport', de: 'ÖPNV', cls: 'mode--bus' },
  regional_train: { Icon: TrainFront, en: 'Regional train', de: 'Regionalzug', cls: 'mode--train' },
  long_distance_train: { Icon: TrainFront, en: 'Long-distance train', de: 'Fernverkehr', cls: 'mode--train' },
  bike_sharing: { Icon: Bike, en: 'Bike-sharing', de: 'Fahrrad-Sharing', cls: 'mode--bike' },
  bicycle: { Icon: Bike, en: 'Bicycle', de: 'Fahrrad', cls: 'mode--bike' },
  car: { Icon: Car, en: 'Car', de: 'Auto', cls: 'mode--car' },
  car_sharing: { Icon: Car, en: 'Car-sharing', de: 'Carsharing', cls: 'mode--car' },
  ride_hailing: { Icon: Car, en: 'Ride-hailing', de: 'Ride-Hailing', cls: 'mode--car' },
  taxi: { Icon: Car, en: 'Taxi', de: 'Taxi', cls: 'mode--car' },
  e_scooter: { Icon: Zap, en: 'E-scooter', de: 'E-Scooter', cls: 'mode--scooter' },
  walking: { Icon: Footprints, en: 'Walking', de: 'Zu Fuß', cls: 'mode--neutral' },
  other: { Icon: Compass, en: 'Other', de: 'Sonstiges', cls: 'mode--neutral' },
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
          const meta = MODE_META[e.mode] || { Icon: Compass, en: e.mode, de: e.mode, cls: 'mode--neutral' }
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
