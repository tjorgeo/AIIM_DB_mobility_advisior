# API Contract — DB MoveOptimizer Backend

**Status:** Living document. Last reconciled with the code **2026-07-08**.
Source of truth is the code itself: backend routes in [`backend/src/main.py`](../backend/src/main.py)
and [`backend/src/orchestrator.py`](../backend/src/orchestrator.py); frontend consumers in
`frontend/src/api/client.js`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/components/chat/useChat.js`.

> ⚠️ **Known divergence (open item).** The July refactor (commits `4d774e9`, `aaba999`)
> replaced the scenario-based Optimizer with a per-category subscription analysis inside the
> Analyst. The backend now emits `summary.category_subscription_analysis`, while the frontend
> `Dashboard.jsx` still reads `summary.scenarios` / `summary.recommended_scenario` and the
> analyst fields `current_annual_spend` / `co2_total_kg` (the engine emits
> `current_annual_spend_eur` / `total_co2_kg`). Backend and frontend must be reconciled before
> this contract can be "frozen" again. Both shapes are documented below; the ⏳ marks fields that
> are still in transition.

Base: same origin, proxied by Vite `/api` → backend `:8000`.
Store: docker **Postgres 16** (`db` service), schema auto-loaded from
[`database/init/*.sql`](../database/init). No SQLite, no Redis.

---

## Auth & onboarding

### `POST /api/login`
Authenticates a username **or** email against the seeded `users` table. Registered users
(created via `/api/register`) are checked against their own `password_hash`; seed personas that
carry no hash fall back to the shared demo password (`DEMO_LOGIN_PASSWORD`, default `mobility`).
```jsonc
// Request
{ "identifier": "julia.berger@example.com", "password": "mobility" }
// 200
{ "id": "ce92d8e0-065e-589b-a60e-c692ef2d2ff9", "name": "Julia Berger",
  "firstName": "Julia", "email": "…", "username": "…", "initials": "JB" }
// 401 { "detail": "Incorrect password." }
```

### `POST /api/register`
Persists a completed onboarding profile. Body: `{ user, onboarding, subscriptions, credentials }`
(see `register_endpoint.py`). Rate-limited. Resolves non-2xx with `{ "detail": "…" }`.

---

## `GET /api/personas`
Returns every user in the database, enriched with onboarding preferences and current
subscriptions (catalog-joined for readable names). Drives the demo persona picker.
```jsonc
[
  {
    "user_id": "ce92d8e0-065e-589b-a60e-c692ef2d2ff9",
    "first_name": "Julia", "last_name": "Berger", "name": "Julia Berger",
    "email": "…", "home_city": "Leipzig", "home_postal_code": "…",
    "age": 35, "gender": "female",
    "preferences": {                       // from user_onboardings (0-100 scores), or null
      "occupation": "Key Account Manager",
      "score_emission": 60, "score_money": 65, "score_flexibility": 60,
      "preferred_transport_modes": ["long_distance_train", "regional_train", "public_transport"],
      "mobility_budget_monthly_eur": 220.0
    },
    "subscriptions": [                      // user_subscriptions ⋈ subscription_catalogs
      { "provider_name": "Deutsche Bahn", "provider_plan_name": "Deutschlandticket",
        "monthly_cost_eur": 63.0, "subscription_status": "active",
        "is_primary_mobility_option": true }
    ]
  }
]
```
IDs are the four seeded persona UUIDs (see [`database/seed/PERSONAS.md`](../database/seed/PERSONAS.md)),
**not** the old `persona_max_commuter` string ids.

---

## `POST /api/analyze`
Runs the deterministic pipeline (`load_context → analyze → forecast → communicate`) for one
user. An unforced call reuses the user's most recent `recommendations` row (read-through cache);
a fresh run returns the deterministic numbers with the **template** memo immediately and
schedules the slow LLM memo as a background task, so the next mount serves the upgraded prose.
```jsonc
// Request
{ "user_id": "ce92d8e0-065e-589b-a60e-c692ef2d2ff9", "force": false }
```
```jsonc
// Response envelope (stable fields)
{
  "session_id": "<uuid>",                  // == recommendations.recommendation_id; used by /approve
  "status": "ready",
  "timestamp": "2026-07-08T…",
  "user_id": "ce92d8e0-…",
  "customer_name": "Julia Berger",
  "db_customer_id": "ce92d8e0-…",
  "preferences": { … },                    // onboarding scores
  "current_subscriptions": [ … ],
  "summary": {
    // ⏳ POST-PIVOT shape the backend now builds (orchestrator.py):
    "total_actual_annual_cost_eur": 696.0,
    "total_co2_kg": 206.0,
    "total_estimated_savings_eur": 0.0,
    "category_subscription_analysis": [      // per-category current vs. alternative vs. pay-as-you-go
      { "category": "public_transport", "actual_annual_cost_eur": 696.0,
        "best_option": "…", "recommended_action": "keep", "…": "…" }
    ],
    "memos": { "english": "<markdown>", "german": "<markdown>" }
    // ⏳ LEGACY shape the frontend still reads (to be removed or re-added):
    //   "recommended_scenario": "A", "scenarios": [ { id, label, annual_cost, annual_savings,
    //   co2_savings_kg, changes:[{action,item}] } ]
  },
  "raw_agent_payloads": {
    "analyst":   { "input": {…}, "output": { /* see below */ } },
    "forecaster":{ "input": {…}, "output": { "forecast_horizon_days": 90, "scenarios": [ … ] } },
    "communicator":{ "input": {…}, "output": { "memo_english": "…", "memo_german": "…",
                     "memo_source": "template|llm|template_fallback", "total_estimated_savings_eur": 0.0,
                     "actions_required": [ … ] } }
  }
}
```
`raw_agent_payloads.analyst.output` (deterministic engine, `analysis.py`):
```jsonc
{
  "total_trips": 468,
  "total_distance_km": 28641.6,
  "total_co2_kg": 229.1,
  "current_annual_spend_eur": 696.0,
  "mode_breakdown": { "public_transport": { "trips": 420, "cost": …, "distance_km": …, "co2_kg": … } },
  "category_subscription_analysis": [ … ],
  "inefficiencies": [ { "type": "…", "service": "…", "annual_waste": 0.0, "details": "…" } ],
  "savings_potential_estimate_eur": 0.0,
  "forecaster_summary": { … }              // handed to the forecaster
}
```
Errors: `404` when the user id is unknown; `500` on any pipeline exception.

## `POST /api/recommendations/{session_id}/approve`
Records approval on the `recommendations` row and (best-effort) writes a
`recommendation-accepted` score to the memo's Langfuse trace.
```jsonc
// Request { "scenario_id": "A" }
// 200 { "status": "success", "message": "…", "recommendation_id": "…", "scenario_id": "A" }
// 404 when the session id is unknown
```

## `POST /api/chat`  — **implemented**
Conversational advisor: an agentic ReAct loop with catalogue tool use (`communicator_agent.run_chat`).
```jsonc
// Request { "user_id": "…", "messages": [ { "role": "user|assistant", "content": "…" } ] }
// 200     { "reply": "<assistant text>", "trace_id": "<langfuse id | null>" }
// 503     when no LLM key is configured → useChat.js falls back to its scripted assistant
```

## `POST /api/feedback`
Attaches a chat thumbs up/down to a Langfuse trace. No-op (still `200`) when tracing is disabled.
```jsonc
// Request { "trace_id": "…", "value": 1, "comment": "…" }   // value: 1 = up, 0 = down
// 200     { "status": "ok" }
```

## Inspection endpoints (not consumed by the UI)
- `GET /api/analyst/{user_id}` — runs the Analyst alone and returns its full output.
- `GET /api/forecaster/{user_id}?forecast_horizon_days=90&as_of_date=YYYY-MM-DD` — runs
  `load_context → analyze → forecast`, stopping before communicate.
- `POST /api/forecaster/test` — runs the forecaster against a supplied `analyst_summary` /
  calendar payload (see `ForecasterTestRequest` in `main.py`).

---

### Current engineering decisions
- **Engine:** LangGraph + LLM (University GPT / kiconnect.nrw, OpenAI-compatible) behind a
  deterministic number-guard pipeline. All euro/CO₂ figures come from the deterministic engines;
  the LLM only writes prose.
- **API shell:** FastAPI (`backend/`).
- **Store:** docker Postgres 16 (`db`). Schema in `database/init/*.sql`, seeded from
  `database/seed/*.csv`.
- **Persona ids** are the seeded UUIDs in `database/seed/PERSONAS.md`.
- **Observability:** Langfuse traces every LLM call; optional (no keys → no-op).
