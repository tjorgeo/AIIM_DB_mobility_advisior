# Backend Merge Report — DB MoveOptimizer

**Date:** 2026-06-21
**Goal:** Consolidate the three existing backends into one service that is (a) the **agentic LangGraph engine** the product needs, and (b) the **session/user API** the frontend already talks to. Frontend and database are treated as fixed.

---

## 1. TL;DR / Recommendation

There are not really "three backends." There is:

- **`backend/`** — an **empty Docker placeholder** (the integration shell that `docker-compose` builds and runs). It contains no code today; its log shows it previously ran `backend_tjorge`'s code.
- **`backend_tjorge/`** — a **working FastAPI service** that the frontend was built against. Its 4 "agents" are **deterministic Python** (no LLM, no LangGraph).
- **`backend_maike/`** — the **real agentic LangGraph engine** (LLM + tool use + onboarding), but it has **no HTTP API** and emits **free-form prose**, not the structured JSON the frontend needs.

**Recommended path: keep `backend_tjorge` as the API/contract shell, transplant `backend_maike`'s LangGraph intelligence into it, and fill the empty `backend/` folder with the result.** Do it in phases so the frontend never breaks. The single hardest problem is **bridging free-form LLM output → the exact structured JSON the frontend consumes**; that is the work, not the plumbing.

---

## 2. What each backend actually is

### 2.1 `backend/` — Docker placeholder (no code)

| Aspect | Finding |
|---|---|
| `src/main.py` | **0 bytes** (empty) |
| `requirements.txt` | **empty** |
| `backend.log` | Shows a prior run serving `POST /api/analyze` and `POST /api/recommendations/{id}/approve`, seeding 5 personas / 687 trips — i.e. it was running `backend_tjorge`'s code |
| Role | This is the service `docker-compose.yml` builds (`context: ./backend`, `CMD python src/main.py`, port 8000) |

**Conclusion:** `backend/` is the deployment target/integration slot, not a third implementation. The merge result should land here.

### 2.2 `backend_tjorge/` — the frontend's API backend (deterministic)

- **Stack:** FastAPI + Uvicorn, CORS open, lifespan auto-seeds on startup. Deps: `fastapi`, `uvicorn`, `pydantic` only.
- **DB:** its own SQLite `mobility_advisor.db`. Schema: `users`, `travel_history`, `subscriptions`, `recommendations`, `audit_log`, `pricing_catalog` (9 products).
- **Endpoints (exactly match `frontend/src/api/client.js`):**
  - `GET /api/personas`
  - `POST /api/analyze` `{ user_id }`
  - `POST /api/recommendations/{rec_id}/approve` `{ scenario_id }`
  - *(`POST /api/chat` is **not** implemented — the chat widget falls back to a scripted client-side assistant.)*
- **"Agents" (`agents/`):** `AnalystAgent`, `ForecasterAgent`, `OptimizerAgent`, `CommunicatorAgent` — all **plain deterministic Python**. The optimizer brute-forces a fixed list of BahnCard/DT/Miles portfolios; the communicator fills **hardcoded bilingual memo templates**. No LLM, no LangGraph, no tool use.
- **Output contract (what the frontend reads):**
  ```
  session_id
  summary.scenarios[] { id, label, annual_cost, annual_savings, co2_impact_kg, co2_savings_kg, changes[]{action,item}, explanation }
  summary.recommended_scenario        ("A" | "B")
  summary.memos.{english, german}
  raw_agent_payloads.analyst.output   { mode_breakdown, inefficiencies[], total_trips, ... }
  ```
- **Persona alignment:** persona IDs (`persona_max_commuter`, `persona_clara_consultant`, …) and `db_customer_id`s **match `frontend/src/data/personas.js` exactly.** This is unambiguously the backend the frontend was built for.

**Strengths:** end-to-end working with the UI, fast, deterministic, no API key, persists approvals + audit trail.
**Weaknesses:** not agentic, not LLM, hardcoded heuristics, tiny 9-product catalogue, separate SQLite schema, ignores the "final" Postgres DB.

### 2.3 `backend_maike/` — the agentic LangGraph engine (no API)

