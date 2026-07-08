# DELIVERABLES — Index

## DB MoveOptimizer — Deutsche Bahn Mobility Portfolio Management Agent

**Partnership:** University AIIM & BCG Platinion (Strategy IT Data Consulting Review)
**Client (framing):** Deutsche Bahn AG
**Team:** 5 Data Scientists · **Timeline:** 16 weeks (May 20 – Aug 31, 2026)
**Last updated:** 2026-07-08

> This folder holds the six planning/architecture deliverables. They describe the **Phase 1
> pilot**. Where a document has been overtaken by the implementation, the correction is noted
> inline in that document and summarised under "Implementation status" below.

---

## The six documents

| # | Document | Purpose |
|---|----------|---------|
| 1 | [CONTEXT_LOCK.md](CONTEXT_LOCK.md) | Scope boundaries, two-phase roadmap, constraints, GDPR stance, tech-stack decisions. |
| 2 | [ARCHITECTURE.md](ARCHITECTURE.md) | 4-agent system design, data flow, database schema, ADRs, resilience. |
| 3 | [MVP_REQUIREMENTS.md](MVP_REQUIREMENTS.md) | 14 user stories with acceptance criteria and Definition of Done. |
| 4 | [PROJECT_PLAN.md](PROJECT_PLAN.md) | 16-week / 4-phase timeline, phase gates, risk register, deliverable milestones. |
| 5 | [API_CONTRACT.md](API_CONTRACT.md) | HTTP contract between the FastAPI backend and the React frontend. |
| 6 | [DELIVERABLES-INDEX.md](DELIVERABLES-INDEX.md) | This index. |

There is no separate "Skill", "Consulting Summary", or "Project Charter" document — earlier
index versions referenced files that do not exist in this repository, along with an €1.1M /
8.5-FTE enterprise plan that was never the scope of this academic pilot. Those references have
been removed.

---

## Implementation status (2026-07-08)

The prototype lives outside this folder:
- **Backend:** `backend/` — FastAPI + LangGraph agent pipeline, deterministic engines under
  `backend/src/agent/engines/`, Postgres access in `backend/src/database.py`.
- **Frontend:** `frontend/` — React 18 + Vite chat/dashboard UI.
- **Database:** `database/init/*.sql` (schema) + `database/seed/*.csv` (6 seeded personas).
- **Orchestration:** `docker-compose.yml` (backend + frontend + Postgres 16).

**What is built and working:** the 4-agent flow (Analyst → Forecaster → Optimizer-as-tool →
Communicator), login/registration/onboarding, the persona picker, the deterministic analysis
pipeline with a read-through cache and a lazy LLM memo, calendar-aware forecasting, an agentic
chat endpoint, and Langfuse observability with user feedback scoring. A backend test suite
(`backend/tests/`) and an eval harness (`backend/eval/`) exist.

**Key deviations from the original plan (reflected in the individual documents):**
- **LLM / framework:** University GPT (`chat.kiconnect.nrw`, GPT-OSS-120b) via **LangGraph** —
  not Claude 3.5 via LangChain.
- **Optimizer:** the scenario A/B/ranking model was removed (July refactor) in favour of a
  per-category "keep / switch / pay-as-you-go" subscription analysis inside the Analyst.
- **Forecaster:** 90-day horizon with LLM demand scenarios + deterministic seasonal fallback,
  **calendar integration included** — not a 6-month Prophet/ARIMA model.
- **Store:** docker Postgres 16 only. No Redis, no Weaviate, no SQLite.
- **Sandbox API:** realised as seeded Postgres data, not a live `GET /v1/sandbox/...` gateway.

**Known open item:** the frontend still consumes the pre-pivot `summary.scenarios` shape while
the backend emits `summary.category_subscription_analysis`; the `/api/analyze` payload builder is
mid-migration. See the divergence note in [API_CONTRACT.md](API_CONTRACT.md).

---

## Consulting methodology (as applied)

1. **Discovery & scope lock** — objective, GDPR-compliant mock-data stance, integration
   de-risking via simulated Navigator schemas → [CONTEXT_LOCK.md](CONTEXT_LOCK.md)
2. **Architecture & decision records** — multi-agent design + ADRs → [ARCHITECTURE.md](ARCHITECTURE.md)
3. **Requirements engineering** — 14 user stories with acceptance criteria → [MVP_REQUIREMENTS.md](MVP_REQUIREMENTS.md)
4. **Delivery governance** — 4-phase plan, gates, risk register → [PROJECT_PLAN.md](PROJECT_PLAN.md)

## Core academic deliverables (Phase 1)
- Working 4-agent technical prototype
- 10-page Management & IT Strategy report
- 3-minute demo video
