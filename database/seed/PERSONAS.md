# Mock Data Personas

This is the seed dataset loaded by `database/init/02_insert_data.sql`:
`user_profiles_v4.csv`, `user_onboardings_v4.csv`, `user_subscriptions_v5.csv`,
`user_trips_v5.csv`, `trip_legs_v8.csv`, `user_calendars_v2.csv`
(`subscription_catalogs_v2.csv` is the product catalog, not persona data — it
adds structured per-unit-rate columns for consumption-based bike-/car-sharing/
e-scooter plans on top of the unchanged `v1` product list; see "Cost / CO₂
model" below).

10 personas, each constructed to exercise one distinct subscription-decision
path through the analyst/optimizer logic in `backend/src/agents/analyst_spec.md`.
The first 5 (Julia, Jonas, Simone, Elif, Maja) hold 0-3 subscriptions across a
full 12-month trip history and were the original dataset; personas 6-10
(Michael, Vera, Claudia, Sabine, Jan) were added later specifically to close
gaps the first 5 left uncovered — a BahnCard-only regional commuter, a
brand-new user with too little data, a 1st-class traveler, a real mobility
constraint, and a subscriber to every category at once (see each persona's
"Exists to exercise" note below for exactly which gap). Trip data spans a
fixed 12-month window, **2025-07-01 → 2026-06-30** — the full window
`analyze_portfolio` uses (it caps to the last 365 days of data itself), not
"today minus N days," so the dataset stays valid as time passes — Vera (7.)
is the deliberate exception, with only ~9 days of history near the end of
that window.

Every leg's `trip_id` belongs to a trip owned by the same `user_id` (no
cross-user contamination), and `user_subscription_id` is only set on legs
actually covered by that persona's held subscription. Regenerate with
`python database/seed/gen_personas.py` (deterministic — same `random.seed`,
same UUIDv5 namespace, always produces byte-identical output).

Calendars are deliberately split: Julia and Simone only have local,
routine-life events with no bearing on their subscription mix (only their
recurring weekly/monthly items ever reach the forecaster — see the note
below); Jonas, Elif and Maja each have an **upcoming** life event (an
apartment move; a home-renovation project; a promotion requiring monthly
travel to a new office) dated ahead of the trip-history window's end, not
reflected in their historical baseline at all, that the forecaster picks up
as a forward-looking signal. Personas 6-10 have no calendar entries at all —
each is scoped tightly to the one gap it exists to close, and none of those
gaps involve the forecaster/calendar path.

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

**Onboarding:** `score_emission=50, score_money=75, score_flexibility=50` —
cost-conscious about the frequent business travel, wants to know if the
BahnCard is still the right one. Money is the clear top priority here (not
just nominally highest): `resolve_weights` normalizes the three scores
relative to each other, so a shallow gap between them (the pre-2026-08 values
were `60/65/60`) washes out to a ~33/33/33 split indistinguishable from "no
preference stated" — see "Priority-score spread" below.

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

