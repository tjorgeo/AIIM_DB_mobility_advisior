import React, { useEffect, useState } from 'react'
import {
  AlertCircle, BriefcaseBusiness, CalendarDays, Car, CheckCircle2, ChevronLeft,
  CreditCard, Link2, MapPin, Save, SlidersHorizontal, UserRound,
} from 'lucide-react'
import { getProfile, updateProfile } from '../api/client'
import { euro } from '../lib/format'
import { MOBILITY_ACCOUNT_OPTIONS } from '../lib/mobilityAccounts'
import { modeLabel } from '../lib/travelModes'

const MODES = [
  'walking', 'bicycle', 'bike_sharing', 'public_transport', 'regional_train',
  'long_distance_train', 'car', 'car_sharing', 'e_scooter', 'ride_hailing', 'taxi',
]

const COUNTRIES = [
  ['DE', 'Deutschland'], ['AT', 'Österreich'], ['CH', 'Schweiz'], ['NL', 'Niederlande'],
  ['FR', 'Frankreich'], ['BE', 'Belgien'], ['LU', 'Luxemburg'], ['PL', 'Polen'],
]

const emptyForm = {
  user: {
    first_name: '', last_name: '', email: '', gender: 'not_specified',
    date_of_birth: '', home_city: '', home_postal_code: '', home_country_code: 'DE',
  },
  onboarding: {
    has_driving_license: null, car_access: null, bike_access: [],
    preferred_transport_modes: [], avoided_transport_modes: [],
    score_money: 50, score_emission: 50, score_flexibility: 50,
    work_arrangement: '', work_city: '', work_postal_code: '', remote_work_share: null,
    mobility_budget_monthly_eur: '', household_size: '', income_band: '',
    typical_weekday_pattern: '', typical_weekend_pattern: '',
    travel_statement: '', activity_statement: '',
    connected_mobility_accounts: [],
  },
}

function nullableNumber(value) {
  return value === '' || value == null ? null : Number(value)
}

function Field({ label, children, hint }) {
  return (
    <label className="profile-field">
      <span className="profile-field__label">{label}</span>
      {children}
      {hint && <span className="profile-field__hint">{hint}</span>}
    </label>
  )
}

function Section({ icon, title, subtitle, colors, children }) {
  return (
    <section className="profile-section" style={{ backgroundColor: colors.card, borderColor: colors.border }}>
      <div className="profile-section__head">
        <span className="profile-section__icon" style={{ color: colors.accentCyan, backgroundColor: colors.cyanFill }}>{icon}</span>
        <div>
          <h2 style={{ color: colors.text }}>{title}</h2>
          {subtitle && <p style={{ color: colors.textMuted }}>{subtitle}</p>}
        </div>
      </div>
      {children}
    </section>
  )
}

function ToggleChip({ selected, onClick, children, colors, disabled = false }) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="profile-chip"
      style={{
        color: selected ? colors.accentPurple : colors.text,
        backgroundColor: selected ? colors.selectFill : colors.inputBg,
        borderColor: selected ? colors.accentPurple : colors.border,
        opacity: disabled ? 0.45 : 1,
      }}
    >
      {children}
    </button>
  )
}

