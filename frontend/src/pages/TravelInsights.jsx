import React, { useMemo, useState } from 'react'
import { ChevronLeft, Route, Leaf, Wallet, MapPin } from 'lucide-react'
import { euro, number, co2 } from '../lib/format'
import { sortModes, modeLabel, modeColor } from '../lib/travelModes'
import StackedBarChart from '../components/insights/StackedBarChart'
import LineChart from '../components/insights/LineChart'

const LOCALE = { de: 'de-DE', en: 'en-IE' }

function monthLabel(key, lang) {
  const [y, m] = key.split('-').map(Number)
  return new Intl.DateTimeFormat(LOCALE[lang] || LOCALE.de, { month: 'short' }).format(new Date(y, m - 1, 1))
}

// Builds the last-12-months series from analyst.monthly_mode_breakdown, plus
// per-month trip/distance/co2/cost aggregates for the trend charts and table.
function useMonthlyDataset(analyst, lang) {
  return useMemo(() => {
    const mmb = analyst?.monthly_mode_breakdown || {}
    const monthKeys = Object.keys(mmb).sort().slice(-12)
    const series = sortModes([...new Set(monthKeys.flatMap((k) => Object.keys(mmb[k] || {})))])

    const months = monthKeys.map((key) => {
      const values = mmb[key] || {}
      let trips = {}, distance = 0, co2Kg = 0, cost = 0
      for (const mode of Object.keys(values)) {
        const v = values[mode]
        trips[mode] = v.trips || 0
        distance += v.distance_km || 0
        co2Kg += v.co2_kg || 0
        cost += v.intrinsic_cost_eur || 0
      }
      return { key, label: monthLabel(key, lang), trips, distance, co2: co2Kg, cost }
    })

    const totals = months.reduce((acc, m) => ({
      trips: acc.trips + Object.values(m.trips).reduce((s, v) => s + v, 0),
      distance: acc.distance + m.distance,
      co2: acc.co2 + m.co2,
      cost: acc.cost + m.cost,
    }), { trips: 0, distance: 0, co2: 0, cost: 0 })

    return { months, series, totals }
  }, [analyst, lang])
}

