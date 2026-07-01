import React, { useState } from 'react'
import { ArrowRight, Wallet, Leaf, Route, AlertCircle, X, Check, Ban } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { submitOnboarding } from '../api/client'
import Logo from '../components/Logo'

const FEATURES = [
  { icon: Wallet, text: 'Sieh genau, was deine Mobilität kostet – und wo Geld verloren geht.' },
  { icon: Route, text: 'Erhalte einen persönlichen Plan, abgestimmt darauf, wie du wirklich unterwegs bist.' },
  { icon: Leaf, text: 'Senke Kosten und CO₂ mit einer einzigen, klaren Empfehlung.' },
]

const TRANSPORT_MODES = [
  { id: 'walking', label: '🚶 Zu Fuß' },
  { id: 'bicycle', label: '🚲 Eigenes Fahrrad' },
  { id: 'bike_sharing', label: '🚴 Leihrad / Bike-Sharing' },
  { id: 'public_transport', label: '🚌 ÖPNV / Bus & Tram' },
  { id: 'regional_train', label: '🚆 Regionalbahn' },
  { id: 'long_distance_train', label: '🚄 Fernverkehr (ICE & IC)' },
  { id: 'car', label: '🚗 Eigenes Auto' },
  { id: 'car_sharing', label: '🚘 Carsharing' },
  { id: 'e_scooter', label: '🛴 E-Scooter' },
  { id: 'ride_hailing', label: '🚖 Uber / Bolt / Ride-Hailing' },
  { id: 'taxi', label: '🚕 Taxi' },
  { id: 'mixed', label: '🔄 Mix / Intermodal' },
  { id: 'other', label: '✨ Sonstiges' }
]

// Lesbare Labels für die in Schritt 2 wählbaren Abos (für die Abo-Detail-Frage)
const SERVICE_LABELS = {
  deutschlandticket: 'Deutschlandticket',
  job_ticket: 'Job-Ticket',
  monthly_pass: 'Monatskarte',
  bahncard25_50: 'BahnCard 25 / 50',
  bahncard100: 'BahnCard 100',
  miles_pass: 'Miles / ShareNow',
  sixt_share: 'SIXT share',
  teilauto: 'teilAuto',
  carsharing_regular: 'Carsharing (ohne Abo)',
  scooter_flat: 'Tier / Voi Pass',
  dott: 'Dott Pass',
  swapfiets: 'Swapfiets',
  nextbike: 'nextbike'
}

const WEEKDAY_PATTERNS = [
  '🏢 Pendeln ins Büro',
  '🏠 Homeoffice mit kurzen Wegen',
  '🗓️ Viel unterwegs (Termine / Außendienst)',
  '🛋️ Kaum unterwegs'
]

const WEEKEND_PATTERNS = [
  '🛋️ Meist zu Hause',
  '🏙️ Lokale Freizeit in der Stadt',
  '🌳 Ausflüge ins Umland',
  '✈️ Häufig längere Reisen'
]

const COUNTRY_OPTIONS = [
  { code: 'DE', label: '🇩🇪 Deutschland' },
  { code: 'AT', label: '🇦🇹 Österreich' },
  { code: 'CH', label: '🇨🇭 Schweiz' },
  { code: 'NL', label: '🇳🇱 Niederlande' },
  { code: 'FR', label: '🇫🇷 Frankreich' },
  { code: 'BE', label: '🇧🇪 Belgien' },
  { code: 'LU', label: '🇱🇺 Luxemburg' },
  { code: 'PL', label: '🇵🇱 Polen' }
]

