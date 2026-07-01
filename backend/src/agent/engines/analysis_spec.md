# Analyst Agent — Specification

## Position in Pipeline

```
DB (trips + subscriptions)
        │
        ▼
  [ Analyst ]   ← this agent
        │
        ▼
  [ Forecaster ]
        │
        ▼
  [ Optimizer ]
```

---

## Role

The Analyst is a **deterministic pipeline node** — no LLM, no system prompt, no generated text.

It reads a user's full leg-level travel history and active subscription records from the database, computes factual usage statistics, detects temporal patterns, and produces a structured summary. It does **not** make recommendations or apply judgment calls. Those belong to the Optimizer.

**Key principle: no hardcoded thresholds.**
Rather than flagging "fewer than N trips = unused", the analyst computes the actual monetary math: if a subscription cost more annually than the intrinsic value of all legs it covered, that is factually an overspend. The numbers speak; no business-defined threshold is needed.

---

## Input

The analyst receives a `user_id` and queries the database directly. It does **not** accept pre-shaped input dicts from the caller — it owns its own data loading.

**Tables queried:**

| Table | What is used |
|---|---|
| `users` | `home_city`, `life_stage` (for context only, not for rule-firing) |
| `user_onboardings` | `score_money`, `score_emission`, `score_flexibility`, `preferred_transport_modes` |
| `trip_legs` | `transport_mode`, `estimated_cost_eur`, `estimated_distance_km`, `estimated_co2_emissions`, `started_at`, `ended_at`, `ticket_type` |
| `user_trips` | `started_at`, `trip_purpose`, `is_commute`, `is_recurring_pattern` |
| `user_subscriptions` | `subscription_status`, `valid_from`, `valid_until` |
| `subscription_catalogs` | `subscription_category`, `provider_plan_name`, `monthly_cost_eur` |

The analyst always uses **all available trip data** for the user. It normalizes every metric to a monthly rate and projects to annual so that comparisons are fair regardless of how much history exists.

```python
data_window_days = (max(leg.started_at) - min(leg.started_at)).days
months_of_data   = data_window_days / 30.44
monthly_rate     = raw_metric / months_of_data
annualized       = monthly_rate * 12
```

---

## Computations (Deterministic, No Thresholds)

### 1. Mode breakdown
Per transport mode (using `group_mode()` for display grouping):
- total trips, total distance (km), total CO₂ (kg)
- intrinsic cost (the pay-as-you-go price on the leg)
- effective cost (0 if an active subscription covers this mode, intrinsic otherwise)
- annualized versions of all of the above

### 2. Dominant patterns
Rank modes by annualized trip count. The top modes become `dominant_patterns` — the primary output field consumed by the Forecaster.

```python
DominantPattern(
    mode: str,
    avg_trips_per_month: float,
    avg_distance_km: float       # average distance per trip in this mode
)
```

### 3. Seasonality detection
Bucket trips by calendar month. Compare each month's trip volume against the overall monthly average. Flag the mode where the seasonal variance is highest and describe the direction (e.g. "higher bike usage in spring/summer, more public transport in winter"). This is a statistical comparison — no LLM involved.

### 4. Subscription cost vs. coverage value

Attribution is **per-leg**, via the leg's `user_subscription_id` — not inferred from category+mode. Every leg carries both `estimated_cost_eur` (what was actually paid) and `reference_cost_eur` (the pay-as-you-go price for the same trip regardless of subscription). This lets one formula correctly handle both subscription shapes:

- **Flat passes** (e.g. Deutschlandticket): `estimated_cost_eur = 0` on covered legs, so realized savings equal the full reference price.
- **Discount cards** (e.g. BahnCard 25): `estimated_cost_eur` is the discounted price actually paid, so realized savings equal just the discount amount — not the full ticket price.

#### Notation

| Symbol | Meaning | Source |
|---|---|---|
| `L` | all legs in the user's travel history | `trip_legs` |
| `p(ℓ)` | amount actually paid for leg `ℓ` | `estimated_cost_eur` |
| `r(ℓ)` | pay-as-you-go reference price for leg `ℓ` | `reference_cost_eur`, falls back to `p(ℓ)` if `NULL` |
| `sub(ℓ)` | subscription used on leg `ℓ`, if any | `user_subscription_id` (nullable FK) |
| `A` | active subscriptions (`subscription_status = 'active'`) | `user_subscriptions` ⋈ `subscription_catalogs` |
| `cost(a)` | annualized fixed cost of subscription `a` | `annual_cost_eur` if set and `> 0`, else `monthly_cost_eur × 12` |
| `L(a)` | legs actually used with subscription `a` | `{ ℓ ∈ L : sub(ℓ) = id(a) }` |
| `months` | length of the observed data window in months | `max(data_window_days, 1) / 30.44` |