export default function TravelInsights({ analysis, lang, colors, isDark, onBack }) {
  const [showTable, setShowTable] = useState(false)
  const langKey = lang === 'DE' ? 'de' : 'en'
  const t = lang === 'DE'
    ? {
      back: 'Zurück zum Dashboard', title: 'Wie du reist', subtitle: 'Letzte 12 Monate im Detail',
      trips: 'Fahrten', distance: 'Distanz', co2: 'CO₂', cost: 'Kosten',
      tripsByMode: 'Fahrten pro Monat nach Verkehrsmittel', distanceTrend: 'Distanz pro Monat',
      co2Trend: 'CO₂ pro Monat', costTrend: 'Kosten pro Monat (vor Abo-Deckung)',
      showTable: 'Als Tabelle anzeigen', showCharts: 'Als Diagramm anzeigen',
      month: 'Monat', noData: 'Für diesen Zeitraum liegen noch keine Reisedaten vor.',
    }
    : {
      back: 'Back to dashboard', title: 'How you travel', subtitle: 'Last 12 months in detail',
      trips: 'Trips', distance: 'Distance', co2: 'CO₂', cost: 'Cost',
      tripsByMode: 'Trips per month by mode', distanceTrend: 'Distance per month',
      co2Trend: 'CO₂ per month', costTrend: 'Cost per month (before subscription coverage)',
      showTable: 'Show as table', showCharts: 'Show as chart',
      month: 'Month', noData: 'No travel data available for this period yet.',
    }

  const analyst = analysis?.raw_agent_payloads?.analyst?.output || null
  const { months, series, totals } = useMonthlyDataset(analyst, langKey)

  const cardStyle = { backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '24px', padding: '1.5rem' }
  const kpi = (icon, label, value) => (
    <div style={{ ...cardStyle, padding: '1.1rem', display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <span style={{ fontSize: '0.7rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em' }}>{label}</span>
        <span style={{ color: colors.accentCyan }}>{icon}</span>
      </div>
      <div style={{ fontSize: '1.4rem', fontWeight: '800', letterSpacing: '-0.02em' }}>{value}</div>
    </div>
  )

  return (
    <div style={{ backgroundColor: colors.bg, color: colors.text, fontFamily: 'system-ui, -apple-system, sans-serif', minHeight: '100vh' }}>
      <style>{`
        .insights-container { display: grid; grid-template-columns: 1fr; gap: 1.25rem; width: 100%; max-width: 480px; margin: 0 auto; padding: 1.5rem 1.25rem 3rem; box-sizing: border-box; }
        .insights-kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
        @media (min-width: 768px) {
          .insights-container { max-width: 1100px; }
          .insights-kpis { grid-template-columns: repeat(4, 1fr); }
        }
      `}</style>

      <header style={{ padding: '1.25rem 1.5rem', borderBottom: `1px solid ${colors.border}`, position: 'sticky', top: 0, backgroundColor: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.85)', backdropFilter: 'blur(12px)', zIndex: 10 }}>
        <button onClick={onBack} className="premium-back-btn" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '12px', color: colors.textMuted, padding: '0.55rem 0.95rem', fontSize: '0.88rem', fontWeight: '600', cursor: 'pointer' }}>
          <ChevronLeft size={16} /> {t.back}
        </button>
      </header>

      <main className="insights-container">
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: '800', letterSpacing: '-0.02em', marginBottom: '0.25rem' }}>{t.title}</h1>
          <p style={{ color: colors.textMuted, fontSize: '0.9rem' }}>{t.subtitle}</p>
        </div>

        {months.length === 0 ? (
          <div style={cardStyle}>{t.noData}</div>
        ) : (
          <>
            <div className="insights-kpis">
              {kpi(<Route size={14} />, t.trips.toUpperCase(), number(totals.trips, langKey))}
              {kpi(<MapPin size={14} />, t.distance.toUpperCase(), `${number(totals.distance, langKey)} km`)}
              {kpi(<Leaf size={14} />, t.co2.toUpperCase(), co2(totals.co2, langKey))}
              {kpi(<Wallet size={14} />, t.cost.toUpperCase(), euro(totals.cost, { lang: langKey }))}
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <button
                onClick={() => setShowTable((v) => !v)}
                style={{ backgroundColor: 'transparent', border: `1px solid ${colors.border}`, color: colors.accentCyan, borderRadius: '12px', padding: '0.5rem 0.9rem', fontSize: '0.8rem', fontWeight: '700', cursor: 'pointer' }}
              >
                {showTable ? t.showCharts : t.showTable}
              </button>
            </div>

            {showTable ? (
              <div style={{ ...cardStyle, overflowX: 'auto' }}>
                <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.82rem', fontVariantNumeric: 'tabular-nums' }}>
                  <thead>
                    <tr style={{ textAlign: 'left', color: colors.textMuted, borderBottom: `1px solid ${colors.border}` }}>
                      <th style={{ padding: '0.5rem 0.6rem' }}>{t.month}</th>
                      {series.map((m) => (
                        <th key={m} style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{modeLabel(m, langKey)}</th>
                      ))}
                      <th style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{t.distance} (km)</th>
                      <th style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{t.co2} (kg)</th>
                      <th style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{t.cost}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {months.map((mo) => (
                      <tr key={mo.key} style={{ borderBottom: `1px solid ${colors.border}` }}>
                        <td style={{ padding: '0.5rem 0.6rem', fontWeight: 600 }}>{mo.label}</td>
                        {series.map((m) => (
                          <td key={m} style={{ padding: '0.5rem 0.6rem', textAlign: 'right', color: colors.textMuted }}>{mo.trips[m] || 0}</td>
                        ))}
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{number(mo.distance, langKey)}</td>
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{number(mo.co2, langKey)}</td>
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{euro(mo.cost, { lang: langKey })}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <>
                <div style={cardStyle}>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '1rem' }}>{t.tripsByMode}</h3>
                  <StackedBarChart
                    data={months.map((mo) => ({ key: mo.key, label: mo.label, values: mo.trips }))}
                    series={series}
                    lang={langKey}
                    isDark={isDark}
                    colors={colors}
                    valueFormatter={(v) => number(v, langKey)}
                    unitLabel={t.trips}
                  />
                </div>

                <div style={cardStyle}>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '1rem' }}>{t.distanceTrend}</h3>
                  <LineChart
                    data={months.map((mo) => ({ key: mo.key, label: mo.label, value: mo.distance }))}
                    color={colors.accentCyan}
                    colors={colors}
                    valueFormatter={(v) => `${number(v, langKey)} km`}
                    unitLabel="km"
                  />
                </div>

                <div style={cardStyle}>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '1rem' }}>{t.co2Trend}</h3>
                  <LineChart
                    data={months.map((mo) => ({ key: mo.key, label: mo.label, value: mo.co2 }))}
                    color={colors.successGreen}
                    colors={colors}
                    valueFormatter={(v) => co2(v, langKey)}
                    unitLabel="kg"
                  />
                </div>

                <div style={cardStyle}>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '1rem' }}>{t.costTrend}</h3>
                  <LineChart
                    data={months.map((mo) => ({ key: mo.key, label: mo.label, value: mo.cost }))}
                    color={modeColor('bike_sharing', isDark)}
                    colors={colors}
                    valueFormatter={(v) => euro(v, { lang: langKey })}
                    unitLabel="€"
                  />
                </div>
              </>
            )}
          </>
        )}
      </main>
    </div>
  )
}
