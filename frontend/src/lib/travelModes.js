// Shared mode taxonomy for charts: a fixed display order + a validated
// categorical palette (see dataviz skill — colors chosen so adjacent slots in
// this exact order clear the colorblind-safety check; re-run
// scripts/validate_palette.js against these hex values before reordering).
// Anything not in MODE_ORDER folds into the trailing "other" slot rather than
// generating a new hue.

export const MODE_ORDER = [
  'regional_train',
  'public_transport',
  'bike_sharing',
  'long_distance_train',
  'car_sharing',
  'e_scooter',
  'car',
  'walking',
]

const COLORS_LIGHT = ['#2a78d6', '#1baf7a', '#eda100', '#008300', '#4a3aa7', '#e34948', '#e87ba4', '#eb6834']
const COLORS_DARK = ['#3987e5', '#199e70', '#c98500', '#008300', '#9085e9', '#e66767', '#d55181', '#d95926']
const OTHER_LIGHT = '#898781'
const OTHER_DARK = '#898781'

const LABELS = {
  de: {
    regional_train: 'Regionalbahn',
    public_transport: 'ÖPNV',
    bike_sharing: 'Bike-Sharing',
    long_distance_train: 'Fernverkehr',
    car_sharing: 'Carsharing',
    e_scooter: 'E-Scooter',
    car: 'Auto',
    walking: 'Zu Fuß',
    ride_hailing: 'Ride-Hailing',
    taxi: 'Taxi',
    other: 'Sonstiges',
  },
  en: {
    regional_train: 'Regional rail',
    public_transport: 'Public transit',
    bike_sharing: 'Bike-sharing',
    long_distance_train: 'Long-distance rail',
    car_sharing: 'Car-sharing',
    e_scooter: 'E-scooter',
    car: 'Car',
    walking: 'Walking',
    ride_hailing: 'Ride-hailing',
    taxi: 'Taxi',
    other: 'Other',
  },
}

export function modeLabel(mode, lang = 'de') {
  const dict = LABELS[lang] || LABELS.de
  return dict[mode] || dict.other
}

export function modeColor(mode, isDark = false) {
  const idx = MODE_ORDER.indexOf(mode)
  if (idx === -1) return isDark ? OTHER_DARK : OTHER_LIGHT
  return (isDark ? COLORS_DARK : COLORS_LIGHT)[idx]
}

// Orders the modes actually present in a dataset by MODE_ORDER, unknown modes last.
export function sortModes(modes) {
  return [...modes].sort((a, b) => {
    const ia = MODE_ORDER.indexOf(a), ib = MODE_ORDER.indexOf(b)
    return (ia === -1 ? MODE_ORDER.length : ia) - (ib === -1 ? MODE_ORDER.length : ib)
  })
}
