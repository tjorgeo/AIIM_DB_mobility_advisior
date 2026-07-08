# DB MoveOptimizer - Context Lock (BCG Platinion Edition)

**Date:** May 20, 2026 | **Project:** DB Mobility Portfolio Management Agent (Pilot)  
**Partnership:** University AIIM & **BCG Platinion** (Strategy IT Data Consulting Review)  
**Team:** 5 Data Scientists (Consulting Pilot Team) | **Duration:** 15 Weeks Remaining (out of 16) | **Status:** Locked & Ready for Execution

---

## 🏛️ STRATEGIC TWO-PHASE ROADMAP
To balance technical feasibility in the 15-week timeline with enterprise strategic vision, we partition the project into two distinct phases. This prototype (Phase 1) serves as a direct technical and business de-risking mechanism for the full-scale commercial rollout (Phase 2).

### Phase 1: High-Fidelity Pilot Sandbox (Current Academic Scope)
*   **Objective:** Deliver a working, fully-orchestrated **4-Agent Prototype** that demonstrates end-to-end analytical reasoning, demand forecasting, multi-scenario optimization, and natural-language presentation.
*   **Infrastructure:** Python FastAPI, LangChain orchestration, Claude 3.5, local PostgreSQL state storage (no Redis in Phase 1 — deferred to Phase 2), a React 18 + Vite frontend, and mock database layers.
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
2.  **Forecaster Agent:** Analyzes travel history to identify seasonality; generates a probabilistic 6-month demand forecast (trip counts by mode/month).
3.  **Optimizer Agent:** Evaluates pricing catalogs (Bahncard tiers, Deutschlandticket, sharing rates) and solves for 2 cost-optimized contract portfolios.
4.  **Communicator Agent:** Leverages Claude 3.5 Sonnet to draft highly personalized, conversational recommendations in German/English, tracking user approval states.

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
*   ❌ Real-time calendar synchronization or raw email signal mining.

---

## 🎯 SUCCESS CRITERIA (Pilot Phase)

| Success Metric | Target / SLA | Validation Method |
| :--- | :--- | :--- |
| **Architectural Integrity** | 4 distinct agents fully orchestrated | Code review & architecture check |
| **Data Sandbox Completeness** | Replicates DB API JSON schemas exactly | API endpoint testing and schema validation |
| **Recommendation Latency** | <30s end-to-end response time | P95 latency logging |
| **Analytical Accuracy** | Optimizer cost calculations within ±5% | Automated validation on 100 test profiles |
| **Academic Deliverables** | 100% complete and polished | Delivery of 10-page report & Demo Video |

---

## ⚠️ CONSTRAINTS & RESILIENCE STRATEGY

| Constraint / Risk | Blocker | Mitigation (Pilot Strategy) |
| :--- | :--- | :--- |
| **API Availability** | Private DB Navigator API cannot be queried live | Implement a **Sandbox Gateway** providing simulated high-fidelity travel data. |
| **Data Privacy (GDPR)** | GDPR restricts active data gathering | Pilot operates strictly on simulated/mock customer data. |
| **Orchestration Latency** | Sequential agent calling can exceed <30s | Run Analyst and Forecaster in parallel; cache static schemas in Redis. |

### Critical Sandbox Dependencies (Weeks 1-2)
1.  **JSON API Schemas:** Locking down the target JSON payloads for DB travel history.
2.  **Synthetic Profile Definitions:** Establishing 5-10 detailed customer travel personas for rigorous automated testing.
3.  **Pricing Database Catalog:** Compiling current Bahncard, Deutschlandticket, and regional German transit rates into local data catalogs.

---

## 🛠️ TECH STACK DECISIONS (Phase 1 Prototype)

| Component | Choice | Rationale |
| :--- | :--- | :--- |
| **Agent Framework** | LangChain (Python) | High ecosystem maturity, robust tooling. |
| **LLM** | Claude 3.5 Sonnet / Gemini | Top-tier analytical reasoning, high speed. |
| **Data Store** | SQLite / PostgreSQL | Lightweight local state storage, SQL compatibility. |
| **Caching Layer** | None in Phase 1 (Redis deferred to Phase 2) | PostgreSQL-only persistence is sufficient for the pilot; session state is the `recommendations` row id. |
| **User Interface** | React 18 + Vite | Component-based chat widget matching the Phase-2 enterprise UI target (no Streamlit). |

