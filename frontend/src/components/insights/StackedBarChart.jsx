import React, { useRef, useState } from 'react'
import { modeColor, modeLabel } from '../../lib/travelModes'

// Rounded-top / square-baseline rect path — the "4px rounded data-end, square
// at the baseline" mark spec, applied only to a stack's topmost segment.
function roundedTopPath(x, y, w, h, r) {
  const rr = Math.min(r, w / 2, Math.max(h, 0))
  if (rr <= 0) return `M${x},${y + h} L${x},${y} L${x + w},${y} L${x + w},${y + h} Z`
  return `M${x},${y + h} L${x},${y + rr} Q${x},${y} ${x + rr},${y} L${x + w - rr},${y} Q${x + w},${y} ${x + w},${y + rr} L${x + w},${y + h} Z`
}

// Stacked monthly bar chart (part-to-whole per month, categorical series).
// data: [{ key: '2025-07', label: 'Jul', values: { mode: number } }, ...]
export default function StackedBarChart({ data, series, lang, isDark, colors, valueFormatter = (v) => String(v), unitLabel = '' }) {
  const wrapRef = useRef(null)
  const [tip, setTip] = useState(null)

  const W = 640
  const H = 220
  const padL = 34
  const padB = 26
  const padT = 10
  const plotW = W - padL - 8
  const plotH = H - padT - padB

  const totals = data.map((d) => series.reduce((s, m) => s + (d.values[m] || 0), 0))
  const rawMax = Math.max(1, ...totals)
  // Round the axis ceiling to a clean step (skill: "round to clean numbers").
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawMax)))
  const niceMax = Math.ceil(rawMax / (magnitude / 2)) * (magnitude / 2)

  const n = Math.max(data.length, 1)
  const slot = plotW / n
  const barW = Math.min(24, slot * 0.55)
  const gridSteps = [0, 0.5, 1]

  const showTip = (e, content) => {
    const rect = wrapRef.current.getBoundingClientRect()
    setTip({ x: e.clientX - rect.left, y: e.clientY - rect.top, ...content })
  }

  return (
    <div ref={wrapRef} style={{ position: 'relative' }}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="auto" role="img" aria-label={unitLabel}>
        {gridSteps.map((s) => {
          const y = padT + plotH * (1 - s)
          return (
            <g key={s}>
              <line x1={padL} y1={y} x2={W - 4} y2={y} stroke={colors.border} strokeWidth="1" />
              <text x={padL - 6} y={y + 3} textAnchor="end" fontSize="9" fill={colors.textMuted}>
                {Math.round(niceMax * s)}
              </text>
            </g>
          )
        })}

        {data.map((d, i) => {
          const x = padL + i * slot + (slot - barW) / 2
          const present = series.filter((m) => (d.values[m] || 0) > 0)
          let yCursor = padT + plotH
          return (
            <g key={d.key}>
              {present.map((m, si) => {
                const v = d.values[m] || 0
                const segH = (v / niceMax) * plotH
                const isTop = si === present.length - 1
                const yTop = yCursor - segH
                // 2px surface gap between stacked segments (skip on the topmost —
                // its own top edge is the rounded cap, not a neighbor boundary).
                const gapAdjustedH = isTop ? segH : Math.max(segH - 2, 0)
                const gapAdjustedY = isTop ? yTop : yTop + 2
                const fill = modeColor(m, isDark)
                yCursor = yTop
                return (
                  <path
                    key={m}
                    d={isTop
                      ? roundedTopPath(x, gapAdjustedY, barW, gapAdjustedH, 4)
                      : roundedTopPath(x, gapAdjustedY, barW, gapAdjustedH, 0)}
                    fill={fill}
                    style={{ cursor: 'pointer' }}
                    onMouseMove={(e) => showTip(e, { title: d.label, label: modeLabel(m, lang), value: valueFormatter(v), color: fill })}
                    onMouseLeave={() => setTip(null)}
                  />
                )
              })}
            </g>
          )
        })}

        {data.map((d, i) => (
          <text key={d.key} x={padL + i * slot + slot / 2} y={H - 8} textAnchor="middle" fontSize="9.5" fill={colors.textMuted}>
            {d.label}
          </text>
        ))}
      </svg>

      {/* Legend — always present for 2+ series, mirrors the mark (swatch = bar) */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.6rem', marginTop: '0.5rem', justifyContent: 'center' }}>
        {series.map((m) => (
          <div key={m} style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', color: colors.textMuted }}>
            <span style={{ width: 9, height: 9, borderRadius: 2, backgroundColor: modeColor(m, isDark), display: 'inline-block' }} />
            {modeLabel(m, lang)}
          </div>
        ))}
      </div>

      {tip && (
        <div style={{
          position: 'absolute', left: tip.x, top: tip.y, transform: 'translate(-50%, -110%)',
          backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '10px',
          padding: '0.45rem 0.65rem', fontSize: '0.78rem', color: colors.text, pointerEvents: 'none',
          boxShadow: '0 6px 20px rgba(0,0,0,0.18)', whiteSpace: 'nowrap', zIndex: 5,
        }}>
          <div style={{ fontWeight: 700 }}>{tip.value} <span style={{ fontWeight: 400, color: colors.textMuted }}>{unitLabel}</span></div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', color: colors.textMuted, marginTop: '0.1rem' }}>
            <span style={{ width: 8, height: 2, backgroundColor: tip.color, display: 'inline-block' }} />
            {tip.label} · {tip.title}
          </div>
        </div>
      )}
    </div>
  )
}
