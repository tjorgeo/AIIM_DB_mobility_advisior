import React, { useState } from 'react'
import { ChevronLeft, ChevronDown, Wallet, PiggyBank, TrendingUp, Calendar, Euro, Leaf, Clock, Check } from 'lucide-react'
import { euro, number } from '../lib/format'
import { modeColor, modeLabel } from '../lib/travelModes'

// A category's projected recommendation only counts as "changed by the life event" if
// the underlying demand actually moved by at least this much vs. the baseline scenario
// — the forecaster LLM estimates every mode independently per scenario, so unrelated
// modes can drift a little between baseline and event-scenario runs by noise alone,
// which would otherwise flip a borderline recommendation with no real cause behind it.
const _PROJECTED_DEMAND_CHANGE_THRESHOLD = 0.15

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

// Button label + "done" confirmation text for a fake "execute this recommendation"
// action — shared between a category's own recommendation and a forecast box that
// projects a *different* recommendation for the same category, so both read with
// identical wording. Returns null for recommendations with nothing to execute
// (keep_current / no_subscription_needed are already the status quo).
function actionCopy(rec, planName, isDE) {
  switch (rec) {
    case 'switch_to_alternative':
      return {
        label: isDE ? `Zu ${planName} wechseln` : `Switch to ${planName}`,
        done: isDE ? `Abo gewechselt zu ${planName}` : `Switched to ${planName}`,
      }
    case 'consider_subscribing':
      return {
        label: isDE ? `${planName} abonnieren` : `Subscribe to ${planName}`,
        done: isDE ? `Abo abgeschlossen: ${planName}` : `Subscribed to ${planName}`,
      }
    case 'cancel_current_go_pay_as_you_go':
      return {
        label: isDE ? 'Jetzt kündigen' : 'Cancel now',
        done: isDE ? 'Abo gekündigt' : 'Subscription cancelled',
      }
    default:
      return null
  }
}

// Turns an action button's label ("Zu X wechseln") into its Ja/Nein confirm
// question ("Wirklich zu X wechseln?") — one rule instead of a separate
// translated question per action type, so new action types need no extra copy.
function confirmQuestion(label, isDE) {
  const lower = label.charAt(0).toLowerCase() + label.slice(1)
  return isDE ? `Wirklich ${lower}?` : `Really ${lower}?`
}

// The target plan name for a "switch" / "consider subscribing" recommendation —
// entries carry the same recommended_alternative/cheapest_alternative shape
// whether they come from category_subscription_analysis or a forecast scenario's
// projected_category_analysis (see PortfolioDetail's projectedByCategory).
function recAltPlanName(entry) {
  return entry?.recommended_alternative?.provider_plan_name || entry?.cheapest_alternative?.provider_plan_name || null
}

// Life-event types are free text from the forecaster LLM (see backend
// forecasting.py's _RULES: "relocation", "new_job", "start_of_studies",
// "Elternzeit", "major_life_change" are the named examples, nothing enforces
// exactly these strings). Mirrors backend/src/agent/engines/memo.py's noun
// tables so the same event reads the same way in the UI as in the memo text.
const _LIFE_EVENT_LABEL_DE = {
  relocation: 'Umzug',
  new_job: 'Jobwechsel',
  start_of_studies: 'Studienbeginn',
  parental_leave: 'Elternzeit',
  elternzeit: 'Elternzeit',
  major_life_change: 'größere Veränderung',
}
const _LIFE_EVENT_LABEL_EN = {
  relocation: 'Relocation',
  new_job: 'New job',
  start_of_studies: 'Start of studies',
  parental_leave: 'Parental leave',
  elternzeit: 'Parental leave',
  major_life_change: 'Life change',
}
// Dative phrase ("nach ...") with gender-agreed article for German; English needs
// only a definite noun phrase since "after" takes no article agreement.
const _LIFE_EVENT_DATIVE_DE = {
  relocation: 'dem Umzug',
  new_job: 'dem Jobwechsel',
  start_of_studies: 'dem Studienbeginn',
  parental_leave: 'der Elternzeit',
  elternzeit: 'der Elternzeit',
  major_life_change: 'der Veränderung',
}
const _LIFE_EVENT_NOUN_EN = {
  relocation: 'the move',
  new_job: 'the new job',
  start_of_studies: 'the start of studies',
  parental_leave: 'the parental leave',
  elternzeit: 'the parental leave',
  major_life_change: 'the life change',
}

