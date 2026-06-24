import React from 'react'
import { Award, Leaf, Check, Plus, X, ArrowRight } from 'lucide-react'
import { euro } from '../lib/format'

const CHANGE_META = {
  add: { cls: 'change--add', Icon: Plus, en: 'Add', de: 'Hinzufügen' },
  cancel: { cls: 'change--cancel', Icon: X, en: 'Cancel', de: 'Kündigen' },
  keep: { cls: 'change--keep', Icon: Check, en: 'Keep', de: 'Behalten' },
}

export default function RecommendationCard({ summary, lang, approvedScenarioId, onApprove }) {
  const t = (en, de) => (lang === 'de' ? de : en)
  const scenarios = [...(summary.scenarios || [])].sort((a, b) =>
    (a.id === summary.recommended_scenario ? -1 : 0) - (b.id === summary.recommended_scenario ? -1 : 0),
  )

  return (
    <section className="card section">
      <div className="section__head">
        <h2 className="section__title">
          <span className="section__title-ico"><Award size={20} /></span>
          {t('Recommended for you', 'Für dich empfohlen')}
        </h2>
        <span className="section__hint">{t('Based on your last 12 months', 'Basierend auf 12 Monaten')}</span>
      </div>

      <div className="plans">
        {scenarios.map((scen) => {
          const isRecommended = scen.id === summary.recommended_scenario
          const isSelected = approvedScenarioId === scen.id
          const decided = approvedScenarioId !== null && approvedScenarioId !== undefined
          const changes = scen.changes || []

          return (
            <article className={`plan${isRecommended ? ' plan--recommended' : ''}`} key={scen.id}>
              {isRecommended && <span className="plan__badge">{t('Best for you', 'Top-Empfehlung')}</span>}

              <h3 className="plan__name">{scen.label}</h3>

              <div className="plan__price">
                <b>{euro(scen.annual_cost, { lang })}</b>
                <span className="plan__price-unit">/ {t('yr', 'Jahr')}</span>
              </div>

              {scen.annual_savings > 0 ? (
                <span className="pill pill--save">
                  {t('Save', 'Spare')} {euro(scen.annual_savings, { lang })}/{t('yr', 'Jahr')}
                </span>
              ) : (
                <span className="pill pill--muted">{t('Your current plan', 'Dein aktueller Tarif')}</span>
              )}

              <div className="plan__changes">
                <span className="plan__changes-label">{t('What changes', 'Was sich ändert')}</span>
                {changes.length > 0 ? (
                  changes.map((chg, i) => {
                    const meta = CHANGE_META[String(chg.action).toLowerCase()] || CHANGE_META.keep
                    const Icon = meta.Icon
                    return (
                      <div className={`change ${meta.cls}`} key={i}>
                        <Icon size={14} />
                        <b>{t(meta.en, meta.de)}</b>
                        <span>{chg.item}</span>
                      </div>
                    )
                  })
                ) : (
                  <div className="change change--keep">
                    <Check size={14} />
                    <span>{t('No changes — keep your current plan', 'Keine Änderung — Tarif behalten')}</span>
                  </div>
                )}
              </div>

              <div className="plan__foot">
                <span className="pill pill--co2">
                  <Leaf size={13} /> −{Math.round(scen.co2_savings_kg || 0)} kg CO₂
                </span>

                <button
                  className={`btn btn--sm ${isRecommended ? 'btn--primary' : 'btn--ghost'}`}
                  onClick={() => onApprove(scen.id)}
                  disabled={decided}
                >
                  {isSelected ? (
                    <><Check size={14} /> {t('Selected', 'Gewählt')}</>
                  ) : isRecommended ? (
                    <>{t('Switch to this plan', 'Zu diesem Plan')} <ArrowRight size={14} /></>
                  ) : (
                    t('Choose this', 'Diesen wählen')
                  )}
                </button>
              </div>
            </article>
          )
        })}
      </div>
    </section>
  )
}
