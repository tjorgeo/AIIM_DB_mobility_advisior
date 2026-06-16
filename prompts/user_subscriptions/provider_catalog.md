# Mobility Provider Catalog

Only use providers listed in this catalog.

Do not invent additional providers.

Provider names must be copied exactly from this file.

## Provider Categories

Allowed provider categories:

- `public_transport`
- `bike_sharing`
- `car_sharing`
- `e_scooter`

## Public Transport Providers

Entries are listed as provider_name: provider_plan_name

- DB: Deutschlandticket
- DB: Bahncard 25
- DB: Bahncard 50 Second Class
- DB: Bahncard 50 First Class
- DB: Bahncard 100 Second Class
- DB: Bahncard 100 First Class

## Bike Sharing Providers

- callabike: pay-as-you-go | subscriptions
- nextbike: pay-as-you-go | subscriptions
- swapfiets: pay-as-you-go | subscriptions

## Car Sharing Providers

- miles: pay-as-you-go | subscriptions
- sixt: pay-as-you-go | subscriptions
- teilauto: pay-as-you-go | subscriptions

## E-Scooter Providers

Use this section for e-scooter sharing accounts, passes, and subscriptions.

- bolt: pay-as-you-go | subscriptions
- dott: pay-as-you-go | subscriptions
- lime: pay-as-you-go | subscriptions
- voi: pay-as-you-go | subscriptions

## Usage Rules

- `provider_category` must match the generated `subscription_category`.
- `provider_name` must match one of the provider names in the matching category.
- `provider_plan_name` may use one of the example plan names or `null`.
- If a city is not listed for a provider, do not assign that provider to a user from that city.
- Prefer public transport providers that match the user's home city or region.
- Do not assign multiple providers from the same category unless it is plausible for the user.