// Mirrors backend agent/engines/memo.py's _MODE_LABEL_DE/_MODE_LABEL_EN +
// _coverage_note: only public_transport and long_distance_rail actually bundle
// more than one raw transport mode (see schema_map.py's _CATEGORY_COVERAGE — a
// public_transport subscription also covers regional_train; long_distance_rail is
// display-only, routed from BahnCard-family plans stored under the same DB
// category), so only those two categories need a coverage note — every other
// category maps 1:1 to a single raw mode already named by its own card title,
// nothing left to disambiguate. Deliberately a distinct dictionary from
// travelModes.js's modeLabel(), not a reuse of it: modeLabel('public_transport')
// already IS this card's own title ("ÖPNV"), so reusing it here would read as
// "ÖPNV (deckt ab: ÖPNV, Regionalbahn)" — these entries name the underlying trip
// legs, not the subscription product.
const _COVERAGE_MODE_LABEL_DE = {
  public_transport: 'lokale Busse/Bahnen',
  regional_train: 'Regionalzüge',
  long_distance_train: 'Fernzüge',
}
const _COVERAGE_MODE_LABEL_EN = {
  public_transport: 'local buses/trams',
  regional_train: 'regional trains',
  long_distance_train: 'long-distance trains',
}
const _CATEGORIES_WORTH_NAMING = new Set(['public_transport', 'long_distance_rail'])

function coverageNote(category, appliesToModes, isDE) {
  if (!_CATEGORIES_WORTH_NAMING.has(category) || !appliesToModes?.length) return ''
  const dict = isDE ? _COVERAGE_MODE_LABEL_DE : _COVERAGE_MODE_LABEL_EN
  const joined = appliesToModes.map((m) => dict[m] || m).join(', ')
  return isDE ? `deckt ab: ${joined}` : `covers: ${joined}`
}

function lifeEventLabel(type, isDE) {
  const key = (type || '').trim().toLowerCase()
  const humanized = (type || '').replace(/_/g, ' ')
  if (isDE) return _LIFE_EVENT_LABEL_DE[key] || humanized || 'Lebensereignis'
  const fallback = humanized ? humanized.charAt(0).toUpperCase() + humanized.slice(1) : 'Life event'
  return _LIFE_EVENT_LABEL_EN[key] || fallback
}

function lifeEventDativePhrase(type, isDE) {
  const key = (type || '').trim().toLowerCase()
  const humanized = (type || '').replace(/_/g, ' ')
  if (isDE) return _LIFE_EVENT_DATIVE_DE[key] || (humanized ? `dem Ereignis „${humanized}“` : 'dem Ereignis')
  return _LIFE_EVENT_NOUN_EN[key] || (humanized ? `the ${humanized}` : 'the event')
}