- **Stack:** LangGraph + LangChain + `langchain-openai` against **University GPT** (`https://chat.kiconnect.nrw/api/v1`, model `Openai GPT OSS 120B`), key `UNI_GPT_API_KEY`. Run via **LangSmith Studio / `langgraph dev`**, declared in `langgraph.json`.
- **DB:** its own SQLite `moveoptimizer.db`, richer schema (`users`, `trips`, `trip_legs`, `subscription_products` with **56 products**, `user_subscriptions`, `recommendations`). Shared via `db/db_utils.py`. This schema mirrors the synthetic `data_generator/` output and is the closest of the three to the "final" Postgres schema.
- **Four graphs (`langgraph.json`):**
  - `onboarding` — multi-turn conversational profile collection → **persists** profile + subscriptions to DB.
  - `travel_analyst` — single-user travel-pattern analysis.
  - `analyst_optimizer_pipeline` — `load_context → analyst → optimizer ⇄ tools` (ReAct loop with `lookup_subscriptions` tool).
  - `analyst_forecaster_pipeline` — analyst **and** forecaster run in **parallel**, fan-in `combine`, then optimizer ReAct loop.
- **Genuinely agentic:** ReAct tool calling, parallel fan-out/fan-in, conversational memory via `add_messages`.

**Strengths:** real LLM reasoning + tool use, 56-product catalogue, onboarding agent, forecasting, aligned with the data generator and final DB design.
**Weaknesses:** **no HTTP server / no `/api/*` contract**; output is **free-form prose** (`messages[-1].content`), not the structured JSON the UI needs; no approval endpoint; non-deterministic; needs an API key; built for Studio, not production serving.

---

## 3. The three-way divergence (the real obstacle)

| Concern | `backend_tjorge` | `backend_maike` | "Final" DB (`database/init`, docker `db`) |
|---|---|---|---|
| Engine | DB query → uvicorn | PostgreSQL 16 | PostgreSQL 16 |
| Store | SQLite `mobility_advisor.db` | SQLite `moveoptimizer.db` | Postgres (init SQL) |
| User table | `users` (JSON prefs) | `users` (flat columns) | `user_information` (rich) |
| Trips | `travel_history` (flat) | `trips` + `trip_legs` | `user_trips` + `trip_legs` (rich) |
| Catalogue | `pricing_catalog` (9) | `subscription_products` (56) | `subscription_catalogs` (**stub: id/name/city**) |
| Recommendations | `recommendations` + `audit_log` | `recommendations` | `recommendations` (**stub: id/name/city**) |
| API | ✅ matches frontend | ❌ none | n/a |
| Intelligence | ❌ deterministic | ✅ LLM + tools | n/a |

Three problems fall out of this table:

1. **No single backend has both the API and the intelligence.** tjorge has the API, maike has the brains.
2. **Three different schemas.** Worse: neither backend uses the "final" Postgres DB at all (both use local SQLite).
3. **The "final" Postgres DB is only half-final.** `user_information` / `user_trips` / `trip_legs` / `user_subscriptions` are well-designed, but `subscription_catalogs`, `recommendations`, `kpis`, `user_preferences`, `user_calenders` are **placeholder stubs** (`id, name, city`). So the recommendation/catalogue side of the "final" DB still needs real tables before a merged backend can persist to it.

---

## 4. Target architecture

```
                      ┌─────────────────────────────────────────────┐
   frontend (fixed) ──┤  FastAPI app  (lands in backend/ )           │
   /api/personas      │                                              │
   /api/analyze       │   API layer  ◀── keep from backend_tjorge    │
   /api/.../approve   │      │         (contract, CORS, sessions,     │
   /api/chat (new)    │      │          approval, audit)             │
                      │      ▼                                        │
                      │   LangGraph engine ◀── from backend_maike     │
                      │   load_context → analyst ∥ forecaster         │
                      │        → combine → optimizer ⇄ tools          │
                      │        → **structured-output node** (NEW)     │
                      │      │                                        │
                      │      ▼                                        │
                      │   Response shaper → exact frontend JSON       │
                      └──────────────────┬──────────────────────────┘
                                         ▼
                          PostgreSQL 16 (docker `db`)  ◀── one DB
                          (real recommendations + catalogue tables added)
```