#### Per-subscription formulas

```
covered(a) = Σ over ℓ ∈ L(a) of r(ℓ)            # raw reference value of every leg used with a
paid(a)    = Σ over ℓ ∈ L(a) of p(ℓ)            # raw amount actually paid on those same legs

annualize(x) = x / months × 12

covered_value_eur(a)    = annualize( covered(a) )
realized_savings_eur(a) = annualize( covered(a) − paid(a) )
net_savings_eur(a)      = realized_savings_eur(a) − cost(a)
```

If `L(a)` is empty, `covered(a) = paid(a) = 0`, so `realized_savings_eur(a) = 0` and `net_savings_eur(a) = −cost(a)` — an unused subscription is automatically reported as a full-cost overpayment with no special-case code.

#### Inefficiency rule

```
if net_savings_eur(a) < 0:
    annual_waste_eur(a) = −net_savings_eur(a) = cost(a) − realized_savings_eur(a)
    emit Inefficiency(type="overpaid_subscription", service=a.name, annual_waste_eur=annual_waste_eur(a))
```

The only test anywhere in this computation is `< 0`. There is no minimum-waste cutoff, no minimum-trip-count cutoff — the sign of `net_savings_eur` is the entire signal.

#### Why this distinguishes flat passes from discount cards

For a **flat pass**, `p(ℓ) = 0` for every `ℓ ∈ L(a)`:
```
covered(a) − paid(a) = covered(a) − 0 = covered(a)
⇒ realized_savings_eur(a) = covered_value_eur(a)
```
The full reference value of every covered leg counts as savings.

For a **25%-discount card** (e.g. BahnCard 25), `p(ℓ) = 0.75 × r(ℓ)` for every `ℓ ∈ L(a)`:
```
covered(a) − paid(a) = covered(a) − 0.75·covered(a) = 0.25 × covered(a)
⇒ realized_savings_eur(a) = 0.25 × covered_value_eur(a)
```
Only the discount itself is counted — never the full ticket price — which is what makes a cheap discount card net-positive even though its `covered_value_eur` looks large.

#### Worked example — Jan Klein, verified output

Data window: 179 days → `months = 179 / 30.44 ≈ 5.881`. Two active subscriptions, both covering `public_transport`-category modes but attributed to disjoint/overlapping leg sets via `sub(ℓ)`:

| | Deutschlandticket (flat pass) | BahnCard 25, 2. Klasse (discount card) |
|---|---|---|
| `cost(a)` | €756.00/yr | €62.90/yr |
| legs in `L(a)` | 34 (PT + regional legs) | 3 (long-distance legs at full Flexpreis) + the same PT/regional legs the card also rode on |
| `covered_value_eur(a)` | €270.59 | €367.24 |
| `realized_savings_eur(a)` | €270.59 *(p(ℓ)=0 throughout ⇒ savings = full covered value)* | €91.81 *(only the ~25% discount on a larger reference base — not the full €367.24)* |
| `net_savings_eur(a)` | 270.59 − 756.00 = **−485.41** | 91.81 − 62.90 = **+28.91** |
| Result | flagged `overpaid_subscription`, `annual_waste_eur = 485.41` | not flagged — the card pays for itself |

This is the concrete case that motivated the per-leg refactor: under the old category-based inference, both subscriptions shared `subscription_category = 'public_transport'`, so both were credited with the *same* `covered_value_eur` regardless of which legs they were actually used on, and the BahnCard's long-distance legs weren't counted as covered at all (`category_covers_mode('public_transport', 'long_distance_train')` was `False`). Per-leg attribution via `user_subscription_id` fixes both problems simultaneously.

> Legs with no `user_subscription_id` (no subscription was used) are never attributed to a subscription, even if their mode falls within a category the user holds a subscription in — coverage must be evidenced by the actual leg record, not inferred. Concretely: a pay-as-you-go bike-sharing leg ridden by a user who *also* holds an unrelated bike-sharing membership contributes to `total_intrinsic_spend_eur`, but never to that membership's `L(a)`.

### 5. Uncovered spend (factual, not a recommendation)
For each subscription category the user does **not** hold, compute the total intrinsic spend on legs that category would cover. This is reported as a raw fact (`uncovered_spend_by_category`). The Optimizer decides whether a subscription would actually save money; the Analyst only measures the raw spend.

> **Why this boundary?** Recommending a subscription requires knowing the cheapest available product in the catalog. That is an optimization decision, not a measurement. The Analyst should not embed catalog lookups or breakeven comparisons — the Optimizer owns that.

### 6. CO₂ profile
Total CO₂ and per-mode CO₂. No threshold-based flagging — the Optimizer or Communicator can frame high-CO₂ modes relative to user preferences (`score_emission`).

