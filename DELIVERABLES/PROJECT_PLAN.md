# DB MoveOptimizer - Pilot Project Plan (BCG Platinion Edition)

## 5-Person Strategy IT Consulting Pilot Team | 16 Weeks

**Project Scope:** Phase 1 high-fidelity functional prototype covering 14 user stories in the Scrum backlog,
**Partnership:** University AIIM & **BCG Platinion** (Strategy IT Data Consulting Review)  
**Duration:** May 20 - Aug 31, 2026  
**Team:** 5 Consultant Data Scientists  
**Goal:** Deliver a working 4-Agent prototype, a 10-page management report, and a 3-minute professional demo video.

> **Reconciliation note (2026-07-08, ~Week 8).** The phase structure still frames the work, but
> two June-16 "locked" decisions were overtaken by implementation: **Decision 1.2** (weighted
> scenario rubric) and **Decision 1.3** (Prophet forecasting baseline) no longer describe the
> system — scenario ranking was removed in favour of a per-category subscription analysis, and
> the forecaster is a 90-day calendar-aware model with a deterministic seasonal fallback, not
> Prophet. The LLM is **University GPT** (not Claude 3.5), the store is **Postgres-only** (Redis
> deferred), and the "100-profile pilot" presupposes a profile generator that doesn't exist
> (6 seeded personas today). These deviations are annotated inline below.

---

## 📅 TIMELINE: 4 Phases, 4 Weeks Each (Phase 1 Pilot)

### Phase 1: Architecture, Sandbox & Schemas (Weeks 1-4 | May 20 - June 15)

* **Goal:** Establish technical blueprints, design mock API schemas, and compile pricing catalogs.
* **Deliverables:**
  * ✅ Technical Architecture Blueprint with complete ADRs (Architecture Decision Records)
  * ✅ Mock API Gateway endpoints (FastAPI) and target JSON schemas defined
  * ✅ Synthetic seed dataset loaded with 6 core traveler personas
  * ✅ Pricing catalog loaded (Deutschlandticket, Bahncard tiers, regional rates)
* **Steering Gate (June 16 BCG Progress Meeting):** Formal phase gate review with BCG Platinion. Obtain sign-off on the **Phase 1 Decision Package** to authorize the kickoff of Phase 2 core agent development.

#### 📦 Phase 1 Decision Package (Prepared in Week 4)

To ensure maximum decision-making velocity during the June 16 progress meeting, the consulting team will compile and distribute a 3-page "Steering Memo" covering:

1. **Mock Schema Specifications:** Target JSON contracts for DB Navigator and partner APIs.
2. **Persona Catalog:** 6 synthetic user profiles representing DB's customer demographics.
3. **Solver Rule Engine Specs:** Mathematical formulation of the greedy optimization heuristic.
4. **Resilience & Failure Matrix:** Detailed mapping of agent fallbacks and timeout thresholds.

#### 🗳️ Key Decisions to be Resolved on June 16

The progress meeting will be structured around a formal voting board to lock the following decisions before entering code production:

1. **Decision 1.1: Sandbox API Schema Approval** — Lock the data contracts (JSON payloads) for travel history, ensuring they are identical to future production payloads.
2. **Decision 1.2: Scenario Weighted Rubric** — ~~Approve weights for Cost / Balanced /
   Sustainability scenario ranking.~~ **⚠️ SUPERSEDED (July refactor):** scenario generation and
   weighted ranking were removed. The system now emits a deterministic per-category
   `keep/switch/drop` subscription analysis; onboarding priority scores frame the memo prose but
   do not drive a numeric scenario rank.
3. **Decision 1.3: Demand Forecasting Model Baseline** — ~~Confirm Prophet moving averages.~~
   **⚠️ SUPERSEDED:** no Prophet. The Forecaster is a 90-day, calendar-aware model producing LLM
   demand scenarios with a **deterministic seasonal fallback** as the number guard.
4. **Decision 1.4: Resilience Thresholds & Timeouts** — Formally approve the maximum SLA timeouts:
    * Max E2E user latency: 30s.
    * Max agent execution timeout: Analyst (8s), Forecaster (8s), Optimizer (5s), Communicator (5s).
    * Fallback mechanism: Naive historical replication if Forecaster fails.
5. **Decision 1.5: Phase 2 Kickoff Approval** — Formal "Go/No-Go" decision based on Phase 1 gate completions to release development sprint resources.

---

### Phase 2: Core 4-Agent Development (Weeks 5-8 | June 16 - July 13)

