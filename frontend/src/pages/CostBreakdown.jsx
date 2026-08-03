import React, { useMemo, useState } from 'react'
import { ChevronLeft, Wallet, CreditCard, Receipt, PiggyBank, CheckCircle2, AlertTriangle } from 'lucide-react'
import { euro } from '../lib/format'
import { modeColor, modeLabel } from '../lib/travelModes'

// Ranked, percent-of-total bar list (part-to-whole, categorical) — same visual
// language as Dashboard's "How you travel" bars, reused here for cost composition.
function ComposedBarList({ items, colors, total }) {
  const safeTotal = total || 1
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.9rem' }}>
      {items.map((it) => {
        const pct = Math.round((it.value / safeTotal) * 100)
        return (
          <div key={it.key}>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.35rem', fontWeight: '500' }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: colors.text }}>
                <span style={{ width: 9, height: 9, borderRadius: 2, backgroundColor: it.color, display: 'inline-block', flexShrink: 0 }} />
                {it.label}
              </span>
              <span style={{ color: colors.textMuted }}>
                <span style={{ color: colors.text, fontWeight: '600' }}>{euro(it.value, { lang: it.lang })}</span> · {pct}%
              </span>
            </div>
            <div style={{ width: '100%', height: '8px', backgroundColor: colors.border, borderRadius: '4px', overflow: 'hidden' }}>
              <div style={{ width: `${pct}%`, height: '100%', backgroundColor: it.color, borderRadius: '4px' }} />
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default function CostBreakdown({ analysis, lang, colors, isDark, onBack, chatSlotRef }) {
  const [showTable, setShowTable] = useState(false)
  const langKey = lang === 'DE' ? 'de' : 'en'
  const t = lang === 'DE'
    ? {
      back: 'Zurück zum Dashboard', title: 'Deine jährlichen Ausgaben', subtitle: 'Wie sich deine Kosten zusammensetzen',
      total: 'Gesamt / Jahr', subs: 'Abo-Kosten', payPerUse: 'Nicht durch Abo gedeckt', realized: 'Ersparnis durch Abos',
      composition: 'Kosten-Zusammensetzung', composeSub: 'Was von deinen jährlichen Ausgaben wohin fließt',
      payPerUseLabel: 'Pay-per-use / nicht gedeckt',
      payPerUseFor: (modeLbl) => `${modeLbl} (Pay-per-use)`,
      valueCheck: 'Deine Abos im Check', valueSub: 'Lohnt sich das Abo gegenüber Einzelfahrten?',
      worthIt: (v) => `Spart ${euro(v, { lang: langKey })}`,
      notWorthIt: (v) => `${euro(v, { lang: langKey })} Mehrkosten ggü. Einzelfahrten`,
      showTable: 'Als Tabelle anzeigen', showCharts: 'Als Diagramm anzeigen',
      subscription: 'Abo', annualCost: 'Kosten/Jahr', covered: 'Gedeckter Wert', net: 'Netto',
      noData: 'Für diesen Zeitraum liegen noch keine Ausgabendaten vor.',
    }
    : {
      back: 'Back to dashboard', title: 'Your annual spend', subtitle: 'How these costs break down',
      total: 'Total / year', subs: 'Subscription costs', payPerUse: 'Not covered by a subscription', realized: 'Saved via subscriptions',
      composition: 'Cost composition', composeSub: 'Where your annual spend actually goes',
      payPerUseLabel: 'Pay-per-use / not covered',
      payPerUseFor: (modeLbl) => `${modeLbl} (pay-per-use)`,
      valueCheck: 'Your subscriptions, checked', valueSub: 'Is each subscription worth it vs. paying per trip?',
      worthIt: (v) => `Saves ${euro(v, { lang: langKey })}`,
      notWorthIt: (v) => `Costs ${euro(v, { lang: langKey })} extra vs. paying per trip`,
      showTable: 'Show as table', showCharts: 'Show as chart',
      subscription: 'Subscription', annualCost: 'Cost/yr', covered: 'Covered value', net: 'Net',
      noData: 'No spend data available for this period yet.',
    }

  const analyst = analysis?.raw_agent_payloads?.analyst?.output || null

  const { totalSpend, subCost, payPerUse, realizedSavings, composeItems, coverage } = useMemo(() => {
    const total = analyst?.current_annual_spend_eur || 0
    const subs = analyst?.subscription_costs_annual_eur || 0
    const cov = analyst?.subscription_coverage || []
    const realized = cov.reduce((s, c) => s + (c.realized_savings_eur || 0), 0)
    const remainder = Math.max(total - subs, 0)

    const items = cov
      .map((c) => ({
        key: c.subscription_id,
        label: c.provider_plan_name,
        value: c.annual_cost_eur || 0,
        color: modeColor(c.subscription_category, isDark),
        lang: langKey,
      }))
      .sort((a, b) => b.value - a.value)

    // Pay-per-use spend isn't one lump sum — break it down by travel mode using
    // the same effective_cost_eur figures the "Wie du reist" cost trend is built
    // from (summed across all months), so it reads as "which category costs you
    // pay-per-use money" instead of one opaque "not covered" bucket.
    const mmb = analyst?.monthly_mode_breakdown || {}
    const effectiveByMode = {}
    for (const monthModes of Object.values(mmb)) {
      for (const [mode, v] of Object.entries(monthModes)) {
        effectiveByMode[mode] = (effectiveByMode[mode] || 0) + (v.effective_cost_eur || 0)
      }
    }
    const payPerUseItems = Object.entries(effectiveByMode)
      .filter(([, v]) => v > 0.5)
      .map(([mode, v]) => ({
        key: `ppu-${mode}`,
        label: t.payPerUseFor(modeLabel(mode, langKey)),
        value: v,
        color: modeColor(mode, isDark),
        lang: langKey,
      }))
      .sort((a, b) => b.value - a.value)
    items.push(...payPerUseItems)

    // Reconciliation: keep the composition bars summing exactly to the "not
    // covered by a subscription" remainder even if per-mode effective costs
    // don't fully account for it (data-model edge cases, rounding).
    const payPerUseAccounted = payPerUseItems.reduce((s, it) => s + it.value, 0)
    const unaccounted = remainder - payPerUseAccounted
    if (unaccounted > 0.5) {
      items.push({ key: 'other', label: t.payPerUseLabel, value: unaccounted, color: isDark ? '#898781' : '#898781', lang: langKey })
    }

    return { totalSpend: total, subCost: subs, payPerUse: remainder, realizedSavings: realized, composeItems: items, coverage: cov }
  }, [analyst, isDark, langKey])

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
        .cost-container { display: grid; grid-template-columns: 1fr; gap: 1.25rem; min-width: 0; }
        .cost-kpis { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; min-width: 0; }
        /* Queries the actual space beside the chat sidebar (see
           .page-split__main in components.css), not the viewport, so this
           only goes 4-wide once there's really room for it. */
        @container page-main (min-width: 700px) {
          .cost-kpis { grid-template-columns: repeat(4, 1fr); }
        }
      `}</style>

      <header style={{ padding: '1.25rem 1.5rem', borderBottom: `1px solid ${colors.border}`, position: 'sticky', top: 0, backgroundColor: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.85)', backdropFilter: 'blur(12px)', zIndex: 10 }}>
        <button onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '12px', color: colors.textMuted, padding: '0.55rem 0.95rem', fontSize: '0.88rem', fontWeight: '600', cursor: 'pointer' }}>
          <ChevronLeft size={16} /> {t.back}
        </button>
      </header>

      <div className="page-split">
      <main className="cost-container page-split__main">
        <div>
          <h1 style={{ fontSize: '1.6rem', fontWeight: '800', letterSpacing: '-0.02em', marginBottom: '0.25rem' }}>{t.title}</h1>
          <p style={{ color: colors.textMuted, fontSize: '0.9rem' }}>{t.subtitle}</p>
        </div>

        {totalSpend === 0 ? (
          <div style={cardStyle}>{t.noData}</div>
        ) : (
          <>
            <div className="cost-kpis">
              {kpi(<Wallet size={14} />, t.total.toUpperCase(), euro(totalSpend, { lang: langKey }))}
              {kpi(<CreditCard size={14} />, t.subs.toUpperCase(), euro(subCost, { lang: langKey }))}
              {kpi(<Receipt size={14} />, t.payPerUse.toUpperCase(), euro(payPerUse, { lang: langKey }))}
              {kpi(<PiggyBank size={14} />, t.realized.toUpperCase(), euro(realizedSavings, { lang: langKey }))}
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
                      <th style={{ padding: '0.5rem 0.6rem' }}>{t.subscription}</th>
                      <th style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{t.annualCost}</th>
                      <th style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{t.covered}</th>
                      <th style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{t.net}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {coverage.map((c) => (
                      <tr key={c.subscription_id} style={{ borderBottom: `1px solid ${colors.border}` }}>
                        <td style={{ padding: '0.5rem 0.6rem', fontWeight: 600 }}>{c.provider_plan_name}</td>
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{euro(c.annual_cost_eur, { lang: langKey })}</td>
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{euro(c.covered_value_eur, { lang: langKey })}</td>
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right', color: c.net_savings_eur >= 0 ? '#0ca30c' : colors.accentRed, fontWeight: 700 }}>
                          {euro(c.net_savings_eur, { lang: langKey })}
                        </td>
                      </tr>
                    ))}
                    {payPerUse > 0.5 && (
                      <tr>
                        <td style={{ padding: '0.5rem 0.6rem', fontWeight: 600, color: colors.textMuted }}>{t.payPerUseLabel}</td>
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>{euro(payPerUse, { lang: langKey })}</td>
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>—</td>
                        <td style={{ padding: '0.5rem 0.6rem', textAlign: 'right' }}>—</td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            ) : (
              <>
                <div style={cardStyle}>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '0.15rem' }}>{t.composition}</h3>
                  <p style={{ fontSize: '0.8rem', color: colors.textMuted, marginBottom: '1.1rem' }}>{t.composeSub}</p>
                  <ComposedBarList items={composeItems} colors={colors} total={totalSpend} />
                </div>

                <div style={cardStyle}>
                  <h3 style={{ fontSize: '1.05rem', fontWeight: '700', marginBottom: '0.15rem' }}>{t.valueCheck}</h3>
                  <p style={{ fontSize: '0.8rem', color: colors.textMuted, marginBottom: '1.1rem' }}>{t.valueSub}</p>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                    {coverage.map((c) => {
                      const positive = (c.net_savings_eur || 0) >= 0
                      const statusColor = positive ? '#0ca30c' : colors.accentRed
                      return (
                        <div key={c.subscription_id} style={{ backgroundColor: colors.inputBg, borderRadius: '14px', padding: '0.75rem 1rem' }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                            <span style={{ fontWeight: '600', fontSize: '0.88rem' }}>{modeLabel(c.subscription_category, langKey)} — {c.provider_plan_name}</span>
                            <span style={{ fontWeight: '700', fontSize: '0.85rem', flexShrink: 0 }}>{euro(c.annual_cost_eur, { lang: langKey })}/{lang === 'DE' ? 'Jahr' : 'yr'}</span>
                          </div>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.4rem', fontSize: '0.78rem', color: statusColor, fontWeight: '600' }}>
                            {positive ? <CheckCircle2 size={13} /> : <AlertTriangle size={13} />}
                            {positive ? t.worthIt(c.net_savings_eur) : t.notWorthIt(Math.abs(c.net_savings_eur))}
                          </div>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </>
            )}
          </>
        )}
      </main>
      <aside className="page-split__sidebar" ref={chatSlotRef} />
      </div>
    </div>
  )
}
