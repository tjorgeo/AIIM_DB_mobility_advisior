# DB MoveOptimizer - Consulting & Delivery Guide
## BCG Platinion Strategy IT Consulting Pilot (AIIM University)

**Project:** Deutsche Bahn Mobility Portfolio Management Agent (Pilot)  
**Partnership:** University AIIM & **BCG Platinion** (Strategy IT Data Consulting Review)  
**Timeline:** 15 Weeks Remaining (out of 16)  
**Team:** 5 Consultant Data Scientists  
**Status:** ✅ Strategic Blueprint Locked — Ready for Technical Execution

---

## 📌 PROJECT MISSION
Establish a cutting-edge **Multi-Agent System** that acts as an intelligent mobility advisor for German transit customers. The prototype reviews historical user travel behavior, predicts 6-month demand, runs multi-scenario cost optimizations against current German transit catalogs (Bahncard, Deutschlandticket, regional fares), and presents conversational, personalized subscription cancellation/addition recommendations.

This prototype (Phase 1) is designed as a high-fidelity de-risking sandbox to validate the core architecture and business case prior to a proposed €1.1M enterprise-scale rollout (Phase 2).

---

## 🏗️ THE 4-AGENT SANDBOX ARCHITECTURE
The system operates as a robust, non-negotiable multi-agent architecture coordinated by a FastAPI state machine:

| Agent | Responsibility | Core Methodologies |
| :--- | :--- | :--- |
| **1. Analyst** | Pattern detection & inefficiency auditing | Ingests 12-month travel logs; clusters behavior and identifies over/under-provisioning. |
| **2. Forecaster** | 6-month demand prediction | Models seasonal moving averages and historical patterns to forecast trip demand. |
| **3. Optimizer** | Scenario formulation & solving | Compares travel demand against current pricing catalogs to output 2 cost-optimized portfolios. |
| **4. Communicator** | Conversational UI & approval management | Deploys Claude 3.5 Sonnet to draft personalized, context-aware suggestions in a chat widget. |

---

## 📚 STRATEGIC DELIVERABLES CHECKLIST
The repository is structured to mirror the high-impact output of a professional BCG Platinion IT Strategy engagement:

1.  **[Context Lock Blueprint](DELIVERABLES/CONTEXT_LOCK.md)** — Outlines the "Pilot vs. Scale" roadmap, de-risking strategies, simulated API JSON schemas, and GDPR boundaries.
2.  **[Architecture Blueprint](DELIVERABLES/ARCHITECTURE.md)** — Features deep technical blueprints of the 4-agent coordination flow, state schema schemas, and 5 detailed ADRs (Architecture Decision Records).
3.  **[Requirements Spec](DELIVERABLES/MVP_REQUIREMENTS.md)** — Houses 12 user stories, acceptance criteria, and a concrete Definition of Done (DoD) for data scientists.
4.  **[Project Plan & Roadmap](DELIVERABLES/PROJECT_PLAN.md)** — Schedules the 16-week delivery roadmap, resource ownership, risk registers, and academic deliverables (10-Page Report, Video, Pitch).
5.  **[Deliverables Index](DELIVERABLES/DELIVERABLES-INDEX.md)** — Central index of consulting methodologies, engagement closeout metrics, and statistics.

---

## 📅 TIMELINE AT A GLANCE (15 Weeks Remaining)

*   **Phase 1: Foundation & Sandbox (Weeks 1-4):** Lock architecture, define simulated API schemas, and compile pricing catalogs.
*   **Phase 2: Agent Development (Weeks 5-8):** Build and unit-test the 4-agent systems and orchestrator state machine.
*   **Phase 3: Pilot & Frontend (Weeks 9-12):** Run 100-profile synthetic simulation, deploy Redis caching, and launch the Streamlit chat UI.
*   **Phase 4: Consulting Delivery (Weeks 13-16):** Perform final hardening, compile the **10-Page Management Report**, record the **Demo Video**, and prepare the **BCG Platinion Final Pitch Presentation**.

---

## 🎯 PILOT RUN SUCCESS KPIS

1.  **Full Orchestration:** Complete E2E modular communication (Analyst $\rightarrow$ Forecaster $\rightarrow$ Optimizer $\rightarrow$ Communicator).
2.  **Mathematical Accuracy:** Solver recommendation costs accurate to within ±5% of real-world optimal values.
3.  **Latency SLA:** End-to-end user recommendation response time under <30 seconds (P95).
4.  **Integration Feasibility:** Flawless verification against mock JSON API schemas (simulating DB Navigator exports).
5.  **Academic Excellence:** Timely handoff of the 10-page report, demo video, and final slide deck.

---

## 📖 DOCUMENT READING PATHWAYS

### For BCG Platinion Partners & Graders (Quick Review - 30 mins)
1.  **This README** (5 mins) — Core orientation.
2.  **[Context Lock](DELIVERABLES/CONTEXT_LOCK.md)** (10 mins) — Understand the "Pilot vs. Scale" framework and integration strategy.
3.  **[Project Plan](DELIVERABLES/PROJECT_PLAN.md)** (15 mins) — Review risk mitigation, WBS, and milestones.

### For Technical Leads & Developers (Deep Dive - 2 hours)
1.  **[Architecture Blueprint](DELIVERABLES/ARCHITECTURE.md)** (60 mins) — Technical architecture, state machine, and the 5 ADRs.
2.  **[Requirements Spec](DELIVERABLES/MVP_REQUIREMENTS.md)** (60 mins) — 12 User Stories, acceptance criteria, and testing boundaries.

---

**Consulting Team:** AIIM-BCG Strategy IT Data Consulting Team  
**Last Updated:** May 28, 2026  
**Classification:** Confidential — For Academic & BCG Platinion Review Only  

