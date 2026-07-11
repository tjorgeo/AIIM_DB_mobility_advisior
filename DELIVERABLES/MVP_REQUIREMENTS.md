# MVP Requirements & Backlog
## DB MoveOptimizer - Prototype Phase (Weeks 1-16)

**Focus:** 14 core user stories + acceptance criteria for data scientists to build and test.  
**Approach:** Backlog-first; refine acceptance criteria during sprint planning.  
**Last reconciled with code:** 2026-07-08

> **Reconciliation note.** Stories 5–7 (scenario generation / scenario cost-CO₂ / scenario
> ranking) were overtaken by the July refactor that replaced portfolio scenarios with a
> per-category `keep/switch/drop` subscription analysis. Story 4 (Forecast) is now 90-day and
> **calendar-aware**. The "sandbox API" is seeded Postgres data, and the LLM is University GPT.
> Per-story ⚠️ callouts flag what changed; the ✅/⏳ status column in the summary table reflects
> current state. The dataset ships **6** personas (not 5).

---

## CORE USER STORIES

### Story 1: Ingest Travel History (Analyst Agent)

As a data scientist building the Analyst agent I need to **load 24 months of synthetic travel history from the seeded database**, so that I can analyze patterns and identify inefficiencies.

> ⚠️ Realised as seeded **Postgres** data (`database/seed/*.csv` via `load_context`), not a live
> sandbox HTTP client. The seed spans a fixed 24-month window; the analyst uses the last 12
> months (+ prior year's final 3 months for seasonality).

**Acceptance Criteria**

- [x] Load trip/leg history for the seeded personas from Postgres (`context.py::load_context`)
- [x] Parse into per-leg records: date, origin, destination, cost, mode, distance, CO₂
- [x] Handle missing fields gracefully (reference vs. estimated cost, unsubscribed legs)
- [x] Schema parity between seed CSVs and the relational structure (`database/init`)
**Definition of Done**

- `load_context` returns clean per-user history for all 6 personas
- Unit tests pass (`test_analysis.py`, `test_imports.py`)

**Estimated Effort**

- Estimated Days: 2 days

---

### Story 2: Detect Travel Patterns & Inefficiencies (Analyst Agent)

As a data scientist I need to **analyze travel history and flag inefficiencies** (wasted subscriptions, wrong Bahncard tier), so that the system can recommend better portfolios
**Acceptance Criteria**

- [ ] Calculate trip frequency by mode (train, scooter, etc.)
- [ ] Identify unused subscriptions (<5% usage vs. cost)
- [ ] Identify Bahncard tier mismatch (overpaying or underpaying)
- [ ] Flag patterns: >20% efficiency gain possible
- [ ] Output: Structured list of inefficiencies + savings potential
**Definition of Done**

- Manual validation on 10 customers: 90%+ pattern detection accuracy
- Code tested; 80%+ coverage
**Estimated Effort**

- Estimated Days: 3 days

---

### Story 3: Calculate Cost for Current Portfolio (Analyst Agent)

As a data scientist I need to **accurately calculate customer's annual mobility cost**, so that I can compare scenarios against baseline
**Acceptance Criteria**

- [ ] Ingest current subscriptions (Bahncard tier, memberships, pay-as-you-go)
- [ ] Calculate annual cost from 12-month history
- [ ] Account for subscription fees, per-trip charges, bundling
- [ ] Accuracy: ±5% vs. customer's actual spend (validated on sample)
- [ ] Output Cost breakdown by service + total
**Definition of Done**

- Validated against 10 real customers' billing statements
- Unit tests pass
**Estimated Effort**

- Estimated Days: 2 days

---

### Story 4: Forecast Demand (Forecaster Agent)

As a data scientist I need to **predict the customer's near-term travel demand**, so that the recommendation reflects what's coming, not just the past.

> ⚠️ **Changed:** implemented as a **90-day** horizon (not 6 months), and it **uses calendar
> entries** (`user_calendars`) in addition to history — the original "history only, no calendar"
> scope no longer holds. Confidence is qualitative (`high`/`medium`/`low`), not a numeric interval.

**Acceptance Criteria**

- [x] Use last 12 months of history (+ prior year's final 3 months) to detect seasonal patterns
- [x] Incorporate upcoming calendar entries (ICS/RRULE-expanded) as demand drivers
- [x] Forecast demand over a 90-day horizon
- [x] Emit LLM demand scenarios with a deterministic seasonal **fallback**
- [x] Output: JSON with `forecast_horizon_days` + `scenarios[]` (label, expected trips, confidence)
**Definition of Done**

- Deterministic fallback is exercised by `backend/tests/test_forecasting.py`
- Forecast reasonably aligns with seasonal patterns (inspect via `GET /api/forecaster/{user_id}`)
- ⏳ Quantitative backtest (±20% on holdout) **not** implemented
**Estimated Effort**

- Estimated Days: 3 days

---

### Story 5: Per-Category Subscription Optimisation (Analyst + Optimization tool)

> ⚠️ **Superseded & rewritten.** The original story asked for 1–2 (then 3) portfolio *scenarios*
> with weighted ranking. That model was removed in the July refactor ("Logik war unsinnig").
> The system now compares, **per travel category**, the current subscription vs. the cheapest
> eligible catalog alternative vs. pay-as-you-go — no A/B/Green scenarios, no ranking weights.

As a data scientist, I need to determine the cheapest **per-category** subscription option for the customer's actual travel, so that I can recommend a concrete `keep` / `switch` / `drop` action.
**Acceptance Criteria**

- [x] Enumerate candidate plans (≤ one per category) over `subscription_catalogs`
- [x] Simulate annual cost of current sub vs. alternative vs. pay-as-you-go off real history
- [x] Respect catalog age-band eligibility (parsed from `subscription_type_other`)
- [x] Output: `category_subscription_analysis[]` with best option, action, and euro delta
- [x] Deterministic, pure function (`agent/engines/optimization.py`) — no LLM
**Definition of Done**

- Covered by `backend/tests/test_optimization.py` and `test_analysis.py`
- Manual review: recommended actions are sensible
**Estimated Effort**

- Estimated Days: 3 days

---

### Story 6: Calculate Cost & CO₂ (Analyst engine)

As a data scientist I need to **calculate annual cost and CO₂ from the travel history**, so that the recommendation and dashboard can quantify spend, emissions, and savings.

> ⚠️ Now computed once by the deterministic Analyst engine over the whole history (not "per
> scenario"). Exposed as `total_co2_kg`, `current_annual_spend_eur`, `savings_potential_estimate_eur`.

**Acceptance Criteria**

- [x] Cost from per-leg `estimated_cost_eur` + subscription fees vs. `reference_cost_eur` baseline
- [x] CO₂ from per-leg `estimated_co2_emissions`, aggregated by mode and total
- [x] Output: annual cost (€), total CO₂ (kg), estimated savings potential
**Definition of Done**

- Figures are deterministic and reproducible (number-guard)
- Unit tests pass (`test_analysis.py`)
**Estimated Effort**

- Estimated Days: 1 day

---

### Story 7: ~~Rank Scenarios~~ → Recommend a per-category action

> ⚠️ **Retired as written.** There are no scenarios to rank. The equivalent output is the
> `recommended_action` (`keep`/`switch`/`drop`) on each `category_subscription_analysis` entry,
> derived deterministically from the euro delta — not from user-weighted scoring. Onboarding
> priority scores (`score_money`/`score_emission`/`score_flexibility`) inform the LLM memo's
> framing, not a numeric scenario rank.

**Status:** folded into Stories 5–6; no separate ranking module.
**Estimated Effort**

- Estimated Days: 0 (removed)

---

### Story 8: Generate Recommendation Text (Communicator Agent)

As a data scientist I need to **generate conversational recommendation text using an LLM**, so that customers understand why we recommend a specific portfolio
**Acceptance Criteria**

- [ ] Input Customer profile, recommended scenario, trade-offs, user query
- [ ] Output: Natural language explanation (2-3 sentences) + Portfolio Savings Visualization
- [ ] Tone: Helpful, non-technical, transparent
- [ ] Include: Savings potential, key changes
**Definition of Done**

- LLM integration working via **University GPT** (`chat.kiconnect.nrw`, configured through `UNI_GPT_*`)
- Manual QA: sample memos sound good
- **Deterministic template memo** fallback when no LLM key (`memo_source` records the path)
- Lazy generation: fresh `/api/analyze` returns the template memo immediately; the LLM memo is
  produced as a background task and served on the next (cached) mount
**Estimated Effort**

- Estimated Days: 2 days

---

### Story 9: Capture User Approval (Communicator Agent)

As a data scientist I need to **implement a state machine for user approvals**, so that I can track whether users accept or reject recommendations
**Acceptance Criteria**

- [ ] States: pending → approved / rejected
- [ ] Store: user decision, timestamp, recommendation ID
- [ ] Optional: allow user to provide feedback ("Why did you reject?")
- [ ] Persist: in PostgreSQL for audit trail
**Definition of Done**

- State machine logic is correct (no invalid transitions)
- Database schema designed & tested
- Unit tests pass
**Estimated Effort**

- Estimated Days: 1 day

---

### Story 10: Orchestrate All Agents (Core System)

As a data scientist I need to wire the agents together in a coordinated flow, so that the system works end-to-end: data → analysis → recommendation
**Acceptance Criteria**

- [x] Analyze Flow: `user_id` → `load_context` → analyze (+ optimization tool) → forecast → communicate → persist `recommendations` row
- [x] Interaction Flow: chat query → agentic ReAct loop with catalogue tools → answer
- [x] Read-through cache: unforced `/api/analyze` reuses the latest recommendation; `force=true` recomputes
- [x] Graceful degradation: LLM-absent → template memo / scripted chat; DB retry on startup
- [x] Interaction tracing via **Langfuse** (full audit is the `recommendations` lifecycle + traces)
- [ ] ⏳ Scheduled 3-month "Update Flow" — **not** implemented
- [ ] End-to-end latency target: <30s (deferred LLM memo keeps the response fast)
**Definition of Done**

- E2E flow runs for the 6 seeded personas
- LLM/DB failure paths fall back cleanly
- ⚠️ Known open item: `orchestrator._shape_payload` still references removed optimizer variables
  after the July refactor — must be finished before the fresh-run path is green
**Estimated Effort**

- Estimated Days: 5 days

---

### Story 11: Build Monitoring Dashboard (Validation)

As a data scientist I need to **observe LLM calls and capture quality signals**, so that I can identify issues during the pilot.

> ⚠️ Delivered as **Langfuse tracing + score feedback**, not a custom metrics dashboard with
> alert thresholds. Every LLM call is traced; chat thumbs (`/api/feedback`) and recommendation
> approvals write scores back to the originating trace.

**Acceptance Criteria**

- [x] Trace every LLM call (memo + chat) with per-user attribution
- [x] Capture user thumbs up/down (`user-thumbs`) and approvals (`recommendation-accepted`)
- [x] Optional: no-op cleanly when Langfuse keys are absent
- [ ] ⏳ Latency/API-success alert thresholds — not implemented
**Definition of Done**

- Traces + scores visible in the Langfuse UI (`backend/eval/` provides an eval harness on top)
**Estimated Effort**

- Estimated Days: 2 days

---

### Story 12: Document System (Knowledge Transfer)

As a data scientist, I need to **document the architecture, API contracts, and troubleshooting, **so that the team can maintain and extend the system
**Acceptance Criteria**

- [ ] Architecture overview (4-page doc with diagrams)
- [ ] API contracts (each agent's input/output spec)
- [ ] Troubleshooting guide (common errors + fixes)
- [ ] Code comments (all major functions documented)
**Definition of Done**

- All docs written & reviewed
- Team can understand system from docs
- New team member could onboard using these docs
**Estimated Effort**

- Estimated Days: 2 days

---

### Story 13: Frontend User Interface

As a data scientist, I need to **present the findings to the user through a chatbot and optional dashboard, **so that the user can query for questions and look at their usage data 
**Acceptance Criteria**

- [ ] Chatbot interface in DB branding for simple Agent interaction
- [ ] Dashboard to have a visual overview on analyzed personal travel data
**Definition of Done**

- Chatbot reacts to user query, with very narrow guidelines on what to answer
- RealTime Dashboard showing travel history
**Estimated Effort**

- Estimated Days: 2 days

---

### Story 14: Create Traveller Personas

As a data scientist, I need to **design travel personas that represent common travel patterns and different needs regarding the agent system, **so that we can synthesize realistic travel history data and emulate real usage.

> ⚠️ **6** personas were built (not 5), each exercising one distinct path through the analyst/
> optimization logic. See [`database/seed/PERSONAS.md`](../database/seed/PERSONAS.md):
> Mara Vogel (flat-pass, well covered), Tobias Hahn (BahnCard 50, frequent business),
> Nina Schröder (pure pay-as-you-go), Lukas Weber (over-subscribed), Petra Sommer (thin data,
> new user), Sandra Hoffmann (family, car-sharing + flat pass).

**Acceptance Criteria**

- [x] Personas created with derived DB usage behaviour and 24 months of seeded trip/leg data
**Definition of Done**

- [x] Personas load into Postgres from `database/seed/*.csv` and drive the full pipeline
- ⏳ A generator that fans personas out into 100 synthetic profiles is **not** built; there are
  6 seeded users. "Tested against 100 profiles" in other stories is currently aspirational.
**Estimated Effort**

- Estimated Days: 1 day


---

## ACCEPTANCE CRITERIA: SUMMARY TABLE

Status: ✅ built · ⏳ partial / differs from original · ➖ retired

| Story | Must-Have | Status | Estimated Effort |
|-------|-----------|:------:|------------------|
| 1. Ingest History | Load seeded Postgres history (not a sandbox client) | ✅ | 2 days |
| 2. Detect Patterns | Pattern + inefficiency detection | ✅ | 3 days |
| 3. Calculate Cost | Deterministic annual cost | ✅ | 2 days |
| 4. Forecast Demand | 90-day, calendar-aware; qualitative confidence | ⏳ (no ±20% backtest) | 3 days |
| 5. Optimise Subscriptions | Per-category keep/switch/drop (replaced scenarios) | ✅ | 3 days |
| 6. Calculate Cost & CO₂ | Deterministic totals | ✅ | 1 day |
| 7. ~~Rank Scenarios~~ | Folded into per-category action | ➖ | 0 |
| 8. Generate Text | University GPT memo + template fallback | ✅ | 2 days |
| 9. Capture Approvals | Approval state on `recommendations` | ✅ (reject path thin) | 1 day |
| 10. Orchestrate Flow | E2E pipeline + cache | ⏳ (post-refactor bug open) | 5 days |
| 11. Observability | Langfuse tracing + feedback (not a metrics dashboard) | ⏳ | 2 days |
| 12. Documentation | Docs + README | ✅ | 2 days |
| 13. Frontend UI | React 18 + Vite chatbot + dashboard | ✅ | 2 days |
| 14. Traveller Personas | 6 seeded personas | ✅ (no 100-profile generator) | 1 day |


---

## PHASE 2+ BACKLOG (DEFER)

These are NOT in MVP; keep for future phases:

- ❌ Detailed CO₂ analysis beyond the aggregate totals Story 6 computes
- ❌ **Passive** life-event / email-signal detection (opt-in *calendar* IS in Phase 1 — Story 4)
- ❌ Production Partner API integration (Miles, Lime, Stadtrad)
- ❌ Live contract execution (no actual DB/partner API changes)
- ❌ "DB Wrapped" annual review dashboard
- ❌ Autonomous decisions (all changes require user approval)
- ❌ Redis caching / Weaviate vector search
- ❌ Scheduled periodic re-analysis ("Update Flow")

> Note: calendar integration was moved **into** Phase 1 and is no longer deferred.

---

## TESTING STRATEGY

### Unit Tests
- `backend/tests/`: `test_analysis.py`, `test_optimization.py`, `test_forecasting.py`,
  `test_memo.py`, `test_analyst_agent.py`, `test_schema_map.py`, `test_imports.py`
- Deterministic engines are the primary target (numbers must be reproducible)

### Integration / Eval
- `backend/eval/`: LLM-output eval harness (judges, fixtures, calibration)
- Inspection endpoints (`/api/analyst/{id}`, `/api/forecaster/{id}`) for manual E2E checks on the
  6 seeded personas

### Validation (manual)
- Recommendations reviewed for sensibility per persona
- ⏳ Quantitative accuracy targets (pattern 90%, forecast ±20%) are not formally measured yet

---

## SUCCESS CRITERIA (Prototype Phase)

| Criterion | Target | Validation |
|-----------|--------|-----------|
| **Stories delivered** | 12 built, 1 partial, 1 retired (see status table) | Code vs. acceptance criteria |
| **Number integrity** | Deterministic, reproducible euro/CO₂ figures | Unit tests on the engines |
| **Performance** | <30s E2E (deferred LLM memo) | Latency measurement (pending) |
| **Stability** | No crashes across the 6 seeded personas | Error logs clean |
| **Documentation** | Architecture + API contract current | Team can understand |

---

## NOTE: Backlog Refinement

This is your working backlog. As you build:
- Move stories from "MVP" → "In Progress" → "Done"
- Refine acceptance criteria as you learn (no big surprises expected)
- Adjust effort estimates after Sprint 1
- Surface blocking issues early (sandbox schema mismatches, data quality)