export default function Login() {
  const { login, loginAs, personas, setSession } = useAuth()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [currentView, setCurrentView] = useState('welcome')

  // Onboarding Umfrage-Daten
  const [onboardingStep, setOnboardingStep] = useState(1)
  const [services, setServices] = useState([])
  const [hasLicense, setHasLicense] = useState(null)
  const [carAccess, setCarAccess] = useState('')
  const [bikeAccess, setBikeAccess] = useState('')
  const [frequentModes, setFrequentModes] = useState([]) 
  const [avoidModes, setAvoidModes] = useState([])       
  const [priorities, setPriorities] = useState([])
  const [activeCategory, setActiveCategory] = useState('')
  const [birthYear, setBirthYear] = useState('') 
  const [submitting, setSubmitting] = useState(false)

  // Persönliche & Kontext-Daten (jeweils überspringbar)
  const [homeCity, setHomeCity] = useState('')
  const [homePostalCode, setHomePostalCode] = useState('')
  const [workArrangement, setWorkArrangement] = useState('')      // onsite | hybrid | remote | unemployed
  const [workCity, setWorkCity] = useState('')
  const [workPostalCode, setWorkPostalCode] = useState('')
  const [remoteDaysPerWeek, setRemoteDaysPerWeek] = useState(null) // 0..5 → remote_work_share
  const [mobilityBudget, setMobilityBudget] = useState('')
  const [householdSize, setHouseholdSize] = useState('')
  const [incomeBand, setIncomeBand] = useState('')

  // Abo-Details, Wochenmuster, Konto-Daten
  const [subscriptionDetails, setSubscriptionDetails] = useState({}) // { [serviceId]: { type, billing } }
  const [typicalWeekday, setTypicalWeekday] = useState('')
  const [typicalWeekend, setTypicalWeekend] = useState('')
  const [homeCountry, setHomeCountry] = useState('DE')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [gender, setGender] = useState('')

  const setSubDetail = (sid, field, value) => {
    setSubscriptionDetails(prev => ({ ...prev, [sid]: { ...(prev[sid] || {}), [field]: value } }))
  }

  // Priorität (Rang) -> Score 0..100 für die DB
  const rankScore = (key) => {
    const i = priorities.indexOf(key)
    return i === -1 ? 0 : [100, 66, 33][i] ?? 0
  }

  // Baut das vollständige Profil und schickt es ans Backend (POST /api/register)
  const handleFinish = async () => {
    setError('')
    if (!firstName.trim() || !lastName.trim() || !regEmail.trim() || !regPassword) {
      setError('Bitte Vor-/Nachname, E-Mail und Passwort ausfüllen.')
      return
    }
    const remoteShare =
      workArrangement === 'remote' ? 1
      : workArrangement === 'onsite' ? 0
      : (workArrangement === 'hybrid' && remoteDaysPerWeek != null) ? Number((remoteDaysPerWeek / 5).toFixed(3))
      : null

    const profile = {
      user: {
        first_name: firstName.trim() || null,
        last_name: lastName.trim() || null,
        email: regEmail.trim() || null,
        gender: gender || 'not_specified',
        date_of_birth: birthYear ? `${birthYear}-01-01` : null,
        age: birthYear ? (new Date().getFullYear() - Number(birthYear)) : null,
        home_city: homeCity.trim() || null,
        home_postal_code: homePostalCode.trim() || null,
        home_country_code: homeCountry || 'DE'
      },
      onboarding: {
        has_driving_license: hasLicense,
        car_access: carAccess || null,
        bike_access: bikeAccess || null,
        preferred_transport_modes: frequentModes,
        avoided_transport_modes: avoidModes,
        score_money: rankScore('budget'),
        score_emission: rankScore('environmental_concerns'),
        score_flexibility: rankScore('time'),
        work_arrangement: workArrangement || null,
        work_city: workCity.trim() || null,
        work_postal_code: workPostalCode.trim() || null,
        remote_work_share: remoteShare,
        mobility_budget_monthly_eur: mobilityBudget !== '' ? Number(mobilityBudget) : null,
        household_size: householdSize ? (householdSize === '5+' ? 5 : Number(householdSize)) : null,
        income_band: incomeBand || null,
        typical_weekday_pattern: typicalWeekday || null,
        typical_weekend_pattern: typicalWeekend || null,
        // NOT-NULL-Textfelder: clientseitig aus den Antworten generiert
        travel_statement: `Bevorzugt: ${frequentModes.join(', ') || 'k. A.'}. Meidet: ${avoidModes.join(', ') || 'nichts'}.`,
        activity_statement: `Werktags: ${typicalWeekday || 'k. A.'}. Wochenende: ${typicalWeekend || 'k. A.'}.`
      },
      subscriptions: services.filter(s => s !== 'none').map(sid => ({
        service: sid,
        subscription_type: subscriptionDetails[sid]?.type || 'subscription',
        billing_cycle: subscriptionDetails[sid]?.billing || 'monthly'
      })),
      // Passwort getrennt, falls das Backend ein Auth-Konto anlegt
      credentials: { password: regPassword || null }
    }

    setSubmitting(true)
    try {
      const res = await submitOnboarding(profile)
      setSubmitting(false)
      if (res.ok) {
        // Direkt eingeloggt ins Dashboard, wenn das Backend das User-Objekt liefert.
        if (res.data?.user) {
          setSession(res.data.user)
        } else {
          setCurrentView('login')
        }
      } else {
        setError(res.error || 'Speichern fehlgeschlagen. Bitte erneut versuchen.')
      }
    } catch {
      setSubmitting(false)
      setError('Verbindung zum Server fehlgeschlagen.')
    }
  }

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

  const textInputStyle = {
    width: '100%',
    padding: '0.9rem 1.1rem',
    borderRadius: '14px',
    backgroundColor: '#1c1c1f',
    border: `1px solid ${colors.border}`,
    color: '#fff',
    fontSize: '1rem',
    fontWeight: '500',
    boxSizing: 'border-box',
    outline: 'none',
    transition: 'border-color 0.2s ease-in-out'
  }

  const inputLabelStyle = {
    color: colors.textMuted,
    fontSize: '0.78rem',
    fontWeight: '500',
    display: 'block',
    marginBottom: '0.3rem',
    paddingLeft: '4px',
    textAlign: 'left'
  }

  const skipLinkStyle = {
    width: '100%',
    padding: '0.8rem',
    backgroundColor: 'transparent',
    color: colors.accentCyan,
    borderRadius: '14px',
    border: 'none',
    fontSize: '1.05rem',
    fontWeight: '600',
    cursor: 'pointer'
  }

  return (
    <div style={{ backgroundColor: colors.bg, color: '#ffffff', fontFamily: 'system-ui, -apple-system, sans-serif', minHeight: '100vh', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
      
      {/* =========================================================
          ANSICHT 1: ONBOARDING-START (WILLKOMMEN)
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
              Clever unterwegs,<br /><span style={{ color: colors.accentCyan }}>weniger zahlen.</span>
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
              Registrieren
            </button>
            <button onClick={() => setCurrentView('login')} style={{ width: '100%', padding: '1rem', backgroundColor: 'transparent', color: '#ffffff', borderRadius: '14px', border: `1px solid ${colors.border}`, fontSize: '1.05rem', fontWeight: '600', cursor: 'pointer' }}>
              Anmelden
            </button>
            <p style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.5rem', lineHeight: '1.4' }}>
              Mit dem Fortfahren akzeptierst du unsere:<br />
              <span style={{ color: colors.accentCyan, cursor: 'pointer' }}>Nutzungsbedingungen</span> – <span style={{ color: colors.accentCyan, cursor: 'pointer' }}>Datenschutzrichtlinie</span>
            </p>
          </div>
        </div>
      )}

      {/* =========================================================
          ANSICHT 2: FRAGE-SCHRITTE (ONBOARDING)
          ========================================================= */}
      {currentView === 'onboarding' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between', padding: '2rem 1.5rem 2.5rem 1.5rem', height: '100vh', boxSizing: 'border-box', overflow: 'hidden' }}>
          <div style={{ width: '100%', maxWidth: '400px', margin: '0 auto', display: 'flex', flexDirection: 'column', height: '100%' }}>
            
            <div 
              onClick={() => {
                if (onboardingStep === 1 && hasLicense !== null) {
                  setHasLicense(null);
                  setCarAccess('');
                  setBikeAccess('');
                } else if (onboardingStep === 2) {
                  setHasLicense(null);
                  setCarAccess('');
                  setBikeAccess('');
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

              {/* SCHRITT 1: FÜHRERSCHEIN & AUTO */}
              {onboardingStep === 1 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  {hasLicense === null ? (
                    <div>
                      <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Hast du einen Führerschein?</h1>
                      <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left' }}>So können wir filtern, welche Sharing-Fahrzeuge du fahren darfst.</p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                        <button onClick={() => setHasLicense(true)} style={{ ...optionButtonStyle, backgroundColor: hasLicense === true ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: hasLicense === true ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>Ja, habe ich 🚗</span></button>
                        <button onClick={() => { setHasLicense(false); setCarAccess('none'); }} style={{ ...optionButtonStyle, backgroundColor: hasLicense === false ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: hasLicense === false ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>Nein, habe ich nicht ❌</span></button>
                      </div>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                      <div style={{ overflowY: 'auto', maxHeight: '72vh', paddingRight: '2px' }}>
                        <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Worauf hast du Zugriff?</h1>
                        <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', textAlign: 'left' }}>So wissen wir, welche Verkehrsmittel für deine Empfehlungen überhaupt in Frage kommen.</p>

                        {/* AUTO — nur bei Führerschein relevant */}
                        {hasLicense === true && (
                          <div style={{ marginBottom: '1.5rem' }}>
                            <span style={{ color: '#ffffff', fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>🚗 Auto</span>
                            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                              {[
                                { id: 'own', label: 'Eigenes Auto' },
                                { id: 'shared', label: 'Carsharing (z. B. Miles, SIXT)' },
                                { id: 'occasional', label: 'Gelegentlich (z. B. Familienauto)' },
                                { id: 'none', label: 'Gar kein Auto' }
                              ].map((carOpt) => {
                                const isCarSelected = carAccess === carOpt.id;
                                return (
                                  <button key={carOpt.id} onClick={() => setCarAccess(carOpt.id)} style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isCarSelected ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: isCarSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>{carOpt.label}</span></button>
                                );
                              })}
                            </div>
                          </div>
                        )}

                        {/* FAHRRAD — immer relevant */}
                        <div>
                          <span style={{ color: '#ffffff', fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>🚲 Fahrrad</span>
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                            {[
                              { id: 'own', label: 'Eigenes Fahrrad' },
                              { id: 'shared', label: 'Leihrad / Bike-Sharing (z. B. nextbike)' },
                              { id: 'occasional', label: 'Gelegentlich' },
                              { id: 'none', label: 'Kein Fahrrad' }
                            ].map((bikeOpt) => {
                              const isBikeSelected = bikeAccess === bikeOpt.id;
                              return (
                                <button key={bikeOpt.id} onClick={() => setBikeAccess(bikeOpt.id)} style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isBikeSelected ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: isBikeSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>{bikeOpt.label}</span></button>
                              );
                            })}
                          </div>
                        </div>
                      </div>
                      <div style={{ flex: 1 }} />
                      {(() => {
                        const ready = (hasLicense === false || carAccess) && bikeAccess;
                        return (
                          <button onClick={() => setOnboardingStep(2)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s', marginTop: '1rem' }}>Weiter</button>
                        );
                      })()}
                    </div>
                  )}
                </div>
              )}

              {/* SCHRITT 2: ABOS */}
              {onboardingStep === 2 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Welche Mobilitäts-Abos hast du?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>Tippe auf eine Kategorie, um deine aktiven Tickets oder Firmenleistungen auszuwählen.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem', maxHeight: '52vh', overflowY: 'auto', paddingRight: '2px' }}>
                      {[
                        { id: 'bahn', title: '🚆 ÖPNV & Deutsche Bahn', options: [{ id: 'deutschlandticket', label: 'Deutschlandticket (49 €-Ticket)' }, { id: 'job_ticket', label: 'Job-Ticket (Firmenticket)' }, { id: 'monthly_pass', label: 'Monatskarte' }, { id: 'bahncard25_50', label: 'DB BahnCard 25 / 50' }, { id: 'bahncard100', label: 'DB BahnCard 100' }] },
                        { id: 'car', title: '🚗 Carsharing & Verleih', options: [{ id: 'miles_pass', label: 'Miles Pass / ShareNow Silver & Gold' }, { id: 'sixt_share', label: 'SIXT share Flat / Plus' }, { id: 'teilauto', label: 'teilAuto (Rahmenvertrag / Abo)' }, { id: 'carsharing_regular', label: 'Gelegentlicher Carsharing-Nutzer (kein Abo)' }] },
                        { id: 'scooter', title: '🛴 E-Scooter & Bike-Sharing', options: [{ id: 'scooter_flat', label: 'Tier / Voi Pass (Scooter-Flat)' }, { id: 'dott', label: 'Dott Pass (Flat / Unbegrenzt)' }, { id: 'swapfiets', label: 'Swapfiets (Fahrrad-Abo)' }, { id: 'nextbike', label: 'nextbike (Monats- / Jahreskarte)' }] }
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

              {/* SCHRITT 3: ABO-DETAILS */}
              {onboardingStep === 3 && (() => {
                const selected = services.filter(s => s !== 'none')
                if (selected.length === 0) {
                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                      <div>
                        <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Keine Abo-Details nötig</h1>
                        <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left' }}>Du hast keine Abos angegeben — weiter geht's.</p>
                      </div>
                      <div style={{ flex: 1 }} />
                      <button onClick={() => setOnboardingStep(4)} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s', marginTop: '1rem' }}>Weiter</button>
                    </div>
                  )
                }
                const TYPE_OPTS = [
                  { id: 'subscription', label: 'Abo' },
                  { id: 'membership', label: 'Mitgliedschaft' },
                  { id: 'employer_benefit', label: 'Über Arbeitgeber' },
                  { id: 'student_benefit', label: 'Studi-Tarif' },
                  { id: 'trial', label: 'Testphase' },
                  { id: 'pay_as_you_go_account', label: 'Pay-per-Use' },
                  { id: 'other', label: 'Sonstiges' }
                ]
                const BILL_OPTS = [
                  { id: 'monthly', label: 'Monatlich' },
                  { id: 'yearly', label: 'Jährlich' },
                  { id: 'pay_as_you_go', label: 'Pay-per-Use' },
                  { id: 'one_time', label: 'Einmalig' },
                  { id: 'none', label: 'Keine' }
                ]
                const chip = (active) => ({
                  padding: '0.5rem 0.85rem', borderRadius: '999px', fontSize: '0.82rem', fontWeight: '600', cursor: 'pointer',
                  backgroundColor: active ? colors.accentPurple : colors.card, color: active ? '#000000' : '#ffffff',
                  border: active ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, transition: 'all 0.15s'
                })
                const miniLabel = { color: colors.textMuted, fontSize: '0.72rem', fontWeight: '500', display: 'block', margin: '0.65rem 0 0.4rem' }
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ overflowY: 'auto', maxHeight: '72vh', paddingRight: '2px' }}>
                      <h1 style={{ fontSize: '1.7rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Erzähl uns mehr zu deinen Abos</h1>
                      <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left', lineHeight: '1.4' }}>So ordnen wir Kosten korrekt zu — etwa ob ein Tarif über deinen Arbeitgeber oder als Studi-Tarif läuft.</p>
                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                        {selected.map((sid) => {
                          const d = subscriptionDetails[sid] || {}
                          return (
                            <div key={sid} style={{ backgroundColor: '#0d0d10', border: `1px solid ${colors.border}`, borderRadius: '16px', padding: '1rem 1.1rem', textAlign: 'left' }}>
                              <span style={{ color: '#ffffff', fontSize: '0.95rem', fontWeight: '700', display: 'block' }}>{SERVICE_LABELS[sid] || sid}</span>
                              <span style={miniLabel}>Art</span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                {TYPE_OPTS.map((o) => (
                                  <span key={o.id} onClick={() => setSubDetail(sid, 'type', o.id)} style={chip((d.type || 'subscription') === o.id)}>{o.label}</span>
                                ))}
                              </div>
                              <span style={miniLabel}>Abrechnung</span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                {BILL_OPTS.map((o) => (
                                  <span key={o.id} onClick={() => setSubDetail(sid, 'billing', o.id)} style={chip((d.billing || 'monthly') === o.id)}>{o.label}</span>
                                ))}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                    <div style={{ flex: 1 }} />
                    <button onClick={() => setOnboardingStep(4)} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s', marginTop: '1rem' }}>Weiter</button>
                  </div>
                )
              })()}

              {/* SCHRITT 4: HÄUFIGSTE VERKEHRSMITTEL */}
              {onboardingStep === 4 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Welche Verkehrsmittel nutzt du hauptsächlich?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>Wähle die Optionen, die du im Alltag am häufigsten nutzt.</p>
                    
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
                  <button onClick={() => setOnboardingStep(5)} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', marginTop: '1rem' }}>Weiter</button>
                </div>
              )}

              {/* SCHRITT 5: VERKEHRSMITTEL MEIDEN */}
              {onboardingStep === 5 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Gibt es Verkehrsmittel, die du vermeiden möchtest?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>Diese schließen wir aus den Empfehlungen aus (z. B. wenn du Fahrrad oder Bus nicht magst).</p>
                    
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
                  <button onClick={() => setOnboardingStep(6)} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', marginTop: '1rem' }}>Weiter</button>
                </div>
              )}

              {/* SCHRITT 6: PRIORITÄTEN */}
              {onboardingStep === 6 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Priorisiere deine Ziele</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left' }}>Tippe die Optionen der Reihe nach an, um sie von 1 (am wichtigsten) bis 3 zu ordnen.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                      {[
                        { id: 'time', label: '⏱️ Zeit sparen (Schnelligkeit)' },
                        { id: 'budget', label: '💰 Geld sparen (Wirtschaftlichkeit)' },
                        { id: 'environmental_concerns', label: '🌱 Umwelt schützen (CO₂)' }
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
                  <button onClick={() => setOnboardingStep(7)} disabled={priorities.length < 3} style={{ width: '100%', padding: '1.1rem', backgroundColor: priorities.length === 3 ? colors.accentCyan : colors.card, color: priorities.length === 3 ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: priorities.length === 3 ? 'pointer' : 'not-allowed', transition: 'all 0.2s', marginTop: '1rem' }}>{priorities.length === 3 ? 'Weiter' : 'Alle 3 zum Ordnen auswählen'}</button>
                </div>
              )}

              {/* SCHRITT 7: TYPISCHE WOCHE */}
              {onboardingStep === 7 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div style={{ overflowY: 'auto', maxHeight: '72vh', paddingRight: '2px' }}>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Wie sieht deine typische Woche aus?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Das hilft uns, deinen Mobilitätsbedarf vorherzusagen.</p>

                    <span style={{ color: '#ffffff', fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>Werktags</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem', marginBottom: '1.5rem' }}>
                      {WEEKDAY_PATTERNS.map((p) => {
                        const isSel = typicalWeekday === p
                        return (
                          <button key={p} onClick={() => setTypicalWeekday(p)} style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isSel ? 'rgba(0, 242, 254, 0.04)' : colors.card, border: isSel ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}` }}><span>{p}</span></button>
                        )
                      })}
                    </div>

                    <span style={{ color: '#ffffff', fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>Wochenende</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                      {WEEKEND_PATTERNS.map((p) => {
                        const isSel = typicalWeekend === p
                        return (
                          <button key={p} onClick={() => setTypicalWeekend(p)} style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isSel ? 'rgba(0, 242, 254, 0.04)' : colors.card, border: isSel ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}` }}><span>{p}</span></button>
                        )
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1rem' }}>
                    {(() => {
                      const ready = typicalWeekday && typicalWeekend
                      return (
                        <button onClick={() => setOnboardingStep(8)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      )
                    })()}
                    <button onClick={() => { setTypicalWeekday(''); setTypicalWeekend(''); setOnboardingStep(8); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 8: WOHNORT */}
              {onboardingStep === 8 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Wo wohnst du?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Damit wir Strecken und Empfehlungen für deine Region berechnen können.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
                      <div>
                        <label style={inputLabelStyle}>Stadt</label>
                        <input type="text" placeholder="z. B. Frankfurt" value={homeCity} onChange={(e) => setHomeCity(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                      </div>
                      <div>
                        <label style={inputLabelStyle}>Postleitzahl</label>
                        <input type="text" inputMode="numeric" placeholder="z. B. 60311" value={homePostalCode} onChange={(e) => setHomePostalCode(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                      </div>
                      <div>
                        <label style={inputLabelStyle}>Land</label>
                        <select value={homeCountry} onChange={(e) => setHomeCountry(e.target.value)} style={{ ...textInputStyle, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border}>
                          {COUNTRY_OPTIONS.map((c) => (
                            <option key={c.code} value={c.code} style={{ backgroundColor: '#1c1c1f', color: '#fff' }}>{c.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1rem' }}>
                    {(() => {
                      const ready = homeCity.trim() && homePostalCode.trim();
                      return (
                        <button onClick={() => setOnboardingStep(9)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      );
                    })()}
                    <button onClick={() => { setHomeCity(''); setHomePostalCode(''); setOnboardingStep(9); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 9: ARBEIT & HYBRID */}
              {onboardingStep === 9 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div style={{ overflowY: 'auto', maxHeight: '72vh', paddingRight: '2px' }}>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Wie arbeitest du?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Dein Pendelmuster bestimmt einen großen Teil deiner Mobilität.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem' }}>
                      {[
                        { id: 'onsite', label: '🏢 Vor Ort im Büro' },
                        { id: 'hybrid', label: '🔄 Hybrid (Büro & Homeoffice)' },
                        { id: 'remote', label: '🏠 Komplett remote' },
                        { id: 'unemployed', label: '🚫 Aktuell nicht berufstätig' }
                      ].map((opt) => {
                        const isSel = workArrangement === opt.id;
                        return (
                          <button key={opt.id} onClick={() => { setWorkArrangement(opt.id); if (opt.id === 'remote' || opt.id === 'unemployed') { setWorkCity(''); setWorkPostalCode(''); } if (opt.id !== 'hybrid') setRemoteDaysPerWeek(null); }} style={{ ...optionButtonStyle, padding: '1rem 1.2rem', backgroundColor: isSel ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>{opt.label}</span></button>
                        );
                      })}
                    </div>

                    {/* Arbeitsort nur bei Büro/Hybrid */}
                    {(workArrangement === 'onsite' || workArrangement === 'hybrid') && (
                      <div style={{ marginTop: '1.5rem', display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
                        <div>
                          <label style={inputLabelStyle}>Arbeitsort — Stadt</label>
                          <input type="text" placeholder="z. B. Frankfurt" value={workCity} onChange={(e) => setWorkCity(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                        </div>
                        <div>
                          <label style={inputLabelStyle}>Arbeitsort — PLZ</label>
                          <input type="text" inputMode="numeric" placeholder="z. B. 60311" value={workPostalCode} onChange={(e) => setWorkPostalCode(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                        </div>
                      </div>
                    )}

                    {/* Homeoffice-Tage nur bei Hybrid */}
                    {workArrangement === 'hybrid' && (
                      <div style={{ marginTop: '1.5rem' }}>
                        <label style={{ ...inputLabelStyle, marginBottom: '0.65rem' }}>Tage pro Woche im Homeoffice</label>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {[0, 1, 2, 3, 4, 5].map((d) => {
                            const isSel = remoteDaysPerWeek === d;
                            return (
                              <button key={d} onClick={() => setRemoteDaysPerWeek(d)} style={{ flex: 1, padding: '0.85rem 0', backgroundColor: isSel ? colors.accentPurple : colors.card, color: isSel ? '#000000' : '#ffffff', border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, borderRadius: '12px', fontSize: '1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s' }}>{d}</button>
                            );
                          })}
                        </div>
                      </div>
                    )}
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1rem' }}>
                    {(() => {
                      const needsLocation = workArrangement === 'onsite' || workArrangement === 'hybrid';
                      const needsDays = workArrangement === 'hybrid';
                      const ready = workArrangement && (!needsLocation || (workCity.trim() && workPostalCode.trim())) && (!needsDays || remoteDaysPerWeek !== null);
                      return (
                        <button onClick={() => setOnboardingStep(10)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      );
                    })()}
                    <button onClick={() => { setWorkArrangement(''); setWorkCity(''); setWorkPostalCode(''); setRemoteDaysPerWeek(null); setOnboardingStep(10); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 10: MOBILITÄTSBUDGET */}
              {onboardingStep === 10 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Was gibst du monatlich für Mobilität aus?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Eine grobe Schätzung reicht — wir verfeinern das später mit deinen echten Daten.</p>
                    <div style={{ position: 'relative', backgroundColor: '#1c1c1f', borderRadius: '14px', border: mobilityBudget ? `2px solid #ffffff` : `1px solid ${colors.border}`, padding: '0.6rem 1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{ flex: 1, textAlign: 'left' }}>
                        <label style={{ display: 'block', color: colors.textMuted, fontSize: '0.75rem', marginBottom: '0.15rem' }}>Budget pro Monat</label>
                        <input type="number" inputMode="numeric" placeholder="z. B. 150" value={mobilityBudget} onChange={(e) => setMobilityBudget(e.target.value)} style={{ width: '100%', backgroundColor: 'transparent', border: 'none', color: '#ffffff', fontSize: '1.2rem', fontWeight: '600', outline: 'none', padding: 0 }} />
                      </div>
                      <span style={{ color: colors.textMuted, fontSize: '1.2rem', fontWeight: '600' }}>€</span>
                      {mobilityBudget && <X size={18} onClick={() => setMobilityBudget('')} style={{ color: colors.textMuted, cursor: 'pointer' }} />}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1rem' }}>
                    {(() => {
                      const ready = mobilityBudget !== '' && Number(mobilityBudget) >= 0;
                      return (
                        <button onClick={() => setOnboardingStep(11)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      );
                    })()}
                    <button onClick={() => { setMobilityBudget(''); setOnboardingStep(11); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 11: FINANZ-KONTEXT */}
              {onboardingStep === 11 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div style={{ overflowY: 'auto', maxHeight: '72vh', paddingRight: '2px' }}>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Ein bisschen Kontext zu deinem Haushalt</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.9rem', textAlign: 'left', lineHeight: '1.4' }}>Hilft uns, Empfehlungen realistisch auf dein Budget abzustimmen.</p>

                    <span style={{ color: '#ffffff', fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>Personen im Haushalt</span>
                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
                      {['1', '2', '3', '4', '5+'].map((h) => {
                        const isSel = householdSize === h;
                        return (
                          <button key={h} onClick={() => setHouseholdSize(h)} style={{ flex: 1, padding: '0.85rem 0', backgroundColor: isSel ? colors.accentPurple : colors.card, color: isSel ? '#000000' : '#ffffff', border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, borderRadius: '12px', fontSize: '1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s' }}>{h}</button>
                        );
                      })}
                    </div>

                    <span style={{ color: '#ffffff', fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>Monatliches Nettoeinkommen</span>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.55rem' }}>
                      {[
                        { id: 'under_1500', label: 'Unter 1.500 €' },
                        { id: '1500_3000', label: '1.500 – 3.000 €' },
                        { id: '3000_4500', label: '3.000 – 4.500 €' },
                        { id: 'over_4500', label: 'Über 4.500 €' },
                        { id: 'prefer_not_say', label: 'Keine Angabe' }
                      ].map((band) => {
                        const isSel = incomeBand === band.id;
                        return (
                          <button key={band.id} onClick={() => setIncomeBand(band.id)} style={{ ...optionButtonStyle, padding: '0.9rem 1.1rem', backgroundColor: isSel ? 'rgba(168, 85, 247, 0.05)' : colors.card, border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>{band.label}</span></button>
                        );
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1rem' }}>
                    {(() => {
                      const ready = householdSize && incomeBand;
                      return (
                        <button onClick={() => setOnboardingStep(12)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      );
                    })()}
                    <button onClick={() => { setHouseholdSize(''); setIncomeBand(''); setOnboardingStep(12); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 12: GEBURTSJAHR */}
              {onboardingStep === 12 && (
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
                    <button onClick={() => setOnboardingStep(13)} disabled={!birthYear || birthYear.length < 4} style={{ width: '100%', padding: '1.1rem', backgroundColor: (birthYear && birthYear.length >= 4) ? colors.accentCyan : colors.card, color: (birthYear && birthYear.length >= 4) ? '#000000' : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: (birthYear && birthYear.length >= 4) ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                    <button onClick={() => { setBirthYear(''); setOnboardingStep(13); }} style={{ width: '100%', padding: '0.8rem', backgroundColor: 'transparent', color: colors.accentCyan, borderRadius: '14px', border: 'none', fontSize: '1.05rem', fontWeight: '600', cursor: 'pointer' }}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 13: KONTO ERSTELLEN */}
              {onboardingStep === 13 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.9rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.25' }}>Konto erstellen</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Lege deine Zugangsdaten fest, um dein Profil abzuschließen.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
                      <div style={{ display: 'flex', gap: '0.75rem' }}>
                        <div style={{ flex: 1, textAlign: 'left' }}>
                          <label style={inputLabelStyle}>Vorname</label>
                          <input type="text" placeholder="Max" value={firstName} onChange={(e) => setFirstName(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                        </div>
                        <div style={{ flex: 1, textAlign: 'left' }}>
                          <label style={inputLabelStyle}>Nachname</label>
                          <input type="text" placeholder="Mustermann" value={lastName} onChange={(e) => setLastName(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                        </div>
                      </div>
                      <div style={{ textAlign: 'left' }}>
                        <label style={inputLabelStyle}>Geschlecht</label>
                        <div style={{ display: 'flex', gap: '0.4rem' }}>
                          {[{ id: 'female', label: 'Weiblich' }, { id: 'male', label: 'Männlich' }, { id: 'diverse', label: 'Divers' }, { id: 'not_specified', label: 'Keine Angabe' }].map((g) => {
                            const isSel = gender === g.id
                            return (<button key={g.id} type="button" onClick={() => setGender(g.id)} style={{ flex: 1, padding: '0.7rem 0.3rem', borderRadius: '12px', fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer', backgroundColor: isSel ? colors.accentPurple : colors.card, color: isSel ? '#000000' : '#ffffff', border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, transition: 'all 0.15s' }}>{g.label}</button>)
                          })}
                        </div>
                      </div>
                      <div style={{ textAlign: 'left' }}><label style={{ color: colors.textMuted, fontSize: '0.78rem', fontWeight: '500', display: 'block', marginBottom: '0.3rem', paddingLeft: '4px' }}>E-Mail-Adresse</label><input type="email" placeholder="name@example.com" value={regEmail} onChange={(e) => setRegEmail(e.target.value)} style={{ width: '100%', padding: '0.9rem 1.1rem', borderRadius: '14px', backgroundColor: '#1c1c1f', border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', fontWeight: '500', boxSizing: 'border-box', outline: 'none', transition: 'border-color 0.2s ease-in-out' }} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} /></div>
                      <div style={{ textAlign: 'left' }}><label style={{ color: colors.textMuted, fontSize: '0.78rem', fontWeight: '500', display: 'block', marginBottom: '0.3rem', paddingLeft: '4px' }}>Passwort erstellen</label><input type="password" placeholder="••••••••" value={regPassword} onChange={(e) => setRegPassword(e.target.value)} style={{ width: '100%', padding: '0.9rem 1.1rem', borderRadius: '14px', backgroundColor: '#1c1c1f', border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', fontWeight: '500', boxSizing: 'border-box', outline: 'none', transition: 'border-color 0.2s ease-in-out' }} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} /></div>
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ marginTop: '1rem' }}>
                    {error && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ff4a5a', backgroundColor: 'rgba(255, 74, 90, 0.1)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '0.85rem' }}>
                        <AlertCircle size={16} /><span>{error}</span>
                      </div>
                    )}
                    <p style={{ fontSize: '0.72rem', color: colors.textMuted, lineHeight: '1.45', textAlign: 'left', marginBottom: '0.85rem' }}>
                      🔒 Deine Angaben werden DSGVO-konform und verschlüsselt verarbeitet, ausschließlich zur Optimierung deiner Mobilität genutzt und nicht an Dritte verkauft. Du kannst sie jederzeit einsehen oder löschen lassen. Mehr in unserer <span style={{ color: colors.accentCyan, cursor: 'pointer' }}>Datenschutzrichtlinie</span>.
                    </p>
                    <button onClick={handleFinish} disabled={submitting} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.7 : 1, boxShadow: '0 4px 25px rgba(0, 242, 254, 0.25)', transition: 'all 0.2s' }}>{submitting ? 'Speichern…' : 'Abschließen & Anmelden'}</button>
                  </div>
                </div>
              )}

            </div>
          </div>
        </div>
      )}

      {/* =========================================================
          ANSICHT 3: ANMELDUNG & DEMO-PROFILE
          ========================================================= */}
      {currentView === 'login' && (
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'center', alignItems: 'center', padding: '2rem 1.5rem' }}>
          <div style={{ width: '100%', maxWidth: '400px' }}>
            <h2 style={{ fontSize: '1.8rem', fontWeight: '700', color: '#ffffff', marginBottom: '0.5rem', textAlign: 'center' }}>Willkommen zurück</h2>
            <p style={{ color: colors.textMuted, marginBottom: '2.5rem', textAlign: 'center', fontSize: '0.95rem' }}>Melde dich an, um deinen persönlichen Mobilitätsplan zu sehen.</p>

            <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ color: '#ffffff', fontSize: '0.85rem', fontWeight: '500', textAlign: 'left' }} htmlFor="email">E-Mail</label>
                <input id="email" style={{ width: '100%', padding: '0.85rem', borderRadius: '12px', backgroundColor: colors.card, border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', boxSizing: 'border-box' }} type="email" placeholder="you@dbmove.de" value={identifier} onChange={(e) => { setIdentifier(e.target.value); setError('') }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ color: '#ffffff', fontSize: '0.85rem', fontWeight: '500', textAlign: 'left' }} htmlFor="password">Passwort</label>
                <input id="password" style={{ width: '100%', padding: '0.85rem', borderRadius: '12px', backgroundColor: colors.card, border: `1px solid ${colors.border}`, color: '#fff', fontSize: '1rem', boxSizing: 'border-box' }} type="password" placeholder="••••••••" value={password} onChange={(e) => { setPassword(e.target.value); setError('') }} />
              </div>

              {error && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: '#ff4a5a', backgroundColor: 'rgba(255, 74, 90, 0.1)', padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                  <AlertCircle size={16} /><span>{error}</span>
                </div>
              )}

              <button style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: '#000000', borderRadius: '12px', border: 'none', fontSize: '1rem', fontWeight: '700', cursor: 'pointer', marginTop: '0.5rem', boxShadow: '0 4px 20px rgba(0, 242, 254, 0.2)' }} type="submit" disabled={submitting}>
                {submitting ? 'Anmelden…' : 'Anmelden'}
              </button>
            </form>

            <div style={{ display: 'flex', alignItems: 'center', color: '#52667a', fontSize: '0.8rem', textTransform: 'uppercase', margin: '2rem 0' }}>
              <div style={{ flex: 1, height: '1px', backgroundColor: colors.border }}></div>
              <span style={{ padding: '0 0.75rem' }}>oder direkt einsteigen</span>
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

            <div onClick={() => setCurrentView('welcome')} style={{ color: colors.textMuted, cursor: 'pointer', textAlign: 'center', fontSize: '0.85rem', fontWeight: '500' }}>← Zurück zum Start</div>
          </div>
        </div>
      )}

    </div>
  )
}