export default function PortfolioDetail({ analysis, lang, colors, isDark, onBack, cancelledSubs = [], onCancelSubscriptions, executedActions = {}, onExecuteAction, chatSlotRef }) {
  const isDE = lang === 'DE'
  // Which single action button is currently showing its "really do this?" Ja/Nein
  // step — keyed the same way as executedActions (see executableAction below), so
  // only one confirm prompt is open across the whole page at a time.
  const [confirmingKey, setConfirmingKey] = useState(null)
  const langKey = isDE ? 'de' : 'en'
  const t = isDE
    ? {
      back: 'Zurück zum Dashboard', title: 'Optimiertes Portfolio', subtitle: 'Kosten heute, Alternativen im Vergleich, Ausblick',
      current: 'Aktuell', optimized: 'Optimiert', savings: 'Ersparnis',
      categoryTrips: (n) => `Basierend auf ${number(n, langKey)} Fahrten/Jahr`,
      todayLabel: 'AKTUELLE KOSTEN', noSubLabel: 'KOSTEN OHNE ABO',
      bestAlt: 'Günstigste Alternative gefunden', vsCurrent: 'ggü. aktuell', vsNoSub: 'ggü. ohne Abo',
      allAlternatives: 'Alle Alternativen im Vergleich', plan: 'Tarif', perYear: 'Kosten/Jahr',
      noAlternatives: 'Keine Alternative im Katalog gefunden — das aktuelle Abo ist bereits die einzige sinnvolle Option.',
      forecastTitle: 'Prognose für die nächsten 12 Monate', forecastSub: 'Erwartete Nutzung auf Basis deiner Historie',
      mode: 'Verkehrsmittel', tripsPerYear: 'Fahrten/Jahr',
      lifeEventTitle: (type) => `Lebensereignis erkannt: ${lifeEventLabel(type, true)}`,
      lifeEventNoun: (type) => lifeEventDativePhrase(type, true),
      moreTrips: 'mehr Fahrten mit', fewerTrips: 'weniger Fahrten mit', expectPrefix: 'Erwartet werden',
      higherCost: 'höhere Kosten für', lowerCost: 'niedrigere Kosten für', perYearShort: 'Jahr',
      forecastBoxLabel: (event) => `Prognose: nach ${event}`,
      recPlanSuffix: (plan) => ` zu ${plan}`,
      forecastBoxReason: (before, after) => `Grund: erwartete Fahrten in dieser Kategorie ${after > before ? 'steigen' : 'sinken'} von ${number(before, langKey)} auf ${number(after, langKey)} pro Jahr.`,
      newRecommendation: (list) => `Neue Empfehlung durch dieses Ereignis: ${list}.`,
      recommendationUnchanged: 'Die Empfehlung ändert sich dadurch nicht.',
      reEval: (days) => `Empfehlung: Analyse in ca. ${days} Tagen erneut prüfen.`,
      demandChange: 'Erwartete Änderung des Reiseverhaltens', baseline: 'Bisher', afterEvent: 'Nach Ereignis',
      noLifeEvent: 'Aktuell sind keine bevorstehenden Lebensereignisse in deinem Kalender erkannt worden, die deine Empfehlungen ändern würden.',
      noForecast: 'Für diesen Zeitraum liegt noch keine Prognose vor.',
      noData: 'Für diesen Zeitraum liegen noch keine Portfolio-Daten vor.',
      co2PerYear: 'CO₂/Jahr', timePerYear: 'Zeit/Jahr', hoursShort: 'Std',
      recommendedBadge: 'EMPFOHLEN',
      recommendedNotCheapest: 'Nicht die günstigste Option, aber besser nach deiner Kosten-/CO₂-/Zeit-Gewichtung.',
      orDifferentMode: 'Oder: anderes Verkehrsmittel',
      stayLabel: 'Aktuell dabei bleiben', shiftTo: (label) => `Wechsel zu ${label}`, shiftAction: (label) => `Zu ${label} wechseln`,
      shiftDone: (label) => `Gewechselt zu ${label}`,
      noBetterShift: 'Kein anderes Verkehrsmittel schneidet nach deiner Gewichtung besser ab.',
      priorityTitle: 'DEINE PRIORITÄTEN', prioritySubtitle: 'Bestimmt, welche Option unten als optimal gilt.',
      priorityCost: 'Kosten', priorityCo2: 'CO₂', priorityFlex: 'Flexibilität / Zeit',
      noCurrentToCompare: 'kein aktuelles Abo zum Vergleich',
      showAlternatives: (n) => (n === 1 ? 'Die 1 Alternative anzeigen' : `Alle ${n} Alternativen anzeigen`),
      hideAlternatives: 'Alternativen ausblenden',
      cancelEyebrow: 'EMPFEHLUNG: KÜNDIGEN', cancelReason: 'Reine Einzelfahrten sind günstiger als jedes Abo.',
      cancelledLabel: 'Gekündigt', applyRecommendation: 'Diese Empfehlung übernehmen',
      confirmYes: 'Ja', confirmNo: 'Nein',
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
      lifeEventTitle: (type) => `Life event detected: ${lifeEventLabel(type, false)}`,
      lifeEventNoun: (type) => lifeEventDativePhrase(type, false),
      moreTrips: 'more trips with', fewerTrips: 'fewer trips with', expectPrefix: 'Expect',
      higherCost: 'higher costs for', lowerCost: 'lower costs for', perYearShort: 'yr',
      forecastBoxLabel: (event) => `Forecast: after ${event}`,
      recPlanSuffix: (plan) => ` to ${plan}`,
      forecastBoxReason: (before, after) => `Reason: expected trips in this category ${after > before ? 'rise' : 'fall'} from ${number(before, langKey)} to ${number(after, langKey)} per year.`,
      newRecommendation: (list) => `New recommendation due to this event: ${list}.`,
      recommendationUnchanged: 'This does not change the recommendation.',
      reEval: (days) => `Recommendation: re-check this analysis in about ${days} days.`,
      demandChange: 'Expected change in travel behavior', baseline: 'Before', afterEvent: 'After event',
      noLifeEvent: 'No upcoming life events were detected in your calendar that would change these recommendations.',
      noForecast: 'No forecast available for this period yet.',
      noData: 'No portfolio data available for this period yet.',
      co2PerYear: 'CO₂/yr', timePerYear: 'Time/yr', hoursShort: 'hrs',
      recommendedBadge: 'RECOMMENDED',
      recommendedNotCheapest: "Not the cheapest option, but scores better on your cost/CO₂/time weighting.",
      orDifferentMode: 'Or: different mode',
      stayLabel: 'Stay as-is', shiftTo: (label) => `Switch to ${label}`, shiftAction: (label) => `Switch to ${label}`,
      shiftDone: (label) => `Switched to ${label}`,
      noBetterShift: 'No other mode scores better under your weighting.',
      priorityTitle: 'YOUR PRIORITIES', prioritySubtitle: 'Determines which option below counts as optimal.',
      priorityCost: 'Cost', priorityCo2: 'CO₂', priorityFlex: 'Flexibility / Time',
      noCurrentToCompare: 'no current plan to compare against',
      showAlternatives: (n) => (n === 1 ? 'Show the 1 alternative' : `Show all ${n} alternatives`),
      hideAlternatives: 'Hide alternatives',
      cancelEyebrow: 'RECOMMENDATION: CANCEL', cancelReason: 'Pay-per-trip is cheaper than any subscription.',
      cancelledLabel: 'Cancelled', applyRecommendation: 'Apply this recommendation',
      confirmYes: 'Yes', confirmNo: 'No',
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
  const shiftByCategory = Object.fromEntries(modalShiftSuggestions.map((s) => [s.from_category, s]))
  const preferences = analysis?.preferences || {}
  const totalCurrent = summary?.total_actual_annual_cost_eur || 0
  const totalSavings = summary?.total_estimated_savings_eur || 0
  const totalOptimized = Math.max(totalCurrent - totalSavings, 0)

  const forecaster = analysis?.raw_agent_payloads?.forecaster?.output || null
  const scenarios = forecaster?.scenarios || []
  const baselineScenario = scenarios.find((s) => s.label === 'baseline') || scenarios[0] || null
  const eventScenario = scenarios.length > 1 ? scenarios[scenarios.length - 1] : null
  const flags = forecaster?.uncertainty_flags
  const lifeEventDetected = !!flags?.life_event_detected
  // Historical recommendations (category_subscription_analysis) are scored purely from
  // past trip legs and never reconsidered against the life-event-adjusted forecast, so
  // the two can disagree — this projects the post-event scenario's own recommendation
  // per category to let the card flag it when they diverge.
  const projectedByCategory = Object.fromEntries(
    (eventScenario?.projected_category_analysis || []).map((p) => [p.category, p]),
  )

  // Data-driven impact summary — computed from the two scenarios' own category-level
  // projections rather than the LLM's free-text rationale, so it's guaranteed to state
  // real numbers. Per category, prefer a trip-volume clause (e.g. a mode shift) when
  // trip counts actually move; otherwise fall back to a cost clause, since a life event
  // can raise costs without changing how often someone travels at all (e.g. moving
  // farther away makes the same daily commute pricier per trip, not more frequent).
  const baselineProjByCategory = Object.fromEntries(
    (baselineScenario?.projected_category_analysis || []).map((p) => [p.category, p]),
  )
  const lifeEventImpactClauses = (lifeEventDetected && baselineScenario && eventScenario)
    ? Object.keys(projectedByCategory)
        .map((category) => {
          const before = baselineProjByCategory[category]
          const after = projectedByCategory[category]
          if (!before || !after) return null
          const tripsPct = before.annual_trips
            ? Math.round(((after.annual_trips - before.annual_trips) / before.annual_trips) * 100)
            : 0
          if (Math.abs(tripsPct) >= 10) {
            return { category, kind: 'trips', pct: tripsPct, magnitude: Math.abs(tripsPct) }
          }
          const costDelta = (after.actual_annual_cost_eur ?? 0) - (before.actual_annual_cost_eur ?? 0)
          const costPct = before.actual_annual_cost_eur ? (costDelta / before.actual_annual_cost_eur) * 100 : 0
          if (Math.abs(costDelta) >= 20 && Math.abs(costPct) >= 5) {
            return { category, kind: 'cost', delta: costDelta, magnitude: Math.abs(costPct) }
          }
          return null
        })
        .filter(Boolean)
        .sort((a, b) => b.magnitude - a.magnitude)
    : []
  const lifeEventImpactSentence = (() => {
    if (lifeEventImpactClauses.length === 0) return null
    const clause = (c) => {
      if (c.kind === 'trips') {
        const dirWord = c.pct > 0 ? t.moreTrips : t.fewerTrips
        return `${dirWord} ${modeLabel(c.category, langKey)} (${c.pct > 0 ? '+' : ''}${c.pct}%)`
      }
      const dirWord = c.delta > 0 ? t.higherCost : t.lowerCost
      return `${dirWord} ${modeLabel(c.category, langKey)} (${c.delta > 0 ? '+' : ''}${euro(c.delta, { lang: langKey })}/${t.perYearShort})`
    }
    const joiner = isDE ? ' und ' : ' and '
    return `${t.expectPrefix} ${lifeEventImpactClauses.slice(0, 2).map(clause).join(joiner)}.`
  })()

  // Whether the life event actually flips any category's recommendation — the
  // expected-usage change above can be non-trivial (e.g. -89% long-distance trips)
  // without changing what we'd tell the customer to do, so this is called out
  // separately rather than left implicit.
  const recDivergences = lifeEventDetected
    ? categoryAnalysis
        .map((c) => {
          const projectedRec = projectedByCategory[c.category]
          if (!projectedRec || projectedRec.recommendation === c.recommendation) return null
          const baselineProj = baselineProjByCategory[c.category]
          const demandChangePct = baselineProj?.annual_trips
            ? Math.abs((projectedRec.annual_trips - baselineProj.annual_trips) / baselineProj.annual_trips)
            : 0
          if (demandChangePct < _PROJECTED_DEMAND_CHANGE_THRESHOLD) return null
          const rec = projectedRec.recommendation
          const altName = (rec === 'switch_to_alternative' || rec === 'consider_subscribing') ? recAltPlanName(projectedRec) : null
          return `${modeLabel(c.category, langKey)}: ${recMeta(rec, colors, isDE).label}${altName ? t.recPlanSuffix(altName) : ''}`
        })
        .filter(Boolean)
    : []
  const recChangeSentence = lifeEventDetected
    ? (recDivergences.length > 0 ? t.newRecommendation(recDivergences.join(', ')) : t.recommendationUnchanged)
    : null

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
  const priorityBar = (icon, label, value, color) => (
    <div style={{ backgroundColor: `${color}14`, border: `1px solid ${color}40`, borderRadius: '12px', padding: '0.55rem 0.75rem' }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.35rem' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', minWidth: 0 }}>
          <span style={{ color, display: 'flex', flexShrink: 0 }}>{icon}</span>
          <span style={{ fontSize: '0.8rem', fontWeight: '700' }}>{label}</span>
        </div>
        <span style={{ fontSize: '1rem', fontWeight: '800', color, flexShrink: 0 }}>{value}</span>
      </div>
      <div style={{ height: '5px', borderRadius: '999px', backgroundColor: colors.inputBg, overflow: 'hidden' }}>
        <div style={{ width: `${Math.max(0, Math.min(100, value))}%`, height: '100%', borderRadius: '999px', backgroundColor: color }} />
      </div>
    </div>
  )

  // One button style, reused for every "execute this recommendation" action
  // (switch plan, subscribe, cancel, apply a shift/forecast suggestion) so they
  // all look and behave the same wherever they appear on the page.
  const actionButtonEl = (label, onClick, color = colors.accentCyan) => (
    <button type="button" onClick={onClick} style={{ marginTop: '0.6rem', display: 'inline-flex', alignItems: 'center', gap: '0.4rem', padding: '0.5rem 0.95rem', borderRadius: '10px', border: `1px solid ${color}66`, backgroundColor: `${color}12`, color, fontWeight: '700', fontSize: '0.82rem', cursor: 'pointer' }}>
      {label}
    </button>
  )
  // Its counterpart once the fake action has been "executed" — same slot, same
  // shape, so clicking a button doesn't shift the surrounding layout.
  const doneBadge = (message) => (
    <div style={{ marginTop: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.4rem', padding: '0.55rem 0.9rem', borderRadius: '10px', backgroundColor: `${colors.successGreen}18`, border: `1px solid ${colors.successGreen}55`, color: colors.successGreen, fontWeight: '700', fontSize: '0.82rem' }}>
      <Check size={14} /> {message}
    </div>
  )
  // Third slot in the same spot: the inline Ja/Nein step shown while this action's
  // key is the one being confirmed. Ja runs onConfirm and clears the prompt, Nein
  // just clears it — nothing is executed on a plain click of the action button itself.
  const confirmBox = (label, onConfirm, color, detail) => (
    <div style={{ marginTop: '0.6rem' }}>
      <div style={{ fontSize: '0.82rem', fontWeight: '700', color: colors.text, marginBottom: detail ? '0.15rem' : '0.5rem' }}>
        {confirmQuestion(label, isDE)}
      </div>
      {detail && <div style={{ fontSize: '0.75rem', color: colors.textMuted, marginBottom: '0.5rem' }}>{detail}</div>}
      <div style={{ display: 'flex', gap: '0.5rem' }}>
        <button type="button" onClick={() => { onConfirm(); setConfirmingKey(null) }} style={{ flex: 1, padding: '0.5rem', borderRadius: '10px', border: 'none', backgroundColor: color, color: '#ffffff', fontWeight: '700', fontSize: '0.82rem', cursor: 'pointer' }}>
          {t.confirmYes}
        </button>
        <button type="button" onClick={() => setConfirmingKey(null)} style={{ flex: 1, padding: '0.5rem', borderRadius: '10px', border: `1px solid ${colors.border}`, backgroundColor: colors.card, color: colors.text, fontWeight: '700', fontSize: '0.82rem', cursor: 'pointer' }}>
          {t.confirmNo}
        </button>
      </div>
    </div>
  )
  // Renders the button/confirm/done-badge triplet for a generic (non-cancel) fake
  // action, keyed so each spot on the page (a category's own recommendation vs.
  // the same recommendation surfaced again in the forecast box) tracks its own
  // confirm and done state independently.
  const executableAction = (key, copy, color = colors.accentAmber) => {
    if (!copy) return null
    if (executedActions[key]) return doneBadge(executedActions[key])
    if (confirmingKey === key) return confirmBox(copy.label, () => onExecuteAction?.(key, copy.done), color)
    return actionButtonEl(copy.label, () => setConfirmingKey(key), color)
  }

  return (
    <div style={{ backgroundColor: colors.bg, color: colors.text, fontFamily: 'system-ui, -apple-system, sans-serif', minHeight: '100vh' }}>
      <style>{`
        .portfolio-container { display: grid; grid-template-columns: 1fr; gap: 1.25rem; min-width: 0; }
        .portfolio-kpis { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 1rem; min-width: 0; }
        .portfolio-compare { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; min-width: 0; }
        .priority-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; min-width: 0; margin-bottom: 0.5rem; }
        /* Queries the actual space beside the chat sidebar (see
           .page-split__main in components.css), not the viewport, so this
           collapses to one column whenever there's genuinely too little
           room for three, sidebar or no sidebar. */
        @container page-main (max-width: 480px) { .portfolio-kpis { grid-template-columns: 1fr; } .priority-grid { grid-template-columns: 1fr; } }
      `}</style>

      <header style={{ padding: '1.25rem 1.5rem', borderBottom: `1px solid ${colors.border}`, position: 'sticky', top: 0, backgroundColor: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.85)', backdropFilter: 'blur(12px)', zIndex: 10 }}>
        <button onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '12px', color: colors.textMuted, padding: '0.55rem 0.95rem', fontSize: '0.88rem', fontWeight: '600', cursor: 'pointer' }}>
          <ChevronLeft size={16} /> {t.back}
        </button>
      </header>

      <div className="page-split">
      <main className="portfolio-container page-split__main">
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

            <div style={{ ...cardStyle, padding: '1rem 1.1rem' }}>
              <div style={{ display: 'flex', flexWrap: 'wrap', alignItems: 'baseline', justifyContent: 'space-between', gap: '0.3rem', marginBottom: '0.6rem' }}>
                <span style={{ fontSize: '0.68rem', fontWeight: '800', letterSpacing: '0.08em', color: colors.textMuted }}>{t.priorityTitle}</span>
                <span style={{ fontSize: '0.75rem', color: colors.textMuted }}>{t.prioritySubtitle}</span>
              </div>
              <div className="priority-grid">
                {priorityBar(<Euro size={14} />, t.priorityCost, preferences.cost_priority ?? 50, colors.accentCyan)}
                {priorityBar(<Leaf size={14} />, t.priorityCo2, preferences.co2_priority ?? 50, colors.successGreen)}
              </div>
              {priorityBar(<Clock size={14} />, t.priorityFlex, preferences.convenience_priority ?? 50, colors.accentPurple)}
            </div>

            {/* Per-category cost comparison — "Vergleich Kosten heute" + "Vergleich mit anderen Abos" */}
            {categoryAnalysis.map((c) => {
              const meta = recMeta(c.recommendation, colors, isDE)
              const projectedRec = projectedByCategory[c.category]
              const baselineProj = baselineProjByCategory[c.category]
              const demandChangePct = (projectedRec && baselineProj && baselineProj.annual_trips)
                ? Math.abs((projectedRec.annual_trips - baselineProj.annual_trips) / baselineProj.annual_trips)
                : 0
              const projectedRecDiverges = projectedRec
                && projectedRec.recommendation !== c.recommendation
                && demandChangePct >= _PROJECTED_DEMAND_CHANGE_THRESHOLD
              const shiftSuggestion = shiftByCategory[c.category]
              const shift = shiftSuggestion?.suggested_shift
              const shiftCostDelta = shift ? shift.annual_cost_eur - (shiftSuggestion.stay_annual_cost_eur ?? 0) : null
              const shiftCo2Delta = shift && shift.annual_co2_kg != null && shiftSuggestion.stay_annual_co2_kg != null
                ? shift.annual_co2_kg - shiftSuggestion.stay_annual_co2_kg : null
              const shiftTimeDeltaHours = shift && shift.annual_time_minutes != null && shiftSuggestion.stay_annual_time_minutes != null
                ? Math.round((shift.annual_time_minutes - shiftSuggestion.stay_annual_time_minutes) / 60) : null
              const shiftDeltaColor = (d) => (d <= 0 ? colors.successGreen : colors.accentRed)
              const swatch = modeColor(c.category, isDark)
              const currentSubs = c.current_subscriptions || []
              const subNames = currentSubs.map((s) => s.provider_plan_name).filter(Boolean)
              const isCancelled = subNames.length > 0 && subNames.every((n) => cancelledSubs.includes(n))
              const canCancel = c.recommendation === 'cancel_current_go_pay_as_you_go' && subNames.length > 0 && !!onCancelSubscriptions
              const cancelActionKey = `cancel:${c.category}`
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
              // Fake "execute this recommendation" copy — cancel goes through the
              // shared confirm-dialog + cancelledSubs flow (see canCancel below),
              // switch/subscribe go through the generic executedActions map.
              const primaryActionKey = `primary:${c.category}`
              const primaryActionCopy = showBestAlternative ? actionCopy(c.recommendation, best.provider_plan_name, isDE) : null
              const cancelCopy = actionCopy('cancel_current_go_pay_as_you_go', null, isDE)
              const shiftActionKey = `shift:${c.category}`
              const forecastActionKey = `forecast:${c.category}`
              const forecastActionCopy = projectedRec
                ? (actionCopy(projectedRec.recommendation, recAltPlanName(projectedRec), isDE) || (
                  (projectedRec.recommendation === 'switch_to_alternative' || projectedRec.recommendation === 'consider_subscribing')
                    ? { label: t.applyRecommendation, done: t.applyRecommendation } : null
                ))
                : null

              return (
                <div key={c.category} style={cardStyle}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.25rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <span style={{ width: 10, height: 10, borderRadius: 3, backgroundColor: swatch, display: 'inline-block' }} />
                      <h3 style={{ fontSize: '1.05rem', fontWeight: '700' }}>{modeLabel(c.category, langKey)}</h3>
                    </div>
{/* Status-only badge — purely informational now, every recommendation type reads
                        the same way here; the actual action lives in a callout box below,
                        in the same spot for every category (see canCancel / showBestAlternative). */}
                    {isCancelled ? (
                      <span style={{ fontSize: '0.85rem', fontWeight: '700', color: colors.textMuted, backgroundColor: colors.inputBg, padding: '0.4rem 0.85rem', borderRadius: '999px' }}>
                        {t.cancelledLabel}
                      </span>
                    ) : (
                      <span style={{ fontSize: '0.85rem', fontWeight: '700', color: meta.color, backgroundColor: `${meta.color}40`, border: `1px solid ${meta.color}66`, padding: '0.4rem 0.85rem', borderRadius: '999px' }}>
                        {meta.label}
                      </span>
                    )}
                  </div>
                  <p style={{ fontSize: '0.78rem', color: colors.textMuted, marginBottom: '0.5rem' }}>
                    {t.categoryTrips(c.annual_trips)}
                    {coverageNote(c.category, c.applies_to_modes, isDE) && ` · ${coverageNote(c.category, c.applies_to_modes, isDE)}`}
                  </p>
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
                      {currentSubs.map((s) => {
                        const struck = cancelledSubs.includes(s.provider_plan_name)
                        return (
                          <div key={s.provider_plan_name} style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.15rem', textDecoration: struck ? 'line-through' : 'none', opacity: struck ? 0.6 : 1 }}>{s.provider_plan_name}{struck ? (isDE ? ' · gekündigt' : ' · cancelled') : ''}</div>
                        )
                      })}
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
                      {executableAction(primaryActionKey, primaryActionCopy)}
                    </div>
                  )}

                  {canCancel && (
                    <div style={{ border: `1px dashed ${colors.accentRed}`, borderRadius: '14px', padding: '0.75rem 1rem', marginBottom: '1rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '700', color: colors.accentRed, letterSpacing: '0.04em' }}>
                        {t.cancelEyebrow}
                      </span>
                      <p style={{ fontSize: '0.8rem', color: colors.textMuted, marginTop: '0.3rem', marginBottom: 0 }}>{t.cancelReason}</p>
                      {isCancelled
                        ? doneBadge(cancelCopy.done)
                        : confirmingKey === cancelActionKey
                          ? confirmBox(cancelCopy.label, () => onCancelSubscriptions(subNames), colors.accentRed, subNames.join(', '))
                          : actionButtonEl(cancelCopy.label, () => setConfirmingKey(cancelActionKey), colors.accentRed)}
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

                  {shiftSuggestion && shift && (
                    <div style={{ border: `1px dashed ${colors.accentCyan}`, borderRadius: '14px', padding: '0.75rem 1rem', marginTop: '1rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '700', color: colors.accentCyan, letterSpacing: '0.04em' }}>
                        {t.orDifferentMode.toUpperCase()}
                      </span>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.3rem' }}>
                        <span style={{ fontWeight: '600', fontSize: '0.9rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
                          <span style={{ width: 8, height: 8, borderRadius: 2, backgroundColor: modeColor(shift.to_category, isDark), display: 'inline-block' }} />
                          {t.shiftTo(modeLabel(shift.to_category, langKey))}
                        </span>
                        <span style={{ fontWeight: '800', fontSize: '1rem', color: colors.accentCyan }}>{euro(shift.annual_cost_eur, { lang: langKey })}</span>
                      </div>
                      <div style={{ display: 'flex', gap: '0.4rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', fontWeight: '700', color: shiftDeltaColor(shiftCostDelta), backgroundColor: `${shiftDeltaColor(shiftCostDelta)}22`, padding: '0.25rem 0.55rem', borderRadius: '999px' }}>
                          <Euro size={11} />
                          {shiftCostDelta > 0 ? '+' : ''}{euro(shiftCostDelta, { lang: langKey })} {t.perYear}
                        </span>
                        {shiftCo2Delta != null && (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', fontWeight: '700', color: shiftDeltaColor(shiftCo2Delta), backgroundColor: `${shiftDeltaColor(shiftCo2Delta)}22`, padding: '0.25rem 0.55rem', borderRadius: '999px' }}>
                            <Leaf size={11} />
                            {shiftCo2Delta > 0 ? '+' : ''}{number(shiftCo2Delta, langKey)} kg {t.co2PerYear}
                          </span>
                        )}
                        {shiftTimeDeltaHours != null && (
                          <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.72rem', fontWeight: '700', color: shiftDeltaColor(shiftTimeDeltaHours), backgroundColor: `${shiftDeltaColor(shiftTimeDeltaHours)}22`, padding: '0.25rem 0.55rem', borderRadius: '999px' }}>
                            <Clock size={11} />
                            {shiftTimeDeltaHours > 0 ? '+' : ''}{number(shiftTimeDeltaHours, langKey)} {t.hoursShort} {t.timePerYear}
                          </span>
                        )}
                      </div>
                      {executableAction(shiftActionKey, { label: t.shiftAction(modeLabel(shift.to_category, langKey)), done: t.shiftDone(modeLabel(shift.to_category, langKey)) }, colors.accentCyan)}
                    </div>
                  )}

                  {shiftSuggestion && !shift && (
                    <p style={{ fontSize: '0.78rem', color: colors.textMuted, marginTop: '1rem' }}>{t.noBetterShift}</p>
                  )}

                  {projectedRecDiverges && (
                    <div style={{ border: `1px dashed ${colors.accentAmber}`, borderRadius: '14px', padding: '0.75rem 1rem', marginTop: '1rem' }}>
                      <span style={{ fontSize: '0.65rem', fontWeight: '700', color: colors.accentAmber, letterSpacing: '0.04em' }}>
                        {t.forecastBoxLabel(t.lifeEventNoun(flags.life_event_type)).toUpperCase()}
                      </span>
                      <div style={{ fontWeight: '600', fontSize: '0.9rem', marginTop: '0.3rem' }}>
                        {recMeta(projectedRec.recommendation, colors, isDE).label}
                        {(projectedRec.recommendation === 'switch_to_alternative' || projectedRec.recommendation === 'consider_subscribing') && recAltPlanName(projectedRec) && t.recPlanSuffix(recAltPlanName(projectedRec))}
                      </div>
                      {executableAction(
                        forecastActionKey,
                        forecastActionCopy,
                        projectedRec.recommendation === 'cancel_current_go_pay_as_you_go' ? colors.accentRed : colors.accentAmber,
                      )}
                      {baselineProj?.annual_trips != null && (
                        <p style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.3rem' }}>
                          {t.forecastBoxReason(baselineProj.annual_trips, projectedRec.annual_trips)}
                        </p>
                      )}
                    </div>
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
                      {lifeEventImpactSentence && (
                        <p style={{ fontSize: '0.88rem', fontWeight: '600', color: colors.text, marginTop: '0.5rem', lineHeight: '1.5' }}>
                          {lifeEventImpactSentence}
                        </p>
                      )}
                      {recChangeSentence && (
                        <p style={{ fontSize: '0.85rem', fontWeight: '700', color: recDivergences.length > 0 ? colors.accentAmber : colors.textMuted, marginTop: '0.5rem', lineHeight: '1.5' }}>
                          {recChangeSentence}
                        </p>
                      )}
                      {(() => {
                        // Per-language field (rationale_en/rationale_de). Prefer the UI
                        // language, then fall back to whichever one is present: the
                        // deterministic projection fills both, but the forecast reasoner
                        // narrates in a single language per call (see the backend's
                        // forecasting.localized), so the fallback is "the other one",
                        // not always English.
                        const rationale = (isDE ? forecaster.rationale_de : forecaster.rationale_en)
                          || (isDE ? forecaster.rationale_en : forecaster.rationale_de)
                        return rationale && (
                          <p style={{ fontSize: '0.8rem', color: colors.textMuted, marginTop: '0.5rem', lineHeight: '1.5' }}>{rationale}</p>
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

          </>
        )}
      </main>
      <aside className="page-split__sidebar" ref={chatSlotRef} />
      </div>
    </div>
  )
}