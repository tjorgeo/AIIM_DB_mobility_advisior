// Frontend-only login profile for the seeded backend dummy user.
// `id` is the backend user id (users.user_id) consumed by POST /api/analyze and
// must match the database seed (database/init/99_seed_dummy_user.sql).
// This is a demo login for the sandbox; the shared password is surfaced subtly
// on the sign-in screen.

export const DEMO_PASSWORD = 'mobility'

export const PERSONAS = [
  {
    id: 'dummy-user-001',
    name: 'Test User',
    firstName: 'Test',
    email: 'test.user@example.com',
    dbCustomerId: 'dummy-user-001',
    tagline: 'Software Engineer · Berlin',
    blurb: 'Daily U-Bahn commuter in Berlin with a Deutschlandticket.',
    initials: 'TU',
  },
]

export function findPersonaByEmail(email) {
  const target = String(email || '').trim().toLowerCase()
  return PERSONAS.find((p) => p.email.toLowerCase() === target) || null
}

export function findPersonaById(id) {
  return PERSONAS.find((p) => p.id === id) || null
}
