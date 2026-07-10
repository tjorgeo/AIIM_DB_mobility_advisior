# Mock Data Personas

This is the seed dataset loaded by `database/init/02_insert_data.sql`:
`user_profiles_v4.csv`, `user_onboardings_v4.csv`, `user_subscriptions_v5.csv`,
`user_trips_v5.csv`, `trip_legs_v8.csv`, `user_calendars_v2.csv`
(`subscription_catalogs_v1.csv` is unchanged — it's the product catalog, not
persona data).

4 personas, each constructed to exercise one distinct subscription-decision
path through the analyst/optimizer logic in `backend/src/agents/analyst_spec.md`,
with a different starting subscription situation (0, 1, 2, and 3 held
subscriptions respectively). Trip data spans a fixed 12-month window,
**2025-07-01 → 2026-06-30** — the full window `analyze_portfolio` uses (it caps
to the last 365 days of data itself), not "today minus N days," so the dataset
stays valid as time passes.

Every leg's `trip_id` belongs to a trip owned by the same `user_id` (no
cross-user contamination), and `user_subscription_id` is only set on legs
actually covered by that persona's held subscription. Regenerate with
`python database/seed/gen_personas.py` (deterministic — same `random.seed`,
same UUIDv5 namespace, always produces byte-identical output).

Calendars are deliberately split: Julia and Simone only have local,
routine-life events with no bearing on their subscription mix; Jonas and Elif
each have a life event (an apartment move; a home-renovation project) plus
recurring trips in their calendar that explain — and, looking forward, keep
driving — the pattern seen in their trip history.

---

## 1. Julia Berger — BahnCard 25 should become BahnCard 50, Deutschlandticket already pays off

`ce92d8e0-065e-589b-a60e-c692ef2d2ff9` · Leipzig · 35 · Key Account Manager, hybrid

**Story:** Two subscriptions, two different verdicts. Her Deutschlandticket
covers a daily regional-train commute and is unambiguously worth it. Her
BahnCard 25 covers frequent long-distance client trips — but she travels
enough that the 50%-discount card would save noticeably more than the 25%
card costs to upgrade to.

**Subscriptions:**
- Deutschlandticket (`a1111111-...`), held since 2023-06-01, primary mobility
  option, daily use.
- BahnCard 25, 2. Klasse (`a3333333-...`), held since 2022-01-15, secondary,
  several-times-per-week use.

**Trip pattern:** ~5 DT-covered regional-train commute round-trips/week within
Leipzig; ~1.4 long-distance client-visit round-trips/week (Berlin, Munich,
Frankfurt, Hamburg, Cologne) on the BahnCard 25; occasional DT-covered weekend
leisure trips; reduced ~65% during summer holidays (Jul/Aug) and the Dec
20–Jan 5 lull.

**Onboarding:** `score_emission=60, score_money=65, score_flexibility=60` —
cost-conscious about the frequent business travel, wants to know if the
BahnCard is still the right one.

**Verified analyst output:** Deutschlandticket `cost=€756/yr`,
`realized_savings=€1,788.79/yr`, **`net_savings=+€1,032.79`** — not flagged,
`public_transport` category recommendation `keep_current`. BahnCard 25
`cost=€62.90/yr`, `realized_savings=€1,801.06/yr`, `net_savings=+€1,738.16` —
also not flagged in isolation, but the `long_distance_rail` category
recommendation is **`switch_to_alternative`**: BahnCard 50 would cost an
estimated `€3,846.09/yr` all-in vs. her actual `€5,466.01/yr` (no-subscription
pay-as-you-go would be `€7,204.17/yr`). `detected_seasonality`: peak in March
(1.3× monthly average), lowest in August (0.3×).

---

## 2. Jonas Keller — no subscription, should pick up a Deutschlandticket

`e1eb9483-d268-57cf-9b5f-0ef5e1a7fed2` · Hamburg · 28 · Junior Data Analyst, in-office

