# DB MoveOptimizer - Technical Architecture
## 4-Agent System Design for Prototype Phase

**Version:** 1.1 (Prototype) | **Date:** May 20, 2026 · **Last reconciled with code:** 2026-07-08  
**Audience:** Data Scientists, Engineers  
**Scope:** MVP Phase (Weeks 1-16); Phase 2+ sections deferred

> **v1.1 reconciliation note.** Sections below have been corrected against the running code.
> The biggest changes since v1.0: the LLM/framework is **University GPT (kiconnect.nrw) via
> LangGraph** (not Claude 3.5 via LangChain); the per-category subscription **optimization is
> computed inside the Analyst engine** (`analysis.py::analyze_portfolio` →
> `category_subscription_analysis`) — the separate scenario-generating optimizer was removed, and
> a constraint-aware re-optimizer (`engines/reoptimize.py`) now backs the chat feedback loop; the
> Forecaster runs a 90-day, **calendar-aware** horizon; and persistence is **docker Postgres 16
> only** (no Redis, no Weaviate, no SQLite). The "sandbox API" is realised as seeded Postgres data, not a live HTTP
> gateway.

---

## SYSTEM OVERVIEW

**Sequential pipeline, 3 agents + 1 embedded tool.** The v1.0 "3 parallel agents fanning into a
Communicator" topology was never built. The real flow is a plain sequential Python pipeline
(`agent/pipeline.py`); the Optimizer is a deterministic **tool called inside the Analyst**, not a
peer agent. Two entry points share the engine: `/api/analyze` (the pipeline) and `/api/chat` (an
agentic ReAct loop that reuses the Communicator + catalogue tools).

```
                 User (React 18 + Vite: dashboard + chat)
                    │                         │
        POST /api/analyze            POST /api/chat
                    │                         │
        ┌───────────▼─────────────────────────▼───────────┐
        │ FastAPI (main.py)  +  Orchestrator               │
        │ • read-through cache (latest recommendations row)│
        │ • persistence + approval  • lazy background memo │
        └───────────┬─────────────────────────┬───────────┘
                    │ (fresh run)              │ (chat)
   ┌────────────────▼──────────────────────┐   │
   │ Pipeline (pipeline.py) — sequential   │   │
   │                                       │   │
   │  load_context                         │   │
   │      │  (Postgres: user, subs,        │   │
   │      ▼   trips/legs, catalog, cal.)   │   │
   │  ┌───────────────────────┐           │   │
   │  │ Analyst (analysis.py)  │           │   │
   │  │  incl. per-category    │           │   │
   │  │  optimization (inline) │           │   │
   │  └────┬───────────────────┘           │   │
   │       ▼                               │   │
   │  ┌────────────┐                       │   │
   │  │ Forecaster │ (90-day, calendar-    │   │
   │  │(forecasting│  aware; LLM + det.    │   │
   │  │   .py)     │  seasonal fallback)   │   │
   │  └────┬───────┘                       │   │
   │       ▼                               │   │
   │  ┌──────────────┐                     │   │
   │  │ Communicator │ template memo now,  │   │
   │  │ (memo.py +   │◀── LLM memo upgrade │◀──┘  ReAct loop: catalogue +
   │  │ communicator)│    (background task)│      tariff-doc + reoptimize tools
   │  └──────┬───────┘                     │      (chat → optimizer loop)
   └─────────┼─────────────────────────────┘
             ▼
   Response → dashboard / chat reply → [Approve]
             │
   ┌─────────▼───────────────────────────────────────────┐
   │ Cross-cutting: Postgres 16 (state) · University GPT  │
   │ (LLM, optional) · Langfuse (tracing + feedback)      │
   └─────────────────────────────────────────────────────┘
```

Agents that use the LLM (Forecaster, Communicator) each have a deterministic fallback, so the
whole system runs with no LLM key configured. Every euro/CO₂/trip number comes from the
deterministic engines, never the LLM.

---

## COMPONENT DETAILS

### 1. Analyst Agent
**Purpose:** Analyze the travel history; identify patterns, inefficiencies, and the best
per-category subscription option

