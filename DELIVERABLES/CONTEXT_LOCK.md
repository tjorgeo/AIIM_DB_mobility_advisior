# DB MoveOptimizer - Context Lock (BCG Platinion Edition)

**Date:** May 20, 2026 | **Project:** DB Mobility Portfolio Management Agent (Pilot)  
**Partnership:** University AIIM & **BCG Platinion** (Strategy IT Data Consulting Review)  
**Team:** 5 Data Scientists (Consulting Pilot Team) | **Duration:** 16 Weeks | **Status:** Locked; reconciled with code 2026-07-08

> **Reconciliation note.** Scope and constraints below still hold. Tech-stack specifics were
> updated to the implementation: LLM is **University GPT** (kiconnect.nrw), framework is
> **LangGraph**, store is **Postgres-only** (Redis never used in Phase 1), the optimizer produces
> a **per-category subscription analysis** rather than 2 portfolios, there are **6** seeded
> personas, and **calendar data is used** by the forecaster.

---

## 🏛️ STRATEGIC TWO-PHASE ROADMAP
To balance technical feasibility in the 15-week timeline with enterprise strategic vision, we partition the project into two distinct phases. This prototype (Phase 1) serves as a direct technical and business de-risking mechanism for the full-scale commercial rollout (Phase 2).

### Phase 1: High-Fidelity Pilot Sandbox (Current Academic Scope)
*   **Objective:** Deliver a working, fully-orchestrated **4-Agent Prototype** that demonstrates end-to-end analytical reasoning, demand forecasting, multi-scenario optimization, and natural-language presentation.
*   **Infrastructure:** Python FastAPI, **LangGraph** orchestration, **University GPT** (kiconnect.nrw) LLM, docker **PostgreSQL 16** state storage (no Redis in Phase 1 — deferred to Phase 2), a React 18 + Vite frontend, and seeded synthetic database layers.
*   **Integration Strategy:** Use a simulated API gateway and high-fidelity mock datasets that replicate the exact JSON schema formats of Deutsche Bahn’s Navigator API and third-party partner systems. This de-risks legal, commercial, and security integration bottlenecks.
*   **Core Deliverables:** Working Technical Prototype + 10-Page Management & IT Strategy Report + 3-Minute Product Demo Video.

### Phase 2: Enterprise Commercial Rollout (Proposed Future Phase)
*   **Objective:** Scale the system to DB's customer base of 1M+ active digital users, generating a projected €3-5M in annual retained customer lifetime value.
*   **Infrastructure:** AWS EKS production cluster, dedicated vector storage (Weaviate Cluster), Redis Enterprise caching, and enterprise monitoring (Datadog/Prometheus).
*   **Integration:** Live DB Navigator production API integration, commercial partner API onboarding (Miles, Lime, Stadtrad), and direct contract execution pipelines.

---

## 📋 SCOPE: What We're Building (Phase 1 Pilot)

### Core 4-Agent Architecture
1.  **Analyst Agent:** Ingests 12-month travel logs; detects inefficiencies and baseline cost metrics using multi-modal clustering and heuristic pattern recognition.
2.  **Forecaster Agent:** Analyzes travel history for seasonality and reads upcoming calendar entries to generate a 90-day demand forecast (LLM scenarios with a deterministic seasonal fallback).
3.  **Optimizer (deterministic tool):** Evaluates pricing catalogs (Bahncard tiers, Deutschlandticket, sharing rates) and computes, per travel category, whether to keep / switch / drop the current subscription.
4.  **Communicator Agent:** Leverages University GPT to draft personalized, conversational recommendations in German/English (with a deterministic template fallback), tracking user approval states.

### In Scope (Phase 1 Pilot)
*   ✅ Complete 4-Agent Orchestration Flow (Analyst $\rightarrow$ Forecaster $\rightarrow$ Optimizer $\rightarrow$ Communicator).
*   ✅ Mock API Gateway & Sandbox mimicking DB Navigator schema formats.
*   ✅ Pricing database for core German transit (Bahncard 25/50/100, Deutschlandticket, pay-as-you-go).
*   ✅ Synthetic Customer Profile Generator (generating travel histories for various target user personas).
*   ✅ React 18 + Vite Chat UI to demonstrate user-agent interaction.
*   ✅ 10-Page Strategic IT Consultant Report (covering architecture, business value, and rollout plan).
*   ✅ 3-Minute Demo Video highlighting technical and business value.

### Out of Scope for Phase 1 (Deferred to Phase 2 Scale)
*   ❌ Real-time live DB Navigator database connections.
*   ❌ Live contract cancellation/execution API calls (Miles, Lime, DB Accounts).
*   ❌ Dedicated production-grade Vector DB (Weaviate deferred if time-constrained).
*   ❌ Real-time **live** calendar synchronization or raw email signal mining. (Seeded, opt-in calendar data *is* used by the forecaster in Phase 1; only live sync and email mining are deferred.)

---

## 🎯 SUCCESS CRITERIA (Pilot Phase)

| Success Metric | Target / SLA | Validation Method |
| :--- | :--- | :--- |
| **Architectural Integrity** | 4 distinct agents fully orchestrated | Code review & architecture check |
| **Data Sandbox Completeness** | Replicates DB API JSON schemas exactly | API endpoint testing and schema validation |
| **Recommendation Latency** | <30s end-to-end response time | P95 latency logging |
| **Analytical Accuracy** | Deterministic, reproducible cost/CO₂ figures (number guard) | Engine unit tests (`backend/tests/`) across the 6 seeded personas |
| **Academic Deliverables** | 100% complete and polished | Delivery of 10-page report & Demo Video |

---

## ⚠️ CONSTRAINTS & RESILIENCE STRATEGY

| Constraint / Risk | Blocker | Mitigation (Pilot Strategy) |
| :--- | :--- | :--- |
| **API Availability** | Private DB Navigator API cannot be queried live | Implement a **Sandbox Gateway** providing simulated high-fidelity travel data. |
| **Data Privacy (GDPR)** | GDPR restricts active data gathering | Pilot operates strictly on simulated/mock customer data. |
| **Orchestration Latency** | Sequential agent calling can exceed <30s | Read-through cache on the latest recommendation; defer the slow LLM memo to a background task (no Redis in Phase 1). |

### Critical Sandbox Dependencies (Weeks 1-2)
1.  **JSON API Schemas:** Locking down the target JSON payloads for DB travel history.
2.  **Synthetic Profile Definitions:** Establishing detailed customer travel personas for rigorous automated testing (6 built; see `database/seed/PERSONAS.md`).
3.  **Pricing Database Catalog:** Compiling current Bahncard, Deutschlandticket, and regional German transit rates into local data catalogs.

---

## 🛠️ TECH STACK DECISIONS (Phase 1 Prototype)

| Component | Choice | Rationale |
| :--- | :--- | :--- |
| **Agent Framework** | LangGraph (Python) | Graph/tool orchestration for the agentic memo + chat loop. |
| **LLM** | University GPT (kiconnect.nrw, GPT-OSS-120b) | Provided OpenAI-compatible endpoint; degrades to deterministic templates when absent. |
| **Data Store** | PostgreSQL 16 (docker) | Relational state storage; the only store in Phase 1. |
| **Observability** | Langfuse (optional) | Traces LLM calls; captures thumbs + approval scores. |
| **Caching Layer** | None (Redis deferred to Phase 2) | Read-through cache is the latest `recommendations` row; session state is that row id. |
| **User Interface** | React 18 + Vite | Component-based chat widget + dashboard (no Streamlit). |

