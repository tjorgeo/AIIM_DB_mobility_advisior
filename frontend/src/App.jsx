import React, { useState, useEffect } from 'react'
import { 
  Users, 
  Activity, 
  TrendingUp, 
  Settings, 
  Compass, 
  ArrowRight, 
  CheckCircle, 
  XCircle, 
  Terminal, 
  Calendar, 
  Euro, 
  Leaf, 
  Car, 
  Train, 
  AlertTriangle, 
  Award,
  Globe,
  RefreshCw,
  FolderOpen
} from 'lucide-react'

export default function App() {
  const [personas, setPersonas] = useState([])
  const [activePersona, setActivePersona] = useState(null)
  const [loading, setLoading] = useState(false)
  const [result, setResult] = useState(null)
  const [activeInspectorTab, setActiveInspectorTab] = useState('analyst')
  const [approvedScenarioId, setApprovedScenarioId] = useState(null)
  const [feedbackMsg, setFeedbackMsg] = useState('')
  const [lang, setLang] = useState('en') // 'en' or 'de'
  const [inspectorOpen, setInspectorOpen] = useState(true)

  // Fetch personas on mount
  useEffect(() => {
    fetchPersonas()
  }, [])

  const fetchPersonas = async () => {
    try {
      const response = await fetch('/api/personas')
      const data = await response.json()
      setPersonas(data)
      if (data.length > 0) {
        setActivePersona(data[0])
      }
    } catch (error) {
      console.error("Error fetching personas:", error)
    }
  }

  const runAnalysis = async () => {
    if (!activePersona) return
    setLoading(true)
    setResult(null)
    setApprovedScenarioId(null)
    setFeedbackMsg('')
    
    try {
      const response = await fetch('/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ user_id: activePersona.id })
      })
      const data = await response.json()
      setResult(data)
    } catch (error) {
      console.error("Error running E2E multi-agent analysis:", error)
    } finally {
      setLoading(false)
    }
  }

  const approveScenario = async (scenarioId) => {
    if (!result) return
    try {
      const response = await fetch(`/api/recommendations/${result.session_id}/approve`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario_id: scenarioId })
      })
      const data = await response.json()
      if (data.status === 'success') {
        setApprovedScenarioId(scenarioId)
        setFeedbackMsg(lang === 'en' ? 'Recommendation approved! Changes successfully saved to database.' : 'Empfehlung genehmigt! Änderungen erfolgreich in der Datenbank gespeichert.')
      }
    } catch (error) {
      console.error("Error approving scenario:", error)
    }
  }

  return (
    <div className="app-container">
      {/* DB Brand Corporate Header */}
      <header className="app-header">
        <div className="header-brand">
          <div className="db-logo">DB</div>
          <div className="header-title">
            <h1>MoveOptimizer</h1>
            <span>Strategy IT Data Consulting Sandbox</span>
          </div>
        </div>
        
        <div className="header-actions">
          <button className="btn-primary" style={{ padding: '6px 12px', fontSize: '11px', width: 'auto', display: 'flex', gap: '4px' }} onClick={() => setLang(lang === 'en' ? 'de' : 'en')}>
            <Globe size={14} />
            {lang === 'en' ? 'Switch to German' : 'Auf Englisch umstellen'}
          </button>
          <span className="consulting-badge">BCG Platinion Pilot</span>
        </div>
      </header>

      {/* Main Portal Content Grid */}
      <main className="portal-main">
        
        {/* Column 1: Persona Simulator Selector */}
        <section className="sidebar-panel">
          <div>
            <h2 className="section-title">
              <Users size={16} />
              {lang === 'en' ? 'Traveler Simulator' : 'Reisenden-Simulator'}
            </h2>
            <p style={{ fontSize: '11px', color: '#6B7280', marginBottom: '14px' }}>
              {lang === 'en' ? 'Select a synthetic persona to simulate custom 12-month travel histories and subscriptions:' : 'Wählen Sie ein künstliches Profil aus, um 12-monatige Reiseverläufe und Abos zu simulieren:'}
            </p>
            
            {personas.map((persona) => (
              <div 
                key={persona.id} 
                className={`persona-card ${activePersona?.id === persona.id ? 'active' : ''}`}
                onClick={() => {
                  setActivePersona(persona)
                  setResult(null)
                  setApprovedScenarioId(null)
                  setFeedbackMsg('')
                }}
              >
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span className="persona-name">{persona.name}</span>
                  <span style={{ fontSize: '9px', fontWeight: 'bold', padding: '2px 6px', borderRadius: '4px', backgroundColor: '#E5E7EB' }}>
                    {persona.preferences.class_preference}
                  </span>
                </div>
                <span className="persona-id">ID: {persona.db_customer_id}</span>
                
                {persona.subscriptions.length > 0 ? (
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: '4px', marginTop: '6px' }}>
                    {persona.subscriptions.map((s, idx) => (
                      <span key={idx} style={{ fontSize: '8px', color: '#EC0016', backgroundColor: '#FEE2E2', padding: '2px 6px', borderRadius: '4px', textTransform: 'capitalize' }}>
                        {s.service.replace(/_/g, ' ')}
                      </span>
                    ))}
                  </div>
                ) : (
                  <span style={{ fontSize: '8px', color: '#6B7280', fontStyle: 'italic', marginTop: '6px' }}>
                    {lang === 'en' ? 'No active subscriptions' : 'Keine aktiven Abonnements'}
                  </span>
                )}
              </div>
            ))}
          </div>

          <button 
            className="btn-primary" 
            onClick={runAnalysis}
            disabled={loading}
          >
            {loading ? (
              <>
                <RefreshCw className="spinner" size={16} />
                {lang === 'en' ? 'Orchestrating Agents...' : 'Agenten werden koordiniert...'}
              </>
            ) : (
              <>
                <Activity size={16} />
                {lang === 'en' ? 'Execute 4-Agent Audit' : '4-Agenten-Audit starten'}
              </>
            )}
          </button>
        </section>

        {/* Column 2: Central Analytical Portal */}
        <section className="center-dashboard">
          
          {loading && (
            <div className="loading-overlay">
              <div className="spinner"></div>
              <h3 style={{ fontFamily: 'var(--font-heading)' }}>
                {lang === 'en' ? 'Running E2E Sandbox Pipeline' : 'E2E-Sandbox-Pipeline wird ausgeführt'}
              </h3>
              <p style={{ fontSize: '12px', color: '#6B7280' }}>
                {lang === 'en' ? 'Analyst → Forecaster → Optimizer → Communicator' : 'Analyst → Forecaster → Optimizer → Communicator'}
              </p>
            </div>
          )}

          {!loading && !result && (
            <div className="empty-state">
              <Compass size={48} color="#C30012" style={{ marginBottom: '8px' }} />
              <h3 style={{ fontSize: '20px', fontFamily: 'var(--font-heading)' }}>
                {lang === 'en' ? 'Ready for Strategic IT Audit' : 'Bereit für strategisches IT-Audit'}
              </h3>
              <p style={{ fontSize: '13px', color: '#6B7280', maxWidth: '400px', margin: '0 auto' }}>
                {lang === 'en' ? 'Select a customer persona in the sidebar and run the analysis to spin up the 4-agent state machine.' : 'Wählen Sie links ein Kundenprofil aus und starten Sie die Analyse, um die 4-Agenten-Zustandsmaschine zu aktivieren.'}
              </p>
            </div>
          )}

          {!loading && result && (
            <>
              {/* Persona Priorities Header */}
              <div className="dashboard-card" style={{ padding: '16px 24px' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h2 style={{ fontSize: '18px' }}>{result.customer_name}</h2>
                    <p style={{ fontSize: '11px', color: '#6B7280' }}>{lang === 'en' ? 'Digital Account:' : 'Digitales Konto:'} {result.db_customer_id}</p>
                  </div>
                  
                  <div style={{ display: 'flex', gap: '24px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                      <span style={{ fontSize: '10px', color: '#6B7280', textTransform: 'uppercase', fontWeight: 600 }}>
                        {lang === 'en' ? 'Cost Focus' : 'Kostenfokus'}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: '80px', height: '6px', backgroundColor: '#E5E7EB', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ width: `${result.preferences.cost_priority}%`, height: '100%', backgroundColor: '#EC0016' }}></div>
                        </div>
                        <span style={{ fontSize: '11px', fontWeight: 'bold' }}>{result.preferences.cost_priority}%</span>
                      </div>
                    </div>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end' }}>
                      <span style={{ fontSize: '10px', color: '#6B7280', textTransform: 'uppercase', fontWeight: 600 }}>
                        {lang === 'en' ? 'Eco Focus' : 'Ökofokus'}
                      </span>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                        <div style={{ width: '80px', height: '6px', backgroundColor: '#E5E7EB', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{ width: `${result.preferences.co2_priority}%`, height: '100%', backgroundColor: '#00875A' }}></div>
                        </div>
                        <span style={{ fontSize: '11px', fontWeight: 'bold' }}>{result.preferences.co2_priority}%</span>
                      </div>
                    </div>
                  </div>
                </div>
              </div>

              {/* 1. Analyst Agent Panel */}
              <div className="dashboard-card">
                <div className="card-header-flex">
                  <h3 style={{ fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Activity size={18} color="#EC0016" />
                    {lang === 'en' ? 'Analyst Agent: Inefficiency Audit' : 'Analyst Agent: Ineffizienz-Audit'}
                  </h3>
                  <div className="pipeline-status">
                    <div className="pulse-dot"></div>
                    <span>{lang === 'en' ? 'Analyst Complete' : 'Analyst abgeschlossen'}</span>
                  </div>
                </div>

                <div className="stats-grid">
                  <div className="stat-widget">
                    <span className="stat-label">{lang === 'en' ? '12mo Trips' : '12M Fahrten'}</span>
                    <span className="stat-value">{result.raw_agent_payloads.analyst.output.total_trips}</span>
                    <span className="stat-subtext">
                      {lang === 'en' ? 'Total logs parsed' : 'Gesamte Protokolle parsed'}
                    </span>
                  </div>
                  <div className="stat-widget">
                    <span className="stat-label">{lang === 'en' ? 'Total Distance' : 'Gesamtdistanz'}</span>
                    <span className="stat-value">{result.raw_agent_payloads.analyst.output.total_distance_km.toLocaleString()} km</span>
                    <span className="stat-subtext">
                      {lang === 'en' ? 'Across all transits' : 'Über alle Verkehrsmittel'}
                    </span>
                  </div>
                  <div className="stat-widget">
                    <span className="stat-label">{lang === 'en' ? 'Annual spend' : 'Jahresausgaben'}</span>
                    <span className="stat-value" style={{ color: '#EC0016' }}>€{result.raw_agent_payloads.analyst.output.current_annual_spend.toFixed(2)}</span>
                    <span className="stat-subtext">
                      {lang === 'en' ? 'Fees + ticket costs' : 'Abogebühren + Tickets'}
                    </span>
                  </div>
                  <div className="stat-widget">
                    <span className="stat-label">{lang === 'en' ? 'Carbon Footprint' : 'CO₂-Bilanz'}</span>
                    <span className="stat-value" style={{ color: '#00875A' }}>{(result.raw_agent_payloads.analyst.output.co2_total_kg / 1000).toFixed(2)} t</span>
                    <span className="stat-subtext">
                      {lang === 'en' ? 'CO2 metric tons' : 'Tonnen CO2'}
                    </span>
                  </div>
                </div>

                {/* Flagged Inefficiencies */}
                <h4 style={{ fontSize: '12px', color: '#6B7280', textTransform: 'uppercase', marginBottom: '10px' }}>
                  {lang === 'en' ? 'Flagged System Inefficiencies' : 'Identifizierte Ineffizienzen'}
                </h4>
                
                {result.raw_agent_payloads.analyst.output.inefficiencies.length > 0 ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    {result.raw_agent_payloads.analyst.output.inefficiencies.map((ineff, idx) => (
                      <div key={idx} style={{ borderLeft: '3px solid #EC0016', padding: '8px 14px', backgroundColor: '#FFF5F5', borderRadius: '0 4px 4px 0', display: 'flex', gap: '10px', alignItems: 'flex-start' }}>
                        <AlertTriangle size={16} color="#EC0016" style={{ marginTop: '2px', flexShrink: 0 }} />
                        <div>
                          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
                            <span style={{ fontSize: '12px', fontWeight: 'bold' }}>{ineff.service}</span>
                            <span style={{ fontSize: '10px', color: '#EC0016', backgroundColor: '#FEE2E2', padding: '1px 6px', borderRadius: '4px', fontWeight: 'bold' }}>
                              -{lang === 'en' ? 'Waste' : 'Verlust'}: €{ineff.annual_waste}
                            </span>
                          </div>
                          <p style={{ fontSize: '11px', color: '#4B5563', marginTop: '2px' }}>{ineff.details}</p>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div style={{ display: 'flex', gap: '8px', alignItems: 'center', backgroundColor: '#F0FDF4', color: '#166534', padding: '10px 14px', borderRadius: '4px', fontSize: '11px' }}>
                    <CheckCircle size={16} />
                    <span>{lang === 'en' ? 'No major financial inefficiencies flagged in baseline. Excellent provisioning!' : 'Keine wesentlichen Ineffizienzen gefunden. Hervorragende Tarifwahl!'}</span>
                  </div>
                )}
              </div>

              {/* 2. Forecaster Agent Panel */}
              <div className="dashboard-card">
                <div className="card-header-flex">
                  <h3 style={{ fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <TrendingUp size={18} color="#0066B3" />
                    {lang === 'en' ? 'Forecaster Agent: 6-Month Demand Projection' : 'Forecaster Agent: 6-Monats-Bedarfsprognose'}
                  </h3>
                  <div className="pipeline-status" style={{ color: '#0066B3', backgroundColor: '#E5F0FA' }}>
                    <div className="pulse-dot" style={{ backgroundColor: '#0066B3' }}></div>
                    <span>{lang === 'en' ? 'Forecaster Complete' : 'Forecaster abgeschlossen'}</span>
                  </div>
                </div>

                <p style={{ fontSize: '12px', color: '#4B5563', fontStyle: 'italic' }}>
                  "{result.raw_agent_payloads.forecaster.output.trend}" — {lang === 'en' ? 'Confidence Score' : 'Konfidenz'}: {(result.raw_agent_payloads.forecaster.output.confidence_score * 100).toFixed(0)}%
                </p>

                {/* CSS Chart Representation */}
                <div className="chart-container">
                  <div className="chart-bars">
                    {result.raw_agent_payloads.forecaster.output.forecast_6mo.map((m, idx) => {
                      // Max trips across all is probably around 40
                      const val = m.total_trips
                      const heightPercent = Math.min((val / 44) * 100, 100)
                      return (
                        <div key={idx} className="chart-bar-group">
                          <div 
                            className="chart-bar" 
                            style={{ height: `${heightPercent}%` }}
                          >
                            <span className="chart-bar-val">{val}</span>
                          </div>
                          <span className="chart-bar-label">{m.month.split(' ')[0]}</span>
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              {/* 3. Optimizer Agent Panel */}
              <div className="dashboard-card">
                <div className="card-header-flex">
                  <h3 style={{ fontSize: '15px', display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Award size={18} color="#00875A" />
                    {lang === 'en' ? 'Optimizer Agent: Contract Portfolios' : 'Optimizer Agent: Vertrags-Portfolios'}
                  </h3>
                  <div className="pipeline-status" style={{ color: '#00875A', backgroundColor: '#E2F0EA' }}>
                    <div className="pulse-dot" style={{ backgroundColor: '#00875A' }}></div>
                    <span>{lang === 'en' ? 'Optimizer Complete' : 'Optimizer abgeschlossen'}</span>
                  </div>
                </div>

                <div className="scenario-grid">
                  {result.summary.scenarios.map((scen, idx) => {
                    const isCheapest = scen.id === result.summary.recommended_scenario
                    return (
                      <div 
                        key={idx} 
                        className={`scenario-card ${isCheapest ? 'recommended' : ''}`}
                      >
                        {isCheapest && (
                          <div className="recommended-badge">
                            {lang === 'en' ? 'Recommended Strategy' : 'Empfohlene Strategie'}
                          </div>
                        )}
                        
                        <div className="scenario-header">
                          <h3>{scen.label}</h3>
                          <p>{lang === 'en' ? 'Calculated Simulation' : 'Berechnete Jahressimulation'}</p>
                        </div>

                        <div className="price-tag">
                          <span className="price-val">€{scen.annual_cost.toFixed(2)}</span>
                          <span style={{ fontSize: '12px', color: '#6B7280' }}>/ {lang === 'en' ? 'yr' : 'Jahr'}</span>
                        </div>

                        {scen.annual_savings > 0 ? (
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <span className="savings-label">
                              {lang === 'en' ? 'Save' : 'Sparen'}: €{scen.annual_savings.toFixed(2)} / {lang === 'en' ? 'yr' : 'Jahr'}
                            </span>
                          </div>
                        ) : (
                          <div style={{ display: 'flex', alignItems: 'center' }}>
                            <span className="savings-label" style={{ backgroundColor: '#F3F4F6', color: '#4B5563' }}>
                              {lang === 'en' ? 'Baseline' : 'Aktuelle Ausgaben'}
                            </span>
                          </div>
                        )}

                        <div style={{ fontSize: '11px', color: '#4B5563', flex: 1 }}>
                          <p style={{ fontWeight: 'bold', marginBottom: '6px' }}>
                            {lang === 'en' ? 'Operations Required:' : 'Erforderliche Schritte:'}
                          </p>
                          {scen.changes.length > 0 ? (
                            scen.changes.map((chg, cIdx) => (
                              <div key={cIdx} className={`change-item ${chg.action}`}>
                                <span style={{ fontWeight: 800 }}>{chg.action.toUpperCase()}</span>
                                <span>{chg.item}</span>
                              </div>
                            ))
                          ) : (
                            <span style={{ fontStyle: 'italic', color: '#6B7280' }}>
                              {lang === 'en' ? 'No adjustments. Keep active packages.' : 'Keine Anpassungen. Behalten Sie Ihre Abos.'}
                            </span>
                          )}
                        </div>

                        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', borderTop: '1px solid #F3F4F6', paddingTop: '12px', fontSize: '11px' }}>
                          <span style={{ color: '#00875A', fontWeight: 'bold', display: 'flex', alignItems: 'center', gap: '4px' }}>
                            <Leaf size={14} />
                            -{scen.co2_savings_kg.toFixed(0)} kg CO₂
                          </span>
                          
                          <button 
                            className="btn-primary" 
                            style={{ width: 'auto', padding: '6px 12px', fontSize: '11px', borderRadius: '4px' }}
                            onClick={() => approveScenario(scen.id)}
                            disabled={approvedScenarioId !== null}
                          >
                            {approvedScenarioId === scen.id ? (
                              <>
                                <CheckCircle size={12} />
                                {lang === 'en' ? 'Approved' : 'Genehmigt'}
                              </>
                            ) : (
                              <>
                                {lang === 'en' ? 'Approve Portfolio' : 'Portfolio wählen'}
                              </>
                            )}
                          </button>
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            </>
          )}
        </section>

        {/* Column 3: AI Conversational Chat Drawer (Communicator) */}
        <section className="communicator-chat">
          <div className="chat-header">
            <div className="agent-avatar">AI</div>
            <div>
              <h3 style={{ fontSize: '14px', fontWeight: '700' }}>
                {lang === 'en' ? 'Communicator Agent' : 'Communicator Agent'}
              </h3>
              <p style={{ fontSize: '10px', color: '#00875A', fontWeight: '600' }}>
                ● {lang === 'en' ? 'Mobility Advisor Online' : 'Berater Online'}
              </p>
            </div>
          </div>

          <div className="chat-body">
            {result ? (
              <>
                <div className="bubble assistant">
                  <p style={{ fontSize: '11px', color: '#374151', textTransform: 'uppercase', letterSpacing: '0.5px', fontWeight: 'bold', marginBottom: '8px', display: 'flex', alignItems: 'center', gap: '4px' }}>
                    <FolderOpen size={14} color="#EC0016" />
                    {lang === 'en' ? 'Consulting Memo' : 'Strategieberater-Memo'}
                  </p>
                  
                  {/* Print English or German letter */}
                  <div style={{ whiteSpace: 'pre-line', fontSize: '12px', color: '#2D323D' }}>
                    {lang === 'en' ? result.summary.memos.english : result.summary.memos.german}
                  </div>
                </div>
                
                {approvedScenarioId && (
                  <div className="bubble user">
                    <p style={{ fontWeight: 'bold' }}>
                      {lang === 'en' ? `Approved Scenario ${approvedScenarioId}!` : `Szenario ${approvedScenarioId} genehmigt!`}
                    </p>
                    <p style={{ fontSize: '11px', marginTop: '2px', opacity: 0.9 }}>
                      {lang === 'en' ? 'Please record this in my corporate DB Account.' : 'Bitte loggen Sie diese Entscheidung in meinem DB-Konto.'}
                    </p>
                  </div>
                )}
              </>
            ) : (
              <div style={{ display: 'flex', flex1: 1, alignItems: 'center', justifyContent: 'center', height: '100%', color: '#9CA3AF', fontSize: '12px', fontStyle: 'italic', textAlign: 'center', padding: '20px' }}>
                {lang === 'en' ? 'Waiting for analytical data to draft personalized recommendation...' : 'Warten auf Analysedaten, um ein personalisiertes Memo zu erstellen...'}
              </div>
            )}
          </div>

          <div className="chat-actions">
            {feedbackMsg && (
              <div style={{ display: 'flex', gap: '6px', alignItems: 'center', backgroundColor: '#ECFDF5', border: '1px solid #A7F3D0', color: '#065F46', padding: '10px 12px', borderRadius: '6px', fontSize: '11px', fontWeight: '600' }}>
                <CheckCircle size={14} />
                <span>{feedbackMsg}</span>
              </div>
            )}
            
            {result && !approvedScenarioId && (
              <div style={{ display: 'flex', gap: '8px' }}>
                <button 
                  className="btn-primary"
                  onClick={() => approveScenario(result.summary.recommended_scenario)}
                  style={{ flex: 1 }}
                >
                  {lang === 'en' ? 'Accept Recommended' : 'Empfehlung annehmen'}
                </button>
                
                <button 
                  className="btn-primary"
                  onClick={() => setApprovedScenarioId('REJECTED')}
                  style={{ flex: 1, backgroundColor: '#F3F4F6', color: '#4B5563', border: '1px solid var(--db-border)' }}
                >
                  {lang === 'en' ? 'Keep Current' : 'Aktuelles behalten'}
                </button>
              </div>
            )}
          </div>
        </section>

      </main>

      {/* Expandable Technical Pipeline Inspector */}
      <footer className="inspector-panel">
        <div className="inspector-header" onClick={() => setInspectorOpen(!inspectorOpen)}>
          <div className="inspector-title">
            <Terminal size={14} color="#EC0016" />
            <span>{lang === 'en' ? 'Real-Time Multi-Agent Pipeline Inspector' : 'Echtzeit Multi-Agenten-Pipeline Inspektor'}</span>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
            <div className="inspector-tabs" onClick={(e) => e.stopPropagation()}>
              <button 
                className={`tab-btn ${activeInspectorTab === 'analyst' ? 'active' : ''}`}
                onClick={() => setActiveInspectorTab('analyst')}
              >
                1. Analyst IO
              </button>
              <button 
                className={`tab-btn ${activeInspectorTab === 'forecaster' ? 'active' : ''}`}
                onClick={() => setActiveInspectorTab('forecaster')}
              >
                2. Forecaster IO
              </button>
              <button 
                className={`tab-btn ${activeInspectorTab === 'optimizer' ? 'active' : ''}`}
                onClick={() => setActiveInspectorTab('optimizer')}
              >
                3. Optimizer IO
              </button>
              <button 
                className={`tab-btn ${activeInspectorTab === 'communicator' ? 'active' : ''}`}
                onClick={() => setActiveInspectorTab('communicator')}
              >
                4. Communicator IO
              </button>
            </div>
            
            <span style={{ fontSize: '10px', color: '#5C6A7F' }}>
              {inspectorOpen ? '▼' : '▲'}
            </span>
          </div>
        </div>

        {inspectorOpen && (
          <div className="inspector-body">
            {result ? (
              <pre className="json-pre">
                {JSON.stringify(result.raw_agent_payloads[activeInspectorTab], null, 2)}
              </pre>
            ) : (
              <span style={{ color: '#5C6A7F', fontStyle: 'italic', fontSize: '11px' }}>
                {lang === 'en' ? '// Awaiting E2E orchestration to capture agent payloads.' : '// Warten auf die E2E-Orchestrierung, um die Agenten-Payloads zu erfassen.'}
              </span>
            )}
          </div>
        )}
      </footer>
    </div>
  )
}
