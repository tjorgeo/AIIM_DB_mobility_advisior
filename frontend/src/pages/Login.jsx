import React, { useState, useEffect, useRef } from 'react'
import { ArrowRight, Wallet, Leaf, Route, AlertCircle, X, Check, Ban, ChevronLeft } from 'lucide-react'
import { useAuth } from '../context/AuthContext.jsx'
import { completeOnboarding, submitOnboarding } from '../api/client'
import Logo from '../components/Logo'
import { useTheme } from '../context/ThemeContext.jsx'
import ThemeToggle from '../components/ThemeToggle.jsx'
import { mobilityAccountLabel } from '../lib/mobilityAccounts'

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

const DEFAULT_TYPE_OPTS = [
  { id: 'subscription', label: 'Abo' },
  { id: 'employer_benefit', label: 'Über Arbeitgeber' },
  { id: 'student_benefit', label: 'Studi-Tarif' },
  { id: 'other', label: 'Sonstiges' }
]

const DEFAULT_BILL_OPTS = [
  { id: 'monthly', label: 'Monatlich' },
  { id: 'yearly', label: 'Jährlich' },
  { id: 'none', label: 'Keine / unbekannt' }
]

const SUBSCRIPTION_OPTIONS = {
  deutschlandticket: {
    label: 'Deutschlandticket',
    typeOptions: [
      { id: 'subscription', label: 'Privates Abo' },
      { id: 'employer_benefit', label: 'Über Arbeitgeber / Jobticket' },
      { id: 'student_benefit', label: 'Studi-Ticket' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'monthly'
  },
  job_ticket: {
    label: 'Job-Ticket / Firmenticket',
    typeOptions: [
      { id: 'employer_benefit', label: 'Über Arbeitgeber' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'yearly', label: 'Jährlich' },
      { id: 'none', label: 'Unbekannt / vom Arbeitgeber getragen' }
    ],
    defaultType: 'employer_benefit',
    defaultBilling: 'monthly'
  },
  bahncard25: {
    label: 'BahnCard 25',
    typeOptions: [
      { id: 'subscription', label: 'Privat gekauft' },
      { id: 'employer_benefit', label: 'Über Arbeitgeber' }
    ],
    billingOptions: [
      { id: 'yearly', label: 'Jährlich' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'yearly',
    asksTravelClass: true
  },
  bahncard50: {
    label: 'BahnCard 50',
    typeOptions: [
      { id: 'subscription', label: 'Privat gekauft' },
      { id: 'employer_benefit', label: 'Über Arbeitgeber' }
    ],
    billingOptions: [
      { id: 'yearly', label: 'Jährlich' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'yearly',
    asksTravelClass: true
  },
  bahncard100: {
    label: 'BahnCard 100',
    typeOptions: [
      { id: 'subscription', label: 'Privat gekauft' },
      { id: 'employer_benefit', label: 'Über Arbeitgeber' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'yearly', label: 'Jährlich' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'yearly',
    asksTravelClass: true
  },
  miles_pass: {
    label: 'Miles / ShareNow Pass',
    typeOptions: [
      { id: 'subscription', label: 'Pass / Abo' },
      { id: 'employer_benefit', label: 'Über Arbeitgeber' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'pay_as_you_go', label: 'Nach Nutzung' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'monthly'
  },
  sixt_share: {
    label: 'SIXT share Pass',
    typeOptions: [
      { id: 'subscription', label: 'Pass / Abo' },
      { id: 'employer_benefit', label: 'Über Arbeitgeber' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'pay_as_you_go', label: 'Nach Nutzung' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'monthly'
  },
  teilauto: {
    label: 'teilAuto',
    typeOptions: [
      { id: 'membership', label: 'Mitgliedschaft' },
      { id: 'employer_benefit', label: 'Rahmenvertrag / Arbeitgeber' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'yearly', label: 'Jährlich' }
    ],
    defaultType: 'membership',
    defaultBilling: 'monthly'
  },
  carsharing_regular: {
    label: 'Carsharing ohne Abo',
    skipDetails: true,
    defaultType: 'pay_as_you_go_account',
    defaultBilling: 'pay_as_you_go'
  },
  scooter_flat: {
    label: 'Tier / Voi Pass',
    typeOptions: [
      { id: 'subscription', label: 'Pass / Flat' },
      { id: 'student_benefit', label: 'Studi-Tarif' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'pay_as_you_go', label: 'Nach Nutzung' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'monthly'
  },
  dott: {
    label: 'Dott Pass',
    typeOptions: [
      { id: 'subscription', label: 'Pass / Flat' },
      { id: 'student_benefit', label: 'Studi-Tarif' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'pay_as_you_go', label: 'Nach Nutzung' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'monthly'
  },
  swapfiets: {
    label: 'Swapfiets',
    typeOptions: [
      { id: 'subscription', label: 'Abo' },
      { id: 'student_benefit', label: 'Studi-Tarif' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'yearly', label: 'Jährlich' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'monthly'
  },
  nextbike: {
    label: 'nextbike',
    typeOptions: [
      { id: 'subscription', label: 'Monats- / Jahreskarte' },
      { id: 'employer_benefit', label: 'Über Arbeitgeber / Hochschule' },
      { id: 'student_benefit', label: 'Studi-Tarif' }
    ],
    billingOptions: [
      { id: 'monthly', label: 'Monatlich' },
      { id: 'yearly', label: 'Jährlich' }
    ],
    defaultType: 'subscription',
    defaultBilling: 'monthly'
  }
}

const SUBSCRIPTION_CATEGORIES = [
  {
    id: 'bahn',
    title: '🚆 ÖPNV & Deutsche Bahn',
    services: ['deutschlandticket', 'job_ticket', 'bahncard25', 'bahncard50', 'bahncard100']
  },
  {
    id: 'car',
    title: '🚗 Carsharing & Verleih',
    services: ['miles_pass', 'sixt_share', 'teilauto', 'carsharing_regular']
  },
  {
    id: 'scooter',
    title: '🛴 E-Scooter & Bike-Sharing',
    services: ['scooter_flat', 'dott', 'swapfiets', 'nextbike']
  }
]

const TYPICAL_WORK_PATTERNS = [
  '🏢 Pendeln ins Büro',
  '🏠 Homeoffice mit kurzen Wegen',
  '🗓️ Viel unterwegs für Termine / Außendienst',
  '🎓 Uni / Ausbildung / Schule',
  '👨‍👩‍👧 Kinderbetreuung / Familie',
  '🧾 Erledigungen im Alltag',
  '🛋️ Kaum regelmäßige Wege'
]

const TYPICAL_LEISURE_PATTERNS = [
  '🏙️ Lokale Freizeit in der Stadt',
  '🌳 Ausflüge ins Umland',
  '🏋️ Sport / Verein / Hobbys',
  '👥 Freunde & Familie besuchen',
  '🛍️ Shopping / Gastronomie',
  '✈️ Häufig längere Reisen',
  '🛋️ Meist zu Hause'
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
  const onboardingStepPosition = ({ 11: 10, 13: 11, 14: 12 })[onboardingStep] || onboardingStep
  const [services, setServices] = useState([])
  const [hasLicense, setHasLicense] = useState(null)
  const [carAccess, setCarAccess] = useState('')
  const [bikeAccess, setBikeAccess] = useState([])
  const [frequentModes, setFrequentModes] = useState([]) 
  const [avoidModes, setAvoidModes] = useState([])       
  const [priorities, setPriorities] = useState([])
  const [activeCategory, setActiveCategory] = useState('')
  const [birthYear, setBirthYear] = useState('') 
  const [submitting, setSubmitting] = useState(false)
  const [priorityScores, setPriorityScores] = useState({ time: 5, budget: 5, environmental_concerns: 5 })
  const [weekNote, setWeekNote] = useState('')
  const [workNote, setWorkNote] = useState('')
  const [pendingUser, setPendingUser] = useState(null)
  const [procMsgIndex, setProcMsgIndex] = useState(0)

  // Persönliche & Kontext-Daten
  const [homeCity, setHomeCity] = useState('')
  const [homePostalCode, setHomePostalCode] = useState('')
  const [workArrangement, setWorkArrangement] = useState('')      
  const [workCity, setWorkCity] = useState('')
  const [workPostalCode, setWorkPostalCode] = useState('')
  const [remoteDaysPerWeek, setRemoteDaysPerWeek] = useState(null) 
  const [mobilityBudget, setMobilityBudget] = useState('')
  const [householdSize, setHouseholdSize] = useState('')
  const [incomeBand, setIncomeBand] = useState('')

  // Abo-Details, Wochenmuster, Konto-Daten
  const [subscriptionDetails, setSubscriptionDetails] = useState({}) 
  const [typicalWorkPatterns, setTypicalWorkPatterns] = useState([])
  const [typicalLeisurePatterns, setTypicalLeisurePatterns] = useState([])
  const [homeCountry, setHomeCountry] = useState('DE')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [regEmail, setRegEmail] = useState('')
  const [regPassword, setRegPassword] = useState('')
  const [regPasswordConfirm, setRegPasswordConfirm] = useState('')
  const [gender, setGender] = useState('')

  // Partner-Konten (Schritt 14): Die Anmeldung bleibt simuliert; der verbundene
  // Status wird aber als Teil des Onboarding-Profils im Backend persistiert.
  const [connectedAccounts, setConnectedAccounts] = useState({}) // { [serviceId]: true }
  const [connectingId, setConnectingId] = useState('')           // welcher Anbieter gerade „verbindet" (Spinner)
  const connectionTimerRef = useRef(null)

  // Kalender-Einbindung (Schritt 14): rein kosmetische Ja/Nein-Abfrage, wird nicht
  // ausgewertet oder übertragen — es gibt keine echte Kalender-Integration.
  const [calendarSync, setCalendarSync] = useState(null) // null | true | false

  const cancelConnectionSimulation = () => {
    if (connectionTimerRef.current) clearTimeout(connectionTimerRef.current)
    connectionTimerRef.current = null
    setConnectingId('')
  }

  const simulateConnect = (sid) => {
    if (connectingId || connectedAccounts[sid]) return
    setConnectingId(sid)
    connectionTimerRef.current = setTimeout(() => {
      setConnectedAccounts((prev) => ({ ...prev, [sid]: true }))
      setConnectingId('')
      connectionTimerRef.current = null
    }, 1200)
  }

  useEffect(() => () => {
    if (connectionTimerRef.current) clearTimeout(connectionTimerRef.current)
  }, [])

  const setSubDetail = (sid, field, value) => {
    setSubscriptionDetails(prev => ({ ...prev, [sid]: { ...(prev[sid] || {}), [field]: value } }))
  }

  const handleCreateAccount = async (event) => {
    event?.preventDefault()
    setError('')
    if (!firstName.trim() || !lastName.trim() || !regEmail.trim() || !regPassword) {
      setError('Bitte Vor-/Nachname, E-Mail und Passwort ausfüllen.')
      return
    }
    if (regPassword.length < 8) {
      setError('Das Passwort muss mindestens 8 Zeichen lang sein.')
      return
    }
    if (regPassword !== regPasswordConfirm) {
      setError('Die Passwörter stimmen nicht überein.')
      return
    }

    const account = {
      user: {
        first_name: firstName.trim(),
        last_name: lastName.trim(),
        email: regEmail.trim(),
        gender: 'not_specified',
        date_of_birth: null,
        age: null,
        home_city: null,
        home_postal_code: null,
        home_country_code: 'DE',
      },
      onboarding: {},
      subscriptions: [],
      credentials: { password: regPassword },
    }

    setSubmitting(true)
    try {
      const res = await submitOnboarding(account)
      if (!res.ok) {
        setError(res.error || 'Registrierung fehlgeschlagen. Bitte erneut versuchen.')
        return
      }
      if (!res.data?.user) {
        setError('Das Konto wurde erstellt, konnte aber nicht automatisch geöffnet werden.')
        return
      }
      setPendingUser(res.data.user)
      setCurrentView('onboardingChoice')
    } catch {
      setError('Verbindung zum Server fehlgeschlagen.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleFinish = async () => {
    setError('')
    if (!pendingUser?.id) {
      setError('Dein Konto konnte nicht zugeordnet werden. Bitte melde dich erneut an.')
      return
    }

    const workPatternSummary = typicalWorkPatterns.join(', ')
    const leisurePatternSummary = typicalLeisurePatterns.join(', ')

    const profile = {
      user: {
        gender: gender || 'not_specified',
        date_of_birth: birthYear ? `${birthYear}-01-01` : null,
        home_city: homeCity.trim() || null,
        home_postal_code: homePostalCode.trim() || null,
        home_country_code: homeCountry || 'DE'
      },
      onboarding: {
        has_driving_license: hasLicense,
        car_access: carAccess || null,
        bike_access: bikeAccess,
        preferred_transport_modes: frequentModes,
        avoided_transport_modes: avoidModes,
        score_money: priorityScores.budget * 10,
        score_emission: priorityScores.environmental_concerns * 10,
        score_flexibility: priorityScores.time * 10,
        mobility_budget_monthly_eur: mobilityBudget !== '' ? Number(mobilityBudget) : null,
        typical_weekday_pattern: workPatternSummary || null,
        typical_weekend_pattern: leisurePatternSummary || null,
        travel_statement: `Bevorzugt: ${frequentModes.join(', ') || 'k. A.'}. Meidet: ${avoidModes.join(', ') || 'nichts'}.`,
        activity_statement: `Arbeit/Verpflichtungen: ${workPatternSummary || 'k. A.'}. Freizeit/Wochenende: ${leisurePatternSummary || 'k. A.'}.` + (weekNote.trim() ? ` Notiz Woche: ${weekNote.trim()}.` : ''),
        connected_mobility_accounts: Object.keys(connectedAccounts).filter((sid) => connectedAccounts[sid])
      },
      subscriptions: services.filter(s => s !== 'none').map(sid => {
        const config = SUBSCRIPTION_OPTIONS[sid] || {}
        const typeOptions = config.typeOptions || DEFAULT_TYPE_OPTS
        const billingOptions = config.billingOptions || DEFAULT_BILL_OPTS
        const details = subscriptionDetails[sid] || {}

        return {
          service: sid,
          subscription_type: details.type || config.defaultType || typeOptions[0]?.id || 'subscription',
          billing_cycle: details.billing || config.defaultBilling || billingOptions[0]?.id || 'monthly',
          travel_class: config.asksTravelClass ? (details.travel_class || null) : null
        }
      }),
    }

    setSubmitting(true)
    try {
      const res = await completeOnboarding(pendingUser.id, profile)
      if (res.ok) {
        setPendingUser(res.data?.user || { ...pendingUser, onboardingStatus: 'completed' })
        setProcMsgIndex(0)
        setCurrentView('processing')
      } else {
        setError(res.error || 'Speichern fehlgeschlagen. Bitte erneut versuchen.')
      }
    } catch {
      setError('Verbindung zum Server fehlgeschlagen.')
    } finally {
      setSubmitting(false)
    }
  }

  const handleSkipOnboarding = () => {
    if (!pendingUser?.id) return
    try {
      sessionStorage.setItem('moveoptimizer.showOnboardingReminder', pendingUser.id)
    } catch {
      /* The one-time reminder is optional if browser storage is unavailable. */
    }
    setSession(pendingUser)
  }

  const COMPONENT_MESSAGES = [
    'Analysiere dein Reiseverhalten…',
    'Vergleiche Tarife und Abos…',
    'Berechne Kosten und CO₂…',
    'Mische deine beste Lösung…'
  ]

  useEffect(() => {
    if (currentView !== 'processing' || !pendingUser) return
    const cycle = setInterval(() => {
      setProcMsgIndex((i) => (i + 1) % COMPONENT_MESSAGES.length)
    }, 900)
    const done = setTimeout(() => { setSession(pendingUser) }, 3600)
    return () => { clearInterval(cycle); clearTimeout(done) }
  }, [currentView, pendingUser])

  const handleServiceToggle = (serviceId) => {
    setServices(prev => {
      if (serviceId === 'none') {
        setSubscriptionDetails({})
        setConnectedAccounts({})
        cancelConnectionSimulation()
        return prev.includes('none') ? [] : ['none']
      }
      const withoutNone = prev.filter(s => s !== 'none')
      if (withoutNone.includes(serviceId)) {
        setSubscriptionDetails(prevDetails => {
          const next = { ...prevDetails }
          delete next[serviceId]
          return next
        })
        setConnectedAccounts((prevAccounts) => {
          const next = { ...prevAccounts }
          delete next[serviceId]
          return next
        })
        if (connectingId === serviceId) cancelConnectionSimulation()
        return withoutNone.filter(s => s !== serviceId)
      }
      return [...withoutNone, serviceId]
    })
  }

  const handleBikeAccessToggle = (id) => {
    setBikeAccess(prev => {
      if (id === 'none') {
        return prev.includes('none') ? [] : ['none']
      }
      const withoutNone = prev.filter(item => item !== 'none')
      return withoutNone.includes(id)
        ? withoutNone.filter(item => item !== id)
        : [...withoutNone, id]
    })
  }

  const handlePatternToggle = (setter, id) => {
    setter(prev =>
      prev.includes(id) ? prev.filter(item => item !== id) : [...prev, id]
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

  const handleSubmit = async (e) => {
    e.preventDefault()
    setSubmitting(true)
    const res = await login(identifier, password)
    setSubmitting(false)
    if (!res.ok) setError(res.error)
  }

  const { isDark } = useTheme()
  const colors = isDark ? {
    bg: '#000000',
    card: '#16161a',
    accentCyan: '#00f2fe',
    accentPurple: '#a855f7',
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

  const optionButtonStyle = {
    width: '100%',
    padding: '1.1rem 1.2rem',
    backgroundColor: colors.card,
    border: `1px solid ${colors.border}`,
    borderRadius: '16px',
    color: colors.text,
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
    backgroundColor: colors.inputBg,
    border: `1px solid ${colors.border}`,
    color: colors.text,
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
    <div style={{ backgroundColor: colors.bg, color: colors.text, fontFamily: 'system-ui, -apple-system, sans-serif', minHeight: '100vh', display: 'flex', flexDirection: 'column', boxSizing: 'border-box' }}>
      <ThemeToggle style={{ position: 'fixed', top: '14px', right: '14px', zIndex: 90 }} />
      
      {/* RESPONSIVE CSS DEFINITION MIT SPIEGEL-GRID-SCHUTZ */}
      <style>{`
        .welcome-layout {
          flex: 1;
          display: flex;
          flex-direction: column;
          align-items: center;
          justify-content: center;
          padding: 3rem 1.5rem;
          text-align: center;
          box-sizing: border-box;
          min-height: 100vh;
          width: 100%;
          max-width: 440px;
          margin: 0 auto;
        }
        .onboarding-step-layout {
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: flex-start;
          padding: 1.5rem 1.25rem;
          min-height: 100vh;
          box-sizing: border-box;
        }
        
        .welcome-title {
          font-size: 1.62rem;
          font-weight: 800;
          color: ${colors.text};
          margin-bottom: 1.5rem;
          letter-spacing: -0.03em;
          line-height: 1.3;
        }

        .welcome-card {
          width: 100%;
          background-color: transparent;
          border: none;
          padding: 0;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
          gap: 0.75rem;
          margin-top: 2rem;
        }

        .onboarding-inner-card {
          width: 100%;
          max-width: 480px;
          background-color: transparent;
          border: none;
          padding: 0;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
        }
        .login-view-container {
          flex: 1;
          display: flex;
          flex-direction: column;
          justify-content: center;
          align-items: center;
          padding: 2rem 1.25rem;
          min-height: 100vh;
        }
        .login-inner-card {
          width: 100%;
          max-width: 460px;
          background-color: transparent;
          border: none;
          padding: 0;
          box-sizing: border-box;
          display: flex;
          flex-direction: column;
        }

        .responsive-options-grid {
          display: flex;
          flex-direction: column;
          gap: 0.65rem;
        }
        .responsive-form-grid {
          display: flex;
          flex-direction: column;
          gap: 1.1rem;
        }

        .personas-grid {
          display: flex;
          flex-direction: column;
          gap: 0.6rem;
          margin-bottom: 2rem;
          width: 100%;
        }

        .premium-back-btn {
          display: inline-flex;
          align-items: center;
          gap: 0.4rem;
          background-color: ${colors.card};
          border: 1px solid ${colors.border};
          border-radius: 12px;
          color: ${colors.textMuted};
          padding: 0.55rem 0.95rem;
          font-size: 0.88rem;
          font-weight: 600;
          cursor: pointer;
          transition: all 0.2s ease;
          width: fit-content;
        }
        .premium-back-btn:hover {
          border-color: ${colors.accentCyan};
          color: ${colors.text};
        }

        @media (min-width: 768px) {
          .welcome-layout {
            max-width: 520px !important;
            padding: 4rem 2rem !important;
          }
          .welcome-title {
            font-size: 2.6rem !important;
          }
          .welcome-card {
            background-color: ${colors.card} !important;
            border: 1px solid ${colors.border} !important;
            border-radius: 28px !important;
            padding: 2.75rem 2.25rem !important;
            box-shadow: ${isDark ? '0 30px 60px rgba(0,0,0,0.6)' : '0 18px 50px rgba(17,24,39,0.10)'} !important;
          }

          .onboarding-step-layout {
            justify-content: center !important;
            align-items: center !important;
          }
          .onboarding-inner-card {
            max-width: 640px !important;
            background-color: ${colors.card} !important;
            border: 1px solid ${colors.border} !important;
            border-radius: 28px !important;
            padding: 3rem !important;
            box-shadow: ${isDark ? '0 30px 60px rgba(0,0,0,0.6)' : '0 18px 50px rgba(17,24,39,0.10)'} !important;
          }
          
          .login-inner-card {
            max-width: 540px !important;
            background-color: ${colors.card} !important;
            border: 1px solid ${colors.border} !important;
            border-radius: 28px !important;
            padding: 3rem !important;
            box-shadow: ${isDark ? '0 30px 60px rgba(0,0,0,0.6)' : '0 18px 50px rgba(17,24,39,0.10)'} !important;
          }

          .responsive-options-grid {
            display: grid !important;
            grid-template-columns: repeat(2, 1fr) !important;
            gap: 0.75rem !important;
          }
          .responsive-form-grid {
            display: grid !important;
            grid-template-columns: 1fr 1fr !important;
            gap: 1rem !important;
          }
          .full-width-desktop { grid-column: span 2 !important; }
          
          .personas-grid {
            display: grid !important;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) !important;
            gap: 0.65rem !important;
          }
        }
      `}</style>
      
      {/* =========================================================
          ANSICHT: LOADING ENGINE / PROCESSING STATUS
          ========================================================= */}
      {currentView === 'processing' && (
        <div style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', padding: '2rem', textAlign: 'center' }}>
          <style>{`
            @keyframes mo-float { 0%,100% { transform: translateY(-7px) } 50% { transform: translateY(7px) } }
            @keyframes mo-pulse { 0%,100% { transform: scale(1); opacity: .5 } 50% { transform: scale(1.18); opacity: .9 } }
            @keyframes mo-spin { to { transform: rotate(360deg) } }
            @keyframes mo-fade { from { opacity: 0; transform: translateY(6px) } to { opacity: 1; transform: translateY(0) } }
          `}</style>
          <div style={{ position: 'relative', width: '220px', height: '220px', display: 'flex', alignItems: 'center', justifyContent: 'center', marginBottom: '2.25rem' }}>
            <div style={{ position: 'absolute', inset: 0, borderRadius: '50%', background: `radial-gradient(circle, ${colors.accentCyan}44 0%, transparent 70%)`, animation: 'mo-pulse 2.4s ease-in-out infinite', filter: 'blur(6px)' }} />
            <div style={{ position: 'absolute', width: '150px', height: '150px', borderRadius: '50%', border: `2px dashed ${colors.accentCyan}55`, animation: 'mo-spin 9s linear infinite' }} />
            <div style={{ position: 'relative', animation: 'mo-float 3s ease-in-out infinite' }}>
              <Logo showText={false} />
            </div>
          </div>
          <h2 style={{ fontSize: '1.5rem', fontWeight: '800', color: colors.text, marginBottom: '0.6rem' }}>Dein Mobility-Agent arbeitet…</h2>
          <p key={procMsgIndex} style={{ color: colors.accentCyan, fontSize: '1rem', fontWeight: '600', minHeight: '1.4em', animation: 'mo-fade 0.4s ease' }}>{COMPONENT_MESSAGES[procMsgIndex]}</p>
        </div>
      )}

      {/* =========================================================
          ANSICHT 1: ONBOARDING-START (WILLKOMMEN)
          ========================================================= */}
      {currentView === 'welcome' && (
        <div className="welcome-layout">
          <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center', gap: '0.1rem' }}>
            <div style={{ transform: 'scale(1.2)', transformOrigin: 'center', display: 'inline-block' }}>
              <Logo showText={false} />
            </div>
            <span style={{ fontSize: '1.5rem', fontWeight: '300', color: colors.text, letterSpacing: '-0.02em', marginTop: '0.5rem' }}>
              move<span style={{ fontWeight: '700', color: colors.accentCyan }}>optimizer</span>
            </span>
          </div>

          <div style={{ width: '100%', marginTop: '2.5rem' }}>
            <h1 className="welcome-title">
              Clever unterwegs,<br /><span style={{ color: colors.accentCyan }}>weniger zahlen.</span>
            </h1>

            <ul style={{ listStyle: 'none', padding: 0, margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '0.95rem', textAlign: 'left', maxWidth: '360px' }}>
              {FEATURES.map(({ icon: Icon, text }, i) => (
                <li key={i} style={{ display: 'flex', alignItems: 'start', gap: '0.75rem', lineHeight: '1.4' }}>
                  <span style={{ color: colors.accentPurple, display: 'flex', flexShrink: 0, marginTop: '3px' }}><Icon size={16} /></span>
                  <span style={{ color: colors.text, fontSize: '0.88rem' }}>{text}</span>
                </li>
              ))}
            </ul>
          </div>

          <div className="welcome-card">
            <button onClick={() => { setError(''); setCurrentView('register') }} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.05rem', fontWeight: '700', cursor: 'pointer', boxShadow: '0 4px 20px rgba(0, 242, 254, 0.15)' }}>
              Registrieren
            </button>
            <button onClick={() => setCurrentView('login')} style={{ width: '100%', padding: '1.1rem', backgroundColor: 'transparent', color: colors.text, borderRadius: '14px', border: `1px solid ${colors.border}`, fontSize: '1.05rem', fontWeight: '600', cursor: 'pointer' }}>
              Anmelden
            </button>
            <p style={{ fontSize: '0.75rem', color: colors.textMuted, marginTop: '0.6rem', lineHeight: '1.45' }}>
              Mit dem Fortfahren akzeptierst du unsere:<br />
              <span style={{ color: colors.accentCyan, cursor: 'pointer' }}>Nutzungsbedingungen</span> – <span style={{ color: colors.accentCyan, cursor: 'pointer' }}>Datenschutzrichtlinie</span>
            </p>
          </div>
        </div>
      )}

      {/* =========================================================
          ANSICHT: ESSENTIELLE KONTOERSTELLUNG
          ========================================================= */}
      {currentView === 'register' && (
        <div className="login-view-container">
          <div className="login-inner-card">
            <div style={{ alignSelf: 'flex-start', marginBottom: '2rem' }}>
              <button type="button" className="premium-back-btn" onClick={() => setCurrentView('welcome')}>
                <ChevronLeft size={16} /> Zurück
              </button>
            </div>
            <h2 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left' }}>Konto erstellen</h2>
            <p style={{ color: colors.textMuted, marginBottom: '2rem', textAlign: 'left', fontSize: '0.95rem', lineHeight: '1.45' }}>Starte mit den wichtigsten Angaben. Dein Mobilitätsprofil kannst du direkt danach oder später vervollständigen.</p>
            <form onSubmit={handleCreateAccount} style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
              <div className="responsive-form-grid">
                <div style={{ textAlign: 'left' }}><label style={inputLabelStyle}>Vorname</label><input autoComplete="given-name" required type="text" placeholder="Max" value={firstName} onChange={(e) => setFirstName(e.target.value)} style={textInputStyle} /></div>
                <div style={{ textAlign: 'left' }}><label style={inputLabelStyle}>Nachname</label><input autoComplete="family-name" required type="text" placeholder="Mustermann" value={lastName} onChange={(e) => setLastName(e.target.value)} style={textInputStyle} /></div>
              </div>
              <div style={{ textAlign: 'left' }}><label style={inputLabelStyle}>E-Mail-Adresse</label><input autoComplete="email" required type="email" placeholder="name@example.com" value={regEmail} onChange={(e) => setRegEmail(e.target.value)} style={textInputStyle} /></div>
              <div className="responsive-form-grid">
                <div style={{ textAlign: 'left' }}><label style={inputLabelStyle}>Passwort</label><input autoComplete="new-password" required minLength={8} type="password" placeholder="Mindestens 8 Zeichen" value={regPassword} onChange={(e) => setRegPassword(e.target.value)} style={textInputStyle} /></div>
                <div style={{ textAlign: 'left' }}><label style={inputLabelStyle}>Passwort wiederholen</label><input autoComplete="new-password" required minLength={8} type="password" placeholder="Passwort bestätigen" value={regPasswordConfirm} onChange={(e) => setRegPasswordConfirm(e.target.value)} style={textInputStyle} /></div>
              </div>
              {error && <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: colors.errorText, backgroundColor: colors.errorBg, padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem' }}><AlertCircle size={16} /><span>{error}</span></div>}
              <p style={{ fontSize: '0.72rem', color: colors.textMuted, lineHeight: '1.45', textAlign: 'left' }}>Mit der Registrierung akzeptierst du unsere Nutzungsbedingungen und Datenschutzrichtlinie.</p>
              <button type="submit" disabled={submitting} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.05rem', fontWeight: '700', cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.65 : 1 }}>{submitting ? 'Konto wird erstellt…' : 'Konto erstellen'}</button>
            </form>
          </div>
        </div>
      )}

      {/* =========================================================
          ANSICHT: ONBOARDING JETZT ODER SPÄTER
          ========================================================= */}
      {currentView === 'onboardingChoice' && (
        <div className="login-view-container">
          <div className="login-inner-card" style={{ textAlign: 'left' }}>
            <div style={{ width: '48px', height: '48px', borderRadius: '15px', display: 'grid', placeItems: 'center', color: colors.onAccent, background: `linear-gradient(135deg, ${colors.accentCyan}, ${colors.accentPurple})`, marginBottom: '1.25rem' }}><Check size={24} /></div>
            <h2 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem' }}>Dein Konto ist erstellt</h2>
            <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', lineHeight: '1.5' }}>Mit ein paar freiwilligen Angaben können wir deine Empfehlungen besser auf dich abstimmen.</p>
            <div style={{ backgroundColor: colors.inputBg, border: `1px solid ${colors.border}`, borderRadius: '16px', padding: '1rem', marginBottom: '1.25rem' }}>
              <div style={{ color: colors.text, fontWeight: '750', marginBottom: '.25rem' }}>Mobilitätsprofil vervollständigen</div>
              <div style={{ color: colors.textMuted, fontSize: '.82rem', lineHeight: '1.45' }}>Führerschein, Verkehrsmittel, Präferenzen, Abos und Wochenmuster · etwa 3 Minuten</div>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '.7rem' }}>
              <button type="button" onClick={() => { setError(''); setOnboardingStep(1); setCurrentView('onboarding') }} style={{ width: '100%', padding: '1.05rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1rem', fontWeight: '750', cursor: 'pointer' }}>Onboarding jetzt durchführen</button>
              <button type="button" onClick={handleSkipOnboarding} style={{ width: '100%', padding: '1.05rem', backgroundColor: colors.card, color: colors.text, borderRadius: '14px', border: `1px solid ${colors.border}`, fontSize: '1rem', fontWeight: '650', cursor: 'pointer' }}>Später im Profil vervollständigen</button>
            </div>
          </div>
        </div>
      )}

      {/* =========================================================
          ANSICHT 2: FRAGE-SCHRITTE (ONBOARDING KARTEN-WIZARD)
          ========================================================= */}
      {currentView === 'onboarding' && (
        <div className="onboarding-step-layout">
          <div className="onboarding-inner-card">
            
            {/* Visual Progress Bar */}
            <div style={{ width: '100%', height: '4px', backgroundColor: colors.border, borderRadius: '99px', marginBottom: '1.5rem', overflow: 'hidden' }}>
              <div style={{ width: `${(onboardingStepPosition / 12) * 100}%`, height: '100%', backgroundColor: colors.accentCyan, borderRadius: '99px', transition: 'width 0.35s cubic-bezier(0.4, 0, 0.2, 1)' }} />
            </div>

            {/* Header mit Zurück-Button & Schrittanzeige */}
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '2rem' }}>
              <button 
                type="button"
                className="premium-back-btn"
                onClick={() => {
                  if (onboardingStep === 1) {
                    setCurrentView('onboardingChoice')
                  } else if (onboardingStep === 2) {
                    setHasLicense(null)
                    setCarAccess('')
                    setBikeAccess([])
                    setOnboardingStep(1)
                  } else if (onboardingStep === 11) {
                    setOnboardingStep(9)
                  } else if (onboardingStep === 13) {
                    setOnboardingStep(11)
                  } else if (onboardingStep === 14) {
                    setOnboardingStep(13)
                  } else {
                    setOnboardingStep(onboardingStep - 1)
                  }
                }} 
              >
                <ChevronLeft size={16} /> Zurück
              </button>

              <span style={{ fontSize: '0.82rem', color: colors.textMuted, fontWeight: '700', letterSpacing: '0.02em' }}>
                Schritt {onboardingStepPosition} von 12
              </span>
            </div>

            <div style={{ flex: 1, display: 'flex', flexDirection: 'column', justifyContent: 'space-between' }}>

              {/* SCHRITT 1: FÜHRERSCHEIN (JA/NEIN) */}
              {onboardingStep === 1 && (
                <div>
                  <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3', letterSpacing: '-0.02em' }}>Hast du einen Führerschein?</h1>
                  <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>So können wir filtern, welche Sharing-Fahrzeuge du fahren darfst.</p>
                  <div className="responsive-options-grid">
                    <button onClick={() => { setHasLicense(true); setOnboardingStep(2); }} style={{ ...optionButtonStyle }}><span>Ja, habe ich 🚗</span></button>
                    <button onClick={() => { setHasLicense(false); setCarAccess('none'); setOnboardingStep(2); }} style={{ ...optionButtonStyle }}><span>Nein, habe ich nicht ❌</span></button>
                  </div>
                </div>
              )}

              {/* SCHRITT 2: FAHRZEUG- / FAHRRAD-ZUGRIFF */}
              {onboardingStep === 2 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div style={{ overflowY: 'auto', paddingRight: '2px' }}>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3', letterSpacing: '-0.02em' }}>Worauf hast du Zugriff?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', textAlign: 'left' }}>So wissen wir, welche Verkehrsmittel für deine Empfehlungen überhaupt in Frage kommen.</p>

                    {/* AUTO (Wird nur bei Führerschein eingeblendet) */}
                    {hasLicense === true && (
                      <div style={{ marginBottom: '1.5rem' }}>
                        <span style={{ color: colors.text, fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>🚗 Auto</span>
                        <div className="responsive-options-grid">
                          {[
                            { id: 'own', label: 'Eigenes Auto' },
                            { id: 'shared', label: 'Carsharing (z. B. Miles, SIXT)' },
                            { id: 'occasional', label: 'Gelegentlich (z. B. Familienauto)' },
                            { id: 'none', label: 'Gar kein Auto' }
                          ].map((carOpt) => {
                            const isCarSelected = carAccess === carOpt.id;
                            return (
                              <button key={carOpt.id} onClick={() => setCarAccess(carOpt.id)} style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isCarSelected ? colors.selectFill : colors.card, border: isCarSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>{carOpt.label}</span></button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    {/* FAHRRAD */}
                    <div>
                      <span style={{ color: colors.text, fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>🚲 Fahrrad</span>
                      <div className="responsive-options-grid">
                        {[
                          { id: 'own', label: 'Eigenes Fahrrad' },
                          { id: 'shared', label: 'Leihrad / Bike-Sharing (z. B. nextbike)' },
                          { id: 'none', label: 'Kein Fahrrad' }
                        ].map((bikeOpt) => {
                          const isBikeSelected = bikeAccess.includes(bikeOpt.id)
                          return (
                            <button
                              key={bikeOpt.id}
                              onClick={() => handleBikeAccessToggle(bikeOpt.id)}
                              style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isBikeSelected ? colors.selectFill : colors.card, border: isBikeSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}
                            >
                              <span>{bikeOpt.label}</span>
                              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', borderRadius: '6px', border: `2px solid ${colors.accentPurple}`, backgroundColor: isBikeSelected ? colors.accentPurple : 'transparent', flexShrink: 0 }}>
                                {isBikeSelected && <Check size={12} strokeWidth={3} color="#000000" />}
                              </div>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  {(() => {
                    const ready = (hasLicense === false || carAccess) && bikeAccess.length > 0;
                    return (
                      <button onClick={() => setOnboardingStep(3)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? colors.onAccent : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s', marginTop: '1.5rem' }}>Weiter</button>
                    );
                  })()}
                </div>
              )}

              {/* SCHRITT 3: ABOS */}
              {onboardingStep === 3 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Welche Mobilitäts-Abos hast du?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>Tippe auf eine Kategorie, um deine aktiven Tickets auszuwählen.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.65rem' }}>
                      {SUBSCRIPTION_CATEGORIES.map((cat) => {
                        if (cat.id === 'car' && hasLicense === false) return null
                        const isOpen = activeCategory === cat.id
                        return (
                          <div key={cat.id} style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                            <div
                              onClick={() => setActiveCategory(isOpen ? '' : cat.id)}
                              style={{ ...optionButtonStyle, padding: '1rem 1.2rem', backgroundColor: isOpen ? 'rgba(0, 242, 254, 0.02)' : colors.card, border: isOpen ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}`, fontWeight: '600' }}
                            >
                              <span style={{ color: colors.text }}>{cat.title}</span>
                              <span style={{ color: colors.accentCyan, fontSize: '0.8rem', transition: 'transform 0.2s', transform: isOpen ? 'rotate(90deg)' : 'rotate(0deg)' }}>▶</span>
                            </div>

                            {isOpen && (
                              <div className="responsive-options-grid" style={{ paddingLeft: '0.75rem' }}>
                                {cat.services.map((sid) => {
                                  const config = SUBSCRIPTION_OPTIONS[sid]
                                  const isSelected = services.includes(sid)
                                  return (
                                    <div
                                      key={sid}
                                      onClick={() => handleServiceToggle(sid)}
                                      style={{ ...optionButtonStyle, padding: '0.85rem 1rem', backgroundColor: isSelected ? colors.selectFill : colors.card, border: isSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}
                                    >
                                      <span style={{ color: colors.text, fontSize: '0.9rem' }}>{config.label}</span>
                                      <div style={{ width: '16px', height: '16px', borderRadius: '5px', border: `2px solid ${colors.accentPurple}`, backgroundColor: isSelected ? colors.accentPurple : 'transparent', flexShrink: 0 }} />
                                    </div>
                                  )
                                })}
                              </div>
                            )}
                          </div>
                        )
                      })}

                      <div
                        onClick={() => handleServiceToggle('none')}
                        style={{ ...optionButtonStyle, padding: '1rem 1.2rem', backgroundColor: services.includes('none') ? 'rgba(0, 242, 254, 0.05)' : colors.card, border: services.includes('none') ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}` }}
                      >
                        <span style={{ color: colors.text }}>❌ Keine Abos (Pay-per-Trip)</span>
                        <div style={{ width: '18px', height: '18px', borderRadius: '5px', border: `2px solid ${colors.accentCyan}`, backgroundColor: services.includes('none') ? colors.accentCyan : 'transparent', flexShrink: 0 }} />
                      </div>
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setOnboardingStep(4)} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', marginTop: '1.5rem' }}>Weiter</button>
                </div>
              )}

              {/* SCHRITT 4: ABO-DETAILS */}
              {onboardingStep === 4 && (() => {
                const selected = services.filter(s => s !== 'none')
                const selectedWithDetails = selected.filter(sid => !SUBSCRIPTION_OPTIONS[sid]?.skipDetails)

                if (selected.length === 0 || selectedWithDetails.length === 0) {
                  return (
                    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                      <div>
                        <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Keine Abo-Details nötig</h1>
                        <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left' }}>Für deine Auswahl brauchen wir keine weiteren Detailangaben.</p>
                      </div>
                      <div style={{ flex: 1 }} />
                      <button onClick={() => setOnboardingStep(5)} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s', marginTop: '1rem' }}>Weiter</button>
                    </div>
                  )
                }

                const chip = (active) => ({
                  padding: '0.5rem 0.85rem', borderRadius: '999px', fontSize: '0.82rem', fontWeight: '600', cursor: 'pointer',
                  backgroundColor: active ? colors.accentPurple : colors.card, color: active ? colors.onAccent : colors.text,
                  border: active ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, transition: 'all 0.15s'
                })

                const miniLabel = { color: colors.textMuted, fontSize: '0.72rem', fontWeight: '500', display: 'block', margin: '0.65rem 0 0.4rem' }

                const detailsReady = selectedWithDetails.every((sid) => {
                  const config = SUBSCRIPTION_OPTIONS[sid]
                  if (!config?.asksTravelClass) return true
                  return Boolean(subscriptionDetails[sid]?.travel_class)
                })

                return (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ overflowY: 'auto', paddingRight: '2px' }}>
                      <h1 style={{ fontSize: '1.7rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Erzähl uns mehr zu deinen Abos</h1>
                      <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left', lineHeight: '1.4' }}>So ordnen wir Kosten, Tarifart und BahnCard-Klasse korrekt zu.</p>

                      <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
                        {selectedWithDetails.map((sid) => {
                          const config = SUBSCRIPTION_OPTIONS[sid]
                          const d = subscriptionDetails[sid] || {}
                          const typeOptions = config.typeOptions || DEFAULT_TYPE_OPTS
                          const billingOptions = config.billingOptions || DEFAULT_BILL_OPTS
                          const selectedType = d.type || config.defaultType || typeOptions[0]?.id
                          const selectedBilling = d.billing || config.defaultBilling || billingOptions[0]?.id

                          return (
                            <div key={sid} style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '16px', padding: '1rem 1.1rem', textAlign: 'left' }}>
                              <span style={{ color: colors.text, fontSize: '0.95rem', fontWeight: '700', display: 'block' }}>{config.label}</span>
                              <span style={miniLabel}>Art</span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                {typeOptions.map((o) => (
                                  <span key={o.id} onClick={() => setSubDetail(sid, 'type', o.id)} style={chip(selectedType === o.id)}>{o.label}</span>
                                ))}
                              </div>

                              {config.asksTravelClass && (
                                <>
                                  <span style={miniLabel}>Klasse</span>
                                  <div style={{ display: 'flex', gap: '0.45rem' }}>
                                    {[{ id: 1, label: '1. Klasse' }, { id: 2, label: '2. Klasse' }].map((travelClassOpt) => {
                                      const isSelected = d.travel_class === travelClassOpt.id
                                      return (
                                        <button
                                          key={travelClassOpt.id} type="button" onClick={() => setSubDetail(sid, 'travel_class', travelClassOpt.id)}
                                          style={{ flex: 1, padding: '0.7rem 0.8rem', borderRadius: '12px', fontSize: '0.82rem', fontWeight: '700', cursor: 'pointer', backgroundColor: isSelected ? colors.accentPurple : colors.card, color: isSelected ? colors.onAccent : colors.text, border: isSelected ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}
                                        >
                                          {travelClassOpt.label}
                                        </button>
                                      )
                                    })}
                                  </div>
                                </>
                              )}

                              <span style={miniLabel}>Abrechnung</span>
                              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.4rem' }}>
                                {billingOptions.map((o) => (
                                  <span key={o.id} onClick={() => setSubDetail(sid, 'billing', o.id)} style={chip(selectedBilling === o.id)}>{o.label}</span>
                                ))}
                              </div>
                            </div>
                          )
                        })}
                      </div>
                    </div>
                    <div style={{ flex: 1 }} />
                    <button onClick={() => setOnboardingStep(5)} disabled={!detailsReady} style={{ width: '100%', padding: '1.1rem', backgroundColor: detailsReady ? colors.accentCyan : colors.card, color: detailsReady ? colors.onAccent : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: detailsReady ? 'pointer' : 'not-allowed', transition: 'all 0.2s', marginTop: '1.5rem' }}>Weiter</button>
                  </div>
                )
              })()}

              {/* SCHRITT 5: HÄUFIGSTE VERKEHRSMITTEL */}
              {onboardingStep === 5 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Welche Verkehrsmittel nutzt du hauptsächlich?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>Wähle die Optionen, die du im Alltag am häufigsten nutzt.</p>
                    <div className="responsive-options-grid">
                      {TRANSPORT_MODES.map((mode) => {
                        if ((mode.id === 'car' || mode.id === 'car_sharing') && hasLicense === false) return null;
                        const isSelected = frequentModes.includes(mode.id);
                        return (
                          <div 
                            key={mode.id} onClick={() => handleFrequentToggle(mode.id)}
                            style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isSelected ? colors.cyanFill : colors.card, border: isSelected ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}` }}
                          >
                            <span style={{ color: colors.text, fontSize: '0.95rem' }}>{mode.label}</span>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', borderRadius: '6px', border: `2px solid ${colors.accentCyan}`, backgroundColor: isSelected ? colors.accentCyan : 'transparent', flexShrink: 0 }}>
                              {isSelected && <Check size={12} strokeWidth={3} color="#000000" />}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setOnboardingStep(6)} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', marginTop: '1.5rem' }}>Weiter</button>
                </div>
              )}

              {/* SCHRITT 6: VERKEHRSMITTEL MEIDEN */}
              {onboardingStep === 6 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Gibt es Verkehrsmittel, die du vermeiden möchtest?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.9rem', textAlign: 'left' }}>Diese schließen wir aus den Empfehlungen aus.</p>
                    <div className="responsive-options-grid">
                      {TRANSPORT_MODES.map((mode) => {
                        if ((mode.id === 'car' || mode.id === 'car_sharing') && hasLicense === false) return null;
                        const isAvoided = avoidModes.includes(mode.id);
                        return (
                          <div 
                            key={mode.id} onClick={() => handleAvoidToggle(mode.id)}
                            style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isAvoided ? 'rgba(244, 63, 94, 0.05)' : colors.card, border: isAvoided ? `1px solid ${colors.accentRed}` : `1px solid ${colors.border}` }}
                          >
                            <span style={{ color: isAvoided ? colors.accentRed : colors.text, fontSize: '0.95rem', fontWeight: isAvoided ? '600' : '500' }}>{mode.label}</span>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', borderRadius: '50%', border: `2px solid ${isAvoided ? colors.accentRed : colors.border}`, backgroundColor: isAvoided ? colors.accentRed : 'transparent', flexShrink: 0 }}>
                              {isAvoided && <Ban size={12} strokeWidth={3} color="#000000" />}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setOnboardingStep(7)} style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', marginTop: '1.5rem' }}>Weiter</button>
                </div>
              )}

              {/* SCHRITT 7: PRIORITÄTEN */}
              {onboardingStep === 7 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div style={{ overflowY: 'auto', maxHeight: '72vh', paddingRight: '2px' }}>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Wie wichtig sind dir diese Ziele?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', textAlign: 'left' }}>Stell für jedes Ziel einen Wert von 1 (egal) bis 10 (sehr wichtig) ein.</p>

                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.6rem' }}>
                      {[
                        { id: 'time', label: '⏱️ Zeit sparen (Schnelligkeit)' },
                        { id: 'budget', label: '💰 Geld sparen (Wirtschaftlichkeit)' },
                        { id: 'environmental_concerns', label: '🌱 Umwelt schützen (CO₂)' }
                      ].map((p) => {
                        const val = priorityScores[p.id]
                        return (
                          <div key={p.id} style={{ textAlign: 'left' }}>
                            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.55rem' }}>
                              <span style={{ color: colors.text, fontSize: '0.95rem', fontWeight: '600' }}>{p.label}</span>
                              <span style={{ minWidth: '28px', textAlign: 'center', color: '#000', backgroundColor: colors.accentPurple, borderRadius: '8px', fontWeight: '800', fontSize: '0.85rem', padding: '0.15rem 0.4rem' }}>{val}</span>
                            </div>
                            <input
                              type="range" min="1" max="10" step="1" value={val}
                              onChange={(e) => setPriorityScores((prev) => ({ ...prev, [p.id]: Number(e.target.value) }))}
                              style={{ width: '100%', accentColor: colors.accentPurple, cursor: 'pointer' }}
                            />
                          </div>
                        )
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <button onClick={() => setOnboardingStep(8)} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s', marginTop: '1.5rem' }}>Weiter</button>
                </div>
              )}

              {/* SCHRITT 8: TYPISCHE WOCHE */}
              {onboardingStep === 8 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div style={{ overflowY: 'auto', maxHeight: '72vh', paddingRight: '2px' }}>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Wie sieht deine typische Woche aus?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Wähle alles aus, was regelmäßig auf dich zutrifft.</p>

                    <span style={{ color: colors.text, fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>Arbeit & Verpflichtungen</span>
                    <div className="responsive-options-grid" style={{ marginBottom: '1.5rem' }}>
                      {TYPICAL_WORK_PATTERNS.map((p) => {
                        const isSel = typicalWorkPatterns.includes(p)
                        return (
                          <button
                            key={p} type="button" onClick={() => handlePatternToggle(setTypicalWorkPatterns, p)}
                            style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isSel ? colors.cyanFill : colors.card, border: isSel ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}` }}
                          >
                            <span>{p}</span>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', borderRadius: '6px', border: `2px solid ${colors.accentCyan}`, backgroundColor: isSel ? colors.accentCyan : 'transparent', flexShrink: 0 }}>
                              {isSel && <Check size={12} strokeWidth={3} color="#000000" />}
                            </div>
                          </button>
                        )
                      })}
                    </div>

                    <span style={{ color: colors.text, fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>Freizeit & Wochenende</span>
                    <div className="responsive-options-grid">
                      {TYPICAL_LEISURE_PATTERNS.map((p) => {
                        const isSel = typicalLeisurePatterns.includes(p)
                        return (
                          <button
                            key={p} type="button" onClick={() => handlePatternToggle(setTypicalLeisurePatterns, p)}
                            style={{ ...optionButtonStyle, padding: '0.95rem 1.1rem', backgroundColor: isSel ? colors.cyanFill : colors.card, border: isSel ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}` }}
                          >
                            <span>{p}</span>
                            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '18px', height: '18px', borderRadius: '6px', border: `2px solid ${colors.accentCyan}`, backgroundColor: isSel ? colors.accentCyan : 'transparent', flexShrink: 0 }}>
                              {isSel && <Check size={12} strokeWidth={3} color="#000000" />}
                            </div>
                          </button>
                        )
                      })}
                    </div>

                    <label style={{ color: colors.text, fontSize: '0.9rem', fontWeight: '600', display: 'block', margin: '1.5rem 0 0.5rem', textAlign: 'left' }}>Noch etwas dazu? <span style={{ color: colors.textMuted, fontWeight: '400' }}>(optional)</span></label>
                    <textarea value={weekNote} onChange={(e) => setWeekNote(e.target.value)} placeholder="z. B. „Dienstags Sport am anderen Ende der Stadt.“" rows={3} style={{ width: '100%', boxSizing: 'border-box', padding: '0.9rem 1.1rem', borderRadius: '14px', backgroundColor: colors.inputBg, border: `1px solid ${colors.border}`, color: colors.text, fontSize: '0.95rem', outline: 'none', resize: 'vertical', fontFamily: 'inherit' }} onFocus={(e) => e.target.style.borderColor = colors.accentCyan} onBlur={(e) => e.target.style.borderColor = colors.border} />
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1.5rem' }}>
                    {(() => {
                      const ready = typicalWorkPatterns.length > 0 || typicalLeisurePatterns.length > 0
                      return (
                        <button onClick={() => setOnboardingStep(9)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? colors.onAccent : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      )
                    })()}
                    <button onClick={() => { setTypicalWorkPatterns([]); setTypicalLeisurePatterns([]); setWeekNote(''); setOnboardingStep(9); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 9: WOHNORT */}
              {onboardingStep === 9 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div style={{ overflowY: 'auto', maxHeight: '72vh', paddingRight: '2px' }}>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Wo wohnst du?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.5rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Damit wir Strecken für deine Region berechnen können.</p>

                    <div style={{ display: 'flex', gap: '0.6rem', backgroundColor: colors.cyanFill, border: `1px solid rgba(0, 242, 254, 0.25)`, borderRadius: '14px', padding: '0.8rem 1rem', marginBottom: '1.75rem', textAlign: 'left' }}>
                      <span style={{ fontSize: '1.1rem', lineHeight: '1.2' }}>💡</span>
                      <span style={{ fontSize: '0.82rem', color: colors.infoText, lineHeight: '1.45' }}>Wir fragen bewusst viel — je besser wir dich verstehen, desto präziser wird deine Empfehlung.</span>
                    </div>

                    <div className="responsive-form-grid">
                      <div>
                        <label style={inputLabelStyle}>Stadt</label>
                        <input type="text" placeholder="z. B. Frankfurt" value={homeCity} onChange={(e) => setHomeCity(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                      </div>
                      <div>
                        <label style={inputLabelStyle}>Postleitzahl</label>
                        <input type="text" inputMode="numeric" placeholder="z. B. 60311" value={homePostalCode} onChange={(e) => setHomePostalCode(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                      </div>
                      <div className="full-width-desktop">
                        <label style={inputLabelStyle}>Land</label>
                        <select value={homeCountry} onChange={(e) => setHomeCountry(e.target.value)} style={{ ...textInputStyle, appearance: 'none', WebkitAppearance: 'none', cursor: 'pointer' }} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border}>
                          {COUNTRY_OPTIONS.map((c) => (
                            <option key={c.code} value={c.code} style={{ backgroundColor: colors.inputBg, color: colors.text }}>{c.label}</option>
                          ))}
                        </select>
                      </div>
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1.5rem' }}>
                    {(() => {
                      const ready = homeCity.trim() && homePostalCode.trim();
                      return (
                        <button onClick={() => setOnboardingStep(11)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? colors.onAccent : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      );
                    })()}
                    <button onClick={() => { setHomeCity(''); setHomePostalCode(''); setOnboardingStep(11); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 10: ARBEIT & HYBRID */}
              {onboardingStep === 10 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Wie arbeitest du?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Dein Pendelmuster bestimmt einen großen Teil deiner Mobilität.</p>
                    <div className="responsive-options-grid">
                      {[
                        { id: 'onsite', label: '🏢 Vor Ort im Büro' },
                        { id: 'hybrid', label: '🔄 Hybrid (Büro & HO)' },
                        { id: 'remote', label: '🏠 Komplett remote' },
                        { id: 'unemployed', label: '🚫 Nicht berufstätig' }
                      ].map((opt) => {
                        const isSel = workArrangement === opt.id;
                        return (
                          <button key={opt.id} onClick={() => { setWorkArrangement(opt.id); if (opt.id === 'remote' || opt.id === 'unemployed') { setWorkCity(''); setWorkPostalCode(''); } if (opt.id !== 'hybrid') setRemoteDaysPerWeek(null); }} style={{ ...optionButtonStyle, padding: '1rem 1.2rem', backgroundColor: isSel ? colors.selectFill : colors.card, border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>{opt.label}</span></button>
                        );
                      })}
                    </div>

                    {/* Arbeitsort */}
                    {(workArrangement === 'onsite' || workArrangement === 'hybrid') && (
                      <div className="responsive-form-grid" style={{ marginTop: '1.5rem' }}>
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

                    {/* Homeoffice-Tage */}
                    {workArrangement === 'hybrid' && (
                      <div style={{ marginTop: '1.5rem' }}>
                        <label style={{ ...inputLabelStyle, marginBottom: '0.65rem' }}>Tage pro Woche im Homeoffice</label>
                        <div style={{ display: 'flex', gap: '0.5rem' }}>
                          {[0, 1, 2, 3, 4, 5].map((d) => {
                            const isSel = remoteDaysPerWeek === d;
                            return (
                              <button key={d} onClick={() => setRemoteDaysPerWeek(d)} style={{ flex: 1, padding: '0.85rem 0', backgroundColor: isSel ? colors.accentPurple : colors.card, color: isSel ? colors.onAccent : colors.text, border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, borderRadius: '12px', fontSize: '1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s' }}>{d}</button>
                            );
                          })}
                        </div>
                      </div>
                    )}

                    <label style={{ color: colors.text, fontSize: '0.9rem', fontWeight: '600', display: 'block', margin: '1.5rem 0 0.5rem', textAlign: 'left' }}>Noch etwas zu deinem Arbeitsweg? <span style={{ color: colors.textMuted, fontWeight: '400' }}>(optional)</span></label>
                    <textarea value={workNote} onChange={(e) => setWorkNote(e.target.value)} placeholder="z. B. „Freitags im anderen Büro.“" rows={3} style={{ width: '100%', boxSizing: 'border-box', padding: '0.9rem 1.1rem', borderRadius: '14px', backgroundColor: colors.inputBg, border: `1px solid ${colors.border}`, color: colors.text, fontSize: '0.95rem', outline: 'none', resize: 'vertical', fontFamily: 'inherit' }} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} />
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1.5rem' }}>
                    {(() => {
                      const needsLocation = workArrangement === 'onsite' || workArrangement === 'hybrid';
                      const needsDays = workArrangement === 'hybrid';
                      const ready = workArrangement && (!needsLocation || (workCity.trim() && workPostalCode.trim())) && (!needsDays || remoteDaysPerWeek !== null);
                      return (
                        <button onClick={() => setOnboardingStep(11)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? colors.onAccent : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      );
                    })()}
                    <button onClick={() => { setWorkArrangement(''); setWorkCity(''); setWorkPostalCode(''); setRemoteDaysPerWeek(null); setWorkNote(''); setOnboardingStep(11); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 11: MOBILITÄTSBUDGET */}
              {onboardingStep === 11 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Was gibst du monatlich für Mobilität aus?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Eine grobe Schätzung reicht — wir verfeinern das später mit deinen echten Daten.</p>
                    <div style={{ position: 'relative', backgroundColor: colors.inputBg, borderRadius: '14px', border: mobilityBudget ? `2px solid #ffffff` : `1px solid ${colors.border}`, padding: '0.6rem 1.1rem', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
                      <div style={{ flex: 1, textAlign: 'left' }}>
                        <label style={{ display: 'block', color: colors.textMuted, fontSize: '0.75rem', marginBottom: '0.15rem' }}>Budget pro Monat</label>
                        <input type="number" inputMode="numeric" placeholder="z. B. 150" value={mobilityBudget} onChange={(e) => setMobilityBudget(e.target.value)} style={{ width: '100%', backgroundColor: 'transparent', border: 'none', color: colors.text, fontSize: '1.2rem', fontWeight: '600', outline: 'none', padding: 0 }} />
                      </div>
                      <span style={{ color: colors.textMuted, fontSize: '1.2rem', fontWeight: '600' }}>€</span>
                      {mobilityBudget && <X size={18} onClick={() => setMobilityBudget('')} style={{ color: colors.textMuted, cursor: 'pointer' }} />}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1.5rem' }}>
                    {(() => {
                      const ready = mobilityBudget !== '' && Number(mobilityBudget) >= 0;
                      return (
                        <button onClick={() => setOnboardingStep(13)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? colors.onAccent : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      );
                    })()}
                    <button onClick={() => { setMobilityBudget(''); setOnboardingStep(13); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 12: FINANZ-KONTEXT */}
              {onboardingStep === 12 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.7rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.3' }}>Ein bisschen Kontext zu deinem Haushalt</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.9rem', textAlign: 'left', lineHeight: '1.4' }}>Hilft uns, Empfehlungen auf dein Budget abzustimmen.</p>

                    <span style={{ color: colors.text, fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>Personen im Haushalt</span>
                    <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '1.5rem' }}>
                      {['1', '2', '3', '4', '5+'].map((h) => {
                        const isSel = householdSize === h;
                        return (
                          <button key={h} onClick={() => setHouseholdSize(h)} style={{ flex: 1, padding: '0.85rem 0', backgroundColor: isSel ? colors.accentPurple : colors.card, color: isSel ? colors.onAccent : colors.text, border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, borderRadius: '12px', fontSize: '1rem', fontWeight: '700', cursor: 'pointer', transition: 'all 0.2s' }}>{h}</button>
                        );
                      })}
                    </div>

                    <span style={{ color: colors.text, fontSize: '0.9rem', fontWeight: '600', display: 'block', marginBottom: '0.65rem', textAlign: 'left' }}>Monatliches Nettoeinkommen</span>
                    <div className="responsive-options-grid">
                      {[
                        { id: 'under_1500', label: 'Unter 1.500 €' }, { id: '1500_3000', label: '1.500 – 3.000 €' },
                        { id: '3000_4500', label: '3.000 – 4.500 €' }, { id: 'over_4500', label: 'Über 4.500 €' },
                        { id: 'prefer_not_say', label: 'Keine Angabe' }
                      ].map((band) => {
                        const isSel = incomeBand === band.id;
                        return (
                          <button key={band.id} onClick={() => setIncomeBand(band.id)} style={{ ...optionButtonStyle, padding: '0.9rem 1.1rem', backgroundColor: isSel ? colors.selectFill : colors.card, border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}` }}><span>{band.label}</span></button>
                        );
                      })}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1.5rem' }}>
                    {(() => {
                      const ready = householdSize && incomeBand;
                      return (
                        <button onClick={() => setOnboardingStep(13)} disabled={!ready} style={{ width: '100%', padding: '1.1rem', backgroundColor: ready ? colors.accentCyan : colors.card, color: ready ? colors.onAccent : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: ready ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                      );
                    })()}
                    <button onClick={() => { setHouseholdSize(''); setIncomeBand(''); setOnboardingStep(13); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 13: GEBURTSJAHR */}
              {onboardingStep === 13 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.9rem', fontWeight: '800', color: colors.text, marginBottom: '0.75rem', textAlign: 'left', lineHeight: '1.25' }}>In welchem Jahr bist du geboren?</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2.5rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Basierend auf deinem Alter erhältst du passende Tipps.</p>
                    <div style={{ position: 'relative', backgroundColor: colors.inputBg, borderRadius: '14px', border: birthYear ? `2px solid #ffffff` : `1px solid ${colors.border}`, padding: '0.6rem 1.1rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                      <div style={{ flex: 1, textAlign: 'left' }}><label style={{ display: 'block', color: colors.textMuted, fontSize: '0.75rem', marginBottom: '0.15rem' }}>Geburtsjahr</label><input type="number" placeholder="z.B. 2002" value={birthYear} onChange={(e) => setBirthYear(e.target.value)} style={{ width: '100%', backgroundColor: 'transparent', border: 'none', color: colors.text, fontSize: '1.2rem', fontWeight: '600', outline: 'none', padding: 0 }} /></div>
                      {birthYear && <X size={18} onClick={() => setBirthYear('')} style={{ color: colors.textMuted, cursor: 'pointer' }} />}
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1.5rem' }}>
                    <button onClick={() => setOnboardingStep(14)} disabled={!birthYear || birthYear.length < 4} style={{ width: '100%', padding: '1.1rem', backgroundColor: (birthYear && birthYear.length >= 4) ? colors.accentCyan : colors.card, color: (birthYear && birthYear.length >= 4) ? colors.onAccent : colors.textMuted, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: (birthYear && birthYear.length >= 4) ? 'pointer' : 'not-allowed', transition: 'all 0.2s' }}>Weiter</button>
                    <button onClick={() => { setBirthYear(''); setOnboardingStep(14); }} style={skipLinkStyle}>Überspringen</button>
                  </div>
                </div>
              )}

              {/* SCHRITT 14: PARTNER-KONTEN VERBINDEN (simuliert) */}
              {onboardingStep === 14 && (() => {
                const linkable = services.filter((s) => s !== 'none')
                const connectedCount = linkable.filter((s) => connectedAccounts[s]).length
                return (
                  <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                    <div style={{ overflowY: 'auto', paddingRight: '2px' }}>
                      <h1 style={{ fontSize: '1.9rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.25' }}>Verbinde deine Mobilitäts-Konten</h1>
                      <p style={{ color: colors.textMuted, marginBottom: '1.75rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Melde dich bei deinen Anbietern an, damit wir deine Fahrten und Kosten automatisch importieren können. Die Anmeldung ist eine Demo und wird nur simuliert.</p>

                      {linkable.length === 0 ? (
                        <div style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '16px', padding: '1.1rem', textAlign: 'left', color: colors.textMuted, fontSize: '0.9rem', lineHeight: '1.4' }}>
                          Du hast keine Abos angegeben — diesen Schritt kannst du einfach überspringen.
                        </div>
                      ) : (
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.7rem' }}>
                          {linkable.map((sid) => {
                            const label = mobilityAccountLabel(sid)
                            const isConnected = !!connectedAccounts[sid]
                            const isConnecting = connectingId === sid
                            const initial = String(label).replace(/[^A-Za-z0-9]/g, '').charAt(0).toUpperCase() || '•'
                            return (
                              <div key={sid} style={{ backgroundColor: colors.card, border: `1px solid ${isConnected ? colors.accentCyan : colors.border}`, borderRadius: '16px', padding: '0.95rem 1.05rem', transition: 'border-color 0.2s' }}>
                                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.75rem' }}>
                                  <div style={{ display: 'flex', alignItems: 'center', gap: '0.7rem', minWidth: 0 }}>
                                    <div style={{ width: '36px', height: '36px', borderRadius: '10px', flexShrink: 0, display: 'grid', placeItems: 'center', background: 'linear-gradient(135deg, #00f2fe, #4facfe)', color: '#04141a', fontWeight: '800', fontSize: '0.95rem' }}>{initial}</div>
                                    <span style={{ fontWeight: '700', color: colors.text, fontSize: '0.95rem', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{label}</span>
                                  </div>
                                  {isConnected ? (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', color: colors.accentCyan, fontWeight: '700', fontSize: '0.85rem', flexShrink: 0 }}><Check size={16} /> Verbunden</span>
                                  ) : isConnecting ? (
                                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.45rem', color: colors.textMuted, fontWeight: '600', fontSize: '0.85rem', flexShrink: 0 }}>
                                      <span style={{ width: '16px', height: '16px', borderRadius: '50%', border: `2px solid ${colors.border}`, borderTopColor: colors.accentCyan, animation: 'spin 0.8s linear infinite', display: 'inline-block' }} />
                                      Verbinden…
                                    </span>
                                  ) : (
                                    <button type="button" onClick={() => simulateConnect(sid)} disabled={!!connectingId} style={{ flexShrink: 0, padding: '0.55rem 1rem', borderRadius: '10px', border: `1px solid ${colors.accentPurple}`, backgroundColor: 'transparent', color: colors.accentPurple, fontWeight: '700', fontSize: '0.85rem', cursor: connectingId ? 'not-allowed' : 'pointer', opacity: connectingId ? 0.5 : 1, transition: 'all 0.15s' }}>Verbinden</button>
                                  )}
                                </div>
                              </div>
                            )
                          })}
                        </div>
                      )}

                      <div style={{ backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '16px', padding: '1.1rem', marginTop: '1.5rem' }}>
                        <h3 style={{ fontSize: '1rem', fontWeight: '700', color: colors.text, marginBottom: '0.35rem', textAlign: 'left' }}>Kalender einbinden?</h3>
                        <p style={{ color: colors.textMuted, marginBottom: '0.9rem', fontSize: '0.88rem', textAlign: 'left', lineHeight: '1.4' }}>Möchtest du deinen Kalender verknüpfen, damit wir bevorstehende Reisen und Termine bei deinen Empfehlungen berücksichtigen können?</p>
                        <div style={{ display: 'flex', gap: '0.6rem' }}>
                          <button type="button" onClick={() => setCalendarSync(true)} style={{ flex: 1, padding: '0.7rem', borderRadius: '10px', fontSize: '0.9rem', fontWeight: '700', cursor: 'pointer', backgroundColor: calendarSync === true ? colors.accentCyan : colors.inputBg, color: calendarSync === true ? colors.onAccent : colors.text, border: calendarSync === true ? `1px solid ${colors.accentCyan}` : `1px solid ${colors.border}`, transition: 'all 0.15s' }}>Ja</button>
                          <button type="button" onClick={() => setCalendarSync(false)} style={{ flex: 1, padding: '0.7rem', borderRadius: '10px', fontSize: '0.9rem', fontWeight: '700', cursor: 'pointer', backgroundColor: calendarSync === false ? colors.accentPurple : colors.inputBg, color: calendarSync === false ? colors.onAccent : colors.text, border: calendarSync === false ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, transition: 'all 0.15s' }}>Nein</button>
                        </div>
                      </div>
                    </div>

                    <div style={{ flex: 1 }} />
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', marginTop: '1.5rem' }}>
                      {linkable.length > 0 && (
                        <span style={{ fontSize: '0.8rem', color: colors.textMuted, textAlign: 'center' }}>{connectedCount} von {linkable.length} verbunden</span>
                      )}
                      {error && <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: colors.errorText, backgroundColor: colors.errorBg, padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem' }}><AlertCircle size={16} /><span>{error}</span></div>}
                      <button type="button" onClick={handleFinish} disabled={submitting} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.65 : 1, transition: 'all 0.2s' }}>{submitting ? 'Wird gespeichert…' : 'Onboarding abschließen'}</button>
                    </div>
                  </div>
                )
              })()}

              {/* SCHRITT 15: KONTO ERSTELLEN */}
              {onboardingStep === 15 && (
                <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                  <div>
                    <h1 style={{ fontSize: '1.9rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'left', lineHeight: '1.25' }}>Konto erstellen</h1>
                    <p style={{ color: colors.textMuted, marginBottom: '2rem', fontSize: '0.95rem', textAlign: 'left', lineHeight: '1.4' }}>Lege deine Zugangsdaten fest, um dein Profil abzuschließen.</p>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
                      <div className="responsive-form-grid">
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
                        <div className="responsive-options-grid" style={{ gap: '0.4rem' }}>
                          {[{ id: 'female', label: 'Weiblich' }, { id: 'male', label: 'Männlich' }, { id: 'diverse', label: 'Divers' }, { id: 'not_specified', label: 'Keine Angabe' }].map((g) => {
                            const isSel = gender === g.id
                            return (<button key={g.id} type="button" onClick={() => setGender(g.id)} style={{ flex: 1, padding: '0.7rem 0.3rem', borderRadius: '12px', fontSize: '0.8rem', fontWeight: '600', cursor: 'pointer', backgroundColor: isSel ? colors.accentPurple : colors.card, color: isSel ? colors.onAccent : colors.text, border: isSel ? `1px solid ${colors.accentPurple}` : `1px solid ${colors.border}`, transition: 'all 0.15s' }}>{g.label}</button>)
                          })}
                        </div>
                      </div>
                      <div style={{ textAlign: 'left' }}><label style={{ color: colors.textMuted, fontSize: '0.78rem', fontWeight: '500', display: 'block', marginBottom: '0.3rem', paddingLeft: '4px' }}>E-Mail-Adresse</label><input type="email" placeholder="name@example.com" value={regEmail} onChange={(e) => setRegEmail(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} /></div>
                      <div style={{ textAlign: 'left' }}><label style={{ color: colors.textMuted, fontSize: '0.78rem', fontWeight: '500', display: 'block', marginBottom: '0.3rem', paddingLeft: '4px' }}>Passwort erstellen</label><input type="password" placeholder="••••••••" value={regPassword} onChange={(e) => setRegPassword(e.target.value)} style={textInputStyle} onFocus={(e) => e.target.style.borderColor = colors.accentPurple} onBlur={(e) => e.target.style.borderColor = colors.border} /></div>
                    </div>
                  </div>
                  <div style={{ flex: 1 }} />
                  <div style={{ marginTop: '1.5rem' }}>
                    {error && (
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: colors.errorText, backgroundColor: colors.errorBg, padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem', marginBottom: '0.85rem' }}>
                        <AlertCircle size={16} /><span>{error}</span>
                      </div>
                    )}
                    <p style={{ fontSize: '0.72rem', color: colors.textMuted, lineHeight: '1.45', textAlign: 'left', marginBottom: '0.85rem' }}>
                      🔒 Deine Angaben werden DSGVO-konform verarbeitet. Mehr in unserer <span style={{ color: colors.accentCyan, cursor: 'pointer' }}>Datenschutzrichtlinie</span>.
                    </p>
                    <button onClick={handleFinish} disabled={submitting} style={{ width: '100%', padding: '1.1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '14px', border: 'none', fontSize: '1.1rem', fontWeight: '700', cursor: submitting ? 'not-allowed' : 'pointer', opacity: submitting ? 0.7 : 1, boxShadow: '0 4px 25px rgba(0, 242, 254, 0.25)', transition: 'all 0.2s' }}>{submitting ? 'Speichern…' : 'Abschließen & Anmelden'}</button>
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
        <div className="login-view-container">
          <div className="login-inner-card">
            
            {/* Perfekt ausgerichteter Zurück-Button jetzt auch beim Login oben links */}
            <div style={{ alignSelf: 'flex-start', marginBottom: '2rem' }}>
              <button 
                type="button"
                className="premium-back-btn"
                onClick={() => setCurrentView('welcome')}
              >
                <ChevronLeft size={16} /> Zurück
              </button>
            </div>

            <h2 style={{ fontSize: '1.8rem', fontWeight: '800', color: colors.text, marginBottom: '0.5rem', textAlign: 'center', letterSpacing: '-0.02em' }}>Willkommen zurück</h2>
            <p style={{ color: colors.textMuted, marginBottom: '2.5rem', textAlign: 'center', fontSize: '0.95rem' }}>Melde dich an, um deinen persönlichen Mobilitätsplan zu sehen.</p>

            <form onSubmit={handleSubmit} noValidate style={{ display: 'flex', flexDirection: 'column', gap: '1.25rem' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ color: colors.text, fontSize: '0.85rem', fontWeight: '500', textAlign: 'left' }} htmlFor="email">E-Mail</label>
                <input id="email" style={{ width: '100%', padding: '0.85rem', borderRadius: '12px', backgroundColor: colors.card, border: `1px solid ${colors.border}`, color: colors.text, fontSize: '1rem', boxSizing: 'border-box' }} type="email" placeholder="you@dbmove.de" value={identifier} onChange={(e) => { setIdentifier(e.target.value); setError('') }} />
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.4rem' }}>
                <label style={{ color: colors.text, fontSize: '0.85rem', fontWeight: '500', textAlign: 'left' }} htmlFor="password">Passwort</label>
                <input id="password" style={{ width: '100%', padding: '0.85rem', borderRadius: '12px', backgroundColor: colors.card, border: `1px solid ${colors.border}`, color: colors.text, fontSize: '1rem', boxSizing: 'border-box' }} type="password" placeholder="••••••••" value={password} onChange={(e) => { setPassword(e.target.value); setError('') }} />
              </div>

              {error && (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', color: colors.errorText, backgroundColor: colors.errorBg, padding: '0.75rem', borderRadius: '8px', fontSize: '0.85rem' }}>
                  <AlertCircle size={16} /><span>{error}</span>
                </div>
              )}

              <button style={{ width: '100%', padding: '1rem', backgroundColor: colors.accentCyan, color: colors.onAccent, borderRadius: '12px', border: 'none', fontSize: '1rem', fontWeight: '700', cursor: 'pointer', marginTop: '0.5rem', boxShadow: '0 4px 20px rgba(0, 242, 254, 0.2)' }} type="submit" disabled={submitting}>
                {submitting ? 'Anmelden…' : 'Anmelden'}
              </button>
            </form>

            <div style={{ display: 'flex', alignItems: 'center', color: '#52667a', fontSize: '0.8rem', textTransform: 'uppercase', margin: '2rem 0' }}>
              <div style={{ flex: 1, height: '1px', backgroundColor: colors.border }}></div>
              <span style={{ padding: '0 0.75rem' }}>oder direkt einsteigen</span>
              <div style={{ flex: 1, height: '1px', backgroundColor: colors.border }}></div>
            </div>

            <div className="personas-grid">
              {personas && personas.map((p) => (
                <button 
                  key={p.id} 
                  type="button" 
                  onClick={() => loginAs(p.id)} 
                  style={{ 
                    display: 'flex', 
                    alignItems: 'center', 
                    gap: '0.6rem', 
                    width: '100%', 
                    padding: '0.6rem 0.75rem', 
                    backgroundColor: colors.card, 
                    border: `1px solid ${colors.border}`, 
                    borderRadius: '12px', 
                    color: colors.text, 
                    cursor: 'pointer',
                    boxSizing: 'border-box',
                    minWidth: 0 
                  }}
                >
                  <span style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', width: '30px', height: '30px', borderRadius: '50%', backgroundColor: colors.border, color: colors.accentCyan, fontWeight: '700', fontSize: '0.78rem', flexShrink: 0 }}>
                    {p.initials}
                  </span>
                  <span style={{ flex: 1, textAlign: 'left', minWidth: 0 }}>
                    <span style={{ fontWeight: '600', fontSize: '0.88rem', display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.name}
                    </span>
                    <span style={{ fontSize: '0.74rem', color: colors.textMuted, display: 'block', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                      {p.tagline}
                    </span>
                  </span>
                  <ArrowRight style={{ color: colors.accentCyan, flexShrink: 0 }} size={14} />
                </button>
              ))}
            </div>

          </div>
        </div>
      )}

    </div>
  )
}
