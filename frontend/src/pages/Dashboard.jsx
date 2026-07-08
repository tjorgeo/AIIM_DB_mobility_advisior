import React, { useState, useEffect } from 'react'
import { 
  Wallet, Leaf, Route, Globe, LogOut, TrendingUp, 
  Check, ChevronDown, ArrowUpRight, BarChart3, AlertCircle 
} from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import Logo from '../components/Logo'
import { analyze } from '../api/client'
import { euro, number } from '../lib/format'

export default function Dashboard() {
  const { logout, currentUser } = useAuth()
  const [lang, setLang] = useState('DE') // Standardmäßig auf Deutsch

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
      seePlan: 'Meinen Plan ansehen',
      annualSpend: 'JÄHRLICHE AUSGABEN',
      distance: 'DISTANZ',
      co2: 'CO₂-FUSABDRUCK (12 MONATE)',
      acrossTransit: 'Über alle Verkehrsmittel',
      estimatedEmissions: 'Geschätzte Emissionen',
      howYouTravel: 'Wie du reist',
      mostlyWalk: 'Hauptsächlich zu Fuß',
      recommended: 'Für dich empfohlen',
      basedMonths: 'Basiert auf deinen letzten 12 Monaten',
      portfolioTitle: 'Kostenoptimiertes Portfolio',
      currentPlan: 'Dein aktueller Tarif',
      whatChanges: 'WAS SICH ÄNDERT',
      noChanges: 'Keine Änderungen — behalte deinen Tarif bei',
      savingOpp: 'Sparpotenziale',
      perfectMix: 'Du nutzt bereits den perfekten Abo-Mix.',
      logout: 'Abmelden',
      subAndTickets: 'Abos + Tickets'
    },
    EN: {
      optimized: "You're optimized",
      optimizedSub: 'Your current plan already fits how you travel — no savings left on the table.',
      seePlan: 'See my plan',
      annualSpend: 'ANNUAL SPEND',
      distance: 'DISTANCE',
      co2: 'CO₂ FOOTPRINT (12 MO)',
      acrossTransit: 'Across all transit',
      estimatedEmissions: 'Estimated emissions',
      howYouTravel: 'How you travel',
      mostlyWalk: 'Mostly by walk',
      recommended: 'Recommended for you',
      basedMonths: 'Based on your last 12 months',
      portfolioTitle: 'Cost-Optimized Portfolio',
      currentPlan: 'Your current plan',
      whatChanges: 'WHAT CHANGES',
      noChanges: 'No changes — keep your current plan',
      savingOpp: 'Savings opportunities',
      perfectMix: 'You are already using the perfect subscription mix.',
      logout: 'Sign out',
      subAndTickets: 'Subscriptions + tickets'
    }
  }[lang]

  // Farbpalette exakt passend zur Onboarding/Login-Seite
  const colors = {
    bg: '#000000',
    card: '#16161a',
    accentCyan: '#00f2fe',
    accentPurple: '#a855f7',
    textMuted: '#747C92',
    border: '#26262b',
    successGreen: '#22c55e'
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

  const langKey = lang.toLowerCase()
  const analyst = analysis?.raw_agent_payloads?.analyst?.output || null
  const summary = analysis?.summary || null
  const scenarios = summary?.scenarios || []
  const recommended = scenarios.find((s) => s.id === summary?.recommended_scenario) || scenarios[0] || null

  const busy = (v) => (loadingData ? '…' : v)
  const annualSpendStr = analyst ? euro(analyst.current_annual_spend, { lang: langKey }) : busy('—')
  const distanceStr = analyst ? `${number(analyst.total_distance_km, langKey)} km` : busy('—')
  const co2Str = analyst ? `${number(analyst.co2_total_kg, langKey)} kg` : busy('—')
  const recPriceStr = recommended ? euro(recommended.annual_cost, { lang: langKey }) : annualSpendStr
  const recSavings = recommended?.annual_savings || 0
  const recChanges = recommended?.changes || []

  const palette = ['#00f2fe', '#a855f7', '#3b82f6', '#22c55e', '#eab308', '#f43f5e']
  const derivedTravelStats = analyst?.mode_breakdown
    ? Object.entries(analyst.mode_breakdown)
        .map(([name, d]) => ({
          name,
          trips: String(d.trips),
          pct: analyst.total_trips ? Math.round((d.trips / analyst.total_trips) * 100) : 0,
        }))
        .sort((a, b) => Number(b.trips) - Number(a.trips))
        .map((x, i) => ({ ...x, color: palette[i % palette.length] }))
    : null
  const modes = derivedTravelStats || travelStats

  return (
    <div style={{
      backgroundColor: colors.bg,
      color: '#ffffff',
      fontFamily: 'system-ui, -apple-system, sans-serif',
      minHeight: '100vh',
      display: 'flex',
      flexDirection: 'column',
      boxSizing: 'border-box'
    }}>
      
      {/* =========================================================
          HEADER: CLEAN LOGO, LANG-TOGGLE & AVATAR
          ========================================================= */}
      <header style={{
        padding: '1.25rem 1.5rem',
        borderBottom: `1px solid ${colors.border}`,
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        position: 'sticky',
        top: 0,
        backgroundColor: 'rgba(0,0,0,0.8)',
        backdropFilter: 'blur(12px)',
        zIndex: 100
      }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Logo showText={false} />
          <span style={{ fontSize: '1.2rem', fontWeight: '300', color: '#ffffff', letterSpacing: '-0.02em' }}>
            move<span style={{ fontWeight: '700', color: colors.accentCyan }}>optimizer</span>
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '1rem' }}>
          {/* Sprachumschalter */}
          <button 
            onClick={() => setLang(lang === 'DE' ? 'EN' : 'DE')}
            style={{
              backgroundColor: colors.card,
              border: `1px solid ${colors.border}`,
              color: '#ffffff',
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

          {/* User Avatar (Abmelden per Klick) */}
          <div 
            onClick={logout}
            title={`${displayName} — ${t.logout}`}
            style={{
              width: '35px',
              height: '35px',
              borderRadius: '50%',
              backgroundColor: colors.accentPurple,
              color: '#000000',
              fontWeight: '700',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              position: 'relative'
            }}
          >
            {initials}
          </div>
        </div>
      </header>

      {/* =========================================================
          MAIN SINGLE PAGE CONTENT (SWIPE DOWN ENGINE)
          ========================================================= */}
      <main style={{
        flex: 1,
        width: '100%',
        maxWidth: '480px',
        margin: '0 auto',
        padding: '1.5rem 1.25rem 3rem 1.25rem',
        display: 'flex',
        flexDirection: 'column',
        gap: '1.25rem',
        boxSizing: 'border-box'
      }}>

        {/* 1. HERO HERO CARD: OPTIMIZED STATUS */}
        <div style={{
          backgroundColor: colors.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '24px',
          padding: '1.5rem',
          textAlign: 'left',
          position: 'relative',
          overflow: 'hidden'
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

          <h2 style={{ fontSize: '1.8rem', fontWeight: '800', letterSpacing: '-0.03em', marginBottom: '0.5rem', lineHeight: '1.2' }}>
            {t.optimized}
          </h2>
          <p style={{ color: colors.textMuted, fontSize: '0.9rem', lineHeight: '1.4', marginBottom: '1.25rem' }}>
            {t.optimizedSub}
          </p>
          
          <button style={{
            backgroundColor: 'transparent',
            border: 'none',
            color: colors.accentCyan,
            fontSize: '0.9rem',
            fontWeight: '700',
            padding: 0,
            display: 'flex',
            alignItems: 'center',
            gap: '0.25rem',
            cursor: 'pointer'
          }}>
            {t.seePlan} <span style={{ fontSize: '1.1rem' }}>↓</span>
          </button>
        </div>

        {/* 2. CORE CORE STATS (GRID CONFIGURATION) */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '1rem' }}>
          {/* ANNUAL SPEND */}
          <div style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '20px', padding: '1.1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em' }}>{t.annualSpend}</span>
              <span style={{ color: colors.accentCyan }}><Wallet size={14} /></span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', letterSpacing: '-0.02em' }}>{annualSpendStr}</div>
            <span style={{ fontSize: '0.75rem', color: colors.textMuted }}>{t.subAndTickets}</span>
          </div>

          {/* DISTANCE */}
          <div style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '20px', padding: '1.1rem' }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '0.75rem' }}>
              <span style={{ fontSize: '0.7rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em' }}>{t.distance}</span>
              <span style={{ color: colors.accentPurple }}><Route size={14} /></span>
            </div>
            <div style={{ fontSize: '1.5rem', fontWeight: '800', letterSpacing: '-0.02em' }}>{distanceStr}</div>
            <span style={{ fontSize: '0.75rem', color: colors.textMuted }}>{t.acrossTransit}</span>
          </div>
        </div>

        {/* CO₂ CARD */}
        <div style={{
          backgroundColor: colors.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '20px',
          padding: '1.1rem',
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center'
        }}>
          <div>
            <span style={{ fontSize: '0.7rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em', display: 'block', marginBottom: '0.35rem' }}>
              {t.co2}
            </span>
            <div style={{ fontSize: '1.6rem', fontWeight: '800', letterSpacing: '-0.02em' }}>{co2Str}</div>
            <span style={{ fontSize: '0.75rem', color: colors.textMuted }}>{t.estimatedEmissions}</span>
          </div>
          <div style={{ width: '40px', height: '40px', borderRadius: '12px', backgroundColor: 'rgba(34, 197, 94, 0.08)', display: 'flex', alignItems: 'center', justifyInContent: 'center', color: colors.successGreen }}>
            <Leaf size={20} style={{ margin: 'auto' }} />
          </div>
        </div>

        {/* 3. PORTFOLIO RECOMMENDATION CARD */}
        <div style={{
          backgroundColor: colors.card,
          border: `2px solid ${colors.accentCyan}`,
          borderRadius: '24px',
          padding: '1.25rem',
          position: 'relative'
        }}>
          <div style={{
            position: 'absolute',
            top: '-12px',
            left: '20px',
            backgroundColor: colors.accentCyan,
            color: '#000000',
            fontSize: '0.65rem',
            fontWeight: '800',
            padding: '0.2rem 0.6rem',
            borderRadius: '6px',
            textTransform: 'uppercase',
            letterSpacing: '0.05em'
          }}>
            BEST FOR YOU
          </div>

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'start', marginTop: '0.25rem', marginBottom: '1rem' }}>
            <div>
              <h3 style={{ fontSize: '1.1rem', fontWeight: '700', marginBottom: '0.15rem' }}>{t.portfolioTitle}</h3>
              <span style={{ fontSize: '0.75rem', color: colors.textMuted }}>{t.recommended}</span>
            </div>
            <div style={{ textAlign: 'right' }}>
              <div style={{ fontSize: '1.35rem', fontWeight: '800', color: colors.accentCyan }}>{recPriceStr}<span style={{ fontSize: '0.75rem', color: colors.textMuted, fontWeight: '400' }}> / yr</span></div>
            </div>
          </div>

          <div style={{ backgroundColor: '#1c1c22', borderRadius: '14px', padding: '0.75rem 1rem', fontSize: '0.85rem', color: '#ffffff', fontWeight: '500', marginBottom: '1rem', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span>⭐ {t.currentPlan}</span>
            <Check size={16} style={{ color: colors.accentCyan }} />
          </div>

          <div style={{ borderTop: `1px solid ${colors.border}`, paddingTop: '0.85rem' }}>
            <span style={{ fontSize: '0.68rem', fontWeight: '700', color: colors.textMuted, letterSpacing: '0.05em', display: 'block', marginBottom: '0.5rem' }}>
              {t.whatChanges}
            </span>
            {recSavings > 0 && recChanges.length > 0 ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.45rem' }}>
                {recChanges.map((c, i) => (
                  <div key={i} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: '#ffffff' }}>
                    <span style={{ color: c.action === 'add' ? colors.successGreen : colors.accentPurple, fontWeight: '800' }}>{c.action === 'add' ? '+' : '−'}</span>
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
          </div>
        </div>

        {/* 4. "HOW YOU TRAVEL" DISTRIBUTION */}
        <div style={{
          backgroundColor: colors.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '24px',
          padding: '1.5rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '1.25rem' }}>
            <div>
              <h3 style={{ fontSize: '1.15rem', fontWeight: '700' }}>{t.howYouTravel}</h3>
              <span style={{ fontSize: '0.78rem', color: colors.textMuted }}>{modes[0] ? `${lang === 'DE' ? 'Meist' : 'Mostly'} ${modes[0].name}` : t.mostlyWalk}</span>
            </div>
            <BarChart3 size={18} style={{ color: colors.accentPurple }} />
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
            {modes.map((item, index) => (
              <div key={index}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem', marginBottom: '0.35rem', fontWeight: '500' }}>
                  <span style={{ color: '#ffffff' }}>{item.name}</span>
                  <span style={{ color: colors.textMuted }}>
                    <span style={{ color: '#ffffff', fontWeight: '600' }}>{item.trips}</span> trips • {item.pct}%
                  </span>
                </div>
                {/* Progress bar im Trade Republic Stil */}
                <div style={{ width: '100%', height: '6px', backgroundColor: '#26262b', borderRadius: '3px', overflow: 'hidden' }}>
                  <div style={{ width: `${item.pct}%`, height: '100%', backgroundColor: item.color, borderRadius: '3px' }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* 5. SAVINGS OPPORTUNITIES HEADER */}
        <div style={{
          backgroundColor: colors.card,
          border: `1px solid ${colors.border}`,
          borderRadius: '20px',
          padding: '1.2rem',
          display: 'flex',
          alignItems: 'center',
          gap: '0.75rem'
        }}>
          <div style={{ color: colors.accentCyan }}><ArrowUpRight size={20} /></div>
          <div style={{ textAlign: 'left' }}>
            <h4 style={{ fontSize: '0.95rem', fontWeight: '700', marginBottom: '0.1rem' }}>{t.savingOpp}</h4>
            <p style={{ fontSize: '0.8rem', color: colors.textMuted, margin: 0 }}>{t.perfectMix}</p>
          </div>
        </div>

      </main>
    </div>
  )
}