---

## Output Schema

The output has two logical sections:

**Section A — consumed directly by the Forecaster** (must match `AnalystSummary` in `forecaster.py`):

```python
class DominantPattern(BaseModel):
    mode: str
    avg_trips_per_month: float
    avg_distance_km: float

class AnalystSummary(BaseModel):         # forwarded to ForecasterAgent
    dominant_patterns: List[DominantPattern]
    detected_seasonality: str            # human-readable description of seasonal pattern
    current_contracts: List[str]         # ["Deutschlandticket (€58/mo)", ...]
    detected_inefficiencies: List[str]   # short human-readable strings for each inefficiency
```

**Section B — full output consumed by the Optimizer** (superset of Section A):

```python
class ModeStats(BaseModel):
    trips_total: int
    trips_per_month: float
    distance_km_total: float
    distance_km_per_month: float
    co2_kg_total: float
    co2_kg_per_month: float
    intrinsic_cost_eur_total: float      # pay-as-you-go price, ignoring subscriptions
    effective_cost_eur_total: float      # actual cost after subscription coverage

class SubscriptionCoverage(BaseModel):
    provider_plan_name: str
    subscription_category: str
    annual_cost_eur: float
    covered_value_eur: float             # reference (pay-as-you-go) value of all attributed legs
    realized_savings_eur: float          # covered_value - amount actually paid on those legs
    net_savings_eur: float               # realized_savings - annual_cost (negative = overpaid)

class Inefficiency(BaseModel):
    type: Literal["overpaid_subscription"]   # only factual types; optimization types go to Optimizer
    service: str
    annual_waste_eur: float              # abs(net_savings) when negative
    details: str

class AnalystOutput(BaseModel):
    # Data window
    data_window_days: int
    months_of_data: float
    analysis_period_start: str           # ISO date
    analysis_period_end: str             # ISO date

    # Aggregates
    total_trips: int
    total_distance_km: float
    co2_total_kg: float
    total_intrinsic_spend_eur: float
    total_effective_spend_eur: float     # after subscription coverage
    subscription_costs_annual_eur: float
    current_annual_spend_eur: float      # effective + subscriptions

    # Breakdowns
    mode_breakdown: dict[str, ModeStats]
    subscription_coverage: List[SubscriptionCoverage]
    uncovered_spend_by_category: dict[str, float]   # category → annual intrinsic spend (no subscription held)

    # Patterns
    dominant_patterns: List[DominantPattern]
    detected_seasonality: str

    # Inefficiencies (factual only — no "should you get X?" recommendations)
    inefficiencies: List[Inefficiency]
    savings_potential_estimate_eur: float    # sum of annual_waste_eur

    # Forecaster-compatible summary (subset of the above, shaped to AnalystSummary)
    forecaster_summary: AnalystSummary
```

---

## What Belongs Here vs. the Optimizer

| Question | Owner |
|---|---|
| How much did the user spend? | **Analyst** |
| How much did a subscription actually save? | **Analyst** |
| Did a subscription cost more than it saved? | **Analyst** (factual math) |
| Should the user cancel a subscription? | **Optimizer** |
| Would a BahnCard 25 save money? | **Optimizer** (requires catalog lookup + breakeven) |
| Should the user switch to a different plan? | **Optimizer** |
| What modes does the user rely on? | **Analyst** |
| Is there a seasonal pattern? | **Analyst** |
| What will usage look like in 90 days? | **Forecaster** |

---

## Failure Modes

| Condition | Behavior |
|---|---|
| No trip data for user | Returns zeroed metrics, empty `inefficiencies`, `dominant_patterns = []`, `detected_seasonality = "insufficient data"` |
| `data_window_days < 14` | Returns output with `data_warning: "too little data for reliable annualization"` flag; all annualized figures still computed but marked unreliable |
| Unknown transport mode on a leg | Aggregated under the raw mode string via `group_mode()`; no rule fires for it |
| Subscription with no `monthly_cost_eur` (pay-as-you-go) | Counted in active categories for coverage purposes; excluded from flat-cost waste calculation |
| Leg has no `user_subscription_id` even though its mode falls in a category the user subscribes to | Not attributed to any subscription — treated as pay-as-you-go at `reference_cost_eur`. Coverage requires evidence on the leg, not inference from category |
| `subscription_category` not recognized by `category_covers_mode()` | Subscription-level coverage is unaffected (attribution is per-leg, not category-based); only `uncovered_spend_by_category` skips the category |

---

## Out of Scope

- LLM calls of any kind
- Product recommendations (which specific subscription to buy)
- Breakeven calculations between subscription tiers
- Anything requiring the subscriptions catalog to be read (Optimizer's job)
- User-facing explanation text beyond the `details` field on each `Inefficiency`