**Principles**
- **One app, two layers:** thin FastAPI contract layer (tjorge) wrapping the LangGraph engine (maike).
- **The API contract is sacred.** The frontend is fixed, so `/api/analyze` must keep returning the exact JSON in §2.2. The LLM pipeline must be forced to produce that shape (structured output), or a deterministic shaper must build it.
- **Converge on one DB.** Target the docker Postgres so frontend, data generator, and backend finally share a store.

---

## 5. The key technical bridge: prose → structured JSON

This is the crux. `backend_maike`'s optimizer ends with `messages[-1].content` = a 5-sentence prose recommendation. The frontend needs ranked `scenarios[]` with numeric `annual_cost` / `annual_savings` / `co2_savings_kg` / `changes[]` plus an `analyst.output` block with `mode_breakdown` and `inefficiencies`. None of the maike graphs use `with_structured_output`.

Two viable strategies:

**Strategy A — Make the LLM emit structured output (most "agentic").**
Add a final node to the pipeline that calls the model with `with_structured_output(SchemaModel)` (Pydantic) or a JSON tool, producing exactly the `summary.scenarios` / `recommended_scenario` / `memos` shape. The communicator becomes an LLM node that writes the EN/DE memos. Risk: LLMs are unreliable at exact numbers (savings math); mitigate by computing the numbers deterministically and letting the LLM only choose/justify.

**Strategy B — Hybrid (recommended, lowest risk).**
- Keep `backend_tjorge`'s **deterministic analyst + optimizer** to produce the **numbers** (`mode_breakdown`, candidate portfolios, `annual_cost`/`savings`/`co2`, `inefficiencies`) — the frontend's quantitative blocks stay exact and stable.
- Use `backend_maike`'s **LLM** for the **judgment and language**: the optimizer's tool-driven reasoning over the **56-product catalogue**, the **communicator memos** (replacing hardcoded templates), the **onboarding agent**, and the **`/api/chat`** endpoint the frontend already calls.
- A response shaper merges both into the §2.2 contract.

Strategy B gets a genuinely agentic backend (LLM + tools + onboarding + chat) while guaranteeing the UI's numeric contract never breaks. Strategy A can be migrated to later, field by field.

---

## 6. Endpoint plan

| Endpoint | Source | Action in merged backend |
|---|---|---|
| `GET /api/personas` | tjorge | Keep; read from Postgres `user_information` (map to the persona shape the UI expects). |
| `POST /api/analyze {user_id}` | tjorge contract + maike engine | Run the LangGraph pipeline (analyst ∥ forecaster → optimizer ⇄ tools) → structured-output/shaper → §2.2 JSON. Persist a `recommendations` row + audit entry. |
| `POST /api/recommendations/{id}/approve {scenario_id}` | tjorge | Keep as-is; update recommendation status + audit. |
| `POST /api/chat {user_id, messages}` | **new** (maike) | **Currently missing** — frontend already calls it and falls back to a scripted bot. Wire it to a LangGraph conversational agent (reuse onboarding/optimizer context) to replace the fallback. |
| Onboarding | maike | Expose the onboarding graph (e.g. via `/api/chat` mode or a dedicated `/api/onboarding`) so new users get persisted profiles. |

---

## 7. Database plan

Target the **docker Postgres `db`** as the single store.

1. **Promote maike's schema into the real Postgres tables.** maike's `subscription_products` (56 products) and `recommendations` schema are the mature versions — port them to replace the `database/init` **stub** tables (`subscription_catalogs`, `recommendations`, `kpis`).
2. **Pick one users/trips shape.** The `database/init` `user_information` + `user_trips` + `trip_legs` design is the richest and is fed by `data_generator/`; make it canonical. Provide a small read layer (replace `db/db_utils.py` SQLite calls with `psycopg2`/SQLAlchemy — the root `requirements.txt` already lists `psycopg2-binary`, `sqlalchemy`, `pandas`).
3. **Seed the catalogue + personas into Postgres** (port `seed_subscription_products.py` + the 5 demo personas) via `database/init` so `docker compose up` produces a ready DB.
4. **Drop the two committed SQLite files** (`mobility_advisor.db`, `moveoptimizer.db`) once the read layer points at Postgres.
5. Keep the persona ↔ `user_id` mapping identical to `personas.js` so login + `/api/analyze` keep working.

