import React, { useState, useEffect } from 'react'
import {
  Wallet, Leaf, Globe, LogOut, TrendingUp,
  Check, ChevronDown, ChevronRight, BarChart3, AlertCircle,
  CheckCircle2, AlertTriangle, RefreshCw
} from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import Logo from '../components/Logo'
import { analyze } from '../api/client'
import { euro, number, subscriptionEmoji } from '../lib/format'
import ChatWidget from '../components/chat/ChatWidget'
import { useTheme } from '../context/ThemeContext.jsx'
import ThemeToggle from '../components/ThemeToggle.jsx'
import TravelInsights from './TravelInsights.jsx'
import CostBreakdown from './CostBreakdown.jsx'
import PortfolioDetail from './PortfolioDetail.jsx'
import { modeLabel } from '../lib/travelModes'

export default function Dashboard() {
  const { logout, currentUser } = useAuth()
  const [lang, setLang] = useState('DE') // Standardmäßig auf Deutsch
  const [profileMenuOpen, setProfileMenuOpen] = useState(false) // State für das kleine Fenster
  const [view, setView] = useState('overview') // 'overview' | 'insights' | 'cost' | 'portfolio' — kein Router nötig, gleiches Muster wie Login.jsx currentView

  // Identität des eingeloggten Users (statt fest verdrahtetem Demo-Avatar)
  const displayName = currentUser?.name?.trim() || currentUser?.firstName || 'Du'
  const initials = (currentUser?.initials
    || (currentUser?.name || '')
        .split(' ')
        .filter(Boolean)
        .map((s) => s[0])
        .slice(0, 2)
        .join('')
    || (currentUser?.firstName?.[0] || 'U')).toUpperCase()

  // Wörterbuch für die schlichte DE/EN-Umschaltung
  const t = {
    DE: {
      optimized: 'Du bist optimiert',
      optimizedSub: 'Dein aktueller Plan passt perfekt zu deinem Reiseverhalten — kein verlorenes Sparpotenzial.',
      savingsTitle: 'Hier ist dein Sparpotenzial',
      analyzing: 'Wir analysieren deine Fahrten…',
      analyzingSub: 'Dein persönlicher Plan ist gleich fertig.',
      annualSpend: 'JÄHRLICHE AUSGABEN',
      co2: 'CO₂-FUSABDRUCK (12 MONATE)',
      estimatedEmissions: 'Geschätzte Emissionen',
      worthIt: (v) => `Spart ${euro(v, { lang: 'de' })}`,
      notWorthIt: (v) => `${euro(v, { lang: 'de' })} Mehrkosten`,
      howYouTravel: 'Wie du reist',
      tripsLabel: 'Fahrten',
      viewDetails: 'Alle Details ansehen',
      recommended: 'Für dich empfohlen',
      basedMonths: 'Basiert auf deinen letzten 12 Monaten',
      portfolioTitle: 'Dein optimiertes Portfolio',
      estimated: 'Geschätzt',
      insteadOfBefore: (v) => `statt bisher ${v}`,
      savingsBadge: (v) => `− ${v} Ersparnis`,
      extraCostBadge: (v) => `+ ${v} Mehrkosten`,
      currentPlan: 'Dein aktueller Tarif',
      currentSubsTitle: 'Deine aktuellen Abos',
      noSubs: 'Keine aktiven Abos hinterlegt.',
      perMonth: '/ Monat',
      perYear: '/ Jahr',
      whatChanges: 'WAS SICH ÄNDERT',
      noChanges: 'Keine Änderungen — behalte deinen Tarif bei',
      logout: 'Abmelden',
      settings: 'Einstellungen',
      editProfile: 'Profildaten ändern',
      subAndTickets: 'Abos + Tickets',
      refreshTitle: 'Analyse neu berechnen',
    },
    EN: {
      optimized: "You're optimized",
      optimizedSub: 'Your current plan already fits how you travel — no savings left on the table.',
      savingsTitle: "Here's your savings potential",
      analyzing: 'Analyzing your trips…',
      analyzingSub: 'Your personalized plan will be ready shortly.',
      annualSpend: 'ANNUAL SPEND',
      co2: 'CO₂ FOOTPRINT (12 MO)',
      estimatedEmissions: 'Estimated emissions',
      worthIt: (v) => `Saves ${euro(v, { lang: 'en' })}`,
      notWorthIt: (v) => `Costs ${euro(v, { lang: 'en' })} extra`,
      howYouTravel: 'How you travel',
      tripsLabel: 'trips',
      viewDetails: 'View all details',
      recommended: 'Recommended for you',
      basedMonths: 'Based on your last 12 months',
      portfolioTitle: 'Your optimized portfolio',
      estimated: 'Estimated',
      insteadOfBefore: (v) => `instead of ${v}`,
      savingsBadge: (v) => `− ${v} savings`,
      extraCostBadge: (v) => `+ ${v} extra`,
      currentPlan: 'Your current plan',
      currentSubsTitle: 'Your current subscriptions',
      noSubs: 'No active subscriptions on file.',
      perMonth: '/ mo',
      perYear: '/ yr',
      whatChanges: 'WHAT CHANGES',
      noChanges: 'No changes — keep your current plan',
      logout: 'Sign out',
      settings: 'Settings',
      editProfile: 'Edit Profile',
      subAndTickets: 'Subscriptions + tickets',
      refreshTitle: 'Recompute analysis',
    }
  }[lang]

  // Farbpalette exakt passend zur Onboarding/Login-Seite
  const { isDark } = useTheme()
  const colors = isDark ? {
    bg: '#000000',
    card: '#16161a',
    accentCyan: '#00f2fe',
    accentPurple: '#a855f7',
    accentAmber: '#f59e0b',
    textMuted: '#747C92',
    border: '#26262b',
    successGreen: '#22c55e',
    accentRed: '#f43f5e',
    text: '#ffffff',
    onAccent: '#000000',
    inputBg: '#1c1c1f',
    selectFill: 'rgba(168,85,247,0.10)',
    cyanFill: 'rgba(0,242,254,0.06)',
    infoText: '#cbd5e1',
    errorText: '#ff4a5a',
    errorBg: 'rgba(255,74,90,0.10)'
  } : {
    bg: '#eef1f4',
    card: '#ffffff',
    accentCyan: '#0499ad',
    accentPurple: '#7c3aed',
    accentAmber: '#d97706',
    textMuted: '#5b6472',
    border: '#e3e7eb',
    successGreen: '#16a34a',
    accentRed: '#dc2626',
    text: '#111827',
    onAccent: '#ffffff',
    inputBg: '#f2f4f7',
    selectFill: 'rgba(124,58,237,0.08)',
    cyanFill: 'rgba(4,153,173,0.08)',
    infoText: '#3f5a4e',
    errorText: '#dc2626',
    errorBg: 'rgba(220,38,38,0.08)'
  }

  // Daten aus den Screenshots extrahiert (Fallback, solange die Analyse lädt)
  const travelStats = [
    { name: lang === 'DE' ? 'Zu Fuß' : 'walk', trips: '247', pct: 56, color: '#00f2fe' },
    { name: lang === 'DE' ? 'Bus' : 'Bus', trips: '84', pct: 19, color: '#a855f7' },
    { name: lang === 'DE' ? 'Fahrrad' : 'bike', trips: '64', pct: 14, color: '#3b82f6' },
    { name: lang === 'DE' ? 'E-Scooter' : 'Scooter', trips: '41', pct: 9, color: '#22c55e' },
    { name: lang === 'DE' ? 'Zug' : 'Train', trips: '6', pct: 1, color: '#eab308' },
  ]

  // --- Echte Analyse für den eingeloggten User laden ---
  const [analysis, setAnalysis] = useState(null)
  const [loadingData, setLoadingData] = useState(true)
  // Abos, die der User (in der Portfolio-Detailseite) gekündigt hat — per
  // provider_plan_name, da dieses Feld in beiden Datenquellen vorhanden ist.
  const [cancelledSubs, setCancelledSubs] = useState([])
  const handleCancelSubscriptions = (names) => {
    const list = (names || []).filter(Boolean)
    if (list.length === 0) return
    setCancelledSubs((prev) => Array.from(new Set([...prev, ...list])))
  }

  useEffect(() => {
    let cancelled = false
    if (!currentUser?.id) { setLoadingData(false); return }
    setLoadingData(true)
    analyze(currentUser.id)
      .then((res) => { if (!cancelled) setAnalysis(res) })
      .catch(() => { /* leer lassen -> Fallback-Anzeige */ })
      .finally(() => { if (!cancelled) setLoadingData(false) })
    return () => { cancelled = true }
  }, [currentUser?.id])

  // Umgeht den Backend-Cache (siehe orchestrator.py) und erzwingt eine frische
  // Neuberechnung — z.B. nachdem sich die Optimierungslogik geändert hat.
  const [refreshing, setRefreshing] = useState(false)
  const handleForceRefresh = () => {
    if (!currentUser?.id || refreshing) return
    setRefreshing(true)
    analyze(currentUser.id, { force: true })
      .then((res) => setAnalysis(res))
      .catch(() => { /* still leave the previous analysis visible */ })
      .finally(() => setRefreshing(false))
  }

  const langKey = lang.toLowerCase()
  const analyst = analysis?.raw_agent_payloads?.analyst?.output || null
  const summary = analysis?.summary || null
  const communicator = analysis?.raw_agent_payloads?.communicator?.output || null
  const recommended = summary || null
  const currentSubscriptions = analysis?.current_subscriptions || []
  const visibleSubscriptions = currentSubscriptions.filter((s) => !cancelledSubs.includes(s.provider_plan_name))
  // subscription_coverage carries the per-subscription worth-it check (net_savings_eur);
  // joined on subscription_id (the catalog id, shared with current_subscriptions).
  const coverageBySubId = new Map((analyst?.subscription_coverage || []).map((c) => [c.subscription_id, c]))

  const busy = (v) => (loadingData ? '…' : v)
  const annualSpendStr = analyst ? euro(analyst.current_annual_spend_eur, { lang: langKey }) : busy('—')
  const co2Str = analyst ? `${number(analyst.total_co2_kg, langKey)} kg` : busy('—')
  const recSavings = summary?.total_estimated_savings_eur || 0
  // Recommended annual cost = what you pay today minus the estimated savings if you
  // follow every suggested action (category_subscription_analysis contract).
  const recPriceStr = summary
    ? euro(Math.max((summary.total_actual_annual_cost_eur || 0) - recSavings, 0), { lang: langKey })
    : annualSpendStr
  // "Before" cost the portfolio card compares against — same basis as recSavings
  // (total_actual_annual_cost_eur), not analyst.current_annual_spend_eur, which also
  // includes uncategorized spend (car ownership, taxis, ...) outside the 5
  // subscribable categories the portfolio recommendation covers.
  const totalCurrentStr = summary ? euro(summary.total_actual_annual_cost_eur || 0, { lang: langKey }) : busy('—')
  // One "+/−" line per suggested subscription change from the communicator agent.
  const recChanges = (communicator?.actions_required || []).flatMap((a) => {
    const lines = []
    if (a.from && a.from !== 'no subscription') lines.push({ action: 'remove', item: a.from })
    if (a.to) lines.push({ action: 'add', item: a.to })
    return lines
  })

  // Hero headline must reflect the actual result, not a fixed "you're optimized"
  // claim — that's true only once we know there's nothing left to save.
  const hasSavings = recSavings > 0 && recChanges.length > 0
  const heroTitle = loadingData ? t.analyzing : hasSavings ? t.savingsTitle : t.optimized
  const heroSub = loadingData
    ? t.analyzingSub
    : hasSavings
      ? (lang === 'DE'
        ? `Mit den empfohlenen Änderungen sparst du schätzungsweise ${euro(recSavings, { lang: langKey })} pro Jahr.`
        : `With the recommended changes you could save an estimated ${euro(recSavings, { lang: langKey })} per year.`)
      : t.optimizedSub

  const palette = ['#00f2fe', '#a855f7', '#3b82f6', '#22c55e', '#eab308', '#f43f5e']
  const derivedTravelStats = analyst?.mode_breakdown
    ? Object.entries(analyst.mode_breakdown)
        .map(([name, d]) => ({
          name: modeLabel(name, langKey),
          trips: String(d.trips),
          pct: analyst.total_trips ? Math.round((d.trips / analyst.total_trips) * 100) : 0,
        }))
        .sort((a, b) => Number(b.trips) - Number(a.trips))
        .map((x, i) => ({ ...x, color: palette[i % palette.length] }))
    : null
  const modes = derivedTravelStats || travelStats

  // ChatWidget must sit at a stable position in the tree regardless of which view
  // is active — computed once as `pageContent` per view below, with ChatWidget
  // always rendered as its sibling in the single return at the bottom. Returning a
  // differently-shaped tree per view (as this used to do, with ChatWidget nested
  // inside only the 'overview' branch) would make React remount ChatWidget on every
  // navigation between views, wiping the conversation each time.
  let pageContent

  if (view === 'insights') {
    pageContent = (
      <TravelInsights
        analysis={analysis}
        lang={lang}
        colors={colors}
        isDark={isDark}
        onBack={() => setView('overview')}
      />
    )
  } else if (view === 'cost') {
    pageContent = (
      <CostBreakdown
        analysis={analysis}
        lang={lang}
        colors={colors}
        isDark={isDark}
        onBack={() => setView('overview')}
      />
    )
  } else if (view === 'portfolio') {
    pageContent = (
      <PortfolioDetail
        analysis={analysis}
        lang={lang}
        colors={colors}
        isDark={isDark}
        onBack={() => setView('overview')}
        cancelledSubs={cancelledSubs}
        onCancelSubscriptions={handleCancelSubscriptions}
      />
    )
  } else {
    pageContent = (
    <div style={{
      backgroundColor: colors.bg,
      color: colors.text,
      fontFamily: 'system-ui, -apple-system, sans-serif',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      boxSizing: 'border-box'
    }}>
      
      {/* RESPONSIVE CSS INJEKTION */}
      <style>{`
        @keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }
        .dashboard-container {
          display: grid;
          grid-template-columns: 1fr;
          gap: 1.25rem;
          width: 100%;
          max-width: 480px;
          margin: 0 auto;
          padding: 1.5rem 1.25rem 3rem 1.25rem;
          box-sizing: border-box;
        }

        /* Responsive Breakpoint für Desktop (z.B. Mac) */
        @media (min-width: 768px) {
          .dashboard-container {
            max-width: 1100px;
            grid-template-columns: repeat(12, 1fr);
          }
          .col-hero { grid-column: span 7; }
          .col-hero-stats { grid-column: span 5; }
          .col-current-subs { grid-column: span 6; }
          .col-travel { grid-column: span 6; }
          .col-portfolio { grid-column: span 12; }
        }
      `}</style>
      
      {/* =========================================================
          HEADER: CLEAN LOGO, LANG-TOGGLE & AVATAR Dropdown
          ========================================================= */}
      <header style={{
        padding: '1.25rem 1.5rem',
        borderBottom: `1px solid ${colors.border}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        position: 'sticky',
        top: 0,
        backgroundColor: isDark ? 'rgba(0,0,0,0.8)' : 'rgba(255,255,255,0.85)',
        backdropFilter: 'blur(12px)',
        zIndex: 100
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Logo showText={false} />
          <span style={{ fontSize: '1.2rem', fontWeight: '300', color: colors.text, letterSpacing: '-0.02em' }}>
            move<span style={{ fontWeight: '700', color: colors.accentCyan }}>optimizer</span>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          <ThemeToggle style={{ width: '35px', height: '35px' }} />
          {/* Unauffälliger Refresh-Button — erzwingt eine frische Analyse statt der
              gecachten letzten recommendations-Zeile (siehe orchestrator.py) */}
          <button
            onClick={handleForceRefresh}
            disabled={refreshing}
            title={t.refreshTitle}
            aria-label={t.refreshTitle}
            style={{
              backgroundColor: 'transparent',
              border: 'none',
              color: colors.textMuted,
              width: '28px',
              height: '28px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: refreshing ? 'default' : 'pointer',
              opacity: refreshing ? 0.5 : 1,
            }}
          >
            <RefreshCw size={15} style={refreshing ? { animation: 'spin 0.9s linear infinite' } : undefined} />
          </button>
          {/* Sprachumschalter */}
          <button 
            onClick={() => setLang(lang === 'DE' ? 'EN' : 'DE')}
            style={{
              backgroundColor: colors.card,
              border: `1px solid ${colors.border}`,
              color: colors.text,
              padding: '0.4rem 0.75rem',
              borderRadius: '20px',
              fontSize: '0.8rem',
              fontWeight: '600',
              display: 'flex',
              alignItems: 'center',
              gap: '0.35rem',
              cursor: 'pointer'
            }}
          >
            <Globe size={13} style={{ color: colors.accentCyan }} />
            {lang}
          </button>

          {/* Relativer Container für das Profil-Fenster */}
          <div style={{ position: 'relative' }}>
            {/* User Avatar (Öffnet das Menü bei Klick) */}
            <div 
              onClick={() => setProfileMenuOpen(!profileMenuOpen)}
              title={displayName}
              style={{
                width: '35px',
                height: '35px',
                borderRadius: '50%',
                backgroundColor: colors.accentPurple,
                color: colors.onAccent,
                fontWeight: '700',
                fontSize: '0.85rem',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                cursor: 'pointer'
              }}
            >
              {initials}
            </div>

            {/* Kleines interaktives Fenster */}
            {profileMenuOpen && (
              <div style={{
                position: 'absolute',
                top: '42px',
                right: 0,
                backgroundColor: colors.card,
                border: `1px solid ${colors.border}`,
                borderRadius: '14px',
                padding: '0.5rem',
                minWidth: '180px',
                display: 'flex',
                flexDirection: 'column',
                gap: '0.25rem',
                boxShadow: '0 10px 30px rgba(0,0,0,0.5)',
                zIndex: 110
              }}>
                <button 
                  onClick={() => {}} 
                  style={{
                    backgroundColor: 'transparent',
                    border: 'none',
                    color: colors.text,
                    padding: '0.55rem 0.75rem',
                    borderRadius: '10px',
                    fontSize: '0.85rem',
                    fontWeight: '500',
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'background-color 0.15s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#222226'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  👤 {t.editProfile}
                </button>
                
                <button 
                  onClick={() => {}} 
                  style={{
                    backgroundColor: 'transparent',
                    border: 'none',
                    color: colors.text,
                    padding: '0.55rem 0.75rem',
                    borderRadius: '10px',
                    fontSize: '0.85rem',
                    fontWeight: '500',
                    textAlign: 'left',
                    cursor: 'pointer',
                    transition: 'background-color 0.15s'
                  }}
                  onMouseEnter={(e) => e.currentTarget.style.backgroundColor = '#222226'}
                  onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                >
                  ⚙️ {t.settings}
                </button>

                <div style={{ height: '1px', backgroundColor: colors.border, margin: '0.2rem 0' }} />

                {/* Hervorgehobener Logout-Button */}
                <button 
                  onClick={() => {
                    setProfileMenuOpen(false);
                    logout();
                  }}
                  style={{
                    backgroundColor: 'rgba(244, 63, 94, 0.12)',
                    border: `1px solid rgba(244, 63, 94, 0.2)`,
                    color: colors.accentRed,
                    padding: '0.55rem 0.75rem',
                    borderRadius: '10px',
                    fontSize: '0.85rem',
                    fontWeight: '700',
                    textAlign: 'left',
                    cursor: 'pointer',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    transition: 'all 0.15s'
                  }}
                  onMouseEnter={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(244, 63, 94, 0.18)';
                    e.currentTarget.style.borderColor = 'rgba(244, 63, 94, 0.3)';
                  }}
                  onMouseLeave={(e) => {
                    e.currentTarget.style.backgroundColor = 'rgba(244, 63, 94, 0.12)';
                    e.currentTarget.style.borderColor = 'rgba(244, 63, 94, 0.2)';
                  }}
                >
                  <span>{t.logout}</span>
                  <LogOut size={13} />
                </button>
              </div>
            )}
          </div>
        </div>
      </header>

      {/* =========================================================
          MAIN SINGLE PAGE CONTENT
          ========================================================= */}
      <main className="dashboard-container">

        {/* 1. HERO CARD: OPTIMIZED STATUS */}
        <div className="col-hero" style={{
          backgroundColor: colors.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '24px',
          padding: '1.5rem',
          textAlign: 'left',
          position: 'relative',
          overflow: 'hidden',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center'
        }}>
          <div style={{
            position: 'absolute',
            top: 0,
            right: 0,
            width: '120px',
            height: '120px',
            background: `radial-gradient(circle, rgba(0, 242, 254, 0.08) 0%, transparent 70%)`,
            pointerEvents: 'none'
          }} />

          <div>
            <div style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: '0.35rem',
              backgroundColor: 'rgba(0, 242, 254, 0.08)',
              color: colors.accentCyan,
              padding: '0.35rem 0.75rem',
              borderRadius: '20px',
              fontSize: '0.75rem',
              fontWeight: '700',
              textTransform: 'uppercase',
              letterSpacing: '0.04em',
              marginBottom: '1rem'
            }}>
              <TrendingUp size={12} /> PERSONALIZED
            </div>

            <h2 style={{ color: colors.text, fontSize: '1.8rem', fontWeight: '800', letterSpacing: '-0.03em', marginBottom: '0.5rem', lineHeight: '1.2' }}>
              {heroTitle}
            </h2>
            <p style={{ color: colors.textMuted, fontSize: '0.9rem', lineHeight: '1.4' }}>
              {heroSub}
            </p>
          </div>
        </div>

        {/* 2. HERO-SIDE STATS — annual spend (wider, clickable through to the
            cost-breakdown subpage) and CO₂ footprint, side by side. Distance is
            intentionally left off the main dashboard now. Realized savings via
            subscriptions lives only on the cost subpage (see CostBreakdown.jsx). */}
        <div className="col-hero-stats" style={{ display: 'grid', gridTemplateColumns: '1.4fr 1fr', gap: '0.85rem' }}>
          <button
            onClick={() => setView('cost')}
            style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '20px', padding: '1.1rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between', textAlign: 'left', cursor: 'pointer', color: colors.text, font: 'inherit' }}
          >
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.7rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em' }}>{t.annualSpend}</span>
                <span style={{ color: colors.accentCyan }}><Wallet size={14} /></span>
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: '800', letterSpacing: '-0.02em' }}>{annualSpendStr}</div>
              <span style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.35rem', display: 'block' }}>{t.subAndTickets}</span>
            </div>
            <span style={{ fontSize: '0.78rem', color: colors.accentCyan, fontWeight: '700', marginTop: '0.6rem', display: 'flex', alignItems: 'center', gap: '0.2rem' }}>
              {t.viewDetails} <ChevronRight size={13} style={{ flexShrink: 0 }} />
            </span>
          </button>

          <div style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '20px', padding: '1.1rem', display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>
            <div>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
                <span style={{ fontSize: '0.7rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em' }}>{t.co2}</span>
                <span style={{ color: colors.successGreen }}><Leaf size={14} /></span>
              </div>
              <div style={{ fontSize: '1.5rem', fontWeight: '800', letterSpacing: '-0.02em' }}>{co2Str}</div>
            </div>
            <span style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.5rem' }}>{t.estimatedEmissions}</span>
          </div>
        </div>

        {/* 4. CURRENT SUBSCRIPTIONS — left */}
        <div className="col-current-subs" style={{
          backgroundColor: colors.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '24px',
          padding: '1.5rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.1rem' }}>
            <h3 style={{ color: colors.text, fontSize: '1.1rem', fontWeight: '700' }}>{t.currentSubsTitle}</h3>
            <Check size={18} style={{ color: colors.accentCyan }} />
          </div>
          {visibleSubscriptions.length > 0 ? (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
              {visibleSubscriptions.map((s) => {
                const label = s.provider_plan_name || s.provider_name || t.currentPlan
                const priceStr = s.monthly_cost_eur
                  ? `${euro(s.monthly_cost_eur, { lang: langKey })} ${t.perMonth}`
                  : s.annual_cost_eur
                    ? `${euro(s.annual_cost_eur, { lang: langKey })} ${t.perYear}`
                    : null
                const coverage = coverageBySubId.get(s.subscription_id)
                const netSavings = coverage?.net_savings_eur
                const worthIt = netSavings != null && netSavings >= 0
                return (
                  <div key={s.user_subscription_id || label} style={{ backgroundColor: colors.inputBg, borderRadius: '14px', padding: '0.75rem 1rem' }}>
                    <div style={{ fontSize: '0.85rem', color: colors.text, fontWeight: '500', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '0.5rem' }}>
                      <span>{subscriptionEmoji(s)} {label}</span>
                      <span style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', flexShrink: 0 }}>
                        {priceStr && <span style={{ color: colors.textMuted, fontWeight: '600', fontSize: '0.8rem' }}>{priceStr}</span>}
                        <Check size={16} style={{ color: colors.accentCyan }} />
                      </span>
                    </div>
                    {netSavings != null && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', marginTop: '0.4rem', fontSize: '0.75rem', fontWeight: '600', color: worthIt ? '#0ca30c' : colors.accentRed }}>
                        {worthIt ? <CheckCircle2 size={12} /> : <AlertTriangle size={12} />}
                        {worthIt ? t.worthIt(netSavings) : t.notWorthIt(Math.abs(netSavings))}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          ) : (
            <div style={{ backgroundColor: colors.inputBg, borderRadius: '14px', padding: '0.75rem 1rem', fontSize: '0.85rem', color: colors.textMuted, fontWeight: '500' }}>
              {t.noSubs}
            </div>
          )}
        </div>

        {/* 5. "HOW YOU TRAVEL" DISTRIBUTION — right */}
        <div className="col-travel" style={{
          backgroundColor: colors.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '24px',
          padding: '1.5rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <h3 style={{ color: colors.text, fontSize: '1.15rem', fontWeight: '700' }}>{t.howYouTravel}</h3>
            <BarChart3 size={18} style={{ color: colors.accentPurple }} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {modes.map((item, index) => (
              <div key={index}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.35rem', fontWeight: '500' }}>
                  <span style={{ color: colors.text }}>{item.name}</span>
                  <span style={{ color: colors.textMuted }}>
                    <span style={{ color: colors.text, fontWeight: '600' }}>{item.trips}</span> {t.tripsLabel} • {item.pct}%
                  </span>
                </div>
                <div style={{ width: '100%', height: '6px', backgroundColor: colors.border, borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${item.pct}%`, height: '100%', backgroundColor: item.color, borderRadius: '3px' }} />
                </div>
              </div>
            ))}
          </div>

          <button
            onClick={() => setView('insights')}
            style={{
              width: '100%', marginTop: '1.25rem', backgroundColor: 'transparent',
              border: 'none', color: colors.accentCyan, fontSize: '0.85rem', fontWeight: '700',
              padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem', cursor: 'pointer',
            }}
          >
            {t.viewDetails} <span style={{ fontSize: '1rem' }}>→</span>
          </button>
        </div>

        {/* 6. OPTIMIZED PORTFOLIO — full-width block */}
        <div className="col-portfolio" style={{
          backgroundColor: colors.card,
          border: `2px solid ${colors.accentCyan}`,
          borderRadius: '24px',
          padding: '1.5rem',
          position: 'relative',
          display: 'flex',
          flexDirection: 'column'
        }}>
          <div style={{
            position: 'absolute',
            top: '-12px',
            left: '20px',
            backgroundColor: colors.accentCyan,
            color: colors.onAccent,
            fontSize: '0.65rem',
            fontWeight: '800',
            padding: '0.2rem 0.6rem',
            borderRadius: '6px',
            textTransform: 'uppercase',
            letterSpacing: '0.05em'
          }}>
            BEST FOR YOU
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: '0.35rem', marginBottom: '1.1rem' }}>
            <h3 style={{ color: colors.text, fontSize: '1.1rem', fontWeight: '700' }}>{t.portfolioTitle}</h3>
            <TrendingUp size={18} style={{ color: colors.accentCyan }} />
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '1rem' }}>
            <span style={{ fontSize: '0.75rem', color: colors.textMuted, paddingTop: '0.15rem' }}>{t.estimated} · {t.recommended}</span>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '1.35rem', fontWeight: '800', color: colors.accentCyan }}>{recPriceStr}<span style={{ fontSize: '0.75rem', color: colors.textMuted, fontWeight: '400' }}> / yr</span></div>
              {summary && (
                <div style={{ fontSize: '0.72rem', color: colors.textMuted, marginTop: '0.2rem' }}>
                  {t.insteadOfBefore(totalCurrentStr)}
                  {recSavings !== 0 && (
                    <span style={{ fontWeight: '700', color: recSavings > 0 ? '#0ca30c' : colors.accentRed, marginLeft: '0.4rem' }}>
                      {recSavings > 0 ? t.savingsBadge(euro(Math.abs(recSavings), { lang: langKey })) : t.extraCostBadge(euro(Math.abs(recSavings), { lang: langKey }))}
                    </span>
                  )}
                </div>
              )}
            </div>
          </div>

          <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '0.85rem', marginTop: 'auto' }}>
            <span style={{ fontSize: '0.68rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em', display: 'block', marginBottom: '0.5rem' }}>
              {t.whatChanges}
            </span>
            {recSavings > 0 && recChanges.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                {recChanges.map((c, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: colors.text }}>
                    <span style={{ color: c.action === 'add' ? colors.successGreen : colors.accentRed, fontWeight: '800' }}>{c.action === 'add' ? '+' : '−'}</span>
                    {c.item}
                  </div>
                ))}
              </div>
            ) : (
              <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: colors.textMuted }}>
                <div style={{ width: '6px', height: '6px', borderRadius: '50%', backgroundColor: colors.accentCyan }} />
                {t.noChanges}
              </div>
            )}

            <button
              onClick={() => setView('portfolio')}
              style={{
                width: '100%', marginTop: '1rem', backgroundColor: 'transparent',
                border: 'none', color: colors.accentCyan, fontSize: '0.85rem', fontWeight: '700',
                padding: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '0.3rem', cursor: 'pointer',
              }}
            >
              {t.viewDetails} <span style={{ fontSize: '1rem' }}>→</span>
            </button>
          </div>
        </div>

      </main>
    </div>
    )
  }

  return (
    <>
      {pageContent}
      {currentUser?.id && (
        <ChatWidget
          user={currentUser}
          lang={lang.toLowerCase()}
          advisorMemo={summary?.memos?.[lang === 'DE' ? 'german' : 'english']}
          getContext={() => ({ recommendation: recommended, analysis })}
          actions={{ optimize: async () => summary?.category_subscription_analysis || [], approve: async () => true }}
          onOpenPortfolio={() => setView('portfolio')}
        />
      )}
    </>
  )
}