**Input** (from `load_context`, all Postgres):
- Travel history (trip + leg level, with `estimated_cost_eur` / `reference_cost_eur` / CO₂)
- Current subscriptions and the `subscription_catalogs` pricing table
- User age (for age-gated catalog eligibility)

**Process:**
- Aggregate trips: `mode_breakdown`, totals (trips / distance / CO₂ / current annual spend)
- Call the **Optimization tool** for the per-category current-vs-alternative-vs-PAYG comparison
- Flag inefficiencies and estimate savings potential
- Emit a `forecaster_summary` (dominant patterns + seasonality) for the next step

**Output** (`agent/engines/analysis.py::analyze_portfolio`, abbreviated):
```json
{
  "total_trips": 468,
  "total_distance_km": 28641.6,
  "total_co2_kg": 229.1,
  "current_annual_spend_eur": 696.0,
  "mode_breakdown": { "public_transport": { "trips": 420, "cost": 660.0, "distance_km": 27000.0, "co2_kg": 210.0 } },
  "category_subscription_analysis": [ { "category": "public_transport", "recommended_action": "keep", "savings_eur": 0.0 } ],
  "inefficiencies": [ { "type": "…", "service": "…", "annual_waste": 0.0 } ],
  "savings_potential_estimate_eur": 0.0,
  "forecaster_summary": { }
}
```

**Tech Stack:**
- Pure-Python deterministic engine (`agent/engines/analysis.py`) — no scikit-learn clustering
- DB: PostgreSQL (travel history + catalog)
- The per-category subscription comparison is computed inline (`_build_category_entry`), not via
  a separate module

---

### 2. Forecaster Agent
**Purpose:** Predict demand for next 6 months

**Input:**
- Historical travel patterns (12-month data from Analyst)
- Calendar events (optional, if user shared)
- Seasonal patterns detected from history

