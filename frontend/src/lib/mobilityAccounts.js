export const MOBILITY_ACCOUNT_OPTIONS = [
  { id: 'deutschlandticket', label: 'Deutschlandticket' },
  { id: 'job_ticket', label: 'Job-Ticket / Firmenticket' },
  { id: 'bahncard25', label: 'BahnCard 25' },
  { id: 'bahncard50', label: 'BahnCard 50' },
  { id: 'bahncard100', label: 'BahnCard 100' },
  { id: 'miles_pass', label: 'MILES / ShareNow' },
  { id: 'sixt_share', label: 'SIXT share' },
  { id: 'teilauto', label: 'teilAuto' },
  { id: 'carsharing_regular', label: 'Carsharing-Konto' },
  { id: 'scooter_flat', label: 'TIER / Voi' },
  { id: 'dott', label: 'Dott' },
  { id: 'swapfiets', label: 'Swapfiets' },
  { id: 'nextbike', label: 'nextbike' },
]

const LABELS = new Map(MOBILITY_ACCOUNT_OPTIONS.map((account) => [account.id, account.label]))

export function mobilityAccountLabel(accountId) {
  return LABELS.get(accountId) || accountId
}
