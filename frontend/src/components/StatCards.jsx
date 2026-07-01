import React from 'react'
import { Wallet, TrainFront, Route, Leaf } from 'lucide-react'
import { euro, number, co2 } from '../lib/format'

export default function StatCards({ analyst, lang }) {
  const t = (en, de) => (lang === 'de' ? de : en)

  const cards = [
    {
      icon: Wallet, tone: '',
      label: t('Annual spend', 'Jahresausgaben'),
      value: euro(analyst.current_annual_spend_eur, { lang }),
      sub: t('Subscriptions + tickets', 'Abos + Tickets'),
    },
    {
      icon: TrainFront, tone: 'blue',
      label: t('Trips (12 mo)', 'Fahrten (12 Mon.)'),
      value: number(analyst.total_trips, lang),
      sub: t('Journeys logged', 'Erfasste Fahrten'),
    },
    {
      icon: Route, tone: 'blue',
      label: t('Distance', 'Distanz'),
      value: `${number(analyst.total_distance_km, lang)} km`,
      sub: t('Across all transit', 'Über alle Verkehrsmittel'),
    },
    {
      icon: Leaf, tone: 'green',
      label: t('CO₂ footprint', 'CO₂-Bilanz'),
      value: co2(analyst.total_co2_kg, lang),
      sub: t('Estimated emissions', 'Geschätzte Emissionen'),
    },
  ]

  return (
    <div className="stats">
      {cards.map(({ icon: Icon, tone, label, value, sub }, i) => (
        <div className="card stat" key={i}>
          <span className={`stat__icon${tone ? ` stat__icon--${tone}` : ''}`}><Icon size={20} /></span>
          <span className="stat__label">{label}</span>
          <span className="stat__value">{value}</span>
          <span className="stat__sub">{sub}</span>
        </div>
      ))}
    </div>
  )
}