export default function ProfileEdit({ userId, lang, colors, isDark, onBack, onSaved, chatSlotRef }) {
  const isDE = lang === 'DE'
  const [form, setForm] = useState(emptyForm)
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [loadFailed, setLoadFailed] = useState(false)
  const [saved, setSaved] = useState(false)
  const [calendarSync, setCalendarSync] = useState(null)

  const t = isDE ? {
    back: 'Zurück zum Dashboard', title: 'Profildaten ändern',
    subtitle: 'Deine Angaben aus dem Onboarding – Änderungen fließen in die nächste Analyse ein.',
    loading: 'Profil wird geladen…', loadError: 'Das Profil konnte nicht geladen werden.', saveError: 'Keine Verbindung zum Server.',
    save: 'Änderungen speichern', saving: 'Wird gespeichert…', saved: 'Profil gespeichert',
    personal: 'Persönliche Angaben', personalSub: 'Name, Konto und Geburtsdatum',
    address: 'Wohnort', addressSub: 'Ausgangspunkt deiner typischen Wege',
    access: 'Mobilitätszugang', accessSub: 'Führerschein und verfügbare Fahrzeuge',
    preferences: 'Mobilitätspräferenzen', preferencesSub: 'Verkehrsmittel und monatlicher finanzieller Rahmen',
    priorities: 'Deine Prioritäten', prioritiesSub: 'Gewichtung für Empfehlungen von 0 bis 100',
    patterns: 'Wochenmuster und Hinweise', patternsSub: 'Freitext aus deinem Onboarding',
    subscriptions: 'Mobilitäts-Abos', subscriptionsSub: 'Übersicht deiner aktiven und früheren Abos. Änderungen sind hier nicht möglich.',
    firstName: 'Vorname', lastName: 'Nachname', email: 'E-Mail', birthDate: 'Geburtsdatum',
    gender: 'Geschlecht', city: 'Wohnort', postal: 'Postleitzahl', country: 'Land',
    license: 'Führerschein', carAccess: 'Autozugang', bikeAccess: 'Fahrradzugang',
    yes: 'Ja', no: 'Nein', unknown: 'Keine Angabe', none: 'Kein Zugang', own: 'Eigen',
    shared: 'Geteilt / Sharing', occasional: 'Gelegentlich', preferred: 'Bevorzugt', avoided: 'Vermieden',
    money: 'Kosten', emission: 'CO₂', flexibility: 'Flexibilität / Zeit',
    budget: 'Mobilitätsbudget pro Monat', weekday: 'Typischer Werktag', weekend: 'Typisches Wochenende',
    travelStatement: 'Mobilitätshinweise', activityStatement: 'Aktivitäten und weitere Hinweise',
    active: 'Aktiv',
    inactiveHistory: 'Inaktive Abos', inactiveHistorySub: 'Diese Abos sind nicht mehr aktiv und bleiben als Historie erhalten.',
    inactive: 'Inaktiv', noSubs: 'Keine aktiven Abos ausgewählt.',
    changedAt: 'Status geändert', unmapped: 'Nicht zugeordnetes Abo',
    accounts: 'Mobilitäts-Konten', accountsSub: 'Verwalte die simulierten Anbieter-Verbindungen aus deinem Onboarding.',
    accountsDemo: 'Die Anmeldung bleibt eine Demo. Änderungen am Verbindungsstatus werden mit dem Profil gespeichert.',
    connected: 'Verbunden', notConnected: 'Nicht verbunden', connect: 'Verbinden', disconnect: 'Trennen',
    calendarTitle: 'Kalender einbinden?',
    calendarText: 'Möchtest du deinen Kalender verknüpfen, damit bevorstehende Reisen und Termine bei deinen Empfehlungen berücksichtigt werden können?',
    calendarDemo: 'Demo-Verknüpfung – es wird keine echte Verbindung zu einem Kalender hergestellt.',
  } : {
    back: 'Back to dashboard', title: 'Edit profile',
    subtitle: 'Your onboarding answers – changes feed into the next analysis.',
    loading: 'Loading profile…', loadError: 'The profile could not be loaded.', saveError: 'Could not connect to the server.',
    save: 'Save changes', saving: 'Saving…', saved: 'Profile saved',
    personal: 'Personal details', personalSub: 'Name, account and date of birth',
    address: 'Home location', addressSub: 'Starting point for your usual journeys',
    access: 'Mobility access', accessSub: 'Driving licence and available vehicles',
    preferences: 'Mobility preferences', preferencesSub: 'Travel modes and monthly financial framework',
    priorities: 'Your priorities', prioritiesSub: 'Recommendation weighting from 0 to 100',
    patterns: 'Weekly patterns and notes', patternsSub: 'Free text from your onboarding',
    subscriptions: 'Mobility subscriptions', subscriptionsSub: 'Overview of active and previous subscriptions. They cannot be changed here.',
    firstName: 'First name', lastName: 'Last name', email: 'Email', birthDate: 'Date of birth',
    gender: 'Gender', city: 'Home city', postal: 'Postal code', country: 'Country',
    license: 'Driving licence', carAccess: 'Car access', bikeAccess: 'Bike access',
    yes: 'Yes', no: 'No', unknown: 'Not specified', none: 'No access', own: 'Own',
    shared: 'Shared', occasional: 'Occasional', preferred: 'Preferred', avoided: 'Avoided',
    money: 'Cost', emission: 'CO₂', flexibility: 'Flexibility / time',
    budget: 'Monthly mobility budget', weekday: 'Typical weekday', weekend: 'Typical weekend',
    travelStatement: 'Mobility notes', activityStatement: 'Activities and other notes',
    active: 'Active',
    inactiveHistory: 'Inactive subscriptions', inactiveHistorySub: 'These subscriptions are no longer active and remain available as history.',
    inactive: 'Inactive', noSubs: 'No active subscriptions selected.',
    changedAt: 'Status changed', unmapped: 'Unmapped subscription',
    accounts: 'Mobility accounts', accountsSub: 'Manage the simulated provider connections from your onboarding.',
    accountsDemo: 'Sign-in remains a demo. Connection status changes are saved with your profile.',
    connected: 'Connected', notConnected: 'Not connected', connect: 'Connect', disconnect: 'Disconnect',
    calendarTitle: 'Connect a calendar?',
    calendarText: 'Would you like to connect your calendar so upcoming trips and appointments can be considered in your recommendations?',
    calendarDemo: 'Demo connection – no real calendar connection is established.',
  }

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    setError('')
    setLoadFailed(false)
    setCalendarSync(null)
    getProfile(userId)
      .then((data) => {
        if (cancelled) return
        const u = data.user || {}
        const o = data.onboarding || {}
        setForm({
          user: {
            first_name: u.first_name || '', last_name: u.last_name || '', email: u.email || '',
            gender: u.gender || 'not_specified', date_of_birth: String(u.date_of_birth || '').slice(0, 10),
            home_city: u.home_city || '', home_postal_code: u.home_postal_code || '',
            home_country_code: u.home_country_code || 'DE',
          },
          onboarding: {
            has_driving_license: o.has_driving_license ?? null,
            car_access: o.car_access || null, bike_access: o.bike_access || [],
            preferred_transport_modes: o.preferred_transport_modes || [],
            avoided_transport_modes: o.avoided_transport_modes || [],
            score_money: o.score_money ?? 50, score_emission: o.score_emission ?? 50,
            score_flexibility: o.score_flexibility ?? 50,
            work_arrangement: o.work_arrangement || '', work_city: o.work_city || '',
            work_postal_code: o.work_postal_code || '', remote_work_share: o.remote_work_share ?? null,
            mobility_budget_monthly_eur: o.mobility_budget_monthly_eur ?? '',
            household_size: o.household_size ?? '', income_band: o.income_band || '',
            typical_weekday_pattern: o.typical_weekday_pattern || '',
            typical_weekend_pattern: o.typical_weekend_pattern || '',
            travel_statement: o.travel_statement === 'n/a' ? '' : (o.travel_statement || ''),
            activity_statement: o.activity_statement === 'n/a' ? '' : (o.activity_statement || ''),
            connected_mobility_accounts: o.connected_mobility_accounts || [],
          },
        })
        setHistory(data.subscriptions || [])
      })
      .catch(() => {
        if (cancelled) return
        setLoadFailed(true)
        setError(t.loadError)
      })
      .finally(() => { if (!cancelled) setLoading(false) })
    return () => { cancelled = true }
  }, [userId])

  const setUser = (key, value) => setForm((prev) => ({ ...prev, user: { ...prev.user, [key]: value } }))
  const setOnboarding = (key, value) => setForm((prev) => ({ ...prev, onboarding: { ...prev.onboarding, [key]: value } }))

  const toggleArray = (key, value, exclusiveKey = null) => {
    setForm((prev) => {
      const current = prev.onboarding[key] || []
      const selected = current.includes(value)
      const onboarding = { ...prev.onboarding, [key]: selected ? current.filter((x) => x !== value) : [...current, value] }
      if (!selected && exclusiveKey) {
        onboarding[exclusiveKey] = (onboarding[exclusiveKey] || []).filter((x) => x !== value)
      }
      return { ...prev, onboarding }
    })
  }

  const activeSubscriptions = history.filter((item) => item.subscription_status === 'active')
  const inactiveHistory = history.filter((item) => item.subscription_status !== 'active')

  const toggleMobilityAccount = (accountId) => {
    setForm((prev) => {
      const connected = prev.onboarding.connected_mobility_accounts || []
      const next = connected.includes(accountId)
        ? connected.filter((id) => id !== accountId)
        : [...connected, accountId]
      return {
        ...prev,
        onboarding: { ...prev.onboarding, connected_mobility_accounts: next },
      }
    })
  }

  const handleSave = async (event) => {
    event.preventDefault()
    setSaving(true)
    setSaved(false)
    setError('')
    const payload = {
      user: {
        ...form.user,
        date_of_birth: form.user.date_of_birth || null,
        home_city: form.user.home_city.trim() || null,
        home_postal_code: form.user.home_postal_code.trim() || null,
      },
      onboarding: {
        ...form.onboarding,
        work_arrangement: form.onboarding.work_arrangement || null,
        work_city: form.onboarding.work_city || null,
        work_postal_code: form.onboarding.work_postal_code || null,
        remote_work_share: nullableNumber(form.onboarding.remote_work_share),
        mobility_budget_monthly_eur: nullableNumber(form.onboarding.mobility_budget_monthly_eur),
        household_size: nullableNumber(form.onboarding.household_size),
        income_band: form.onboarding.income_band || null,
        car_access: form.onboarding.car_access || null,
      },
    }
    try {
      const result = await updateProfile(userId, payload)
      if (!result.ok) {
        setError(result.error)
        return
      }

      setSaved(true)
      onSaved(result.data.user)
    } catch {
      setError(t.saveError)
    } finally {
      setSaving(false)
    }
  }

  const inputStyle = { backgroundColor: colors.inputBg, borderColor: colors.border, color: colors.text }
  const cardStyle = { backgroundColor: colors.card, borderColor: colors.border }

  return (
    <div className="profile-page" style={{ backgroundColor: colors.bg, color: colors.text }}>
      <style>{`
        .profile-page { min-height: 100vh; font-family: system-ui, -apple-system, sans-serif; }
        .profile-header { padding: 1.25rem 1.5rem; border-bottom: 1px solid; position: sticky; top: 0; backdrop-filter: blur(12px); z-index: 10; }
        .profile-form { display: grid; gap: 1.25rem; min-width: 0; }
        .profile-title h1 { font-size: 1.7rem; font-weight: 800; letter-spacing: -0.025em; margin-bottom: .25rem; }
        .profile-title p { font-size: .9rem; line-height: 1.45; }
        .profile-section { border: 1px solid; border-radius: 24px; padding: 1.5rem; }
        .profile-section__head { display: flex; gap: .8rem; align-items: flex-start; margin-bottom: 1.25rem; }
        .profile-section__head h2 { font-size: 1.05rem; margin-bottom: .2rem; }
        .profile-section__head p { font-size: .8rem; line-height: 1.4; }
        .profile-section__icon { width: 36px; height: 36px; border-radius: 11px; display: grid; place-items: center; flex-shrink: 0; }
        .profile-grid { display: grid; grid-template-columns: 1fr; gap: 1rem; }
        .profile-grid--three { grid-template-columns: 1fr; }
        .profile-grid--stacked { grid-template-columns: minmax(0, 1fr) !important; gap: 1.1rem; }
        .profile-patterns textarea { min-height: 112px; }
        .profile-field { display: flex; flex-direction: column; gap: .4rem; min-width: 0; }
        .profile-field__label { font-size: .72rem; font-weight: 700; letter-spacing: .045em; text-transform: uppercase; }
        .profile-field__hint { font-size: .7rem; opacity: .72; }
        .profile-input { width: 100%; min-height: 44px; border: 1px solid; border-radius: 11px; padding: .7rem .8rem; outline: none; transition: border-color .15s, box-shadow .15s; }
        .profile-input:focus { border-color: #00b8ca !important; box-shadow: 0 0 0 3px rgba(0,184,202,.14); }
        textarea.profile-input { min-height: 88px; resize: vertical; line-height: 1.45; }
        .profile-chips { display: flex; flex-wrap: wrap; gap: .55rem; }
        .profile-chip { padding: .55rem .75rem; border: 1px solid; border-radius: 11px; font-size: .8rem; font-weight: 600; transition: transform .15s, border-color .15s; }
        .profile-chip:not(:disabled):hover { transform: translateY(-1px); }
        .profile-preferences-budget { border: 1px solid; border-radius: 14px; padding: .9rem; margin-bottom: 1.15rem; max-width: 28rem; }
        .profile-budget-input { position: relative; }
        .profile-budget-input input { padding-right: 2.4rem; }
        .profile-budget-input span { position: absolute; right: .85rem; top: 50%; transform: translateY(-50%); font-size: .85rem; font-weight: 750; pointer-events: none; }
        .profile-priority { display: grid; gap: .55rem; }
        .profile-priority__top { display: flex; justify-content: space-between; align-items: center; font-size: .83rem; font-weight: 650; }
        .profile-priority output { font-size: .78rem; font-weight: 800; min-width: 36px; text-align: right; }
        .profile-priority input { accent-color: #7c3aed; width: 100%; }
        .profile-sub-list { display: grid; gap: .65rem; }
        .profile-sub { border: 1px solid; border-radius: 13px; padding: .8rem .9rem; display: flex; align-items: center; justify-content: space-between; gap: 1rem; }
        .profile-sub__name { font-size: .86rem; font-weight: 700; }
        .profile-sub__meta { font-size: .72rem; margin-top: .15rem; }
        .profile-sub-history { border-top: 1px solid; margin-top: 1.25rem; padding-top: 1.15rem; }
        .profile-sub-history__head { display: flex; align-items: flex-start; justify-content: space-between; gap: 1rem; margin-bottom: .75rem; }
        .profile-sub-history__title { font-size: .86rem; font-weight: 800; }
        .profile-sub-history__subtitle { font-size: .73rem; line-height: 1.4; margin-top: .18rem; }
        .profile-sub--inactive { border-style: dashed; }
        .profile-sub__status { border: 1px solid; border-radius: 999px; padding: .3rem .58rem; font-size: .7rem; font-weight: 800; flex-shrink: 0; }
        .profile-account-note { border: 1px solid; border-radius: 12px; padding: .75rem .85rem; font-size: .76rem; line-height: 1.45; margin-bottom: .9rem; }
        .profile-account-grid { display: grid; grid-template-columns: minmax(0, 1fr); gap: .65rem; }
        .profile-account { border: 1px solid; border-radius: 14px; padding: .75rem; display: flex; align-items: center; justify-content: space-between; gap: .75rem; min-width: 0; }
        .profile-account__identity { display: flex; align-items: center; gap: .65rem; min-width: 0; }
        .profile-account__initial { width: 34px; height: 34px; border-radius: 10px; display: grid; place-items: center; flex-shrink: 0; font-size: .82rem; font-weight: 850; }
        .profile-account__name { font-size: .8rem; font-weight: 750; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
        .profile-account__status { font-size: .68rem; margin-top: .12rem; }
        .profile-account__button { border: 1px solid; border-radius: 9px; padding: .5rem .65rem; font-size: .72rem; font-weight: 750; cursor: pointer; flex-shrink: 0; }
        .profile-calendar { border: 1px solid; border-radius: 16px; padding: 1rem; margin-top: 1.15rem; }
        .profile-calendar__head { display: flex; align-items: flex-start; gap: .7rem; }
        .profile-calendar__icon { width: 36px; height: 36px; border-radius: 10px; display: grid; place-items: center; flex-shrink: 0; }
        .profile-calendar__title { font-size: .9rem; font-weight: 800; }
        .profile-calendar__text { font-size: .76rem; line-height: 1.45; margin-top: .2rem; }
        .profile-calendar__actions { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: .6rem; margin-top: .9rem; }
        .profile-calendar__button { border: 1px solid; border-radius: 10px; padding: .65rem; font-size: .8rem; font-weight: 750; cursor: pointer; transition: border-color .15s, background-color .15s; }
        .profile-calendar__demo { display: block; font-size: .68rem; line-height: 1.4; margin-top: .65rem; }
        .profile-actions { display: flex; justify-content: flex-end; align-items: center; gap: .8rem; padding-bottom: 2rem; }
        .profile-save { border-radius: 13px; padding: .8rem 1.2rem; font-weight: 750; display: inline-flex; align-items: center; gap: .5rem; }
        @container page-main (min-width: 600px) {
          .profile-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
          .profile-grid--three { grid-template-columns: repeat(3, minmax(0, 1fr)); }
          .profile-account-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
        }
        @media (max-width: 520px) {
          .profile-sub { align-items: flex-start; }
          .profile-account { align-items: flex-start; }
        }
      `}</style>

      <header className="profile-header" style={{ borderColor: colors.border, backgroundColor: isDark ? 'rgba(0,0,0,.82)' : 'rgba(255,255,255,.88)' }}>
        <button type="button" onClick={onBack} style={{ display: 'inline-flex', alignItems: 'center', gap: '.4rem', backgroundColor: colors.card, border: `1px solid ${colors.border}`, borderRadius: '12px', color: colors.textMuted, padding: '.55rem .95rem', fontSize: '.88rem', fontWeight: 600 }}>
          <ChevronLeft size={16} /> {t.back}
        </button>
      </header>

      <div className="page-split">
        <main className="profile-form page-split__main">
          <div className="profile-title">
            <h1 style={{ color: colors.text }}>{t.title}</h1>
            <p style={{ color: colors.textMuted }}>{t.subtitle}</p>
          </div>

          {loading ? (
            <div className="profile-section" style={cardStyle}>{t.loading}</div>
          ) : loadFailed ? (
            <div className="profile-section" style={{ ...cardStyle, color: colors.errorText }}><AlertCircle size={18} /> {error}</div>
          ) : (
            <form onSubmit={handleSave} className="profile-form">
              <Section icon={<UserRound size={18} />} title={t.personal} subtitle={t.personalSub} colors={colors}>
                <div className="profile-grid profile-grid--three">
                  <Field label={t.firstName}><input required className="profile-input" style={inputStyle} value={form.user.first_name} onChange={(e) => setUser('first_name', e.target.value)} /></Field>
                  <Field label={t.lastName}><input required className="profile-input" style={inputStyle} value={form.user.last_name} onChange={(e) => setUser('last_name', e.target.value)} /></Field>
                  <Field label={t.email}><input required type="email" className="profile-input" style={inputStyle} value={form.user.email} onChange={(e) => setUser('email', e.target.value)} /></Field>
                  <Field label={t.birthDate}><input type="date" className="profile-input" style={inputStyle} value={form.user.date_of_birth} onChange={(e) => setUser('date_of_birth', e.target.value)} /></Field>
                  <Field label={t.gender}>
                    <select className="profile-input" style={inputStyle} value={form.user.gender} onChange={(e) => setUser('gender', e.target.value)}>
                      <option value="not_specified">{t.unknown}</option><option value="female">Weiblich / Female</option><option value="male">Männlich / Male</option><option value="diverse">Divers</option>
                    </select>
                  </Field>
                </div>
              </Section>

              <Section icon={<MapPin size={18} />} title={t.address} subtitle={t.addressSub} colors={colors}>
                <div className="profile-grid profile-grid--three">
                  <Field label={t.city}><input className="profile-input" style={inputStyle} value={form.user.home_city} onChange={(e) => setUser('home_city', e.target.value)} /></Field>
                  <Field label={t.postal}><input className="profile-input" style={inputStyle} value={form.user.home_postal_code} onChange={(e) => setUser('home_postal_code', e.target.value)} /></Field>
                  <Field label={t.country}><select className="profile-input" style={inputStyle} value={form.user.home_country_code} onChange={(e) => setUser('home_country_code', e.target.value)}>{COUNTRIES.map(([code, name]) => <option value={code} key={code}>{name}</option>)}</select></Field>
                </div>
              </Section>

              <Section icon={<Car size={18} />} title={t.access} subtitle={t.accessSub} colors={colors}>
                <div className="profile-grid">
                  <Field label={t.license}>
                    <select className="profile-input" style={inputStyle} value={form.onboarding.has_driving_license == null ? '' : String(form.onboarding.has_driving_license)} onChange={(e) => {
                      const value = e.target.value === '' ? null : e.target.value === 'true'
                      setForm((prev) => ({
                        ...prev,
                        onboarding: {
                          ...prev.onboarding,
                          has_driving_license: value,
                          car_access: value === false ? 'none' : prev.onboarding.car_access,
                        },
                      }))
                    }}>
                      <option value="">{t.unknown}</option><option value="true">{t.yes}</option><option value="false">{t.no}</option>
                    </select>
                  </Field>
                  <Field label={t.carAccess}>
                    <select className="profile-input" style={inputStyle} disabled={form.onboarding.has_driving_license === false} value={form.onboarding.has_driving_license === false ? 'none' : (form.onboarding.car_access || '')} onChange={(e) => setOnboarding('car_access', e.target.value || null)}>
                      <option value="">{t.unknown}</option><option value="none">{t.none}</option><option value="own">{t.own}</option><option value="shared">{t.shared}</option><option value="occasional">{t.occasional}</option>
                    </select>
                  </Field>
                </div>
                <div style={{ marginTop: '1rem' }}><span className="profile-field__label" style={{ display: 'block', marginBottom: '.55rem' }}>{t.bikeAccess}</span><div className="profile-chips">{['own', 'shared', 'none'].map((item) => <ToggleChip key={item} colors={colors} selected={form.onboarding.bike_access.includes(item)} onClick={() => setOnboarding('bike_access', item === 'none' ? (form.onboarding.bike_access.includes('none') ? [] : ['none']) : [...form.onboarding.bike_access.filter((x) => x !== 'none' && x !== item), ...(form.onboarding.bike_access.includes(item) ? [] : [item])])}>{item === 'own' ? `🚲 ${t.own}` : item === 'shared' ? `🚴 ${t.shared}` : t.none}</ToggleChip>)}</div></div>
              </Section>

              <Section icon={<SlidersHorizontal size={18} />} title={t.preferences} subtitle={t.preferencesSub} colors={colors}>
                <div className="profile-preferences-budget" style={{ backgroundColor: colors.inputBg, borderColor: colors.border }}>
                  <Field label={t.budget}>
                    <div className="profile-budget-input">
                      <input min="0" step="1" type="number" className="profile-input" style={inputStyle} value={form.onboarding.mobility_budget_monthly_eur} onChange={(e) => setOnboarding('mobility_budget_monthly_eur', e.target.value)} />
                      <span style={{ color: colors.textMuted }}>€</span>
                    </div>
                  </Field>
                </div>
                <span className="profile-field__label" style={{ display: 'block', marginBottom: '.55rem' }}>{t.preferred}</span>
                <div className="profile-chips">{MODES.map((mode) => <ToggleChip key={mode} colors={colors} selected={form.onboarding.preferred_transport_modes.includes(mode)} onClick={() => toggleArray('preferred_transport_modes', mode, 'avoided_transport_modes')}>{modeLabel(mode, isDE ? 'de' : 'en')}</ToggleChip>)}</div>
                <span className="profile-field__label" style={{ display: 'block', margin: '1.15rem 0 .55rem' }}>{t.avoided}</span>
                <div className="profile-chips">{MODES.map((mode) => <ToggleChip key={mode} colors={colors} selected={form.onboarding.avoided_transport_modes.includes(mode)} onClick={() => toggleArray('avoided_transport_modes', mode, 'preferred_transport_modes')}>{modeLabel(mode, isDE ? 'de' : 'en')}</ToggleChip>)}</div>
              </Section>

              <Section icon={<SlidersHorizontal size={18} />} title={t.priorities} subtitle={t.prioritiesSub} colors={colors}>
                <div className="profile-grid profile-grid--three">{[['score_money', t.money], ['score_emission', t.emission], ['score_flexibility', t.flexibility]].map(([key, label]) => <label className="profile-priority" key={key}><span className="profile-priority__top"><span>{label}</span><output style={{ color: colors.accentPurple }}>{form.onboarding[key]}</output></span><input type="range" min="0" max="100" step="10" value={form.onboarding[key]} onChange={(e) => setOnboarding(key, Number(e.target.value))} /></label>)}</div>
              </Section>

              <Section icon={<BriefcaseBusiness size={18} />} title={t.patterns} subtitle={t.patternsSub} colors={colors}>
                <div className="profile-grid profile-grid--stacked profile-patterns">
                  <Field label={t.weekday}><textarea className="profile-input" style={inputStyle} value={form.onboarding.typical_weekday_pattern} onChange={(e) => setOnboarding('typical_weekday_pattern', e.target.value)} /></Field>
                  <Field label={t.weekend}><textarea className="profile-input" style={inputStyle} value={form.onboarding.typical_weekend_pattern} onChange={(e) => setOnboarding('typical_weekend_pattern', e.target.value)} /></Field>
                  <Field label={t.travelStatement}><textarea className="profile-input" style={inputStyle} value={form.onboarding.travel_statement} onChange={(e) => setOnboarding('travel_statement', e.target.value)} /></Field>
                  <Field label={t.activityStatement}><textarea className="profile-input" style={inputStyle} value={form.onboarding.activity_statement} onChange={(e) => setOnboarding('activity_statement', e.target.value)} /></Field>
                </div>
              </Section>

              <Section icon={<CreditCard size={18} />} title={t.subscriptions} subtitle={t.subscriptionsSub} colors={colors}>
                <div className="profile-sub-list">
                  {activeSubscriptions.length === 0 && <p style={{ color: colors.textMuted, fontSize: '.84rem' }}>{t.noSubs}</p>}
                  {activeSubscriptions.map((item) => (
                    <div className="profile-sub" style={cardStyle} key={item.user_subscription_id}>
                      <div>
                        <div className="profile-sub__name">{item.provider_plan_name || t.unmapped}</div>
                        <div className="profile-sub__meta" style={{ color: colors.textMuted }}>
                          {item.provider_name ? `${item.provider_name} · ` : ''}{item.billing_cycle || '—'} · {item.monthly_cost_eur != null ? `${euro(item.monthly_cost_eur, { lang: isDE ? 'de' : 'en' })}/${isDE ? 'Monat' : 'month'}` : item.annual_cost_eur != null ? `${euro(item.annual_cost_eur, { lang: isDE ? 'de' : 'en' })}/${isDE ? 'Jahr' : 'year'}` : '—'}
                        </div>
                      </div>
                      <span className="profile-sub__status" style={{ color: colors.successGreen, backgroundColor: `${colors.successGreen}12`, borderColor: `${colors.successGreen}55` }}>{t.active}</span>
                    </div>
                  ))}
                </div>
                {inactiveHistory.length > 0 && (
                  <div className="profile-sub-history" style={{ borderColor: colors.border }}>
                    <div className="profile-sub-history__head">
                      <div>
                        <div className="profile-sub-history__title" style={{ color: colors.text }}>{t.inactiveHistory} ({inactiveHistory.length})</div>
                        <div className="profile-sub-history__subtitle" style={{ color: colors.textMuted }}>{t.inactiveHistorySub}</div>
                      </div>
                    </div>
                    <div className="profile-sub-list">
                      {inactiveHistory.map((item) => (
                        <div className="profile-sub profile-sub--inactive" style={{ backgroundColor: colors.inputBg, borderColor: colors.border }} key={item.user_subscription_id}>
                          <div>
                            <div className="profile-sub__name" style={{ color: colors.textMuted }}>{item.provider_plan_name || t.unmapped}</div>
                            <div className="profile-sub__meta" style={{ color: colors.textMuted }}>
                              {item.provider_name ? `${item.provider_name} · ` : ''}{t.changedAt}: {item.status_changed_at ? new Date(item.status_changed_at).toLocaleString(isDE ? 'de-DE' : 'en-GB') : '—'}
                            </div>
                          </div>
                          <span className="profile-sub__status" style={{ color: colors.textMuted, backgroundColor: colors.card, borderColor: colors.border }}>{t.inactive}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </Section>

              <Section icon={<Link2 size={18} />} title={t.accounts} subtitle={t.accountsSub} colors={colors}>
                <div className="profile-account-note" style={{ color: colors.textMuted, backgroundColor: colors.inputBg, borderColor: colors.border }}>{t.accountsDemo}</div>
                <div className="profile-account-grid">
                  {MOBILITY_ACCOUNT_OPTIONS.map((account) => {
                    const connected = form.onboarding.connected_mobility_accounts.includes(account.id)
                    const initial = account.label.replace(/[^A-Za-z0-9]/g, '').charAt(0).toUpperCase() || '•'
                    return (
                      <div className="profile-account" style={{ backgroundColor: colors.inputBg, borderColor: connected ? colors.accentCyan : colors.border }} key={account.id}>
                        <div className="profile-account__identity">
                          <span className="profile-account__initial" style={{ color: connected ? colors.onAccent : colors.textMuted, background: connected ? `linear-gradient(135deg, ${colors.accentCyan}, ${colors.accentPurple})` : colors.card }}>{initial}</span>
                          <div style={{ minWidth: 0 }}>
                            <div className="profile-account__name" style={{ color: colors.text }}>{account.label}</div>
                            <div className="profile-account__status" style={{ color: connected ? colors.accentCyan : colors.textMuted }}>{connected ? t.connected : t.notConnected}</div>
                          </div>
                        </div>
                        <button type="button" className="profile-account__button" aria-pressed={connected} onClick={() => toggleMobilityAccount(account.id)} style={{ color: connected ? colors.textMuted : colors.accentPurple, backgroundColor: colors.card, borderColor: connected ? colors.border : colors.accentPurple }}>
                          {connected ? t.disconnect : t.connect}
                        </button>
                      </div>
                    )
                  })}
                </div>
                <div className="profile-calendar" style={{ backgroundColor: colors.inputBg, borderColor: colors.border }}>
                  <div className="profile-calendar__head">
                    <span className="profile-calendar__icon" style={{ color: colors.accentCyan, backgroundColor: colors.cyanFill }}><CalendarDays size={18} /></span>
                    <div>
                      <div className="profile-calendar__title" style={{ color: colors.text }}>{t.calendarTitle}</div>
                      <div className="profile-calendar__text" style={{ color: colors.textMuted }}>{t.calendarText}</div>
                    </div>
                  </div>
                  <div className="profile-calendar__actions">
                    <button type="button" aria-pressed={calendarSync === true} className="profile-calendar__button" onClick={() => setCalendarSync(true)} style={{ color: calendarSync === true ? colors.onAccent : colors.text, backgroundColor: calendarSync === true ? colors.accentCyan : colors.card, borderColor: calendarSync === true ? colors.accentCyan : colors.border }}>{t.yes}</button>
                    <button type="button" aria-pressed={calendarSync === false} className="profile-calendar__button" onClick={() => setCalendarSync(false)} style={{ color: calendarSync === false ? colors.onAccent : colors.text, backgroundColor: calendarSync === false ? colors.accentPurple : colors.card, borderColor: calendarSync === false ? colors.accentPurple : colors.border }}>{t.no}</button>
                  </div>
                  <span className="profile-calendar__demo" style={{ color: colors.textMuted }}>{t.calendarDemo}</span>
                </div>
              </Section>

              {error && <div style={{ backgroundColor: colors.errorBg, color: colors.errorText, border: `1px solid ${colors.errorText}`, borderRadius: 12, padding: '.8rem 1rem', display: 'flex', alignItems: 'center', gap: '.5rem', fontSize: '.84rem' }}><AlertCircle size={16} /> {error}</div>}
              {saved && <div style={{ color: colors.successGreen, display: 'flex', justifyContent: 'flex-end', alignItems: 'center', gap: '.4rem', fontSize: '.82rem', fontWeight: 700 }}><CheckCircle2 size={16} /> {t.saved}</div>}
              <div className="profile-actions"><button type="button" onClick={onBack} style={{ color: colors.textMuted, padding: '.8rem 1rem', fontWeight: 650 }}>{t.back}</button><button type="submit" disabled={saving} className="profile-save" style={{ backgroundColor: colors.accentCyan, color: colors.onAccent, opacity: saving ? .65 : 1 }}><Save size={16} /> {saving ? t.saving : t.save}</button></div>
            </form>
          )}
        </main>
        <aside className="page-split__sidebar" ref={chatSlotRef} />
      </div>
    </div>
  )
}