* **Goal:** Implement the non-negotiable 4-agent systems and orchestrator state machine.
* **Deliverables:**
  * **Week 5:** Analyst Agent (travel logs parsing and efficiency heuristic clustering) operational
  * **Week 6:** Forecaster Agent (90-day, calendar-aware; LLM scenarios + deterministic seasonal fallback) callable
  * **Week 7:** Optimization tool (deterministic catalog analysis) and Communicator (University GPT memo, with template fallback) integrated
  * **Week 8:** End-to-end multi-agent orchestration running under the FastAPI state machine
* **Phase Gate (July 13):** Working CLI / API flow showing all 4 agents executing on mock profile data.

---

### Phase 3: Pilot Run & Interface Hardening (Weeks 9-12 | July 14 - Aug 10)

* **Goal:** Run the prototype against 100 synthetic customer travel profiles; validate accuracy and launch the React frontend.
* **Deliverables:**
  * ⚠️ Multi-persona pilot run (6 seeded personas; a 100-profile generator was not built)
  * ✅ React 18 + Vite Premium Chat Widget deployed (local / web-accessible)
  * ✅ Deterministic engine test suite (`backend/tests/`) + LLM eval harness (`backend/eval/`)
  * ✅ PostgreSQL state store verified (Redis caching deferred to Phase 2)
* **Phase Gate (Aug 10):** Prototype functional, stable, and user-testable.

---

### Phase 4: Business Delivery & Academic Handoff (Weeks 13-16 | Aug 11 - Aug 31)

* **Goal:** Complete technical hardening and produce the final consulting deliverables.
* **Deliverables:**
  * **Week 13:** Bug fixes and performance tuning (<30s end-to-end response time). Begin writing the **10-Page Management & IT Strategy Report**.
  * **Week 14:** Hardening state persistence. Draft the executive summary and architectural justifications of the **10-Page Report**.
  * **Week 15:** Script, shoot, and edit the **3-Minute Demo Video** highlighting system intelligence and value. Finalize the 10-page report.
  * **Week 16:** Compile the **BCG Platinion Final Pitch Presentation** slides. Code cleanup and GitHub repository handoff.
* **Phase Gate (Aug 31):** Hand off working prototype, video, report, and slide deck.

---

## ⚠️ RISK REGISTER (BCG Platinion Pilot Focus)

| Risk Event | Likelihood | Impact | Proactive Mitigation Strategy |
| :--- | :---: | :---: | :--- |
| **API Contract Delays** | High | High | **Mitigated:** Use simulated sandbox endpoints and high-fidelity mock datasets. |
| **Orchestrator Latency** | Medium | Medium | Read-through cache on the latest recommendation; defer the slow LLM memo to a background task (no Redis in Phase 1). |
| **Scope Creep** | Medium | High | Rely on the strict Phase 1 vs. Phase 2 boundaries; push advanced APIs to Phase 2. |

---

## 📝 DEFINITION OF DONE (Phase 1 Gates)

### Gate 1 (Week 4 - Foundation & Sandbox)

- [ ] Technical Architecture document complete and approved.
* [ ] Sandbox API Gateway operational with JSON schemas matching DB specifications.
* [ ] Synthetic seed dataset working with 6 traveler personas ([US 14]).
* [ ] Local environment operational (Python FastAPI + React 18/Vite base).

### Gate 2 (Week 8 - Agent Integration)

- [ ] Analyst, Forecaster, Optimizer, and Communicator agents callable.
* [ ] End-to-end flow operational (raw JSON input $\rightarrow$ natural language recommendation).
* [ ] Core agent reasoning logic covered by >80% automated unit tests.

### Gate 3 (Week 12 - Prototype Hardening)

- [ ] React interface fully integrated with the backend ([US 13]).
* [ ] Pipeline runs cleanly across all 6 seeded personas (100-profile generator not in scope).
* [ ] Caching — read-through recommendation cache (Redis deferred to Phase 2; Postgres-only).
* [ ] Recommendations validated for mathematical accuracy (deterministic number guard).

### Gate 4 (Week 16 - Consulting Delivery)

- [ ] Working prototype deployed and available for BCG Platinion review.
* [ ] **10-Page Management & IT Strategy Report** completed and formatted professionally.
* [ ] **3-Minute Demo Video** completed, showing full end-to-end user flows.
* [ ] **BCG Platinion Final Pitch Presentation** slides ready for delivery.
* [ ] GitHub repository clean, documented, and ready for grading.

---

## 🎯 KEY STRATEGIC PILOT KPIS

* **Completion Rate:** 100% of the 4 agents working in a cohesive state machine.
* **Analytical Precision:** Solver cost calculations within ±5% of real-world optimal values.
* **Orchestration Latency:** Response time <40 seconds for complete agent runs.
* **Presentation Excellence:** Clear, professional documentation ready for C-level BCG Platinion review.