---

## 8. Recommended phased plan

**Phase 0 — Decide & freeze contract.** Lock the §2.2 JSON as the API spec. Pin engine = maike, API shell = tjorge, store = Postgres.

**Phase 1 — Make tjorge the canonical `backend/` and put it on Postgres.**
Move `backend_tjorge` code into `backend/src/`, fill `requirements.txt`, confirm `docker compose up` serves the frontend end-to-end against Postgres (deterministic engine still). *Now the empty placeholder is gone and the app is green.*

**Phase 2 — Bring the data layer together.** Port the 56-product catalogue + recommendations tables into Postgres; repoint the data access layer; seed personas. Frontend still works.

**Phase 3 — Transplant the LLM engine (Strategy B).** Add LangGraph deps; introduce the optimizer ReAct loop + `lookup_subscriptions` (over the 56-product Postgres catalogue) and replace the hardcoded communicator with the LLM memo node. Add a **structured-output/shaper node** so `/api/analyze` keeps returning the exact contract. Feature-flag LLM vs deterministic so you can fall back if the API key/model is unavailable.

**Phase 4 — Add `/api/chat` + onboarding.** Wire maike's conversational agents behind real endpoints, retiring the frontend's scripted fallback.

**Phase 5 — Cleanup.** Delete `backend_tjorge/` and `backend_maike/` once their code lives in `backend/`; remove committed SQLite DBs; update README/architecture docs.

---

## 9. Risks & decisions to confirm

- **LLM numeric reliability.** Don't let the LLM compute savings; compute deterministically, let the LLM select/justify (Strategy B). *Decision: A vs B vs phased B→A.*
- **API key availability in Docker.** `UNI_GPT_API_KEY` must be in `.env`/compose env; need a deterministic fallback for demos without a key.
- **Latency / determinism.** `/api/analyze` auto-runs on dashboard mount; LLM + ReAct loop is slower and non-deterministic. Consider caching the latest recommendation per user (the `recommendations` table already supports this).
- **"Final" DB is half-stub.** `subscription_catalogs` / `recommendations` / `kpis` must be replaced with real tables before the merged backend can persist to Postgres — confirm the DB is allowed to change here, since the rest of the DB is "final."
- **Onboarding vs seeded personas.** Frontend logs in via fixed local personas; onboarding creates new DB users. Decide how/whether onboarding-created users surface in the UI.

---

## 10. One-line summary

`backend/` is an empty shell, `backend_tjorge` is the frontend's API with a fake (deterministic) brain, and `backend_maike` is the real brain with no API — so the merge is **"put maike's LangGraph engine inside tjorge's FastAPI contract, on the Postgres DB,"** done in phases, with a structured-output bridge as the single critical piece of new work.

---

# POST-MERGE STATUS (as built)

The merge is complete. There is now **one backend** (`backend/`) — a FastAPI service with an
agentic LangGraph engine, on Postgres — serving the unchanged frontend. `backend_tjorge/` and
`backend_maike/` have been removed (recoverable from git history at commit **`e8db4cc`**).

## As-built architecture

```
frontend (Vite/React, unchanged)
  │  /api proxied → backend:8000
  ▼
backend/  (FastAPI, single service)
  ├─ main.py            API: /api/personas, /api/analyze, /api/recommendations/{id}/approve,
  │                          /api/chat, /api/onboarding
  ├─ orchestrator.py    session + persistence + response shaping (stable contract)
  ├─ graph/pipeline.py  LangGraph: load_context → analyst ∥ forecaster ∥ optimizer → communicator
  ├─ graph/chat_agent.py     ReAct agent (create_react_agent) + lookup_subscriptions tool
  ├─ graph/onboarding.py     LangGraph onboarding interview → persists user to Postgres
  ├─ graph/llm.py / tools.py University GPT client + catalogue tool
  └─ agents/*           deterministic analyst/forecaster/optimizer/communicator (the numbers)
  ▼
Postgres 16 (docker `db`)   users, travel_history, subscriptions, recommendations, audit_log, pricing_catalog
```

