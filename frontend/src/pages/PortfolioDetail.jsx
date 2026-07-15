import React, { useState } from 'react'
import { ChevronLeft, ChevronDown, Wallet, PiggyBank, TrendingUp, Calendar, Euro, Leaf, Clock } from 'lucide-react'
import { euro, number } from '../lib/format'
import { modeColor, modeLabel } from '../lib/travelModes'
import Markdown from '../components/chat/Markdown'

function recMeta(rec, colors, isDE) {
  switch (rec) {
    case 'keep_current': return { label: isDE ? 'Behalten' : 'Keep', color: colors.successGreen }
    case 'switch_to_alternative': return { label: isDE ? 'Abo wechseln' : 'Switch plan', color: colors.accentAmber }
    case 'cancel_current_go_pay_as_you_go': return { label: isDE ? 'Kündigen' : 'Cancel', color: colors.accentRed }
    case 'no_subscription_needed': return { label: isDE ? 'Kein Abo nötig' : 'No subscription needed', color: colors.successGreen }
    case 'consider_subscribing': return { label: isDE ? 'Abo empfohlen' : 'Consider subscribing', color: colors.accentAmber }
    default: return { label: rec || (isDE ? 'Unbekannt' : 'Unknown'), color: colors.textMuted }
  }
}

export default function PortfolioDetail({ analysis, lang, colors, isDark, onBack }) {
  const isDE = lang === 'DE'
  const langKey = isDE ? 'de' : 'en'
  const t = isDE
    ? {
      back: 'Zurück zum Dashboard', title: 'Kostenoptimiertes Portfolio', subtitle: 'Kosten heute, Alternativen im Vergleich, Ausblick',
      current: 'Aktuell', optimized: 'Optimiert', savings: 'Ersparnis',
      categoryTrips: (n) => `Basierend auf ${number(n, langKey)} Fahrten/Jahr`,
      todayLabel: 'AKTUELLE KOSTEN', noSubLabel: 'KOSTEN OHNE ABO',
      bestAlt: 'Günstigste Alternative gefunden', vsCurrent: 'ggü. aktuell', vsNoSub: 'ggü. ohne Abo',
      allAlternatives: 'Alle Alternativen im Vergleich', plan: 'Tarif', perYear: 'Kosten/Jahr',
      noAlternatives: 'Keine Alternative im Katalog gefunden — das aktuelle Abo ist bereits die einzige sinnvolle Option.',
      forecastTitle: 'Prognose für die nächsten 12 Monate', forecastSub: 'Erwartete Nutzung auf Basis deiner Historie',
      mode: 'Verkehrsmittel', tripsPerYear: 'Fahrten/Jahr',
      lifeEventTitle: (type) => `Lebensereignis erkannt: ${type === 'relocation' ? 'Umzug' : type}`,
      reEval: (days) => `Empfehlung: Analyse in ca. ${days} Tagen erneut prüfen.`,
      demandChange: 'Erwartete Änderung des Reiseverhaltens', baseline: 'Bisher', afterEvent: 'Nach Ereignis',
      noLifeEvent: 'Aktuell sind keine bevorstehenden Lebensereignisse in deinem Kalender erkannt worden, die deine Empfehlungen ändern würden.',
      noForecast: 'Für diesen Zeitraum liegt noch keine Prognose vor.',
      fullMemo: 'Vollständige Analyse deines Beraters',
      noData: 'Für diesen Zeitraum liegen noch keine Portfolio-Daten vor.',
      co2PerYear: 'CO₂/Jahr', timePerYear: 'Zeit/Jahr', hoursShort: 'Std',
      recommendedBadge: 'EMPFOHLEN',
      recommendedNotCheapest: 'Nicht die günstigste Option, aber besser nach deiner Kosten-/CO₂-/Zeit-Gewichtung.',
      modalShiftTitle: 'Andere Verkehrsmittel im Vergleich', modalShiftSub: 'Basierend auf deinen bisherigen Fahrten in der jeweiligen Kategorie',
      stayLabel: 'Aktuell dabei bleiben', shiftTo: (label) => `Wechsel zu ${label}`,
      noBetterShift: 'Kein anderes Verkehrsmittel schneidet nach deiner Gewichtung besser ab.',
      excludedNote: 'Geprüft, aber nicht vorgeschlagen:',
      confidenceLow: 'geringe Sicherheit',
      priorityIntro: (cost, co2, time) => `Gewichtet nach deinen Prioritäten: Kosten ${cost}/100, CO₂ ${co2}/100, Flexibilität/Zeit ${time}/100`,
      noCurrentToCompare: 'kein aktuelles Abo zum Vergleich',
      showAlternatives: (n) => (n === 1 ? 'Die 1 Alternative anzeigen' : `Alle ${n} Alternativen anzeigen`),
      hideAlternatives: 'Alternativen ausblenden',
    }
    : {
      back: 'Back to dashboard', title: 'Cost-Optimized Portfolio', subtitle: "Today's costs, alternatives compared, and what's ahead",
      current: 'Current', optimized: 'Optimized', savings: 'Savings',
      categoryTrips: (n) => `Based on ${number(n, langKey)} trips/year`,
      todayLabel: 'CURRENT COST', noSubLabel: 'COST WITHOUT SUBSCRIPTION',
      bestAlt: 'Cheapest alternative found', vsCurrent: 'vs. current', vsNoSub: 'vs. no subscription',
      allAlternatives: 'All alternatives compared', plan: 'Plan', perYear: 'Cost/yr',
      noAlternatives: 'No alternative found in the catalog — the current plan is already the only sensible option.',
      forecastTitle: 'Forecast for the next 12 months', forecastSub: 'Expected usage based on your history',
      mode: 'Mode', tripsPerYear: 'Trips/yr',
      lifeEventTitle: (type) => `Life event detected: ${type === 'relocation' ? 'Relocation' : type}`,
      reEval: (days) => `Recommendation: re-check this analysis in about ${days} days.`,
      demandChange: 'Expected change in travel behavior', baseline: 'Before', afterEvent: 'After event',
      noLifeEvent: 'No upcoming life events were detected in your calendar that would change these recommendations.',
      noForecast: 'No forecast available for this period yet.',
      fullMemo: "Your advisor's full analysis",
      noData: 'No portfolio data available for this period yet.',
      co2PerYear: 'CO₂/yr', timePerYear: 'Time/yr', hoursShort: 'hrs',
      recommendedBadge: 'RECOMMENDED',
      recommendedNotCheapest: "Not the cheapest option, but scores better on your cost/CO₂/time weighting.",
      modalShiftTitle: 'Other modes compared', modalShiftSub: 'Based on your past trips in each category',
      stayLabel: 'Stay as-is', shiftTo: (label) => `Switch to ${label}`,
      noBetterShift: 'No other mode scores better under your weighting.',
      excludedNote: 'Checked, but not suggested:',
      confidenceLow: 'low confidence',
      priorityIntro: (cost, co2, time) => `Weighted by your priorities: cost ${cost}/100, CO₂ ${co2}/100, flexibility/time ${time}/100`,
      noCurrentToCompare: 'no current plan to compare against',
      showAlternatives: (n) => (n === 1 ? 'Show the 1 alternative' : `Show all ${n} alternatives`),
      hideAlternatives: 'Hide alternatives',
    }

  // Per-category "all alternatives" table — collapsed by default so the page leads
  // with the verdict (recommendation + best option), not a wall of every plan
  // considered. Keyed by category so each card's toggle is independent.
  const [expandedAlternatives, setExpandedAlternatives] = useState(() => new Set())
  const toggleAlternatives = (category) => setExpandedAlternatives((prev) => {
    const next = new Set(prev)
    next.has(category) ? next.delete(category) : next.add(category)
    return next
  })

  const summary = analysis?.summary || null
  // Most-used mode first — same ordering for the category cards and the modal-shift
  // list below, so both read consistently top-to-bottom by how much the customer
  // actually relies on that category.
  const categoryAnalysis = [...(summary?.category_subscription_analysis || [])]
    .sort((a, b) => (b.annual_trips || 0) - (a.annual_trips || 0))
  const tripsByCategory = Object.fromEntries(categoryAnalysis.map((c) => [c.category, c.annual_trips || 0]))
  const modalShiftSuggestions = [...(summary?.modal_shift_suggestions || [])]
    .sort((a, b) => (tripsByCategory[b.from_category] || 0) - (tripsByCategory[a.from_category] || 0))
  const preferences = analysis?.preferences || {}
  const totalCurrent = summary?.total_actual_annual_cost_eur || 0
  const totalSavings = summary?.total_estimated_savings_eur || 0
  const totalOptimized = Math.max(totalCurrent - totalSavings, 0)
  const memo = summary?.memos?.[isDE ? 'german' : 'english']

  const forecaster = analysis?.raw_agent_payloads?.forecaster?.output || null
  const scenarios = forecaster?.scenarios || []
  const baselineScenario = scenarios.find((s) => s.label === 'baseline') || scenarios[0] || null
  const eventScenario = scenarios.length > 1 ? scenarios[scenarios.length - 1] : null
  const flags = forecaster?.uncertainty_flags
  const lifeEventDetected = !!flags?.life_event_detected

  const cardStyle = { backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '24px', padding: '1.5rem' }
  const kpi = (icon, label, value) => (
    <div style={{ ...cardStyle, padding: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.7rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em' }}>{label}</span>
        <span style={{ color: colors.accentCyan }}>{icon}</span>
      </div>
      <div style={{ fontSize: '1.3rem', fontWeight: '800', letterSpacing: '-0.02em' }}>{value}</div>
    </div>
  )

  return (
    <div style={{ backgroundColor: colors.bg, color: colors.text, fontFamily: 'system-ui, -apple-system, sans-serif', minHeight: '100vh' }}>
      <style>{`
        .portfolio-container { display: grid; grid-template-columns: 1fr; gap: 1.25rem; width: 100%; max-width: 480px; margin: 0 auto; padding: 1.5rem 1.25rem 3rem; box-sizing: border-box; }
        .portfolio-kpis { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; }
        .portfolio-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
        @media (min-width: 768px) { .portfolio-container { max-width: 900px; } }
        @media (max-width: 480px) { .portfolio-kpis { grid-template-columns: 1fr; } }
      `}</style>

      <header style={{ padding: '1.25rem 1.5rem', borderBottom: `1px solid ${colors.border}`, position: 'sticky', top: 0, backgroundColor: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.85)', backdropFilter: 'blur(12px)', zIndex: 10 }}>
        <button onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '12px', color: colors.textMuted, padding: '0.55rem 0.95rem', fontSize: '0.88rem', fontWeight: '600', cursor: 'pointer' }}>
          <ChevronLeft size={16} /> {t.back}
        </button>
      </header>

      <main className="portfolio-container">
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: '800', letterSpacing: '-0.02em', marginBottom: '0.25rem' }}>{t.title}</h1>
          <p style={{ color: colors.textMuted, fontSize: '0.9rem' }}>{t.subtitle}</p>
        </div>

        {categoryAnalysis.length === 0 ? (
          <div style={cardStyle}>{t.noData}</div>
        ) : (
          <>
            <div className="portfolio-kpis">
              {kpi(<Wallet size={14} />, t.current.toUpperCase(), euro(totalCurrent, { lang: langKey }))}
              {kpi(<TrendingUp size={14} />, t.optimized.toUpperCase(), euro(totalOptimized, { lang: langKey }))}
              {kpi(<PiggyBank size={14} />, t.savings.toUpperCase(), euro(totalSavings, { lang: langKey }))}
            </div>

            {/* Per-category cost comparison — "Vergleich Kosten heute" + "Vergleich mit anderen Abos" */}
            {categoryAnalysis.map((c) => {
              const meta = recMeta(c.recommendation, colors, isDE)
              const swatch = modeColor(c.category, isDark)
              const currentSubs = c.current_subscriptions || []
              const alternatives = [...(c.alternatives || [])].sort((a, b) => a.estimated_annual_cost_eur - b.estimated_annual_cost_eur)
              const cheapest = c.cheapest_alternative
              const best = c.recommended_alternative || cheapest
              const bestDiffersFromCheapest = best && cheapest && best.provider_plan_name !== cheapest.provider_plan_name
              // cheapest_alternative is just alternatives[0] — the cheapest plan on
              // file, kept around for the comparison table even when it LOSES to
              // "keep current" or "cancel" (e.g. every alternative is pricier than
              // just paying as you go). Only show the prominent callout when an
              // alternative actually IS the recommendation, never as a fallback
              // display of a rejected, pricier plan.
              const showBestAlternative = best
                && (c.recommendation === 'switch_to_alternative' || c.recommendation === 'consider_subscribing')
              const isAlternativesExpanded = expandedAlternatives.has(c.category)

              return (
                <div key={c.category} style={cardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: swatch, display: 'inline-block' }} />
                      <h3 style={{ fontSize: '1.05rem', fontWeight: '700' }}>{modeLabel(c.category, langKey)}</h3>
                    </div>
                    <span style={{ fontSize: '0.72rem', fontWeight: '700', color: meta.color, backgroundColor: `${meta.color}40`, border: `1px solid ${meta.color}66`, padding: '0.25rem 0.6rem', borderRadius: '999px' }}>
                      {meta.label}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: colors.textMuted, marginBottom: '0.5rem' }}>{t.categoryTrips(c.annual_trips)}</p>
                  {(c.annual_co2_kg != null || c.annual_time_minutes != null) && (
                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1rem' }}>
                      {c.annual_co2_kg != null && (
                        <span style={{ fontSize: '0.72rem', color: colors.textMuted, backgroundColor: colors.inputBg, borderRadius: '999px', padding: '0.2rem 0.6rem' }}>
                          {t.co2PerYear}: {number(c.annual_co2_kg, langKey)} kg
                        </span>
                      )}
                      {c.annual_time_minutes != null && (
                        <span style={{ fontSize: '0.72rem', color: colors.textMuted, backgroundColor: colors.inputBg, borderRadius: '999px', padding: '0.2rem 0.6rem' }}>
                          {t.timePerYear}: {number(Math.round(c.annual_time_minutes / 60), langKey)} {t.hoursShort}
                        </span>
                      )}
                    </div>
                  )}

                  <div className="portfolio-compare" style={{ marginBottom: '1rem' }}>
                    <div style={{ backgroundColor: colors.inputBg, borderRadius: '14px', padding: '0.75rem 1rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.04em', display: 'block', marginBottom: '0.3rem' }}>{t.todayLabel}</span>
                      <div style={{ fontSize: '1.1rem', fontWeight: '800' }}>{euro(c.actual_annual_cost_eur, { lang: langKey })}</div>
                      {currentSubs.map((s) => (
                        <div key={s.provider_plan_name} style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.15rem' }}>{s.provider_plan_name}</div>
                      ))}
                    </div>
                    <div style={{ backgroundColor: colors.inputBg, borderRadius: '14px', padding: '0.75rem 1rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.04em', display: 'block', marginBottom: '0.3rem' }}>{t.noSubLabel}</span>
                      <div style={{ fontSize: '1.1rem', fontWeight: '800' }}>{euro(c.no_subscription_annual_cost_eur, { lang: langKey })}</div>
                      <div style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.15rem' }}>{isDE ? 'reine Einzelfahrten' : 'pure pay-per-trip'}</div>
                    </div>
                  </div>

                  {showBestAlternative && (
                    <div style={{ border: `1px dashed ${colors.accentCyan}`, borderRadius: '14px', padding: '0.75rem 1rem', marginBottom: '1rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '700', color: colors.accentCyan, letterSpacing: '0.04em' }}>
                        {(bestDiffersFromCheapest ? t.recommendedBadge : t.bestAlt.toUpperCase())}
                      </span>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.3rem' }}>
                        <span style={{ fontWeight: '600', fontSize: '0.9rem' }}>{best.provider_plan_name}</span>
                        <span style={{ fontWeight: '800', fontSize: '1rem', color: colors.accentCyan }}>{euro(best.estimated_annual_cost_eur, { lang: langKey })}</span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.2rem' }}>
                        {best.annual_savings_vs_current_eur == null
                          ? t.noCurrentToCompare
                          : best.annual_savings_vs_current_eur >= 0
                            ? (isDE ? `Spart ${euro(best.annual_savings_vs_current_eur, { lang: langKey })} ${t.vsCurrent}` : `Saves ${euro(best.annual_savings_vs_current_eur, { lang: langKey })} ${t.vsCurrent}`)
                            : (isDE ? `${euro(Math.abs(best.annual_savings_vs_current_eur), { lang: langKey })} teurer ${t.vsCurrent}` : `${euro(Math.abs(best.annual_savings_vs_current_eur), { lang: langKey })} more expensive ${t.vsCurrent}`)}
                      </div>
                      {bestDiffersFromCheapest && (
                        <div style={{ fontSize: '0.72rem', color: colors.textMuted, marginTop: '0.35rem', fontStyle: 'italic' }}>
                          {t.recommendedNotCheapest}
                        </div>
                      )}
                    </div>
                  )}

                  {alternatives.length > 0 ? (
                    <div>
                      <button
                        onClick={() => toggleAlternatives(c.category)}
                        style={{
                          display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%',
                          background: 'none', border: 'none', padding: 0, cursor: 'pointer', color: 'inherit', font: 'inherit',
                        }}
                      >
                        <span style={{ fontSize: '0.68rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em' }}>
                          {(isAlternativesExpanded ? t.hideAlternatives : t.showAlternatives(alternatives.length)).toUpperCase()}
                        </span>
                        <ChevronDown
                          size={16}
                          style={{ color: colors.textMuted, transition: 'transform 0.15s', transform: isAlternativesExpanded ? 'rotate(180deg)' : 'none' }}
                        />
                      </button>
                      {isAlternativesExpanded && (
                        <div style={{ overflowX: 'auto', marginTop: '0.6rem' }}>
                          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                            <thead>
                              <tr style={{ textAlign: 'left', color: colors.textMuted }}>
                                <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600' }}>{t.plan}</th>
                                <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600', textAlign: 'right' }}>{t.perYear}</th>
                                <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600', textAlign: 'right' }}>{t.vsCurrent}</th>
                              </tr>
                            </thead>
                            <tbody>
                              {alternatives.map((a) => {
                                const isRecommended = bestDiffersFromCheapest && a.provider_plan_name === best.provider_plan_name
                                return (
                                  <tr key={a.provider_plan_name} style={{ borderTop: `1px solid ${colors.border}`, backgroundColor: isRecommended ? `${colors.accentCyan}12` : 'transparent' }}>
                                    <td style={{ padding: '0.4rem 0.5rem', fontWeight: isRecommended ? '700' : '400' }}>
                                      {a.provider_plan_name}
                                      {isRecommended && (
                                        <span style={{ marginLeft: '0.4rem', fontSize: '0.62rem', fontWeight: '700', color: colors.accentCyan }}>★ {t.recommendedBadge}</span>
                                      )}
                                    </td>
                                    <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right' }}>{euro(a.estimated_annual_cost_eur, { lang: langKey })}</td>
                                    {a.annual_savings_vs_current_eur == null ? (
                                      <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', color: colors.textMuted, fontStyle: 'italic' }} title={t.noCurrentToCompare}>
                                        {'–'}
                                      </td>
                                    ) : (
                                      <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', color: a.annual_savings_vs_current_eur >= 0 ? colors.successGreen : colors.accentRed, fontWeight: '600' }}>
                                        {a.annual_savings_vs_current_eur <= 0 ? '+' : ''}{euro(-a.annual_savings_vs_current_eur, { lang: langKey })}
                                      </td>
                                    )}
                                  </tr>
                                )
                              })}
                            </tbody>
                          </table>
                        </div>
                      )}
                    </div>
                  ) : (
                    <p style={{ fontSize: '0.78rem', color: colors.textMuted }}>{t.noAlternatives}</p>
                  )}
                </div>
              )
            })}

            {/* Cross-category modal-shift suggestions */}
            {modalShiftSuggestions.length > 0 && (
              <div style={cardStyle}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '0.15rem' }}>{t.modalShiftTitle}</h3>
                <p style={{ fontSize: '0.8rem', color: colors.textMuted, marginBottom: '0.35rem' }}>{t.modalShiftSub}</p>
                <p style={{ fontSize: '0.75rem', color: colors.textMuted, marginBottom: '1.1rem', fontWeight: '600' }}>
                  {t.priorityIntro(
                    preferences.cost_priority ?? 50,
                    preferences.co2_priority ?? 50,
                    preferences.convenience_priority ?? 50,
                  )}
                </p>
                <div style={{ display: 'grid', gap: '0.9rem' }}>
                  {modalShiftSuggestions.map((s) => {
                    const shift = s.suggested_shift
                    const costDelta = shift ? shift.annual_cost_eur - (s.stay_annual_cost_eur ?? 0) : null
                    const co2Delta = shift && shift.annual_co2_kg != null && s.stay_annual_co2_kg != null
                      ? shift.annual_co2_kg - s.stay_annual_co2_kg : null
                    const timeDeltaHours = shift && shift.annual_time_minutes != null && s.stay_annual_time_minutes != null
                      ? Math.round((shift.annual_time_minutes - s.stay_annual_time_minutes) / 60) : null
                    const deltaColor = (d) => (d <= 0 ? colors.successGreen : colors.accentRed)
                    const excluded = s.excluded_candidates || []

                    return (
                      <div key={s.from_category} style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '0.9rem' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                          <span style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: modeColor(s.from_category, isDark), display: 'inline-block' }} />
                          <span style={{ fontWeight: '700', fontSize: '0.9rem' }}>{modeLabel(s.from_category, langKey)}</span>
                        </div>

                        {shift ? (
                          <div style={{ backgroundColor: colors.inputBg, borderRadius: '14px', padding: '0.75rem 1rem' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
                              <span style={{ fontWeight: '600', fontSize: '0.88rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: modeColor(shift.to_category, isDark), display: 'inline-block' }} />
                                {t.shiftTo(modeLabel(shift.to_category, langKey))}
                              </span>
                              <span style={{ textAlign: 'right' }}>
                                <div style={{ fontWeight: '800', fontSize: '0.95rem' }}>{euro(shift.annual_cost_eur, { lang: langKey })}</div>
                                <div style={{ fontSize: '0.65rem', color: colors.textMuted, fontWeight: '600' }}>{t.perYear}</div>
                              </span>
                            </div>
                            <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.6rem', flexWrap: 'wrap' }}>
                              <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', fontWeight: '700', color: deltaColor(costDelta), backgroundColor: `${deltaColor(costDelta)}22`, padding: '0.25rem 0.55rem', borderRadius: '999px' }}>
                                <Euro size={11} />
                                {costDelta > 0 ? '+' : ''}{euro(costDelta, { lang: langKey })} {t.perYear}
                              </span>
                              {co2Delta != null && (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', fontWeight: '700', color: deltaColor(co2Delta), backgroundColor: `${deltaColor(co2Delta)}22`, padding: '0.25rem 0.55rem', borderRadius: '999px' }}>
                                  <Leaf size={11} />
                                  {co2Delta > 0 ? '+' : ''}{number(co2Delta, langKey)} kg {t.co2PerYear}
                                </span>
                              )}
                              {timeDeltaHours != null && (
                                <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', fontWeight: '700', color: deltaColor(timeDeltaHours), backgroundColor: `${deltaColor(timeDeltaHours)}22`, padding: '0.25rem 0.55rem', borderRadius: '999px' }}>
                                  <Clock size={11} />
                                  {timeDeltaHours > 0 ? '+' : ''}{number(timeDeltaHours, langKey)} {t.hoursShort} {t.timePerYear}
                                </span>
                              )}
                            </div>
                            {shift.feasibility?.confidence === 'low' && (
                              <div style={{ fontSize: '0.68rem', color: colors.textMuted, marginTop: '0.4rem', fontStyle: 'italic' }}>
                                ({t.confidenceLow}{shift.feasibility?.reasoning ? `: ${shift.feasibility.reasoning}` : ''})
                              </div>
                            )}
                          </div>
                        ) : (
                          <p style={{ fontSize: '0.8rem', color: colors.textMuted }}>{t.noBetterShift}</p>
                        )}

                        {excluded.length > 0 && (
                          <div style={{ fontSize: '0.7rem', color: colors.textMuted, marginTop: '0.5rem' }}>
                            {t.excludedNote} {excluded.map((e) => modeLabel(e.to_category, langKey)).join(', ')}
                          </div>
                        )}
                      </div>
                    )
                  })}
                </div>
              </div>
            )}

            {/* Forecast + life events */}
            <div style={cardStyle}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.15rem' }}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: '700' }}>{t.forecastTitle}</h3>
                <Calendar size={18} style={{ color: colors.accentCyan }} />
              </div>
              <p style={{ fontSize: '0.8rem', color: colors.textMuted, marginBottom: '1.1rem' }}>{t.forecastSub}</p>

              {!baselineScenario ? (
                <p style={{ fontSize: '0.85rem', color: colors.textMuted }}>{t.noForecast}</p>
              ) : (
                <>
                  <div style={{ overflowX: 'auto', marginBottom: lifeEventDetected ? '1.25rem' : 0 }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem' }}>
                      <thead>
                        <tr style={{ textAlign: 'left', color: colors.textMuted }}>
                          <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600' }}>{t.mode}</th>
                          <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600', textAlign: 'right' }}>{lifeEventDetected ? t.baseline : t.tripsPerYear}</th>
                          {lifeEventDetected && <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600', textAlign: 'right' }}>{t.afterEvent}</th>}
                        </tr>
                      </thead>
                      <tbody>
                        {baselineScenario.predicted_demand.map((pd) => {
                          const afterPd = eventScenario?.predicted_demand?.find((x) => x.mode === pd.mode)
                          return (
                            <tr key={pd.mode} style={{ borderTop: `1px solid ${colors.border}` }}>
                              <td style={{ padding: '0.4rem 0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                                <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: modeColor(pd.mode, isDark), display: 'inline-block' }} />
                                {modeLabel(pd.mode, langKey)}
                              </td>
                              <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right' }}>{number(pd.estimated_trips, langKey)}</td>
                              {lifeEventDetected && (
                                <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', fontWeight: afterPd && afterPd.estimated_trips !== pd.estimated_trips ? '700' : '400', color: afterPd && afterPd.estimated_trips > pd.estimated_trips ? colors.accentCyan : colors.text }}>
                                  {afterPd ? number(afterPd.estimated_trips, langKey) : '—'}
                                </td>
                              )}
                            </tr>
                          )
                        })}
                      </tbody>
                    </table>
                  </div>

                  {lifeEventDetected ? (
                    <div style={{ border: `1px dashed ${colors.accentCyan}`, borderRadius: '14px', padding: '0.9rem 1rem' }}>
                      <span style={{ fontSize: '0.75rem', fontWeight: '700', color: colors.accentCyan }}>{t.lifeEventTitle(flags.life_event_type)}</span>
                      {(() => {
                        // Bilingual field (rationale_en/rationale_de) — falls back to
                        // rationale_en for older persisted rows from before the split.
                        const rationale = (isDE ? forecaster.rationale_de : forecaster.rationale_en) || forecaster.rationale_en
                        return rationale && (
                          <p style={{ fontSize: '0.82rem', color: colors.text, marginTop: '0.5rem', lineHeight: '1.5' }}>{rationale}</p>
                        )
                      })()}
                      {flags.recommend_re_evaluation_in_days && (
                        <p style={{ fontSize: '0.78rem', color: colors.textMuted, marginTop: '0.5rem' }}>{t.reEval(flags.recommend_re_evaluation_in_days)}</p>
                      )}
                    </div>
                  ) : (
                    <p style={{ fontSize: '0.82rem', color: colors.textMuted }}>{t.noLifeEvent}</p>
                  )}
                </>
              )}
            </div>

            {memo && (
              <div style={cardStyle}>
                <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '1rem' }}>{t.fullMemo}</h3>
                <Markdown text={memo} />
              </div>
            )}
          </>
        )}
      </main>
    </div>
  )
}
