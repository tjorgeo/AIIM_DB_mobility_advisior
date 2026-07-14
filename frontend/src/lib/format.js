// Lightweight formatting helpers shared across the consumer UI.

const LOCALE = { en: 'en-IE', de: 'de-DE' }

export function euro(value, { decimals, lang = 'en' } = {}) {
  const n = Number(value)
  if (!Number.isFinite(n)) return '€0'
  const frac = decimals ?? (Number.isInteger(n) ? 0 : 2)
  return new Intl.NumberFormat(LOCALE[lang] || LOCALE.en, {
    style: 'currency',
    currency: 'EUR',
    minimumFractionDigits: frac,
    maximumFractionDigits: frac,
  }).format(n)
}

export function number(value, lang = 'en') {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0'
  return new Intl.NumberFormat(LOCALE[lang] || LOCALE.en).format(Math.round(n))
}

// CO2 mass: tonnes once we cross 1000 kg, otherwise kilograms.
export function co2(value, lang = 'en') {
  const n = Number(value)
  if (!Number.isFinite(n)) return '0 kg'
  if (n >= 1000) {
    const t = (n / 1000).toLocaleString(LOCALE[lang] || LOCALE.en, {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2,
    })
    return `${t} t`
  }
  return `${number(n, lang)} kg`
}

export function greeting(name, lang = 'en') {
  const h = new Date().getHours()
  const part = h < 12 ? 'morning' : h < 18 ? 'afternoon' : 'evening'
  const words = {
    en: { morning: 'Good morning', afternoon: 'Good afternoon', evening: 'Good evening' },
    de: { morning: 'Guten Morgen', afternoon: 'Guten Tag', evening: 'Guten Abend' },
  }
  const g = (words[lang] || words.en)[part]
  return name ? `${g}, ${name}` : g
}

// Picks a representative emoji for a subscription. Name-based rules come first
// because `subscription_category` alone can't tell a BahnCard (long-distance
// train) apart from a Deutschlandticket (local/regional transit) — both are
// "public_transport" in the DB (see database/init/01_create_table.sql).
export function subscriptionEmoji({ provider_name = '', provider_plan_name = '', subscription_category = '' } = {}) {
  const name = `${provider_name} ${provider_plan_name}`.toLowerCase()
  if (name.includes('bahncard')) return '🚆'
  if (name.includes('deutschlandticket') || name.includes('jobticket')) return '🚊'
  switch (subscription_category) {
    case 'bike_sharing': return '🚲'
    case 'car_sharing': return '🚗'
    case 'e_scooter': return '🛴'
    case 'public_transport': return '🚌'
    default: return '🎫'
  }
}

// "bahncard_25_2nd" -> "Bahncard 25 2nd"
export function titleizeService(service) {
  return String(service || '')
    .replace(/_/g, ' ')
    .replace(/\b\w/g, (c) => c.toUpperCase())
}
