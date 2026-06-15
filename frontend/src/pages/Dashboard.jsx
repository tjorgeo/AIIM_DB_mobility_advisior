import React, { useState, useEffect, useCallback, useRef } from 'react'
import { Sparkles, RotateCcw, CheckCircle, AlertCircle, ArrowDown } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { analyze, approve as apiApprove } from '../api/client'
import { euro } from '../lib/format'
import AppShell from '../components/AppShell.jsx'
import StatCards from '../components/StatCards.jsx'
import RecommendationCard from '../components/RecommendationCard.jsx'
import ForecastChart from '../components/ForecastChart.jsx'
import Insights from '../components/Insights.jsx'
import AdvisorNote from '../components/AdvisorNote.jsx'
import SkeletonDashboard from '../components/SkeletonDashboard.jsx'
import ChatWidget from '../components/chat/ChatWidget.jsx'

function recOf(result) {
  const s = result?.summary?.scenarios || []
  return s.find((x) => x.id === result.summary.recommended_scenario) || s[0] || null
}

export default function Dashboard() {
  const { currentUser, logout } = useAuth()
  const [lang, setLang] = useState('en')
  const [status, setStatus] = useState('loading') // loading | ready | error
  const [result, setResult] = useState(null)
  const [approvedScenarioId, setApprovedScenarioId] = useState(null)
  const [toast, setToast] = useState('')

  const resultRef = useRef(null)
  const inflightRef = useRef(null)
  const plansRef = useRef(null)
  const t = (en, de) => (lang === 'de' ? de : en)

  const runAnalysis = useCallback(() => {
    setStatus('loading')
    setApprovedScenarioId(null)
    setToast('')
    const p = (async () => {
      try {
        const data = await analyze(currentUser.id)
        resultRef.current = data
        setResult(data)
        setStatus('ready')
        return data
      } catch {
        setStatus('error')
        return null
      } finally {
        inflightRef.current = null
      }
    })()
    inflightRef.current = p
    return p
  }, [currentUser.id])

  // Auto-run the analysis when the dashboard mounts.
  useEffect(() => { runAnalysis() }, [runAnalysis])

  const handleApprove = useCallback(async (scenarioId) => {
    const r = resultRef.current
    if (!r) return false
    try {
      const res = await apiApprove(r.session_id, scenarioId)
      if (res.status === 'success') {
        setApprovedScenarioId(scenarioId)
        setToast(t('Your new plan is saved ✓', 'Dein neuer Tarif ist gespeichert ✓'))
        return true
      }
      return false
    } catch {
      return false
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [lang])

  // Chat wiring — stable references that always read the latest data.
  const getContext = useCallback(() => ({
    status,
    result: resultRef.current,
    recommendation: resultRef.current ? recOf(resultRef.current) : null,
  }), [status])

  const actionsRef = useRef({})
  actionsRef.current.optimize = () => resultRef.current || inflightRef.current || runAnalysis()
  actionsRef.current.approve = handleApprove

  const analyst = result?.raw_agent_payloads?.analyst?.output
  const forecaster = result?.raw_agent_payloads?.forecaster?.output
  const rec = result ? recOf(result) : null
  const savings = rec?.annual_savings || 0
  const memo = lang === 'de' ? result?.summary?.memos?.german : result?.summary?.memos?.english
  const dataReady = status === 'ready' && analyst && forecaster && result?.summary

  return (
    <>
      <AppShell
        user={currentUser}
        lang={lang}
        onToggleLang={() => setLang((l) => (l === 'en' ? 'de' : 'en'))}
        onSwitchProfile={logout}
        onLogout={logout}
      />

      <main className="content-wrap dash">
        {status === 'loading' && <SkeletonDashboard />}

        {status === 'error' && (
          <div className="card state">
            <span className="state__icon"><AlertCircle size={26} /></span>
            <h3>{t('We couldn’t load your plan', 'Plan konnte nicht geladen werden')}</h3>
            <p>{t('Please make sure you’re connected and try again.', 'Bitte prüfe deine Verbindung und versuche es erneut.')}</p>
            <button className="btn btn--primary" onClick={runAnalysis}>
              <RotateCcw size={16} /> {t('Try again', 'Erneut versuchen')}
            </button>
          </div>
        )}

        {dataReady && (
          <div className="dash__stack">
            {toast && (
              <div className="toast"><CheckCircle size={16} /> {toast}</div>
            )}

            {/* Hero summary */}
            <section className={`hero${savings > 0 ? '' : ' hero--flat'}`}>
              <span className="hero__eyebrow"><Sparkles size={13} /> <span>{t('Personalized for you', 'Für dich personalisiert')}</span></span>
              {savings > 0 ? (
                <>
                  <div className="hero__amount">{euro(savings, { lang })} <span>/ {t('year', 'Jahr')}</span></div>
                  <p className="hero__sub">
                    {t(
                      `That's how much you could save by switching to “${rec.label}”. Here's your personalized breakdown.`,
                      `So viel kannst du sparen, wenn du zu „${rec.label}“ wechselst. Hier ist deine persönliche Auswertung.`,
                    )}
                  </p>
                </>
              ) : (
                <>
                  <div className="hero__amount">{t('You’re optimized', 'Optimal aufgestellt')}</div>
                  <p className="hero__sub">
                    {t(
                      'Your current plan already fits how you travel — no savings left on the table.',
                      'Dein Tarif passt bereits zu deinem Reiseverhalten — kein Sparpotenzial offen.',
                    )}
                  </p>
                </>
              )}
              <div className="hero__actions">
                <button className="btn btn--primary" onClick={() => plansRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })}>
                  {t('See my plan', 'Plan ansehen')} <ArrowDown size={16} />
                </button>
                <button className="btn btn--ghost" onClick={runAnalysis}>
                  <RotateCcw size={15} /> {t('Re-run', 'Neu berechnen')}
                </button>
              </div>
            </section>

            <StatCards analyst={analyst} lang={lang} />

            <div className="dash__cols">
              <div ref={plansRef} style={{ scrollMarginTop: 88 }}>
                <RecommendationCard
                  summary={result.summary}
                  lang={lang}
                  approvedScenarioId={approvedScenarioId}
                  onApprove={handleApprove}
                />
              </div>

              <div className="dash__stack">
                <ForecastChart forecaster={forecaster} lang={lang} />
                <Insights inefficiencies={analyst.inefficiencies} lang={lang} />
                <AdvisorNote memo={memo} lang={lang} />
              </div>
            </div>
          </div>
        )}
      </main>

      <ChatWidget user={currentUser} lang={lang} getContext={getContext} actions={actionsRef.current} />
    </>
  )
}