**Story:** Never bothered with a pass because he used to live close to the
office — single-ticket public transport was cheap enough. Then he moved
farther out partway through the window, which lengthened and increased the
frequency of his commute; the single-ticket spend that follows now clearly
justifies a Deutschlandticket.

**Subscriptions:** none.

**Trip pattern:** short in-city bus/S-Bahn commute (`public_transport`,
~80% of weekdays) through 2026-01-09; from the 2026-01-10 move onward, a
longer `regional_train` commute (~90% of weekdays) from the new, farther-out
address — both pay-as-you-go, single tickets; occasional weekend
`public_transport` errands; biweekly `regional_train` weekend visit to his
parents in Lüneburg.

**Onboarding:** `score_emission=50, score_money=70, score_flexibility=45` —
cost-conscious, framed around the move making single tickets add up fast.

**Calendar (life-event/trip-affecting):** an apartment viewing
(2025-12-20) and the move itself (2026-01-10, "Umzug - neue Wohnung in
Norderstedt"), plus the recurring biweekly Lüneburg family visit and a
full-day in-office event — all reinforcing that his (now longer) commute
pattern is ongoing, not a one-off.

**Verified analyst output:** no `subscription_coverage` entries.
`public_transport` category: `no_subscription_annual_cost_eur=€2,481.78`,
recommendation **`consider_subscribing`**, cheapest alternative
Deutschlandticket at `€756.00/yr`. `detected_seasonality`: peak in June (1.3×
monthly average), lowest in July (0.3×).

---

## 3. Simone Wagner — three subscriptions, at least one (really two) should be cancelled

`725be174-ba53-516d-8beb-a4056cbac517` · Dresden · 46 · Project Manager, hybrid

**Story:** Kept two subscriptions from a busier period of her job that never
got cleaned up. Her Deutschlandticket still earns its keep on the regular
hybrid commute — but the BahnCard 25 (from when she used to see a
since-ended client) and the Call a Bike Member Plus membership (from a
fitness kick two years ago) are both barely touched anymore.

**Subscriptions:**
- Deutschlandticket (`a1111111-...`), held since 2021-09-01, primary,
  several-times-per-week use.
- BahnCard 25, 2. Klasse (`a3333333-...`), held since 2022-04-01, secondary,
  rarely used.
- Call a Bike Member Plus (`m1111111-...`), held since 2023-05-01, secondary,
  rarely used.

**Trip pattern:** DT-covered regional-train commute ~3 days/week (hybrid);
occasional DT-covered weekend errands; only 2 long-distance round-trips/year
on the BahnCard 25 (a conference in Leipzig); ~15 short (<30 min) Call a Bike
rides/year, each free under the membership's 30-free-minutes allowance.

**Onboarding:** `score_emission=55, score_money=45, score_flexibility=55` —
low money-priority is the narrative reason she hasn't noticed/cancelled the
two unused subscriptions.

**Verified analyst output:** Deutschlandticket `net=+€348.60` — not flagged,
`public_transport` recommendation `keep_current`. BahnCard 25
`cost=€62.90/yr`, `realized_savings=€49.38/yr`, **`net=-€13.52`** — flagged
`overpaid_subscription`; `long_distance_rail` recommendation
`cancel_current_go_pay_as_you_go` (pay-as-you-go `€197.49/yr` beats both her
current `€211.01/yr` and a BahnCard 50 upgrade at `€342.75/yr`). Call a Bike
Member Plus `cost=€96.00/yr`, `realized_savings=€44.80/yr`,
**`net=-€51.20`** — also flagged `overpaid_subscription`;
`bike_sharing` recommendation `cancel_current_go_pay_as_you_go`.
`detected_seasonality`: peak in March (1.5×), lowest in August (0.1×).

---

## 4. Elif Yildiz — car-free, car-sharing-centric multi-modal freelancer

`932d3626-708a-596b-a1fc-99c2fa1ce9b3` · Bremen · 33 · Freelance UX Designer, remote

**Story:** Gave up owning a car years ago. A heavily-used car-sharing
membership covers client visits and supply runs; pay-as-you-go e-scooter and
bike-share cover everything shorter. Currently mid-way through a home-studio
renovation, which is driving a visible burst of extra car-sharing hauling
trips in both the calendar and the trip history — a forward-looking signal,
not just a historical one.

**Subscriptions:**
- teilAuto Vielfahrertarif (`x1111111-...`), held since 2024-03-01, primary
  mobility option, several-times-per-week use.

No bike-sharing, e-scooter, or public-transport subscription — those stay
pay-as-you-go by design.

**Trip pattern:** frequent teilAuto-covered car-sharing trips for client
visits/supply runs (several times/week, +35pp during the Apr–May 2026
renovation window for hardware-store runs); pay-as-you-go e-scooter for
quick last-mile hops; occasional pay-as-you-go bike-share leisure rides;
monthly pay-as-you-go regional-train visit to her parents in Oldenburg.

**Onboarding:** `score_emission=45, score_money=60, score_flexibility=80` —
flexibility weighted highest, reflecting a deliberately car-free, contract-
light lifestyle.

**Calendar (life-event/trip-affecting):** a contractor walkthrough
(2026-03-25) and a two-month "Studio renovation project" block
(2026-04-01 → 2026-05-31) that matches the extra car-sharing trips in the
history, plus a recurring monthly Oldenburg family visit and a one-off client
design-fair booth.

**Verified analyst output:** teilAuto Vielfahrertarif `cost=€360.00/yr`,
`realized_savings=€894.01/yr`, **`net_savings=+€534.01`** — not flagged,
`car_sharing` recommendation `keep_current` (pay-as-you-go would cost
`€1,424.12/yr` vs. her actual `€890.11/yr`). `bike_sharing` (`€166.48/yr`),
`e_scooter` (`€414.08/yr`), and `public_transport` (`€162.07/yr`, cheapest
alternative Deutschlandticket at `€756.00/yr` — not worth it at this volume)
all correctly resolve to `no_subscription_needed`. `detected_seasonality`:
peak in May (1.8×), lowest in August (0.2×).

---

## Cost / CO₂ model used by the generator

`database/seed/gen_personas.py` prices each leg with `estimated_cost_eur`
(amount actually paid) and `reference_cost_eur` (pay-as-you-go price for the
same trip, ignoring any subscription), per the attribution model in
`analyst_spec.md`.

| Mode | Reference (PAYG) price | Subscription-covered price |
|---|---|---|
| `public_transport` | €2.90 flat | €0 (Deutschlandticket) |
| `regional_train` | €2.50 + €0.20/km | €0 (Deutschlandticket) or 50% (BahnCard 50) |
| `long_distance_train` | max(€19.90, €0.16/km) | 25% (BahnCard 25) / 50% (BahnCard 50) |
| `bike_sharing` | €1.00 + €0.12/min (Call a Bike Starter) | first 30 min free, then €0.10/min (Member Plus) |
| `car_sharing` | €1.00 + €0.79/km (MILES PAYG benchmark) | €1.68/h + €0.224/km (teilAuto member rate) |
| `e_scooter` | €1.00 + €0.25/min | always PAYG in this dataset (no persona holds an e-scooter pass) |

CO₂ factors (kg/km): bike_sharing 0.005, e_scooter 0.02, long_distance_train
0.03, regional_train 0.035, public_transport 0.04, car_sharing 0.15.

Every trip in this dataset is a single leg (no multi-leg walk-access/
main/walk-egress structure) — the app only records legs with a real
mobility-service transaction (a ticket, a subscription swipe, a shared-vehicle
rental), so personal walking/cycling isn't logged as a trip at all.

Reduced ~65% activity during summer holidays (Jul/Aug) and the Dec 20–Jan 5
lull applies to every persona, giving `detected_seasonality` real signal
across the single 12-month window.
