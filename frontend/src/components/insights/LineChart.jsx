import React, { useRef, useState } from 'react'

// Monthly trend line(s) — sequential job (magnitude over time). Accepts one or
// more series sharing the same x-axis (months) and y-scale.
// series: [{ key, label, color, data: [{ key, label, value }, ...] }, ...]
export default function LineChart({ series, colors, valueFormatter = (v) => String(v), unitLabel = '' }) {
  const wrapRef = useRef(null)
  const [hoverIdx, setHoverIdx] = useState(null)

  const W = 640
  const H = 160
  const padL = 34
  const padR = 12
  const padT = 14
  const padB = 24
  const plotW = W - padL - padR
  const plotH = H - padT - padB
  const isMulti = series.length > 1

  const months = series[0]?.data || []
  const allValues = series.flatMap((s) => s.data.map((d) => d.value))
  const rawMax = Math.max(1, ...allValues)
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawMax)))
  const niceMax = Math.ceil(rawMax / (magnitude / 2)) * (magnitude / 2)

  const n = Math.max(months.length - 1, 1)
  const xAt = (i) => padL + (i / n) * plotW
  const yAt = (v) => padT + plotH * (1 - v / niceMax)

  const linePath = (d) => d.map((pt, i) => `${i === 0 ? 'M' : 'L'}${xAt(i)},${yAt(pt.value)}`).join(' ')
  const areaPath = (d) => `${linePath(d)} L${xAt(d.length - 1)},${padT + plotH} L${xAt(0)},${padT + plotH} Z`

  const onMove = (e) => {
    const rect = wrapRef.current.getBoundingClientRect()
    const relX = ((e.clientX - rect.left) / rect.width) * W
    let idx = Math.round(((relX - padL) / plotW) * n)
    idx = Math.max(0, Math.min(months.length - 1, idx))
    setHoverIdx(idx)
  }

  const gridSteps = [0, 0.5, 1]

  // End-value labels with basic collision avoidance: when two series' end
  // points land within 12px vertically, drop the lower-priority one and let
  // the legend + tooltip carry it (skill: "when end-labels collide, don't
  // stack them").
  const endPoints = series.map((s) => ({ key: s.key, y: yAt(s.data[s.data.length - 1].value), text: valueFormatter(s.data[s.data.length - 1].value), color: s.color }))
  const MIN_GAP = 12
  const visibleKeys = new Set()
  ;[...endPoints].sort((a, b) => a.y - b.y).reduce((lastY, ep) => {
    if (ep.y - lastY >= MIN_GAP) { visibleKeys.add(ep.key); return ep.y }
    return lastY
  }, -Infinity)

  return (
    <div ref={wrapRef} style={{ position: 'relative' }} onMouseMove={onMove} onMouseLeave={() => setHoverIdx(null)}>
      <svg viewBox={`0 0 ${W} ${H}`} width="100%" height="auto" role="img" aria-label={unitLabel}>
        {gridSteps.map((s) => {
          const y = padT + plotH * (1 - s)
          return (
            <g key={s}>
              <line x1={padL} y1={y} x2={W - padR} y2={y} stroke={colors.border} strokeWidth="1" />
              <text x={padL - 6} y={y + 3} textAnchor="end" fontSize="9" fill={colors.textMuted}>
                {Math.round(niceMax * s)}
              </text>
            </g>
          )
        })}

        {series.map((s) => (
          <g key={s.key}>
            {!isMulti && <path d={areaPath(s.data)} fill={s.color} opacity="0.1" stroke="none" />}
            <path d={linePath(s.data)} fill="none" stroke={s.color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />
          </g>
        ))}

        {hoverIdx != null && (
          <line x1={xAt(hoverIdx)} y1={padT} x2={xAt(hoverIdx)} y2={padT + plotH} stroke={colors.textMuted} strokeWidth="1" strokeDasharray="2 2" />
        )}

        {series.map((s) => {
          const lastI = s.data.length - 1
          return (
            <g key={s.key}>
              <circle cx={xAt(lastI)} cy={yAt(s.data[lastI].value)} r="4" fill={s.color} stroke={colors.card} strokeWidth="2" />
              {hoverIdx != null && hoverIdx !== lastI && (
                <circle cx={xAt(hoverIdx)} cy={yAt(s.data[hoverIdx].value)} r="4" fill={s.color} stroke={colors.card} strokeWidth="2" />
              )}
              {visibleKeys.has(s.key) && (
                <text x={xAt(lastI)} y={yAt(s.data[lastI].value) - 10} textAnchor="end" fontSize="10.5" fontWeight="700" fill={colors.text}>
                  {valueFormatter(s.data[lastI].value)}
                </text>
              )}
            </g>
          )
        })}

        {months.map((d, i) => (
          <text key={d.key} x={xAt(i)} y={H - 6} textAnchor="middle" fontSize="9.5" fill={colors.textMuted}>
            {d.label}
          </text>
        ))}
      </svg>

      {/* Legend — mirrors the mark (a line key, not a box) — required once 2+ series share a chart */}
      {isMulti && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.9rem', marginTop: '0.4rem', justifyContent: 'center' }}>
          {series.map((s) => (
            <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.75rem', color: colors.textMuted }}>
              <span style={{ width: 12, height: 2, backgroundColor: s.color, display: 'inline-block' }} />
              {s.label}
            </div>
          ))}
        </div>
      )}

      {hoverIdx != null && (
        <div style={{
          position: 'absolute', left: `${(xAt(hoverIdx) / W) * 100}%`, top: 0, transform: 'translate(-50%, -100%)',
          backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '10px',
          padding: '0.45rem 0.65rem', fontSize: '0.78rem', color: colors.text, pointerEvents: 'none',
          boxShadow: '0 6px 20px rgba(0,0,0,0.18)', whiteSpace: 'nowrap', zIndex: 5,
        }}>
          {series.map((s) => (
            <div key={s.key} style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', marginTop: '0.1rem' }}>
              <span style={{ width: 8, height: 2, backgroundColor: s.color, display: 'inline-block', flexShrink: 0 }} />
              <span style={{ fontWeight: 700 }}>{valueFormatter(s.data[hoverIdx].value)}</span>
              {isMulti && <span style={{ color: colors.textMuted }}>{s.label}</span>}
            </div>
          ))}
          <div style={{ color: colors.textMuted, marginTop: '0.25rem', borderTop: isMulti ? `1px solid ${colors.border}` : 'none', paddingTop: isMulti ? '0.25rem' : 0 }}>
            {months[hoverIdx].label}
          </div>
        </div>
      )}
    </div>
  )
}
