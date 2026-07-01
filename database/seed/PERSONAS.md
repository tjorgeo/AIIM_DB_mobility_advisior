# Mock Data Personas

This is the seed dataset loaded by `database/init/02_insert_data.sql`:
`user_profiles_v3.csv`, `user_onboardings_v3.csv`, `user_subscriptions_v4.csv`,
`user_trips_v4.csv`, `trip_legs_v7.csv` (`subscription_catalogs_v1.csv` is
unchanged — it's the product catalog, not persona data).

6 personas, each constructed to exercise one distinct path through the
analyst/optimizer logic in `backend/src/agents/analyst_spec.md`. Trip data
spans a fixed 24-month window, **2024-07-01 → 2026-06-29**, with two full
summer/winter cycles so seasonality detection has real signal — not
"today minus N days," so the dataset stays valid as time passes.

Every leg's `trip_id` belongs to a trip owned by the same `user_id` (no
cross-user contamination), and `user_subscription_id` is only set on legs
actually covered by that persona's held subscription — both fixed bugs
present in the previous (23-user) dataset.

---

## 1. Mara Vogel — flat-pass commuter, well covered

`38bb9fdb-7d90-55a0-98d8-f9935f1aec70` · Berlin · 29 · Marketing Specialist, in-office

**Story:** Textbook positive case for a flat pass. Commutes by public transport
nearly every weekday, plus occasional weekend leisure trips, all ridden on the
Deutschlandticket. Demonstrates a subscription that is unambiguously worth it.

**Subscription:** Deutschlandticket (`a1111111-...`), held since 2023-09, primary
mobility option.

**Trip pattern:** ~5 commute round-trips/week (home ↔ office, public_transport,
3-leg walk-access/main/walk-egress structure), reduced ~65% during summer
holidays (Jul/Aug) and the Dec 20–Jan 5 lull, occasional weekend PT trips
(leisure/social/shopping/errands), rare short walking errands.

**Onboarding:** `score_emission=75, score_money=55, score_flexibility=40` —
cares about emissions, low need for flexibility (fixed routine), avoids car.

**Verified analyst output:** Deutschlandticket `cost=€756/yr`,
`realized_savings=€1,635.53/yr`, **`net_savings=+€879.53`** — not flagged.
`total_effective_spend=€0` (every cost-bearing leg is subscription-covered).
`detected_seasonality`: lowest activity in August.

---

## 2. Tobias Hahn — BahnCard 50, frequent business traveler

`be6f3d9a-713a-5a56-bd77-5b27feea6827` · Frankfurt · 41 · Management Consultant, hybrid

**Story:** Discount-card case — the card never makes a trip free, only cheaper,
so `realized_savings` should equal the discount, not the full ticket price.
Also exercises **uncovered** local public transport, since BahnCard 50 only
discounts DB train tickets (long-distance + regional), not city buses/trams.

**Subscription:** BahnCard 50, 2. Klasse (`d1111111-...`), held since 2022-03,
attributed only to `regional_train` and `long_distance_train` legs (at 50% of
reference price) — never to his `public_transport` city legs, which are paid
in full as single tickets and correctly **not** attributed to the card.

**Trip pattern:** ~2–3 client-visit trips/week by long-distance train to one of
5 cities (Munich/Hamburg/Berlin/Stuttgart/Cologne), often with a local
public_transport leg at the destination (uncovered, single ticket); regular
regional-train commute to Offenbach; reduced ~60% in summer/winter lulls;
occasional weekend single-ticket PT trips in Frankfurt.

**Onboarding:** `score_emission=60, score_money=70, score_flexibility=65` —
cost-conscious about travel spend, wants to know if the card pays off.

**Verified analyst output:** BahnCard 50 `cost=€244/yr`,
`realized_savings=€5,031.00/yr`, **`net_savings=+€4,787.00`** — not flagged.
`detected_seasonality`: peak in May, lowest in August.

---

## 3. Nina Schröder — pure pay-as-you-go, no subscriptions

`d90794d2-efac-5b8d-b1cd-01244a890cb2` · Cologne · 33 · Graphic Designer, hybrid (60% remote)

**Story:** Holds zero subscriptions by choice ("avoids fixed contracts"),
exercising `uncovered_spend_by_category` across multiple categories at once —
the raw-fact signal the Optimizer would use to evaluate whether a pass would
actually save her money.

**Trip pattern:** ~2 office days/week via single-ticket public_transport,
occasional e-scooter for errands/social trips (pay-as-you-go), rare
pay-as-you-go car-sharing for bulky shopping (e.g. furniture).

**Onboarding:** `score_emission=55, score_money=80, score_flexibility=85` —
very cost-conscious and explicitly values flexibility over commitment; the
dataset is designed to let the analyst/optimizer reveal whether that instinct
is actually saving her money.

**Verified analyst output:** no `subscription_coverage` entries.
`uncovered_spend_by_category`: `public_transport=€597.41/yr`,
`e_scooter=€228.24/yr`, `car_sharing=€100.50/yr`. `detected_seasonality`:
peak in July, lowest in March.

---

## 4. Lukas Weber — over-subscribed, barely uses any of it

`671fbc5b-99f1-505f-aaaa-1c682f552803` · Munich · 38 · Software Engineer, 90% remote

**Story:** Kept 3 subscriptions from when he used to commute, never canceled
after going fully remote. Clean negative case ×3 — every held subscription
should be flagged `overpaid_subscription`, and the optimizer should recommend
canceling all three.

**Subscriptions (all "kept out of inertia", `is_primary_mobility_option=False`,
`estimated_usage_frequency=rarely`):**
- Deutschlandticket (`a1111111-...`), held since 2022-01
- Call a Bike Member Plus (`m1111111-...`), held since 2022-01
- teilAuto Rahmentarif (`w2222222-...`), held since 2022-06

