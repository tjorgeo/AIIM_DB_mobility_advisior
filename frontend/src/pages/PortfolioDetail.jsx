import React from 'react'
import { ChevronLeft, Wallet, PiggyBank, TrendingUp, Calendar } from 'lucide-react'
import { euro, number } from '../lib/format'
import { modeColor, modeLabel } from '../lib/travelModes'
import Markdown from '../components/chat/Markdown'

function recMeta(rec, colors, isDE) {
  switch (rec) {
    case 'keep_current': return { label: isDE ? 'Behalten' : 'Keep', color: colors.successGreen }
    case 'switch_to_alternative': return { label: isDE ? 'Abo wechseln' : 'Switch plan', color: colors.accentCyan }
    case 'cancel_current_go_pay_as_you_go': return { label: isDE ? 'Kündigen' : 'Cancel', color: colors.accentRed }
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
      todayLabel: 'AKTUELL', noSubLabel: 'OHNE ABO',
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
    }
    : {
      back: 'Back to dashboard', title: 'Cost-Optimized Portfolio', subtitle: "Today's costs, alternatives compared, and what's ahead",
      current: 'Current', optimized: 'Optimized', savings: 'Savings',
      categoryTrips: (n) => `Based on ${number(n, langKey)} trips/year`,
      todayLabel: 'CURRENT', noSubLabel: 'NO SUBSCRIPTION',
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
    }

  const summary = analysis?.summary || null
  const categoryAnalysis = summary?.category_subscription_analysis || []
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
              const best = c.cheapest_alternative

              return (
                <div key={c.category} style={cardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: swatch, display: 'inline-block' }} />
                      <h3 style={{ fontSize: '1.05rem', fontWeight: '700' }}>{modeLabel(c.category, langKey)}</h3>
                    </div>
                    <span style={{ fontSize: '0.72rem', fontWeight: '700', color: meta.color, backgroundColor: `${meta.color}18`, padding: '0.25rem 0.6rem', borderRadius: '999px' }}>
                      {meta.label}
                    </span>
                  </div>
                  <p style={{ fontSize: '0.78rem', color: colors.textMuted, marginBottom: '1rem' }}>{t.categoryTrips(c.annual_trips)}</p>

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

                  {best && (
                    <div style={{ border: `1px dashed ${colors.accentCyan}`, borderRadius: '14px', padding: '0.75rem 1rem', marginBottom: '1rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '700', color: colors.accentCyan, letterSpacing: '0.04em' }}>{t.bestAlt.toUpperCase()}</span>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.3rem' }}>
                        <span style={{ fontWeight: '600', fontSize: '0.9rem' }}>{best.provider_plan_name}</span>
                        <span style={{ fontWeight: '800', fontSize: '1rem', color: colors.accentCyan }}>{euro(best.estimated_annual_cost_eur, { lang: langKey })}</span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.2rem' }}>
                        {best.annual_savings_vs_current_eur >= 0
                          ? (isDE ? `Spart ${euro(best.annual_savings_vs_current_eur, { lang: langKey })} ${t.vsCurrent}` : `Saves ${euro(best.annual_savings_vs_current_eur, { lang: langKey })} ${t.vsCurrent}`)
                          : (isDE ? `${euro(Math.abs(best.annual_savings_vs_current_eur), { lang: langKey })} teurer ${t.vsCurrent}` : `${euro(Math.abs(best.annual_savings_vs_current_eur), { lang: langKey })} more expensive ${t.vsCurrent}`)}
                      </div>
                    </div>
                  )}

                  {alternatives.length > 0 ? (
                    <div>
                      <span style={{ fontSize: '0.68rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em', display: 'block', marginBottom: '0.5rem' }}>
                        {t.allAlternatives.toUpperCase()}
                      </span>
                      <div style={{ overflowX: 'auto' }}>
                        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.8rem' }}>
                          <thead>
                            <tr style={{ textAlign: 'left', color: colors.textMuted }}>
                              <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600' }}>{t.plan}</th>
                              <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600', textAlign: 'right' }}>{t.perYear}</th>
                              <th style={{ padding: '0.35rem 0.5rem', fontWeight: '600', textAlign: 'right' }}>{t.vsCurrent}</th>
                            </tr>
                          </thead>
                          <tbody>
                            {alternatives.map((a) => (
                              <tr key={a.provider_plan_name} style={{ borderTop: `1px solid ${colors.border}` }}>
                                <td style={{ padding: '0.4rem 0.5rem' }}>{a.provider_plan_name}</td>
                                <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right' }}>{euro(a.estimated_annual_cost_eur, { lang: langKey })}</td>
                                <td style={{ padding: '0.4rem 0.5rem', textAlign: 'right', color: a.annual_savings_vs_current_eur >= 0 ? '#0ca30c' : colors.accentRed, fontWeight: '600' }}>
                                  {a.annual_savings_vs_current_eur >= 0 ? '+' : ''}{euro(a.annual_savings_vs_current_eur, { lang: langKey })}
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <p style={{ fontSize: '0.78rem', color: colors.textMuted }}>{t.noAlternatives}</p>
                  )}
                </div>
              )
            })}

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
                      {forecaster.rationale && (
                        <p style={{ fontSize: '0.82rem', color: colors.text, marginTop: '0.5rem', lineHeight: '1.5' }}>{forecaster.rationale}</p>
                      )}
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
