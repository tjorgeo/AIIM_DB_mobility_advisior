import React, { useState } from 'react'
import { ArrowRight, Wallet, Leaf, Route, AlertCircle, X, Check, Ban } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { DEMO_PASSWORD } from '../data/personas'
import Logo from '../components/Logo'

const FEATURES = [
  { icon: Wallet, text: 'See exactly what your mobility costs — and where it leaks.' },
  { icon: Route, text: 'Get a personalized plan tuned to how you actually travel.' },
  { icon: Leaf, text: 'Cut spend and CO₂ in a single, clear recommendation.' },
]

const TRANSPORT_MODES = [
  { id: 'walking', label: '🚶 Zu Fuß / Walking' },
  { id: 'bicycle', label: '🚲 Eigenes Fahrrad / Bicycle' },
  { id: 'bike_sharing', label: '🚴 Leihrad / Bike Sharing' },
  { id: 'public_transport', label: '🚌 ÖPNV / Bus & Tram' },
  { id: 'regional_train', label: '🚆 Regionalbahn / Regional Train' },
  { id: 'long_distance_train', label: '🚄 Fernverkehr / ICE & IC' },
  { id: 'car', label: '🚗 Eigenes Auto / Private Car' },
  { id: 'car_sharing', label: '🚘 Carsharing / Shared Car' },
  { id: 'e_scooter', label: '🛴 E-Scooter' },
  { id: 'ride_hailing', label: '🚖 Uber / Bolt / Ride Hailing' },
  { id: 'taxi', label: '🚕 Taxi' },
  { id: 'mixed', label: '🔄 Mix / Intermodal' },
  { id: 'other', label: '✨ Sonstiges / Other' }
]