**Design principle held throughout:** deterministic agents produce every number the frontend reads
(contract is guaranteed); the LLM only writes prose (memos, chat, onboarding). LLM features degrade
gracefully — no key ⇒ template memos + `503` on chat/onboarding ⇒ frontend scripted fallback.

## What is DONE (verified)

| Area | Status |
|---|---|
| Single merged backend in `backend/`, old folders deleted | ✅ |
| Frontend contract (`/api/personas`, `/api/analyze`, `/approve`) unchanged & green | ✅ verified in Docker |
| App runs on **Postgres** (not SQLite); data persisted & confirmed via `psql` | ✅ |
| **Agentic LangGraph** analyze pipeline (parallel analyst/forecaster/optimizer) | ✅ |
| **LLM memos** live (`memo_source: llm`), template fallback when no key | ✅ live-tested |
| **`/api/chat`** — ReAct agent w/ catalogue tool, grounded in user context | ✅ live-tested |
| **`/api/onboarding`** — conversational, persists profile + subscriptions to Postgres | ✅ live-tested |
| Graceful no-key fallbacks (503 → frontend scripted assistant) | ✅ |
| Vite proxy works in Docker (`BACKEND_URL`) and locally | ✅ |
| 7/7 backbone unit tests pass through the LangGraph pipeline | ✅ |
| Model id corrected to `OpenAI GPT OSS 120b KI:Inferenz.nrw` (was stale) | ✅ |
| `.env` untracked (was committed with a secret) | ✅ — **rotate the JIRA token; it is in history** |

## What NEEDS REFINEMENT (next)

1. **DB canonicalisation (the deferred Phase 2/3 decision).** The app still uses tjorge's demo
   schema + 9-product `pricing_catalog`. The canonical target is `database/init/` (rich, typed)
   filled with Maike's **56-product catalogue** + real recommendations table. Today `database/init/`
   is **not even loaded** into Postgres (no `docker-entrypoint-initdb.d` mount) and its
   `subscription_catalogs` / `recommendations` / `kpis` are `id/name/city` **stubs**. Maike's
   `seed_subscription_products.py` + `schema.sql` (recoverable at `e8db4cc`) are the reference.
   - **Name clash to resolve:** `database/init/07_recommendations.sql` vs the app's `recommendations`
     table have different shapes.
2. **Richer catalogue ⇒ richer optimizer.** The deterministic optimizer hardcodes a small portfolio
   list (BahnCard/DT/Miles). Once the 56-product catalogue lands, broaden it (bike/scooter/car-sharing,
   per-minute/per-km pricing) — or let the LLM optimizer (ReAct) propose and the deterministic layer cost it.
3. **Onboarding not frontend-wired.** Endpoint works and persists, but the UI logs in via fixed demo
   personas; onboarded users don't yet surface. Also onboarding collects no person name (set to
   occupation/placeholder) and no trip history (so `/api/analyze` on a fresh onboarded user is thin).
4. **LLM latency / caching.** `/api/analyze` auto-runs on dashboard mount; the LLM memo adds latency
   and is non-deterministic. Cache the latest recommendation per user (the `recommendations` table
   already supports it) and/or generate the memo lazily.
5. **Memo robustness.** LLM memo parsing expects a JSON object; malformed output falls back to template
   (safe) but loses the LLM memo. Consider `with_structured_output`/function-calling once the model's
   support is confirmed.
6. **Tests for LLM paths.** Only deterministic/fallback paths are unit-tested. Add tests with a mocked
   LLM for the chat agent, onboarding save, and memo JSON parsing.
7. **Secrets & ops.** Rotate the leaked `JIRA_TOKEN`. Add `.env.example`. Consider a Postgres
   healthcheck + `depends_on: condition: service_healthy` (currently handled by a connect-retry loop).
8. **Forecaster is unused downstream.** It runs and is returned in `raw_agent_payloads`, but neither the
   optimizer nor the memo consume it yet — wire it in (e.g. seasonal demand → plan choice) or surface it in the UI.
