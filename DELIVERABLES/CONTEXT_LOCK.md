# DB MoveOptimizer - Context Lock (Prototype Edition)

**Date:** May 20, 2026 | **Project:** DB Mobility Portfolio Management Agent  
**Team:** 5 Data Scientists | **Duration:** 16 weeks | **Status:** Ready for Sprint Planning

---

## SCOPE: What We're Building

### MVP System (Prototype, 1,000 customers)

**4-Agent System:**
1. **Analyst Agent** — Analyze 12-month travel history; detect inefficiencies & cost patterns
2. **Forecaster Agent** — Predict 6-month demand from historical trends + seasonality
3. **Optimizer Agent** — Generate 1-2 cost-optimized portfolio scenarios
4. **Communicator Agent** — Chat interface for recommendations + approval capture

**Deliverable:** Working prototype showing all 4 agents functioning end-to-end with real APIs

### In Scope (MVP Only)
- ✅ Portfolio analysis (12-month retrospective)
- ✅ Basic forecasting (historical patterns + seasonality)
- ✅ 1-2 cost-focused scenarios per customer
- ✅ Chat-based recommendation presentation
- ✅ Human approval before execution
- ✅ DB Navigator API integration (travel history)
- ✅ Pricing catalog integration (subscriptions)

### Out of Scope (Phase 2+)
- ❌ CO₂ footprint calculation
- ❌ Calendar integration
- ❌ Life event detection (email signals)
- ❌ Partner API integration (Miles, Lime, Stadtrad)
- ❌ Approval workflow + contract execution
- ❌ Autonomous decision-making

---

## SUCCESS CRITERIA (Prototype Phase)

| Criterion | Target | Notes |
|-----------|--------|-------|
| **All 4 agents callable** | ✅ End-of Week 8 | Can invoke each agent; returns output |
| **Travel data ingestion** | >95% completeness | Successfully fetch DB Navigator data |
| **Pattern detection** | 100+ customer samples | Analyst finds inefficiencies correctly |
| **Demand forecast** | ±20% accuracy | Reasonable predictions on holdout data |
| **Recommendation latency** | <30s per customer | API + agent processing time |
| **100-customer pilot** | ✅ End of Week 12 | Full end-to-end flow with real APIs |
| **Cost accuracy** | ±5% vs. actual spend | Validate against statements |

---

## HARD CONSTRAINTS & DEPENDENCIES

| Constraint | Blocker | Mitigation |
|-----------|---------|-----------|
| **DB Navigator API** | Must support 12-month historical export | Confirm contract by Week 1; test early |
| **API Rate Limits** | DB: 100 req/s; Google Maps: 50 req/s | Batch requests; cache results |
| **Data Privacy** | GDPR compliance required | Explicit consent only; no inferred signals |
| **Response Time** | <30s per recommendation | Parallel agent execution; async caching |

### Critical Dependencies (Resolve by Week 1)
1. **DB Navigator API Contract** — Must be signed; historical export available
2. **Google Maps API Access** — OAuth configured for trip routing
3. **Pricing Catalog Data** — All current subscriptions + Bahncard tiers available
4. **DB App Integration Point** — Where does chat UI live? (Embed vs. separate screen?)

---

## TECH STACK DECISIONS

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Agent Framework** | LangChain (Python) | Mature, good tool integration |
| **LLM** | Claude 3.5 Sonnet (Anthropic) | Strong reasoning, cost-effective |
| **Data Store** | PostgreSQL + Redis | Relational (user data) + cache (sessions) |
| **Vector DB** | Optional (defer if time) | For contract catalog search (Phase 2) |
| **Orchestration** | Python async | Lightweight, team familiarity |

---

## OPEN QUESTIONS FOR CLIENT

1. **Target Pilot Size?** (1,000 customers assumed; confirm)
2. **Approval Flow?** (Simple approve/reject vs. complex workflow?)
3. **Scenario Count?** (1-2 scenarios recommended; more = choice paralysis)
4. **Phase 2 Timeline?** (When do we add CO₂, calendar, partner APIs?)

---

## TIMELINE AT A GLANCE

| Weeks | Goal | Gate |
|-------|------|------|
| 1-4 | Architecture + API integration complete | Can fetch & analyze real data |
| 5-8 | All 4 agents implemented | End-to-end demo working |
| 9-12 | 100-customer pilot running | Production APIs live |
| 13-16 | Polish + deliver | Demo-ready prototype |


---

## DATA & INTEGRATIONS (Tier 1: MVP Critical)

| Source | Data Type | Status |
|--------|-----------|--------|
| DB Navigator API | Travel history (12 months) | Must confirm by Week 1 |
| DB Account System | Current subscriptions | Available |
| Google Maps API | Trip routing | OAuth needed |
| Pricing Catalog | Bahncard, Deutschlandticket | Need current data |

---

## TEAM & ROLES

- **Data Scientist 1:** Analyst agent + demand forecasting
- **Data Scientist 2:** Optimizer agent + scenario generation
- **Data Scientist 3:** Communicator agent + orchestration
- **Data Scientist 4:** API integration + data pipelines
- **Data Scientist 5:** Testing, validation, documentation

---

## NEXT STEPS (This Week)

1. ✅ Confirm DB Navigator API contract (historical export)
2. ✅ Verify Google Maps API access
3. ✅ Clarify DB App integration point
4. ✅ Get pricing catalog data
5. ✅ Start sprint planning on Week 2