**Onboarding:** `score_emission=60, score_money=30, score_flexibility=60` —
low money-priority is the narrative reason she hasn't noticed/cancelled the
two unused subscriptions; money is now the clear *lowest* of the three (the
pre-2026-08 values, `55/45/55`, only had a 10-point gap, which normalizes to
a barely-there ~6pp difference from an even split — see "Priority-score
spread" below).

**Verified analyst output:** Deutschlandticket `net=+€366.72` — not flagged,
`public_transport` recommendation `keep_current`. BahnCard 25
`cost=€62.90/yr`, `realized_savings=€51.08/yr`, **`net=-€11.82`** — flagged
`overpaid_subscription`; `long_distance_rail` recommendation
`cancel_current_go_pay_as_you_go` (pay-as-you-go `€204.26/yr` beats both her
current `€216.09/yr` and a BahnCard 50 upgrade at `€346.13/yr`). Call a Bike
Member Plus `cost=€96.00/yr`, `realized_savings=€46.34/yr`,
**`net=-€49.66`** — also flagged `overpaid_subscription`; `bike_sharing`
recommendation is **`switch_to_alternative`**, not just "cancel" — nextbike
Basic's own pay-as-you-go rate (`€17.05/yr` simulated from its per-minute rate)
beats both her current membership and plain pay-as-you-go (`€46.34/yr`) for
how rarely she actually rides. `detected_seasonality`: peak in March (1.5×),
lowest in August (0.2×).

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
`realized_savings=€763.81/yr`, **`net_savings=+€403.81`** — not flagged (it
does beat plain pay-as-you-go, `€1,215.66/yr`), but `car_sharing`'s
recommendation is **`switch_to_alternative`**: Sixt Share Minutentarif, priced
from its own per-minute rate, comes out at `€612.95/yr` — cheaper than her
actual `€811.85/yr` — a comparison the analyst could only make once
consumption-based plans (per-km/per-hour/per-minute rates, not just flat-rate
passes and BahnCard-style discounts) became priceable at all; teilAuto's own
Rahmentarif (`€636.78/yr`) and cityflitzer (`€667.15/yr`) tariffs also beat her
current Vielfahrertarif, all ranked in `alternatives`. `bike_sharing`
(`€178.44/yr`) now has real alternatives too — nextbike Jahresabo at
`€60.00/yr` makes it `consider_subscribing` rather than a dead end. `e_scooter`
(`€422.54/yr`, cheapest alternative Dott Pro at `€204.86/yr`) is
`consider_subscribing` for the same reason. `public_transport` (`€210.55/yr`,
cheapest alternative Deutschlandticket at `€756.00/yr` — not worth it at this
volume) stays `no_subscription_needed`. `detected_seasonality`: peak in
September (1.4×), lowest in August (0.3×).

---

## 5. Maja Hoffmann — habitual car-sharing for trips a bike would cover just as well

`c0533b37-8d16-5c9a-b16c-8cdbac66ee7e` · Cologne · 29 · Marketing Manager, hybrid

**Story:** Commutes on the Deutschlandticket, but automatically grabs a
car-sharing car for every errand in between — even though, by her own
admission, most of those short hops would work just as well by bike. Her
onboarding scores emissions highest of any persona (85), making her the
dataset's clearest CO₂-first preference profile, set against a habit she
knows isn't actually climate-friendly. Also holds a BahnCard 25 for two
long-distance trips a year that barely break even, and a Bolt e-scooter pass.

**Subscriptions:**
- Deutschlandticket (`a1111111-...`), held since 2023-09-01, primary,
  several-times-per-week use.
- BahnCard 25, 2. Klasse (`a3333333-...`), held since 2022-11-01, secondary,
  rarely used.
- Bolt Unbegrenzte Freischaltungen (`t1111111-...`), held since 2024-06-01,
  secondary, several-times-per-week use.

**Trip pattern:** DT-covered hybrid commute most weekdays; short (~4-8km),
deliberately-under-bike-share-plausibility car-sharing errands pay-as-you-go,
a couple of times a month (client hops, supermarket runs) — this is the
persona referenced in the car-sharing pricing/Sixt-tariff investigation
earlier in this project's history (see `database/seed/subscription_catalogs_v2.csv`'s
`sixt_share_minute` row); light Bolt-covered e-scooter hops most days; two
BahnCard-covered long-distance trips a year (Berlin, Munich).

