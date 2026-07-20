import React from 'react'

// Minimal markdown renderer for chat/memo text (headers, bold, italic, inline
// code, bullet/numbered lists, paragraphs). The advisor LLM writes plain
// markdown (see analyst_system.md: "Use short markdown sections") but the chat
// bubble used to dump it as a raw string — this turns it back into elements
// instead of pulling in a full markdown library for a handful of constructs.

const INLINE_RE = /\*\*\*(.+?)\*\*\*|\*\*(.+?)\*\*|\*(.+?)\*|`(.+?)`/g

// GFM pipe-table separator row, e.g. "|---|:--:|---|". The LLM is instructed not to
// emit tables (this renderer has no table layout), but as a safety net any that slip
// through are parsed here and rendered as a bullet list instead of raw pipe characters.
const TABLE_SEP_RE = /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/

function splitTableRow(line) {
  let s = line.trim()
  if (s.startsWith('|')) s = s.slice(1)
  if (s.endsWith('|')) s = s.slice(0, -1)
  return s.split('|').map((c) => c.trim())
}

function parseInline(text) {
  const nodes = []
  let lastIndex = 0
  let key = 0
  let m
  INLINE_RE.lastIndex = 0
  while ((m = INLINE_RE.exec(text))) {
    if (m.index > lastIndex) nodes.push(text.slice(lastIndex, m.index))
    if (m[1] !== undefined) nodes.push(<strong key={key}><em>{m[1]}</em></strong>)
    else if (m[2] !== undefined) nodes.push(<strong key={key}>{m[2]}</strong>)
    else if (m[3] !== undefined) nodes.push(<em key={key}>{m[3]}</em>)
    else if (m[4] !== undefined) nodes.push(<code key={key}>{m[4]}</code>)
    key++
    lastIndex = INLINE_RE.lastIndex
  }
  if (lastIndex < text.length) nodes.push(text.slice(lastIndex))
  return nodes
}

function parseBlocks(text) {
  const lines = String(text).split('\n')
  const blocks = []
  let paraBuffer = []

  const flushPara = () => {
    if (paraBuffer.length) {
      blocks.push({ type: 'p', lines: paraBuffer })
      paraBuffer = []
    }
  }

  let i = 0
  while (i < lines.length) {
    const line = lines[i]
    const heading = line.match(/^(#{1,6})\s+(.*)$/)
    if (heading) {
      flushPara()
      blocks.push({ type: 'h', level: heading[1].length, text: heading[2] })
      i++
      continue
    }

    if (line.includes('|') && i + 1 < lines.length && TABLE_SEP_RE.test(lines[i + 1])) {
      flushPara()
      const headers = splitTableRow(line)
      i += 2
      const rows = []
      while (i < lines.length && lines[i].includes('|') && lines[i].trim() !== '') {
        rows.push(splitTableRow(lines[i]))
        i++
      }
      blocks.push({ type: 'table', headers, rows })
      continue
    }

    const ulMatch = line.match(/^\s*[-*]\s+(.*)$/)
    if (ulMatch) {
      flushPara()
      const items = []
      while (i < lines.length) {
        const m = lines[i].match(/^\s*[-*]\s+(.*)$/)
        if (!m) break
        items.push(m[1])
        i++
      }
      blocks.push({ type: 'ul', items })
      continue
    }

    const olMatch = line.match(/^\s*\d+\.\s+(.*)$/)
    if (olMatch) {
      flushPara()
      const items = []
      while (i < lines.length) {
        const m = lines[i].match(/^\s*\d+\.\s+(.*)$/)
        if (!m) break
        items.push(m[1])
        i++
      }
      blocks.push({ type: 'ol', items })
      continue
    }

    if (line.trim() === '') {
      flushPara()
      i++
      continue
    }

    paraBuffer.push(line)
    i++
  }
  flushPara()
  return blocks
}

// Headings are demoted two levels (## -> h4) so they stay proportionate inside
// a ~390px chat bubble instead of rendering at full-page h2 size.
export default function Markdown({ text }) {
  if (!text) return null
  const blocks = parseBlocks(text)

  return blocks.map((b, idx) => {
    if (b.type === 'h') {
      const Tag = `h${Math.min(b.level + 2, 6)}`
      return <Tag key={idx} className="md-heading">{parseInline(b.text)}</Tag>
    }
    if (b.type === 'ul') {
      return (
        <ul key={idx} className="md-list">
          {b.items.map((it, j) => <li key={j}>{parseInline(it)}</li>)}
        </ul>
      )
    }
    if (b.type === 'table') {
      return (
        <ul key={idx} className="md-list">
          {b.rows.map((row, r) => (
            <li key={r}>
              {row.map((cell, c) => (
                <React.Fragment key={c}>
                  {c > 0 && ' · '}
                  {b.headers[c] && <strong>{parseInline(b.headers[c])}: </strong>}
                  {parseInline(cell)}
                </React.Fragment>
              ))}
            </li>
          ))}
        </ul>
      )
    }
    if (b.type === 'ol') {
      return (
        <ol key={idx} className="md-list">
          {b.items.map((it, j) => <li key={j}>{parseInline(it)}</li>)}
        </ol>
      )
    }
    return (
      <p key={idx} className="md-p">
        {b.lines.map((ln, j) => (
          <React.Fragment key={j}>
            {j > 0 && <br />}
            {parseInline(ln)}
          </React.Fragment>
        ))}
      </p>
    )
  })
}