export default function Login() {
  const { login, loginAs, personas } = useAuth()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [currentView, setCurrentView] = useState('welcome')

  // Onboarding Umfrage-Daten
  const [onboardingStep, setOnboardingStep] = useState(1)
  const [services, setServices] = useState([])
  const [hasLicense, setHasLicense] = useState(null)
  const [carAccess, setCarAccess] = useState('')
  const [frequentModes, setFrequentModes] = useState([]) 
  const [avoidModes, setAvoidModes] = useState([])       
  const [priorities, setPriorities] = useState([])
  const [activeCategory, setActiveCategory] = useState('')
  const [birthYear, setBirthYear] = useState('') 
  const [submitting, setSubmitting] = useState(false)

  const handleServiceToggle = (serviceId) => {
    setServices(prev => 
      prev.includes(serviceId) ? prev.filter(s => s !== serviceId) : [...prev, serviceId]
    )
  }

  const handleFrequentToggle = (id) => {
    setFrequentModes(prev =>
      prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
    )
    setAvoidModes(prev => prev.filter(m => m !== id))
  }

  const handleAvoidToggle = (id) => {
    setAvoidModes(prev =>
      prev.includes(id) ? prev.filter(m => m !== id) : [...prev, id]
    )
    setFrequentModes(prev => prev.filter(m => m !== id))
  }

  const handlePriorityToggle = (key) => {
    setPriorities(prev => {
      if (prev.includes(key)) {
        return prev.filter(p => p !== key);
      } else if (prev.length < 3) {
        return [...prev, key];
      }
      return prev;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    const res = await login(identifier, password)
    setSubmitting(false)
    if (!res.ok) setError(res.error)
  }

  const colors = {
    bg: '#000000',
    card: '#16161a',
    accentCyan: '#00f2fe',
    accentPurple: '#a855f7',
    accentRed: '#f43f5e',   
    textMuted: '#747C92',
    border: '#26262b'
  }

  const optionButtonStyle = {
    width: '100%',
    padding: '1.1rem 1.2rem',
    backgroundColor: colors.card,
    border: `1px solid ${colors.border}`,
    borderRadius: '16px',
    color: '#ffffff',
    fontSize: '0.95rem',
    fontWeight: '500',
    textAlign: 'left',
    cursor: 'pointer',
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center',
    boxSizing: 'border-box',
    transition: 'all 0.2s'
  }

  return (
    <div style={{ backgroundColor: colors.bg, color: '#ffffff', fontFamily: 'system-ui, -apple-system, sans-serif', minHeight: '100vh', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
      
      {/* =========================================================
          VIEW 1: CLEAN FINTECH ONBOARDING (WELCOME)
          ========================================================= */}
      {currentView === 'welcome' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', alignItems: 'center', padding: '2rem 1.5rem 2.5rem 1.5rem', textAlign: 'center', boxSizing: 'border-box', height: '100vh', overflow: 'hidden' }}>
          {/* Logo container */}
          <div style={{ marginTop: '0.25rem', display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '0.1rem' }}>
            <div style={{ transform: 'scale(1.2)', transformOrigin: 'center' }}>
              <Logo showText={false} />
            </div>
            <span style={{ fontSize: '1.5rem', fontWeight: '300', color: '#ffffff', letterSpacing: '-0.02em', marginTop: '0.5rem' }}>
              move<span style={{ fontWeight: '700', color: colors.accentCyan }}>optimizer</span>
            </span>
          </div>

          {/* Headline & Features */}
          <div style={{ width: '100%', maxWidth: '380px', marginTop: '1.5rem' }}>
            <h1 style={{ fontSize: '2.2rem', fontWeight: '800', color: '#ffffff', marginBottom: '1.5rem', letterSpacing: '-0.04em', lineHeight: '1.2' }}>
              Smarter mobility,<br /><span style={{ color: colors.accentCyan }}>less spend.</span>
            </h1>

            <ul style={{ listStyle: 'none', padding: 0, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.65rem', textAlign: 'left', maxWidth: '340px' }}>
              {FEATURES.map(({ icon: Icon, text }, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'start', gap: '0.75rem', lineHeight: '1.35' }}>
                  <span style={{ color: colors.accentPurple, display: 'flex', flexShrink: 0, marginTop: '2px' }}><Icon size={16} /></span>
                  <span style={{ color: '#ffffff', fontSize: '0.85rem' }}>{text}</span>
                </li>
              ))}
            </ul>
          </div>

          <div style={{ flex: 1 }} />

          {/* Action Buttons & AGB */}
          <div style={{ width: '100%', maxWidth: '380px', display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
            <button onClick={() => setCurrentView('onboarding')} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.05rem', fontWeight: '700', cursor: 'pointer', boxShadow: '0 4px 20px rgba(0, 242, 254, 0.15)' }}>
              Register
            </button>
            <button onClick={() => setCurrentView('login')} style={{ width: '100%', padding: '1rem', backgroundColor: 'transparent', color: '#ffffff', borderRadius: '14px', border: `1px solid ${colors.border}`, fontSize: '1.05rem', fontWeight: '600', cursor: 'pointer' }}>
              Sign in
            </button>
            <p style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.5rem', lineHeight: '1.4' }}>
              By continuing, you agree to our:<br />
              <span style={{ color: colors.accentCyan, cursor: 'pointer' }}>Terms of Service</span> – <span style={{ color: colors.accentCyan, cursor: 'pointer' }}>Privacy Policy</span>
            </p>
          </div>
        </div>
      )}

      {/* =========================================================
          VIEW 2: FRAGEN-STEPS (ONBOARDING)
          ========================================================= */}
      {currentView === 'onboarding' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '2rem 1.5rem 2.5rem 1.5rem', height: '100vh', boxSizing: 'border-box', overflow: 'hidden' }}>
          <div style={{ width: '100%', maxWidth: '400px', margin: '0 auto', display: 'flex', flexDirection: 'column', height: '100%' }}>
            
            <div 
              onClick={() => {
                if (onboardingStep === 1 && hasLicense !== null) {
                  setHasLicense(null);
                } else if (onboardingStep === 2) {
                  setHasLicense(null);
                  setCarAccess('');
                  setOnboardingStep(1);
                } else if (onboardingStep > 1) {
                  setOnboardingStep(onboardingStep - 1);
                } else {
                  setCurrentView('welcome');
                }
              }} 
              style={{ color: colors.accentCyan, cursor: 'pointer', fontSize: '1rem', fontWeight: '600', marginBottom: '1.5rem', display: 'flex', alignItems: 'center', gap: '0.25rem' }}
            >
              〈 Zurück
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>

              {/* STEP 1: FÜHRERSCHEIN & AUTO */}
              {onboardingStep === 1 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  {hasLicense === null ? (
                    <div>
                      <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Do you have a driving license?</h1>
                      <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left' }}>This helps us filter which sharing vehicles you are allowed to drive.</p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        <button onClick={() => setHasLicense(true)} style={{ ...optionButtonStyle, backgroundColor: hasLicense === true ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: hasLicense === true ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>Yes, I do 🚗</span></button>
                        <button onClick={() => { setHasLicense(false); setCarAccess('none'); setOnboardingStep(2); }} style={{ ...optionButtonStyle, backgroundColor: hasLicense === false ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: hasLicense === false ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>No, I don't ❌</span></button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                      <div>
                        <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Do you own a car?</h1>
                        <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left' }}>Tell us if you have constant access to a private vehicle.</p>
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                          {[
                            { id: 'own', label: 'Yes, I own a car 🚗' },
                            { id: 'shared', label: 'No, I rely on shared cars 🚙' },
                            { id: 'none', label: 'No car at all ❌' }
                          ].map((carOpt) => {
                            const isCarSelected = carAccess === carOpt.id;
                            return (
                              <button key={carOpt.id} onClick={() => setCarAccess(carOpt.id)} style={{ ...optionButtonStyle, backgroundColor: isCarSelected ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: isCarSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>{carOpt.label}</span></button>
                            );
                          })}
                        </div>
                      </div>
                      <div style={{ flex: 1 }} />
                      <button onClick={() => setOnboardingStep(2)} disabled={!carAccess} style={{ width: '100%', padding: '1.1rem', backgroundColor: carAccess ? colors.accentCyan : colors.card, color: carAccess ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s', marginTop: '1rem' }}>Weiter</button>
                    </div>
                  )}
                </div>
              )}

              {/* STEP 2: SUBSCRIPTIONS */}
              {onboardingStep === 2 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Which transit subscriptions do you have?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>Tap a category to reveal and select your active tickets or corporate benefits.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', maxHeight: '52vh', overflowY: 'auto', paddingRight: '2px' }}>
                      {[
                        { id: 'bahn', title: '🚆 ÖPNV & Deutsche Bahn', options: [{ id: 'deutschlandticket', label: 'Deutschlandticket (49€ Ticket)' }, { id: 'job_ticket', label: 'Job-Ticket (Corporate Transit)' }, { id: 'monthly_pass', label: 'Monatskarte / Monthly Pass' }, { id: 'bahncard25_50', label: 'DB BahnCard 25 / 50' }, { id: 'bahncard100', label: 'DB BahnCard 100' }] },
                        { id: 'car', title: '🚗 Carsharing & Verleih', options: [{ id: 'miles_pass', label: 'Miles Pass / ShareNow Silver & Gold' }, { id: 'sixt_share', label: 'SIXT share Flat / Plus' }, { id: 'teilauto', label: 'teilAuto (Rahmenvertrag / Abo)' }, { id: 'carsharing_regular', label: 'Regular Carsharing User (No Sub)' }] },
                        { id: 'scooter', title: '🛴 E-Scooter & Bike-Sharing', options: [{ id: 'scooter_flat', label: 'Tier / Voi Pass (Scooter Flat)' }, { id: 'dott', label: 'Dott Pass (Flat / Unilimited)' }, { id: 'swapfiets', label: 'Swapfiets (Fahrrad-Abo)' }, { id: 'nextbike', label: 'nextbike (Monats- / Jahreskarte)' }] }
                      ].map((cat) => {
                        if (cat.id === 'car' && hasLicense === false) return null;
                        const isOpen = activeCategory === cat.id;
                        return (
                          <div key={cat.id} style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                            <div onClick={() => setActiveCategory(isOpen ? '' : cat.id)} style={{ ...optionButtonStyle, padding: '1rem 1.2rem', backgroundColor: isOpen ? 'rgba(0, 242, 254, 0.02)' : colors.card, border: isOpen ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}`, fontWeight: '600' }}><span style={{ color: '#ffffff' }}>{cat.title}</span><span style={{ color: colors.accentCyan, fontSize: '0.8rem', transition: 'transform 0.2s', transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span></div>
                            {isOpen && (<div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem', paddingLeft: '0.75rem' }}>{cat.options.map((opt) => { const isSelected = services.includes(opt.id); return (<div key={opt.id} onClick={() => handleServiceToggle(opt.id)} style={{ ...optionButtonStyle, padding: '0.85rem 1rem', backgroundColor: isSelected ? 'rgba(168, 85, 247, 0.05)' : '#0d0d10', border: isSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span style={{ color: '#ffffff', fontSize: '0.9rem' }}>{opt.label}</span><div style={{ width: '16px', height: '16px', borderRadius: '5px', border: `2px solid ${colors.accentPurple}`, backgroundColor: isSelected ? colors.accentPurple : 'transparent', flexShrink: 0 }} /></div>); })}</div>)}
                          </div>
                        );
                      })}
                      <div onClick={() => handleServiceToggle('none')} style={{ ...optionButtonStyle, padding: '1rem 1.2rem', backgroundColor: services.includes('none') ? 'rgba(0, 242, 254, 0.05)' : colors.card, border: services.includes('none') ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}` }}><span style={{ color: '#ffffff' }}>❌ Keine Abos (Pay-per-Trip)</span><div style={{ width: '18px', height: '18px', borderRadius: '5px', border: `2px solid ${colors.accentCyan}`, backgroundColor: services.includes('none') ? colors.accentCyan : 'transparent', flexShrink: 0 }} /></div>
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setOnboardingStep(3)} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', marginTop: '1rem' }}>Weiter</button>
                </div>
              )}

              {/* STEP 3: HÄUFIGSTE TRANSPORTMITTEL */}
              {onboardingStep === 3 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>What are your primary modes of transit?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>Select the options you use most frequently for your daily commutes.</p>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', maxHeight: '52vh', overflowY: 'auto', paddingRight: '2px' }}>
                      {TRANSPORT_MODES.map((mode) => {
                        if ((mode.id === 'car' || mode.id === 'car_sharing') && hasLicense === false) return null;
                        const isSelected = frequentModes.includes(mode.id);

                        return (
                          <div 
                            key={mode.id}
                            onClick={() => handleFrequentToggle(mode.id)}
                            style={{
                              ...optionButtonStyle,
                              padding: '0.95rem 1.1rem',
                              backgroundColor: isSelected ? 'rgba(0, 242, 254, 0.04)' : colors.card,
                              border: isSelected ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}`
                            }}
                          >
                            <span style={{ color: '#ffffff', fontSize: '0.95rem' }}>{mode.label}</span>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', borderRadius: '6px', border: `2px solid ${colors.accentCyan}`, backgroundColor: isSelected ? colors.accentCyan : 'transparent', flexShrink: 0 }}>
                              {isSelected && <Check size={12} strokeWidth={3} color="#000000" />}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setOnboardingStep(4)} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', marginTop: '1rem' }}>Weiter</button>
                </div>
              )}

              {/* STEP 4: VERKEHRSMITTEL MEIDEN */}
              {onboardingStep === 4 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Are there modes you want to avoid?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>We will exclude these from recommendations (e.g. if you hate biking or buses).</p>
                    
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', maxHeight: '52vh', overflowY: 'auto', paddingRight: '2px' }}>
                      {TRANSPORT_MODES.map((mode) => {
                        if ((mode.id === 'car' || mode.id === 'car_sharing') && hasLicense === false) return null;
                        const isAvoided = avoidModes.includes(mode.id);

                        return (
                          <div 
                            key={mode.id}
                            onClick={() => handleAvoidToggle(mode.id)}
                            style={{
                              ...optionButtonStyle,
                              padding: '0.95rem 1.1rem',
                              backgroundColor: isAvoided ? 'rgba(244, 63, 94, 0.05)' : colors.card,
                              border: isAvoided ? `1px solid ${colors.accentRed}` : `1px solid ${colors.border}`
                            }}
                          >
                            <span style={{ color: isAvoided ? colors.accentRed : '#ffffff', fontSize: '0.95rem', fontWeight: isAvoided ? '600' : '500' }}>{mode.label}</span>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', borderRadius: '50%', border: `2px solid ${isAvoided ? colors.accentRed : colors.border}`, backgroundColor: isAvoided ? colors.accentRed : 'transparent', flexShrink: 0 }}>
                              {isAvoided && <Ban size={12} strokeWidth={3} color="#000000" />}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setOnboardingStep(5)} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', marginTop: '1rem' }}>Weiter</button>
                </div>
              )}

              {/* STEP 5: PRIORITÄTEN */}
              {onboardingStep === 5 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Rank your priorities</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left' }}>Tap the options in order to rank them from 1 (most important) to 3.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {[
                        { id: 'time', label: '⏱️ Saving Time (Speed)' },
                        { id: 'budget', label: '💰 Saving Money (Economy)' },
                        { id: 'environmental_concerns', label: '🌱 Protecting the Planet (CO₂)' }
                      ].map((p) => {
                        const rankIndex = priorities.indexOf(p.id);
                        const isSelected = rankIndex !== -1;
                        return (
                          <button key={p.id} onClick={() => handlePriorityToggle(p.id)} style={{ ...optionButtonStyle, backgroundColor: isSelected ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: isSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span style={{ color: '#ffffff' }}>{p.label}</span><div style={{ width: '24px', height: '24px', borderRadius: '50%', border: `2px solid ${isSelected ? colors.accentPurple : colors.border}`, backgroundColor: isSelected ? colors.accentPurple : 'transparent', display: 'flex', alignItems: 'center', justifyContent: 'center', color: isSelected ? '#000000' : colors.textMuted, fontSize: '0.85rem', fontWeight: '800', flexShrink: 0 }}>{isSelected ? rankIndex + 1 : ''}</div></button>
                        );
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setOnboardingStep(6)} disabled={priorities.length < 3} style={{ width: '100%', padding: '1.1rem', backgroundColor: priorities.length === 3 ? colors.accentCyan : colors.card, color: priorities.length === 3 ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: priorities.length === 3 ? 'pointer' : 'not-allowed', transition: 'all 0.2s', marginTop: '1rem' }}>{priorities.length === 3 ? 'Weiter' : 'Select all 3 to rank'}</button>
                </div>
              )}

              {/* STEP 6: GEBURTSJAHR */}
              {onboardingStep === 6 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.9rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.75rem', textAlign: 'left', lineHeight: '1.25' }}>In welchem Jahr bist du geboren?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2.5rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Basierend auf deinem Alter erhältst du passende Finanztipps.</p>
                    <div style={{ position: 'relative', backgroundColor: '#1c1c1f', borderRadius: '14px', border: birthYear ? `2px solid #ffffff` : `1px solid ${colors.border}`, padding: '0.6rem 1.1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ flex: 1, textAlign: 'left' }}><label style={{ display: 'block', color: colors.textMuted, fontSize: '0.75rem', marginBottom: '0.15rem' }}>Geburtsjahr</label><input type="number" placeholder="z.B. 2002" value={birthYear} onChange={(e) => setBirthYear(e.target.value)} style={{ width: '100%', backgroundColor: 'transparent', border: 'none', color: '#ffffff', fontSize: '1.2rem', fontWeight: '600', outline: 'none', padding: 0 }} /></div>
                      {birthYear && <X size={18} onClick={() => setBirthYear('')} style={{ color: colors.textMuted, cursor: 'pointer' }} />}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1rem' }}>
                    <button onClick={() => setOnboardingStep(7)} disabled={!birthYear || birthYear.length < 4} style={{ width: '100%', padding: '1.1rem', backgroundColor: (birthYear && birthYear.length >= 4) ? colors.accentCyan : colors.card, color: (birthYear && birthYear.length >= 4) ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: (birthYear && birthYear.length >= 4) ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                    <button onClick={() => { setBirthYear(''); setOnboardingStep(7); }} style={{ width: '100%', padding: '0.8rem', backgroundColor: 'transparent', color: colors.accentCyan, borderRadius: '14px', border: 'none', fontSize: '1.05rem', fontWeight: '600', cursor: 'pointer' }}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* STEP 7: CREATE ACCOUNT */}
              {onboardingStep === 7 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.9rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.25' }}>Create Account</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Set up your access keys to finish profile creation.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
                      <div style={{ textAlign: 'left' }}><label style={{ color: colors.textMuted, fontSize: '0.78rem', fontWeight: '500', display: 'block', marginBottom: '0.3rem', paddingLeft: '4px' }}>Full Name</label><input type="text" placeholder="e.g. John Doe" style={{ width: '100%', padding: '0.9rem 1.1rem', borderRadius: '14px', backgroundColor: '#1c1c1f', border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', fontWeight: '500', boxSizing: 'border-box', outline: 'none', transition: 'border-color 0.2s ease-in-out' }} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} /></div>
                      <div style={{ textAlign: 'left' }}><label style={{ color: colors.textMuted, fontSize: '0.78rem', fontWeight: '500', display: 'block', marginBottom: '0.3rem', paddingLeft: '4px' }}>Email Address</label><input type="email" placeholder="name@example.com" style={{ width: '100%', padding: '0.9rem 1.1rem', borderRadius: '14px', backgroundColor: '#1c1c1f', border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', fontWeight: '500', boxSizing: 'border-box', outline: 'none', transition: 'border-color 0.2s ease-in-out' }} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} /></div>
                      <div style={{ textAlign: 'left' }}><label style={{ color: colors.textMuted, fontSize: '0.78rem', fontWeight: '500', display: 'block', marginBottom: '0.3rem', paddingLeft: '4px' }}>Create Password</label><input type="password" placeholder="••••••••" style={{ width: '100%', padding: '0.9rem 1.1rem', borderRadius: '14px', backgroundColor: '#1c1c1f', border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', fontWeight: '500', boxSizing: 'border-box', outline: 'none', transition: 'border-color 0.2s ease-in-out' }} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} /></div>
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setCurrentView('login')} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', boxShadow: '0 4px 25px rgba(0, 242, 254, 0.25)', transition: 'all 0.2s', marginTop: '1rem' }}>Finish & Sign In</button>
                </div>
              )}

            </div>
          </div>
        </div>
      )}

      {/* =========================================================
          VIEW 3: STANDARD SIGN IN & DEMO PROFILES
          ========================================================= */}
      {currentView === 'login' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '2rem 1.5rem' }}>
          <div style={{ width: '100%', maxWidth: '400px' }}>
            <h2 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '#0.5rem', textAlign: 'center' }}>Welcome back</h2>
            <p style={{ color: colors.textMuted, marginBottom: '2.5rem', textAlign: 'center', fontSize: '0.95rem' }}>Sign in to see your personalized mobility plan.</p>

            <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ color: '#ffffff', fontSize: '0.85rem', fontWeight: '500', textAlign: 'left' }} htmlFor="email">Email</label>
                <input id="email" style={{ width: '100%', padding: '0.85rem', borderRadius: '12px', backgroundColor: colors.card, border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', boxSizing: 'border-box' }} type="email" placeholder="you@dbmove.de" value={email} onChange={(e) => { setEmail(e.target.value); setError('') }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ color: '#ffffff', fontSize: '0.85rem', fontWeight: '500', textAlign: 'left' }} htmlFor="password">Password</label>
                <input id="password" style={{ width: '100%', padding: '0.85rem', borderRadius: '12px', backgroundColor: colors.card, border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', boxSizing: 'border-box' }} type="password" placeholder="••••••••" value={password} onChange={(e) => { setPassword(e.target.value); setError('') }} />
              </div>

              {error && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ff4a5a', backgroundColor: 'rgba(255, 74, 90, 0.1)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                  <AlertCircle size={16} /><span>{error}</span>
                </div>
              )}

              <button style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '12px', border: 'none', fontSize: '1rem', fontWeight: '700', cursor: 'pointer', marginTop: '0.5rem', boxShadow: '0 4px 20px rgba(0, 242, 254, 0.2)' }} type="submit" disabled={submitting}>
                {submitting ? 'Signing in…' : 'Sign in'}
              </button>
            </form>

            <div style={{ display: 'flex', alignItems: 'center', color: '#52667a', fontSize: '0.8rem', textTransform: 'uppercase', margin: '2rem 0' }}>
              <div style={{ flex: 1, height: '1px', backgroundColor: colors.border }}></div>
              <span style={{ padding: '0 0.75rem' }}>or jump straight in</span>
              <div style={{ flex: 1, height: '1px', backgroundColor: colors.border }}></div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginBottom: '2rem' }}>
              {personas && personas.map((p) => (
                <button key={p.id} type="button" onClick={() => loginAs(p.id)} style={{ display: 'flex', alignItems: 'center', gap: '0.85rem', width: '100%', padding: '0.85rem', backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '14px', color: '#fff', cursor: 'pointer' }}>
                  <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '36px', height: '36px', borderRadius: '50%', backgroundColor: colors.border, color: colors.accentCyan, fontWeight: '700' }}>{p.initials}</span>
                  <span style={{ flex: 1, textAlign: 'left' }}><span style={{ fontWeight: '600' }}>{p.name}</span><br /><span style={{ fontSize: '0.8rem', color: colors.textMuted }}>{p.tagline}</span></span>
                  <ArrowRight style={{ color: colors.accentCyan }} size={16} />
                </button>
              ))}
            </div>

            <div onClick={() => setCurrentView('welcome')} style={{ color: colors.textMuted, cursor: 'pointer', textAlign: 'center', fontSize: '0.85rem', fontWeight: '500' }}>← Go back to start</div>
          </div>
        </div>
      )}

    </div>
  )
}