**Onboarding:** `score_emission=85, score_money=40, score_flexibility=45` —
the dataset's only CO₂-dominant preference profile, deliberately in tension
with her own stated habit ("car-sharing is just the convenient habit I've
fallen into, even though I could bike almost everywhere I actually go").

**Calendar (life-event/trip-affecting):** *upcoming* — a promotion to Senior
Marketing Manager (accepted 2026-08-05, starting 2026-09-01) that adds a
recurring monthly on-site day at the Munich HQ, not reflected in the
twice-a-year baseline above — meant to flip `long_distance_rail`'s
cancel-the-BahnCard call (see below) forward once the forecaster projects
that volume rising from 2×/yr toward monthly.

**Verified analyst output:** Deutschlandticket `cost=€756/yr`,
`realized_savings=€957.17/yr`, `net=+€201.17` — not flagged, `public_transport`
`keep_current`. BahnCard 25 `cost=€62.90/yr`, `realized_savings=€45.81/yr`,
**`net=-€17.09`** — flagged `overpaid_subscription`; `long_distance_rail`
recommendation `cancel_current_go_pay_as_you_go` (pay-as-you-go `€183.22/yr`
beats both her actual `€200.32/yr` and a BahnCard 50 upgrade at `€335.61/yr`).
`car_sharing` (`€196.97/yr`, no subscription held) is `consider_subscribing` —
cheapest alternative teilAuto cityflitzer at `€96.92/yr` (see the Sixt
Minutentarif pricing-floor correction in `subscription_catalogs_v2.csv` for
why this number isn't lower still). `e_scooter` (`€316.73/yr` no-subscription
baseline, actual `€229.99/yr` on the held Bolt pass) is `switch_to_alternative`
to Dott Pro at `€178.40/yr`. `detected_seasonality`: peak in October (1.4×),
lowest in August (0.2×).

---

## 6. Michael Voss — BahnCard-only regional commuter, no Deutschlandticket

`9a9617f8-5780-5004-8b72-c5bd6a52536c` · Stuttgart · 41 · Sales Consultant, hybrid

**Story:** Commutes by regional train into a nearby office on a BahnCard 50 —
and nothing else. **Exists to exercise the BahnCard-on-regional-train credit**
in `agent/engines/analysis.py`'s `_build_category_entry` with real persona
data: personas 1-5 all hold a BahnCard *alongside* a Deutschlandticket (or no
BahnCard at all), so none of them ever exercises the case this rule was
actually built for — someone whose BahnCard is the *only* thing discounting
their regional trips (see PERSONAS.md's "BahnCard-on-regional-train rule"
note below, now no longer purely test-fixture-only).

**Subscriptions:**
- BahnCard 50, 2. Klasse (`d1111111-...`), held since 2021-05-01, primary,
  several-times-per-week use. No Deutschlandticket.

**Trip pattern:** BahnCard-covered regional-train commute (Stuttgart↔Tübingen,
~30km) most weekdays; a small, deliberately modest pay-as-you-go local
`public_transport` footprint (so the credit's effect on the regional slice
stays easy to isolate from the uncredited local slice); 4 BahnCard-covered
long-distance trips a year (Frankfurt, Munich, Cologne).

**Onboarding:** `score_emission=50, score_money=65, score_flexibility=50` —
mildly cost-conscious, framed around "is a single BahnCard actually enough."

**Verified analyst output:** `public_transport` (which owns his regional-train
spend): `no_subscription_annual_cost_eur=€3,261.70`,
`actual_annual_cost_eur=€1,666.06` — the BahnCard 50's 50% credit is visibly
applied to the regional slice even though the card itself lives in a
different category bucket — recommendation **`consider_subscribing`**
(Deutschlandticket at `€756.00/yr` beats even the BahnCard-discounted
pay-as-you-go rate at this commute volume). `long_distance_rail`:
`actual_annual_cost_eur=€380.66` (his BahnCard 50's `€244/yr` fee plus the
discounted fare on only 4 round-trips/yr) is *more* than paying full price
pay-as-you-go (`€273.36/yr`) — too light a long-distance travel volume to
justify a 50%-off card — recommendation **`switch_to_alternative`** to
BahnCard 25 at `€267.92/yr`. A third, distinct long_distance_rail story from
Julia's (upgrade) and Simone's (cancel): here the right move is to *downgrade*
to a cheaper discount card. `detected_seasonality`: peak in October (1.3×),
lowest in July (0.4×).

---

## 7. Vera Neumann — brand-new user, too little data to annualize reliably

`fcbeb8f0-20fe-5070-89ed-b6024b6f8abe` · Munich · 30 · Product Marketing Manager, hybrid

**Story:** Just moved to Munich and started using the app; only about a week
and a half of trip history exists so far. **Exists to exercise
`analyze_portfolio`'s `data_warning`** ("too little data for reliable
annualization," triggered when `data_window_days < 14`) with real persona
data — every other persona's trip history spans close to the full 12-month
window, so none of them ever produces this warning.

**Subscriptions:** none — too new to have picked one yet.

**Trip pattern:** ~9 days of history (2026-06-22 → 2026-06-30, deliberately
placed at the very end of the dataset's 12-month window): a short daily
public-transport commute on single tickets, plus one or two pay-as-you-go
bike-share rides exploring the new neighbourhood. 14 legs total.

**Onboarding:** `score_emission=50, score_money=50, score_flexibility=50` —
neutral defaults; there isn't enough of an established pattern yet to frame
a real preference around.

**Verified analyst output:** `data_window_days=8`, **`data_warning="too
little data for reliable annualization"`** — the only persona that ever
surfaces this field as non-`None`. The engine still computes a full verdict
regardless (this is a warning, not a refusal): `public_transport`
`no_subscription_annual_cost_eur=€1,853.80`, recommendation
`consider_subscribing` to a Deutschlandticket at `€756.00/yr` — a real number,
just one that should be read with the caveat front and center given how thin
the underlying sample is. `detected_seasonality`: "insufficient data for
seasonality detection."

---

## 8. Claudia Herrmann — 1st-class business traveler

`7455f3a7-6592-5612-b69a-bdf133597f75` · Düsseldorf · 44 · Management Consultant, hybrid

**Story:** Travels to clients nationwide several times a week, always 1st
class. **Exists to exercise travel-class matching end-to-end** (never
compared against a 2nd-class alternative) **and** the 1st-class fare
multiplier added to the generator for this persona specifically
(`CLASS_1_MULTIPLIER = 1.5` in `gen_personas.py`, applied to
`ref_long_distance_train`/`ref_regional_train`) — see "First-class fare
pricing" below for why that multiplier had to be added at all rather than
this persona just working out of the box.

**Subscriptions:**
- BahnCard 50, 1. Klasse (`i1111111-...`), held since 2020-02-01, primary,
  several-times-per-week use. No Deutschlandticket.

**Trip pattern:** local Düsseldorf errands pay-as-you-go (no class
distinction — bus/tram fares don't split by class in this taxonomy); frequent
1st-class, BahnCard-50-covered long-distance client trips (~1.3 round-trips/
week: Frankfurt, Munich, Berlin, Hamburg, Stuttgart, Cologne); occasional
1st-class, BahnCard-covered regional trips to a satellite office in
Wuppertal — every long-distance/regional leg carries `ticket_class=1` and a
reference price scaled by `CLASS_1_MULTIPLIER`.

**Onboarding:** `score_emission=40, score_money=55, score_flexibility=75` —
comfort/convenience-weighted, matching a business traveler who pays for
quiet and reliability rather than optimizing hard on cost.

**Verified analyst output:** `long_distance_rail`:
`no_subscription_annual_cost_eur=€11,625.69` (1st-class-scaled reference
fares), `actual_annual_cost_eur=€6,299.80` — recommendation **`keep_current`**;
her only priced alternatives are the *other* 1st-class BahnCards (`BahnCard
100, 1. Klasse` at `€7,714.00/yr`, `BahnCard 25, 1. Klasse` at
`€8,844.27/yr`, both losing to her BahnCard 50), while every 2nd-class
BahnCard variant lands in `non_comparable_alternatives` — confirms the
travel-class filter holds even with a real, non-fixture persona. The
BahnCard-on-regional-train credit (see Michael, above) also applies correctly
to her 1st-class regional fares: `public_transport`
`no_subscription_annual_cost_eur=€612.57` → `actual_annual_cost_eur=€409.56`,
`keep_current`. `detected_seasonality`: peak in February (1.9×), lowest in
August (0.4×).

---

## 9. Sabine Krüger — a real mobility constraint (cannot cycle)

`9ef16060-525f-5a42-a9a5-0ad99d95d204` · Hannover · 52 · Office Administrator, in-office

**Story:** A long-standing knee condition rules out cycling and standing
e-scooters entirely — not a preference, a hard constraint. Relies on her
Deutschlandticket for the commute and pay-as-you-go car-sharing for whatever
transit doesn't reach well. **Exists to check that
`agent/engines/modal_shift.py`'s candidate filtering actually respects
`avoided_transport_modes`/`mobility_constraints`** rather than suggesting a
switch to bike-sharing or e-scooter on cost/CO₂ grounds alone — every other
persona's `mobility_constraints` is `["none"]`.

**Subscriptions:**
- Deutschlandticket (`a1111111-...`), held since 2022-08-01, primary,
  several-times-per-week use.

**Trip pattern:** DT-covered commute most weekdays; pay-as-you-go car-sharing
for trips transit doesn't cover well (a monthly physio appointment, garden
centre runs); occasional DT-covered weekend errands. Zero bike-sharing or
e-scooter trips of any kind — not because she never needed one, but because
she structurally can't use either.

**Onboarding:** `avoided_transport_modes=["bike_sharing", "e_scooter"]`,
`mobility_constraints=["mobility_impairment", "cannot_cycle"]`;
`score_emission=55, score_money=60, score_flexibility=55` — fairly balanced.

**Verified analyst output:** `car_sharing` (`no_sub=€214.54/yr`,
`consider_subscribing`, cheapest alternative teilAuto cityflitzer at
`€108.00/yr`) and `public_transport` (`keep_current` on the Deutschlandticket)
both look ordinary — the real check is in `modal_shift_suggestions`, called
directly (not through the API) for verification: **every candidate shift onto
`bike_sharing` or `e_scooter`, from both categories, is excluded with reason
`"customer's onboarding lists this as an avoided transport mode"`** — the
deterministic hard-filter in `_hard_exclusion_reason` (`modal_shift.py`)
catches it before an LLM feasibility judge would ever be consulted.
`detected_seasonality`: peak in October (1.3×), lowest in August (0.5×).

---

## 10. Jan Albrecht — mobility maximalist, a subscription in every category

`5f6d733a-2132-5cb8-9dec-ddb5420df922` · Berlin · 37 · Software Engineer, hybrid

**Story:** Holds a subscription in all 5 category buckets the system tracks
at once — public_transport, long_distance_rail, bike_sharing, car_sharing,
e_scooter — because he values having every option available over optimizing
cost. **Exists to stress-test the full `category_subscription_analysis`
output shape** (5 populated entries, the richest `current_contracts` list of
any persona) **and give `modal_shift.py`'s cross-category comparison the
fullest possible baseline to work from** — no other persona holds more than 3
subscriptions simultaneously.

**Subscriptions:**
- Deutschlandticket (`a1111111-...`), held since 2023-01-01, primary,
  several-times-per-week use.
- BahnCard 25, 2. Klasse (`a3333333-...`), held since 2023-06-01, secondary,
  several-times-per-month use.
- Call a Bike Member Plus (`m1111111-...`), held since 2023-06-01, secondary,
  several-times-per-week use.
- teilAuto Vielfahrertarif (`x1111111-...`), held since 2023-06-01, secondary,
  several-times-per-week use.
- Bolt Unbegrenzte Freischaltungen (`t1111111-...`), held since 2023-06-01,
  secondary, several-times-per-week use.

**Trip pattern:** DT-covered commute most weekdays; teilAuto-covered
car-sharing errands; Bolt-covered e-scooter hops; weekend Call-a-Bike-covered
bike rides (first 30 min free); roughly-monthly BahnCard-covered weekend
trips out of the city (Leipzig, Dresden, Hamburg).

**Onboarding:** `score_emission=55, score_money=45, score_flexibility=70` —
values optionality, low cost-sensitivity — the narrative reason he holds five
subscriptions instead of optimizing down to one or two.

**Verified analyst output:** all 5 category buckets populated in a single
run. `public_transport` `keep_current`. `long_distance_rail`
`switch_to_alternative` (BahnCard 50 at `€614.76/yr` beats his current
BahnCard 25's `€619.07/yr` at this volume). `bike_sharing`
`switch_to_alternative` (nextbike Basic `€34.94/yr` vs. his actual
`€96.00/yr`) and `car_sharing` `switch_to_alternative` (teilAuto cityflitzer
`€92.87/yr` vs. his actual `€423.19/yr`) are both flagged
`overpaid_subscription` inefficiencies (`€7.05/yr` and `€243.71/yr` waste
respectively — the teilAuto Vielfahrertarif is real overkill for how little
he actually drives). `e_scooter` `switch_to_alternative` to Dott Pro
(`€153.08/yr` vs. actual `€164.07/yr`). `detected_seasonality`: peak in
September (1.5×), lowest in July (0.3×).

---

## Priority-score spread

Each persona's `score_emission`/`score_money`/`score_flexibility` (0-100,
onboarding) feed `agent/engines/scoring.py::resolve_weights`, which
normalizes them **relative to each other** (`cost/total`, `co2/total`,
`time/total`) rather than against a fixed scale — so what actually drives the
keep/switch/cancel and modal-shift weighting isn't how high a score is, but
how far apart the three scores are for that persona. A persona whose scores
sit close together (e.g. `60/65/60`) normalizes to something like
`35%/32%/32%` — a couple of points from an even three-way split, i.e.
practically indistinguishable from "no preference stated" at all, even if the
narrative claims a clear priority.

As of 2026-08, whenever a persona's story asserts a directional priority, its
three raw scores are chosen so the resulting normalized spread (max share −
min share) clears roughly **15 percentage points** — enough to read as a real
lean rather than noise. Near-equal raw scores are reserved for personas whose
story is explicitly "no strong preference yet" (Vera, 7. — too new to have
one) or "fairly balanced" (Sabine, 9. — the persona's point is the hard
mobility-constraint filter, not priority-weighted ranking). Julia (1.) and
Simone (3.) were tightened to this rule on 2026-08-12 (Julia: `60/65/60` →
`50/75/50`; Simone: `55/45/55` → `60/30/60`) — the earlier gaps normalized to
~3pp and ~6pp respectively, both reading as flat despite their narratives
explicitly calling out cost-consciousness (Julia) and a deliberately low
money-priority (Simone). Verified this doesn't flip any documented
recommendation for either persona (category recommendations and modal-shift
suggested-shift targets are identical before/after — only the underlying
weights and candidate scores move).

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

Note this table is the *generator's* cost model for pricing each persona's
actual historical legs — a separate thing from `subscription_catalogs_v2.csv`'s
`unlock_fee_eur`/`per_km_eur`/`per_hour_eur`/`per_minute_eur`/
`free_minutes_included`/`daily_cap_eur` columns, which the analyst engine uses
to evaluate *untried* car-/bike-sharing/e-scooter alternatives against those
same legs (see `agent/engines/analysis.py`'s `_simulate_consumption_annual_cost`).
The two happen to agree for teilAuto Vielfahrertarif and Call a Bike Member
Plus (this file's numbers were the source for those catalog rates), but the
generator's table only covers the products these personas actually hold —
the catalog now has structured rates for most other bike-/car-sharing/
e-scooter products too, which is what lets the analyst propose switching to a
provider none of the personas have ever used.

**BahnCard-on-regional-train rule.** The `regional_train` row's "50% (BahnCard
50)" isn't a per-leg `paid_regional_train_*` function like the other
discounted modes above (no such function exists in `gen_personas.py`) — it's
the real-world tariff rule, implemented instead as a category-level credit in
`agent/engines/analysis.py`'s `_build_category_entry`: a held BahnCard's
%-discount is applied to a `public_transport`-category's `regional_train`
spend, but *only* when no Deutschlandticket-style flat pass is also held.
With a flat pass held, regional trips are already free/covered by it, so
which product is "really" discounting a given regional trip becomes
ambiguous — exactly the ambiguity the public_transport/long_distance_rail
split (below) exists to avoid — so the credit is deliberately skipped in that
case. Julia and Maja both hold a BahnCard *alongside* a Deutschlandticket (their
regional trips are DT-covered, so the BahnCard's regional discount is moot
for them) — Michael (6.) and Claudia (8.) are the personas that actually
exercise this rule end-to-end: a BahnCard with no Deutschlandticket in the
picture at all. It's also covered at the unit level by
`backend/tests/test_analysis.py`'s
`test_held_bahncard_discounts_regional_train_when_no_flat_pass_held` and
`test_bahncard_regional_discount_not_applied_when_flat_pass_also_held`.

**First-class fare pricing.** Every persona above Claudia (8.) is implicitly
priced in 2nd class — none of the `ref_*` functions take a class parameter,
and `ticket_class` is otherwise never populated (matching real production
data — see `agent/engines/analysis.py`'s module comments on why the analyst
engine never reads it back for pricing anyway, only for alternative-matching).
Claudia is the one persona whose `reference_cost_eur` is deliberately scaled
by `CLASS_1_MULTIPLIER = 1.5` (in `gen_personas.py`) wherever she travels
1st class, and whose legs carry `ticket_class=1` — without that multiplier, a
1st-class BahnCard's own (correctly, independently priced) annual fee would
look like a bad deal relative to a reference fare that was still implicitly
priced as 2nd class, understating her real savings. 1.5× roughly matches DB's
real 1st/2nd-class Flexpreis ratio; it isn't a measured figure.
