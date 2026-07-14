import React, { useRef, useState } from 'react'

// Single-series monthly trend line (sequential job — magnitude over time).
// data: [{ key, label, value }, ...]
export default function LineChart({ data, color, colors, valueFormatter = (v) => String(v), unitLabel = '' }) {
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

  const values = data.map((d) => d.value)
  const rawMax = Math.max(1, ...values)
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawMax)))
  const niceMax = Math.ceil(rawMax / (magnitude / 2)) * (magnitude / 2)

  const n = Math.max(data.length - 1, 1)
  const xAt = (i) => padL + (i / n) * plotW
  const yAt = (v) => padT + plotH * (1 - v / niceMax)

  const linePath = data.map((d, i) => `${i === 0 ? 'M' : 'L'}${xAt(i)},${yAt(d.value)}`).join(' ')
  const areaPath = `${linePath} L${xAt(data.length - 1)},${padT + plotH} L${xAt(0)},${padT + plotH} Z`

  const onMove = (e) => {
    const rect = wrapRef.current.getBoundingClientRect()
    const relX = ((e.clientX - rect.left) / rect.width) * W
    let idx = Math.round(((relX - padL) / plotW) * n)
    idx = Math.max(0, Math.min(data.length - 1, idx))
    setHoverIdx(idx)
  }

  const gridSteps = [0, 0.5, 1]
  const last = data[data.length - 1]
  const hovered = hoverIdx != null ? data[hoverIdx] : null

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

        <path d={areaPath} fill={color} opacity="0.1" stroke="none" />
        <path d={linePath} fill="none" stroke={color} strokeWidth="2" strokeLinejoin="round" strokeLinecap="round" />

        {hoverIdx != null && (
          <line x1={xAt(hoverIdx)} y1={padT} x2={xAt(hoverIdx)} y2={padT + plotH} stroke={colors.textMuted} strokeWidth="1" strokeDasharray="2 2" />
        )}

        {data.map((d, i) => {
          const isEnd = i === data.length - 1
          const isHover = i === hoverIdx
          if (!isEnd && !isHover) return null
          return (
            <circle key={d.key} cx={xAt(i)} cy={yAt(d.value)} r="4" fill={color} stroke={colors.card} strokeWidth="2" />
          )
        })}

        {/* End-value label — the one direct label a trend line earns */}
        <text x={xAt(data.length - 1)} y={yAt(last.value) - 10} textAnchor="end" fontSize="10.5" fontWeight="700" fill={colors.text}>
          {valueFormatter(last.value)}
        </text>

        {data.map((d, i) => (
          <text key={d.key} x={xAt(i)} y={H - 6} textAnchor="middle" fontSize="9.5" fill={colors.textMuted}>
            {d.label}
          </text>
        ))}
      </svg>

      {hovered && (
        <div style={{
          position: 'absolute', left: `${(xAt(hoverIdx) / W) * 100}%`, top: 0, transform: 'translate(-50%, -100%)',
          backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '10px',
          padding: '0.45rem 0.65rem', fontSize: '0.78rem', color: colors.text, pointerEvents: 'none',
          boxShadow: '0 6px 20px rgba(0,0,0,0.18)', whiteSpace: 'nowrap', zIndex: 5,
        }}>
          <div style={{ fontWeight: 700 }}>{valueFormatter(hovered.value)} <span style={{ fontWeight: 400, color: colors.textMuted }}>{unitLabel}</span></div>
          <div style={{ color: colors.textMuted, marginTop: '0.1rem' }}>{hovered.label}</div>
        </div>
      )}
    </div>
  )
}