**Process:**
- Uses the last 12 months of history (with the prior year's final 3 months for seasonal signal)
- Detect seasonality: summer/winter cycles, recurring commute patterns
- Forecast demand over a **90-day** horizon
- Incorporates the user's upcoming **calendar entries** (`user_calendars`, ICS/RRULE-expanded)
- LLM-generated demand scenarios with a **deterministic seasonal fallback** (numbers stay guarded)

**Output** (`agent/engines/forecasting.py::forecast`):
```json
{
  "forecast_horizon_days": 90,
  "scenarios": [
    { "label": "…", "expected_trips": 24, "confidence": "high",
      "drivers": ["seasonal winter uptick", "calendar: Munich trip 2026-07-15"] }
  ]
}
```
Confidence is qualitative (`high` | `medium` | `low`), not a numeric interval.

**Tech Stack:**
- Deterministic seasonal engine (pure Python) as the guaranteed fallback
- LLM reasoning over patterns + calendar via University GPT (see Tech Stack Decisions)
- ICS parsing (`icalendar`) and RRULE expansion (`python-dateutil`) for calendar entries

**Note:** calendar integration is **implemented** in Phase 1 (opt-in seed data). Passive email /
life-event signal mining remains deferred to Phase 2.

---

### 3. Optimizer (deterministic logic inside the Analyst, not a standalone agent)
**Purpose:** Price the best subscription option per travel category against the user's real history

> **Changed since v1.0.** The scenario A/B generator + weighted ranking was removed (July
> refactor: "Logik war unsinnig"), and the standalone `optimization.py` module was later deleted
> as dead code. The per-category comparison now lives **inside** the Analyst engine
> (`analysis.py::analyze_portfolio`, built by `_build_category_entry` into
> `category_subscription_analysis`). A separate **constraint-aware re-optimizer**
> (`engines/reoptimize.py`) re-derives that verdict under user constraints and backs the chat
> feedback loop (see Communicator). There is no separate Optimizer agent in the pipeline.

**Input:**
- The user's travel history (per-leg `estimated_cost_eur` and `reference_cost_eur`)
- Current subscriptions
- `subscription_catalogs` (all plans, priced; age-band eligibility parsed from free text)

**Process (per travel category):**
1. Enumerate candidate portfolios (≤ one plan per category) over the catalog
2. Simulate the annual cost of each against the actual trips
3. Compare **current subscription vs. cheapest eligible alternative vs. pay-as-you-go**
4. Emit a `keep` / `switch` / `drop` recommendation with the euro delta — never a "holding a plan
   makes the category free" assumption (see `_pricing_basis`)

**Output** (`category_subscription_analysis`, one entry per category):
```json
{
  "category": "public_transport",
  "actual_annual_cost_eur": 696.0,
  "best_option": "Deutschlandticket",
  "recommended_action": "keep",
  "alternative_annual_cost_eur": 696.0,
  "savings_eur": 0.0
}
```

**Tech Stack:**
- Deterministic catalog enumeration + simulation (pure Python, no LLM, no I/O)
- Age-band eligibility parsed from `subscription_type_other` free text

---

### 4. Communicator Agent
**Purpose:** Present recommendations; run the chat; capture user approval

**Input:**
- The Analyst's `category_subscription_analysis` + totals and the Forecaster's demand outlook
- The pricing catalog (with `markdown_ref` tariff docs the memo can cite)
- User context (onboarding priority scores, language)

**Process:**
1. Build the deterministic **template memo** immediately (English + German)
2. Upgrade the memo prose with one grounded LLM call (background task); fall back to the template
   on any failure. `memo_source` records which path was taken.
3. Chat path (`/api/chat`): agentic **ReAct loop** with catalogue, tariff-doc, and **`reoptimize`**
   tools. The last closes the **chat → optimizer feedback loop**: when the user asks for changes
   ("keep my car", "drop the BahnCard", "switch to the Deutschlandticket"), the LLM parses the
   wish into constraints and calls `reoptimize` (`agent/tools/optimize.py` →
   `engines/reoptimize.py`), which re-derives the per-category verdict **deterministically** from
   the Analyst's already-priced alternatives — numbers stay engine-grounded. With `apply=true`
   (only on explicit user confirmation) it persists a new `recommendations` row so the dashboard
   reflects the revision.
4. Capture the user decision (approve) and persist approval state + Langfuse score

**Output (memo, abbreviated):**
```
"Ich habe deine Reisen analysiert. Dein Deutschlandticket passt zu deinem
 Pendelverhalten — du nutzt es an fast jedem Werktag, kein Sparpotenzial offen.
 Empfehlung: aktuellen Tarif behalten."   (+ English version; both markdown)

User Decision: [Approve]
```

**Tech Stack:**
- LLM: University GPT (kiconnect.nrw, OpenAI-compatible) for memo + chat generation
- Memo path: one grounded LLM call over already-computed numbers, with a deterministic
  **template memo** fallback (`agent/engines/memo.py::template_memos`) if the LLM is absent/errors
- Chat path: agentic **ReAct loop** with catalogue tool use (`communicator_agent.run_chat`)
- Approval state persisted in the `recommendations` table; the memo's Langfuse `trace_id` links
  approval/feedback back to the exact generation
- UI: React 18 + Vite chat widget + dashboard

---

## DATA FLOW (HAPPY PATH)

The pipeline is plain sequential Python (`agent/pipeline.py`), not a routed state graph:
`load_context → analyze → forecast → communicate`.

```
1. User logs in → Dashboard mounts → POST /api/analyze { user_id }

2. Orchestrator cache check:
   ├─ unforced → reuse the user's latest `recommendations` row (read-through cache) and return
   └─ force=true OR no prior row → run a FRESH pipeline:

3. load_context(user_id): pull user, onboarding prefs, subscriptions, 24-month trip/leg
   history, pricing catalog, and calendar entries from Postgres.

4. analyze (deterministic engine, analysis.py):
   ├─ mode_breakdown, total_trips/distance/CO₂, current_annual_spend
   ├─ category_subscription_analysis  ← calls the optimization tool (catalog enumeration)
   ├─ inefficiencies + savings_potential_estimate
   └─ forecaster_summary (dominant patterns + seasonality)

5. forecast (forecasting.py):
   ├─ consume forecaster_summary + upcoming calendar entries
   ├─ LLM demand scenarios (90-day horizon) OR deterministic seasonal fallback
   └─ Return: demand scenarios

6. communicate:
   ├─ template memo (deterministic) built immediately  ← fresh run returns here
   └─ background task: one grounded Analyst LLM call upgrades the memo prose (memo_source→"llm");
      next cached mount serves it. Falls back to template on any LLM failure.

7. Persist one `recommendations` row (analyst/forecaster/optimizer JSON + memo_trace_id).

8. USER APPROVES (POST /api/recommendations/{id}/approve):
   ├─ update row → analysis_status='approved', selected_scenario_id, approved_at
   └─ best-effort Langfuse `recommendation-accepted` score on the memo trace

Latency target: <30s end-to-end (fresh run returns deterministic numbers immediately;
the LLM memo is deferred to a background task).
```

---

## DATA STORAGE

**Authoritative schema:** [`database/init/01_create_table.sql`](../database/init/01_create_table.sql).
Store is **docker Postgres 16** (`db` service). The summary below tracks the real tables; consult
the SQL for exact columns and CHECK constraints.

### PostgreSQL tables (as implemented)

| Table | Role | Notable columns |
|-------|------|-----------------|
| `users` | Person + account | `user_id` (TEXT PK), `email`, `username`, `password_hash`, `first_name`, `last_name`, `age`, `gender`, `home_city`, `home_postal_code`. Case-insensitive unique partial indexes on `email`/`username`. |
| `user_onboardings` | Preferences & context | `score_emission`, `score_money`, `score_flexibility` (0-100), `preferred_transport_modes[]`, `mobility_budget_monthly_eur`, employment/household fields, `travel_statement`, `activity_statement`, `connected_mobility_accounts[]` (persisted status of simulated provider connections). |
| `subscription_catalogs` | Product catalog | `subscription_id` PK, `provider_name`, `provider_plan_name`, `subscription_category` (public_transport/bike_sharing/car_sharing/e_scooter), `pricing_model`, `monthly_cost_eur`, `annual_cost_eur`, `markdown_ref` (tariff doc). |
| `user_subscriptions` | Held plans | FK to `users` + `subscription_catalogs`, `valid_from/until`, `subscription_status` (active/inactive/paused/cancelled/expired), `status_changed_at`, `is_primary_mobility_option`, `estimated_usage_frequency`. Profile editing reads active and historical rows but never mutates them. |
| `user_trips` | Trip-level history | `main_transport_mode` (CHECK enum), `trip_purpose`, `estimated_distance_km`, `is_commute`/`is_intermodal`/`is_recurring_pattern`. |
| `trip_legs` | Leg-level history | `transport_mode` (CHECK enum — regional vs. long-distance rail encoded directly, AMB-01), `estimated_cost_eur`, `reference_cost_eur` (pay-as-you-go baseline), `estimated_co2_emissions`, `ticket_class`, `user_subscription_id` (set only when the leg is actually covered). |
| `user_calendars` | iCalendar events | Full VEVENT model: `dtstart/dtend`, `summary`, `rrule`/`rdate`/`exdate`, `location`, etc. Consumed by the Forecaster. (Note: a legacy stub table `user_calenders` also exists in the SQL — `user_calendars` is the one in use.) |
| `recommendations` | Analysis runs & approvals | `analyst_output`, `forecaster_output`, `optimizer_scenarios` (all JSON TEXT), `analysis_status` (analysing/ready/presented/approved/rejected/executed), `selected_scenario_id`, `approved_at`, `memo_trace_id`, `created_at`. The `optimizer_scenarios` column name is retained to avoid a migration; it now stores the per-category analysis payload, not scenario objects. |

There is **no** separate `audit_log` table; the audit trail is the `recommendations` row lifecycle
plus Langfuse traces/scores.

### Not implemented in Phase 1
- **Redis** — no container. The read-through cache is simply the latest `recommendations` row;
  session state is the row id returned to the frontend. (Redis remains a Phase-2 target.)
- **Vector store (Weaviate)** — not used. Tariff docs are retrieved by direct `markdown_ref`
  lookup, not embeddings.

---

## DATA SOURCES

### "Sandbox" travel history — seeded Postgres, not a live gateway
The v1.0 plan called for a simulated `GET /v1/sandbox/travel-history` HTTP gateway. It was
**not built as an HTTP service**. Instead the sandbox is realised as **seeded Postgres data**:
`database/seed/*.csv` (trips, legs, subscriptions, onboardings, calendars) loaded by
`database/init/02_insert_data.sql`, and read through `agent/context.py::load_context`. This
still meets the goal — high-fidelity synthetic data matching the target schema — without a
network hop, so the retry/backoff/"API down" fallbacks below are not applicable in Phase 1.

The trip data spans a fixed 24-month window (2024-07-01 → 2026-06-29) with two summer/winter
cycles so seasonality detection has real signal.

### Google Maps API
Not used. Distances come from seeded `estimated_distance_km`. (Phase 2 candidate.)

### Pricing / tariff catalog — `subscription_catalogs` table
The pricing catalog is the `subscription_catalogs` Postgres table (see schema above), not a JSON
blob. Each row carries `monthly_cost_eur`/`annual_cost_eur`, a `subscription_category`, and a
`markdown_ref` pointing at the tariff document under `data/Markdownfiles Abos/`, which the
Analyst's grounded LLM memo call can cite. The optimization tool prices every candidate plan off
this table.

---

## TECH STACK DECISIONS

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.11+ | Team expertise; ML libraries; agent frameworks |
| **Agent Framework** | LangGraph (+ `langchain-openai`, `langchain-core`) | Graph/tool orchestration for the agentic chat + memo loop |
| **LLM** | University GPT — kiconnect.nrw, GPT-OSS-120b (OpenAI-compatible) | Provided endpoint; configured via `UNI_GPT_*` env. Degrades gracefully to templates when absent |
| **Web Framework** | FastAPI | Async support; type safety; auto-generated docs |
| **Database** | PostgreSQL 16 (docker) | Relational data; the only store in Phase 1 |
| **Observability** | Langfuse | Traces every LLM call; user thumbs + approval scores. Optional (no keys → no-op) |
| **Cache** | None (Redis deferred to Phase 2) | Read-through cache is the latest `recommendations` row |
| **Vector DB** | None (Weaviate deferred to Phase 2) | Tariff docs retrieved by `markdown_ref`, not embeddings |

Not used despite earlier mentions: LangChain agents (superseded by LangGraph), Claude/Gemini,
Prophet/ARIMA/statsmodels, scikit-learn clustering, Redis, Weaviate, SQLite.

---

## ERROR HANDLING & RESILIENCE

### Data source failures
Travel history / subscriptions / catalog live in Postgres (not a remote API), so the v1.0
gateway-down fallbacks don't apply in Phase 1. The relevant resilience is DB connectivity:
`database.py::get_connection` retries the Postgres connection on startup (compose `depends_on`
doesn't wait for readiness).

### Agent / LLM failures
- **LLM absent or errors (memo):** fall back to the deterministic template memo; `memo_source`
  records `template` / `llm` / `template_fallback`.
- **LLM absent (chat):** `/api/chat` returns `503` and the frontend uses its scripted assistant.
- **Forecaster LLM fails:** fall back to the deterministic seasonal forecast.
- **Optimization:** pure deterministic function — no timeout path; it always returns a result.

### Data Quality Issues
- **Missing travel data:** Log gaps; flag customer for manual review
- **Cost inconsistencies:** Use best-estimate; show confidence intervals
- **API data format changes:** Add schema validation; fail loudly

---

## KEY DECISIONS (Architecture Decision Records)

### ADR-1: Multi-Agent Decomposition (as a sequential pipeline)
**Decision:** Decompose into Analyst → Forecaster → Communicator, with Optimization as a
deterministic tool the Analyst calls — rather than a single monolithic agent.

> **Revised since v1.0.** The original ADR listed 4 peer agents run partly in parallel. In
> practice the flow is **sequential** (`load_context → analyze → forecast → communicate`) because
> the Forecaster consumes the Analyst's `forecaster_summary` and the Optimizer is an in-Analyst
> tool, so there is no independent branch to parallelize. "4 agents" is a conceptual framing;
> topologically it's 3 pipeline steps + 1 embedded tool.

**Rationale:**
- ✅ Separation of concerns (each step has a clear responsibility and its own tests)
- ✅ Deterministic engines are independently unit-testable
- ✅ Reusability (the Communicator + catalogue tools also power `/api/chat`)

---

### ADR-2: Synchronous Flow vs. Async/Event-Driven
**Decision:** Synchronous orchestration (user waits) vs. async (notification after analysis).

**Rationale:**
- ✅ Better UX (user gets immediate feedback)
- ✅ Simpler error handling (know result right away)
- ✅ MVP doesn't need long-running async (16-week timeline)

**Tradeoff / mitigation:** to keep the synchronous response fast, the fresh run returns the
deterministic numbers + template memo immediately and defers the slow LLM memo to a background
task (latency target <30s).

---

### ADR-3: LLM for Natural Language, with a deterministic template fallback
**Decision:** Use the University GPT endpoint for memo + chat prose; keep a deterministic
template memo as the guaranteed fallback. (Provider changed from the v1.0 "Claude API".)

**Rationale:**
- ✅ More natural, personalized explanations
- ✅ Template fallback keeps the app fully functional with no LLM key
- ✅ Numbers never come from the LLM — only prose — so figures stay exact

**Risk / mitigation:** LLM failures fall back to the template memo (`memo_source` records which
path was taken); the lazy background-memo design keeps the fresh response fast.

---

### ADR-4: Deterministic number-guard, LLM for prose only
**Decision:** All euro/CO₂/trip figures are produced by pure deterministic engines
(`analysis.py`, `optimization.py`, `forecasting.py` fallback). The LLM is confined to writing the
memo and driving the chat tool loop.

> Supersedes the v1.0 "greedy vs. linear programming" ADR. Optimization is a deterministic
> catalog-enumeration tool; there is no greedy/LP scenario solver and no weighted scenario
> ranking. The per-category `keep/switch/drop` analysis replaced scenario generation entirely.

**Rationale:**
- ✅ Reproducible, auditable numbers (the "number guard")
- ✅ LLM output can be validated against the deterministic figures
- ✅ Simpler to test than a scenario solver

---

## WHAT'S DEFERRED TO PHASE 2

❌ **Deployment & Infrastructure** (AWS EKS, load balancing, CDN)  
❌ **Redis caching & Weaviate vector search**  
❌ **Passive life-event detection** (email/behavioral signals — opt-in *calendar* IS in Phase 1)  
❌ **Live contract execution via partner APIs** (analysis only in Phase 1)  
❌ **Live DB Navigator production API** (seeded synthetic data in Phase 1)  
❌ **Production Security & Compliance** (defer to hardening phase)  

---

## IMPLEMENTATION STATUS (2026-07-08)

**Done:** Postgres schema + seed (6 personas), `load_context`, deterministic Analyst
(incl. `category_subscription_analysis` and the optimization tool), calendar-aware Forecaster,
template + LLM memo with lazy background upgrade, agentic chat, login/registration/onboarding,
Langfuse observability + feedback scoring, read-through cache, backend test suite + eval harness,
React 18 + Vite dashboard/chat UI, docker-compose (backend + frontend + Postgres).

**Open items:**
- [ ] Reconcile `/api/analyze` `summary` shape with the frontend (scenarios vs.
      `category_subscription_analysis`) — see [API_CONTRACT.md](API_CONTRACT.md).
- [ ] Finish the July optimizer→category-analysis refactor in `orchestrator.py`
      (`_shape_payload` currently references removed variables) and align frontend field names
      (`current_annual_spend_eur`, `total_co2_kg`).
- [ ] Hit the <30s p95 latency target under measurement.
