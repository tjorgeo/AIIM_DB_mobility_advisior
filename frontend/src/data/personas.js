// Frontend-only login profiles for the five seeded backend personas.
// `id` is the backend persona id consumed by POST /api/analyze.
// These accounts are demo logins for the sandbox; the shared password is
// surfaced subtly on the sign-in screen.

export const DEMO_PASSWORD = 'mobility'

export const PERSONAS = [
  {
    id: 'persona_max_commuter',
    name: 'Max Commuter',
    firstName: 'Max',
    email: 'max.commuter@dbmove.de',
    dbCustomerId: 'DB-992-MAX',
    tagline: 'Daily Commuter · Munich',
    blurb: 'Munich ⇄ Augsburg, every workday on regional trains.',
    initials: 'MC',
  },
  {
    id: 'persona_clara_consultant',
    name: 'Clara Eco-Consultant',
    firstName: 'Clara',
    email: 'clara.consultant@dbmove.de',
    dbCustomerId: 'DB-334-CLARA',
    tagline: 'Eco Consultant · Berlin',
    blurb: 'Long-distance business trips with a low-carbon priority.',
    initials: 'CE',
  },
  {
    id: 'persona_anna_occasional',
    name: 'Anna Occasional',
    firstName: 'Anna',
    email: 'anna.occasional@dbmove.de',
    dbCustomerId: 'DB-112-ANNA',
    tagline: 'Occasional Traveler · Hamburg',
    blurb: 'A handful of trips a year — but paying for full subscriptions.',
    initials: 'AO',
  },
  {
    id: 'persona_sophie_explorer',
    name: 'Sophie Weekend Explorer',
    firstName: 'Sophie',
    email: 'sophie.explorer@dbmove.de',
    dbCustomerId: 'DB-748-SOPHIE',
    tagline: 'Weekend Explorer · Bavaria',
    blurb: 'Regional weekend adventures across Bavaria and Austria.',
    initials: 'SE',
  },
  {
    id: 'persona_lukas_executive',
    name: 'Lukas Corporate Lead',
    firstName: 'Lukas',
    email: 'lukas.lead@dbmove.de',
    dbCustomerId: 'DB-881-LUKAS',
    tagline: 'Corporate Lead · Frankfurt',
    blurb: 'High-frequency 1st-class travel; convenience comes first.',
    initials: 'LC',
  },
]

export function findPersonaByEmail(email) {
  const target = String(email || '').trim().toLowerCase()
  return PERSONAS.find((p) => p.email.toLowerCase() === target) || null
}

export function findPersonaById(id) {
  return PERSONAS.find((p) => p.id === id) || null
}