**Trip pattern:** Mostly free — walking or his own bicycle for ~half of
weekdays/weekends, ~2.5% chance/day of a Call a Bike ride, ~1.2% chance/day of
a Deutschlandticket commute, ~1% chance/day of a teilAuto car-sharing trip.
Only ~12% of his trips actually touch a subscription.

**Onboarding:** `score_emission=50, score_money=35, score_flexibility=70` — low
money-priority is the narrative reason he hasn't noticed/canceled the waste.

**Verified analyst output:** Deutschlandticket `net=-€715.03`,
Call a Bike Member Plus `net=-€74.87`, teilAuto Rahmentarif `net=-€35.57` — all
three flagged `overpaid_subscription`. Optimizer's top recommendation cancels
all three and switches to pay-as-you-go (Call a Bike Starter + MILES PAYG),
saving an estimated `€924/yr`.

---

## 5. Petra Sommer — thin data (joined ~6 weeks ago)

`b31247a7-eb90-533a-bff7-1f0d37d28adc` · Düsseldorf · 52 · Physiotherapist, in-office

**Story:** Recently relocated; her trip history only covers the last ~6 weeks
of the 24-month window (2026-05-18 → 2026-06-29), not the full 2 years like
the other 5. Demonstrates that the current `data_warning` threshold
(`data_window_days < 14`) is too narrow to catch a 42-day window — her
annualized figures (`realized_savings≈€1,286/yr` off of 51 trips) are
extrapolated from 6 weeks of data with **no warning surfaced**, and
`detected_seasonality` correctly falls back to "insufficient data" since
fewer than 3 calendar months are present. Useful as a concrete repro case if
the threshold is widened later.

**Subscription:** Deutschlandticket (`a1111111-...`), `valid_from=2026-05-18`
(matches her actual join date), primary mobility option.

**Trip pattern:** Regular weekday PT commute (~80% of weekdays), occasional
weekend leisure trips (~35% of weekend days) — a normal, fully-formed routine,
just observed for too short a window.

**Onboarding:** `score_emission=65, score_money=60, score_flexibility=50` —
neutral-ish, framed as still building routine in a new city.

**Verified analyst output:** `data_window_days=42`, `data_warning=None`.
Deutschlandticket `net=+€530.31` — not flagged, but the annualization rests on
1.4 months of data.

---

## 6. Sandra Hoffmann — family, multi-modal

`99cb2bd6-228b-566d-a250-16290da30521` · Stuttgart · 41 · Physical Therapist (part-time), hybrid

**Story:** The multi-modal/family case — childcare logistics drive a mix of
car-sharing, public transport, and personal bicycle, with two subscriptions
that land on *opposite sides* of the net-savings line: a heavily-used
car-sharing membership that clearly pays off, and a flat pass whose part-time
commute usage doesn't quite cover its own cost. A more nuanced, realistic
result than a clean win/loss.

**Subscriptions:**
- teilAuto Vielfahrertarif (`x1111111-...`), held since 2023-02, primary
  mobility option — heavy-user car-sharing tier.
- Deutschlandticket (`a1111111-...`), held since 2023-02, secondary.

**Trip pattern:** Bicycle school drop-off most weekdays (free, personal bike);
part-time PT commute (Deutschlandticket-covered) roughly half of weekdays;
car-sharing (teilAuto-covered) for shopping/errands and weekend family
outings; all reduced during summer/winter lulls. Trip purposes deliberately
span commute, childcare, shopping, errands, social, and leisure.

**Onboarding:** `score_emission=45, score_money=55, score_flexibility=75` —
flexibility weighted highest, reflecting unpredictable family logistics.

**Verified analyst output:** teilAuto Vielfahrertarif `net=+€498.65` — not
flagged. Deutschlandticket `net=-€97.59` — flagged `overpaid_subscription`
(small magnitude; her part-time commute doesn't generate enough PT volume to
clear the €756/yr flat cost). `detected_seasonality`: peak in October, lowest
in July.

---

## Cost / CO₂ model used by the generator

The generator (not checked into the repo — see `gen_personas.py` if
regenerating) prices each leg with `estimated_cost_eur` (amount actually
paid) and `reference_cost_eur` (pay-as-you-go price for the same trip,
ignoring any subscription), per the attribution model in `analyst_spec.md`.

| Mode | Reference (PAYG) price | Subscription-covered price |
|---|---|---|
| `walking` / `bicycle` (owned) | €0 | n/a |
| `public_transport` | €2.90 flat | €0 (Deutschlandticket) |
| `regional_train` | €2.50 + €0.20/km | €0 (Deutschlandticket) or 50% (BahnCard 50) |
| `long_distance_train` | max(€19.90, €0.16/km) | 50% (BahnCard 50) |
| `bike_sharing` | €1.00 + €0.12/min (Call a Bike Starter) | first 30 min free, then €0.10/min (Member Plus) |
| `car_sharing` | €1.00 + €0.79/km (MILES PAYG benchmark) | €1.68/h + €0.224/km (teilAuto member rate) |
| `e_scooter` | €1.00 + €0.25/min | always PAYG in this dataset (no persona holds an e-scooter pass) |

CO₂ factors (kg/km): walking/bicycle 0, bike_sharing 0.005, e_scooter 0.02,
long_distance_train 0.03, regional_train 0.035, public_transport 0.04,
car_sharing 0.15.

Multi-leg PT/train trips follow the existing convention: a short walking
access leg → the main (subscription/ticket-bearing) leg → a short walking
egress leg, flagged via `is_access_leg`/`is_main_leg`/`is_egress_leg`.
Single-mode trips (bike-share, scooter, car-share, walking, personal bike)
are a single leg.
