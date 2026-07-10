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
routine-life events with no bearing on their subscription mix (only their
recurring weekly/monthly items ever reach the forecaster — see the note
below); Jonas and Elif each have an **upcoming** life event (an apartment
move; a home-renovation project) dated ahead of the trip-history window's
end, not reflected in their historical baseline at all, that the forecaster
picks up as a forward-looking signal.

> **Calendar life-events must be dated in the future.** The forecaster only
> ever sees calendar entries whose next occurrence falls within
> `[now, now+180 days]` (`agent/context.py::_CALENDAR_LOOKAHEAD_DAYS`) — it's
> a "known future plans" signal, not a historical one. A one-off event dated
> in the past (even last month) never reaches it at all, no matter how
> relevant it would be to explain the trip history. Recurring events (RRULE)
> are the exception: `_next_occurrence` expands the rule forward from its
> `dtstart` regardless of how long ago that `dtstart` was, so a weekly/monthly
> series keeps surfacing as long as it has occurrences left in the window.
> Jonas's and Elif's one-off life-event entries are deliberately dated after
> `WINDOW_END` (2026-06-30) for this reason — regenerating the dataset much
> later than mid-2026 will eventually need those dates bumped forward again,
> or the life events will silently stop reaching the forecaster.

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

**Story:** Never bothered with a pass because he lives close to the office —
single-ticket public transport has been cheap enough. His trip history alone
already justifies a Deutschlandticket; on top of that, his calendar has an
*upcoming* move to a farther-out apartment that will make single tickets
noticeably more expensive still — a forward-looking signal the historical
baseline doesn't even need in order to make the case.

**Subscriptions:** none.

**Trip pattern:** short in-city bus/S-Bahn commute (`public_transport`, ~85%
of weekdays), unchanged across the full 12-month window — pay-as-you-go,
single tickets; occasional weekend `public_transport` errands; biweekly
`regional_train` weekend visit to his parents in Lüneburg.

**Onboarding:** `score_emission=50, score_money=70, score_flexibility=45` —
cost-conscious, framed around the upcoming move making single tickets about
to get a lot more expensive.

**Calendar (life-event/trip-affecting):** *upcoming* — not yet reflected in
the trip history above — apartment viewing in Norderstedt, a packing weekend,
and the move itself ("Umzug - neue Wohnung in Norderstedt"), plus the
recurring biweekly Lüneburg family visit. Only calendar entries whose next
occurrence falls within the forecaster's 180-day lookahead are ever surfaced
to it (see `agent/context.py::_CALENDAR_LOOKAHEAD_DAYS`), so these are
deliberately dated ahead of the trip-history window's end, not behind it —
this is what lets the forecaster flag the relocation as a life event even
though it isn't in the historical baseline yet.

**Verified analyst output:** no `subscription_coverage` entries.
`public_transport` category: `no_subscription_annual_cost_eur=€1,670.01`,
recommendation **`consider_subscribing`**, cheapest alternative
Deutschlandticket at `€756.00/yr`. `detected_seasonality`: peak in October
(1.4× monthly average), lowest in July (0.3×).

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

**Verified analyst output:** Deutschlandticket `net=+€366.72` — not flagged,
`public_transport` recommendation `keep_current`. BahnCard 25
`cost=€62.90/yr`, `realized_savings=€51.08/yr`, **`net=-€11.82`** — flagged
`overpaid_subscription`; `long_distance_rail` recommendation
`cancel_current_go_pay_as_you_go` (pay-as-you-go `€204.26/yr` beats both her
current `€216.09/yr` and a BahnCard 50 upgrade at `€346.13/yr`). Call a Bike
Member Plus `cost=€96.00/yr`, `realized_savings=€46.34/yr`,
**`net=-€49.66`** — also flagged `overpaid_subscription`;
`bike_sharing` recommendation `cancel_current_go_pay_as_you_go`.
`detected_seasonality`: peak in March (1.5×), lowest in August (0.2×).

---

## 4. Elif Yildiz — car-free, car-sharing-centric multi-modal freelancer

`932d3626-708a-596b-a1fc-99c2fa1ce9b3` · Bremen · 33 · Freelance UX Designer, remote

**Story:** Gave up owning a car years ago. A heavily-used car-sharing
membership covers client visits and supply runs; pay-as-you-go e-scooter and
bike-share cover everything shorter. Her trip history is her ordinary
baseline — but her calendar has an *upcoming* home-studio renovation that
will drive a burst of extra car-sharing hauling trips ahead, not yet reflected
in that baseline at all.

**Subscriptions:**
- teilAuto Vielfahrertarif (`x1111111-...`), held since 2024-03-01, primary
  mobility option, several-times-per-week use.

No bike-sharing, e-scooter, or public-transport subscription — those stay
pay-as-you-go by design.

**Trip pattern:** frequent teilAuto-covered car-sharing trips for client
visits/supply runs (several times/week), unchanged across the full 12-month
window; pay-as-you-go e-scooter for quick last-mile hops; occasional
pay-as-you-go bike-share leisure rides; monthly pay-as-you-go regional-train
visit to her parents in Oldenburg.

**Onboarding:** `score_emission=45, score_money=60, score_flexibility=80` —
flexibility weighted highest, reflecting a deliberately car-free, contract-
light lifestyle.

**Calendar (life-event/trip-affecting):** *upcoming* — not yet reflected in
the trip history above — a contractor walkthrough (2026-07-20) and a
two-month "Studio renovation project" block (2026-08-01 → 2026-09-30) that
will start driving extra hardware-store car-sharing trips, plus a recurring
monthly Oldenburg family visit that's already part of her routine.

**Verified analyst output:** teilAuto Vielfahrertarif `cost=€360.00/yr`,
`realized_savings=€763.81/yr`, **`net_savings=+€403.81`** — not flagged,
`car_sharing` recommendation `keep_current` (pay-as-you-go would cost
`€1,215.66/yr` vs. her actual `€811.85/yr`). `bike_sharing` (`€178.44/yr`),
`e_scooter` (`€422.54/yr`), and `public_transport` (`€210.55/yr`, cheapest
alternative Deutschlandticket at `€756.00/yr` — not worth it at this volume)
all correctly resolve to `no_subscription_needed`. `detected_seasonality`:
peak in September (1.4×), lowest in August (0.3×).

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
