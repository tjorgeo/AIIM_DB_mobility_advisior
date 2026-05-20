# Deutsche Bahn Mobility Portfolio Management Agent
## Context Locking Document

**Date:** May 20, 2026  
**Project:** Mobility Service Portfolio Management Agent (Working Title: "DB MoveOptimizer")  
**Client:** Deutsche Bahn AG  
**Engagement Type:** End-to-end GenAI solution design & prototyping with working implementation

---

## 1. BUSINESS CONTEXT

### Strategic Objective
Enable Deutsche Bahn to continuously optimize customer mobility portfolios across DB and partner services, reducing churn, increasing customer lifetime value, and supporting sustainability goals through measurable CO₂ reduction.

### Business Case Foundation
- **Customer Problem:** Customers overspend on mobility subscriptions; lack visibility into optimal portfolio combinations
- **DB Opportunity:** 
  - Increase attach rate of premium services (Bahncard tiers, Deutschlandticket)
  - Reduce churn through proactive portfolio optimization
  - Strengthen ecosystem position vs. point-solution competitors (e.g., comparison apps)
  - Create defensible competitive advantage through data integration depth
- **Sustainability Alignment:** Quantify and reduce CO₂ footprint per customer; market as sustainability leadership
- **Expected Impact:** €100s per customer annual savings, measurable CO₂ reduction, increased retention

### Target Users
**Primary:** DB Kunden (consumers) with active subscription portfolio (€50-500 annual spend minimum)  
**Secondary:** Corporate mobility managers (B2B future variant, out of scope for pilot)

---

## 2. FUNCTIONAL SCOPE

### In Scope: Core MVP (Pilot Phase)
1. **Portfolio Analysis** (retrospective, 12-month window)
   - Ingest mobility history across modes (DB, partners)
   - Detect patterns, inefficiencies, underutilization
   - Calculate cost and CO₂ for current vs. alternative portfolios

2. **Smart Recommendations** (forward-looking, 6-month horizon)
   - Predict mobility demand from calendar + historical patterns
   - Generate 2-3 contract scenarios with cost/CO₂ trade-offs
   - Rank by customer priority (cost minimization vs. sustainability vs. flexibility)

3. **Execution & Governance** (human-in-the-loop)
   - Present recommendations in DB App conversational interface
   - Capture user approval/rejection at each decision point
   - Execute approved changes via DB + partner APIs

4. **Annual Review** (DB Wrapped-style output)
   - Mobility review summary with savings achieved and CO₂ avoided
   - Ad-hoc Q&A interface for customer questions about recommendations

### Out of Scope: Phase 2+ (Post-MVP)
- Real-time dynamic pricing recommendations
- Multi-user household optimization
- Autonomous contract execution without approval
- B2B corporate mobility management variant
- Third-party comparison/switching recommendations (initially)

### Life Event Detection (MVP: Opt-In Only)
- Calendar sharing (planned trips)
- Email opt-in signals (job change, relocation detected via keywords)
- **Constraint:** No behavioral inference from location data; explicit user signals only

---

## 3. DATA & INTEGRATION LANDSCAPE

### Data Inputs (MVPs Priority)

**Tier 1: Critical for MVP**
| Source | Data Type | Availability | Dependencies |
|--------|-----------|--------------|--------------|
| DB Navigator API | Travel history (12mo) | Real-time | Must support historical export |
| DB Account System | Current subscriptions (BC, DT, PayBack) | Real-time | Master customer data |
| Partner APIs | Subscription status (Miles, Lime, E-Scooter, Stadtrad) | Real-time | Partnership agreements in place |
| Google Maps API | Multi-modal trip routing | Real-time | Geolocation consent for historical trips |
| Customer Preferences | Cost vs. CO₂ priority, flexibility needs | User input | Onboarding flow in DB App |

**Tier 2: Nice-to-Have MVP, Essential Phase 2**
| Source | Data Type | Availability | Dependencies |
|--------|-----------|--------------|--------------|
| Google Calendar | Planned trips & events | User opt-in | OAuth integration |
| Email signals | Life events (job, move, family) | User opt-in | Secure scanning, privacy compliance |
| Credit card statement | Non-tracked mobility spending | User opt-in | Open Banking / PSD2 integration |
| Payback, PayPal | Transaction history across modes | Real-time | Account linking |

**Tier 3: Future Enhancements**
- Corporate calendar (for B2B variant)
- Real-time traffic/transit disruptions
- Peer benchmarking (anonymized)

### Data Volume Estimates (Pilot: 1,000 customers)
- Travel history: 1-2GB (12 months × 1K customers × sparse events)
- Subscription/contract data: <100MB
- Generated scenarios/recommendations: ~50MB
- **Total:** ~2-3GB managed; easily runs in-memory for individual user analysis

### Data Quality & Governance Requirements
- **Travel history completeness:** Must cover all DB transactions; partners: best-effort baseline
- **Latency:** Portfolio analysis <10s; recommendation generation <30s (user waits)
- **Freshness:** Travel history synced daily; subscriptions updated on change
- **Privacy:** User opt-in for email/calendar; anonymize for benchmarking; GDPR compliance built-in
- **Audit trail:** All recommendations and approvals logged for dispute resolution & model monitoring

---

## 4. USER JOURNEY & INTERACTION MODEL

### Happy Path: Proactive Annual Review
```
1. User receives notification → "Your Mobility Review is ready"
2. Opens DB App → "Here's what we found in your 2025 travel"
3. System shows:
   - Portfolio summary (cost: €245/year, CO₂: 1.2 tons)
   - 3 scenarios: 
     * Option A: Save €80/year, CO₂ -0.1t (reduced flexibility)
     * Option B: Save €35/year, CO₂ -0.3t (recommended)
     * Option C: Increase spend €50/year, CO₂ -0.8t (sustainability focus)
4. User selects recommendation + approves contract changes
5. System executes changes in DB + partner systems
6. Confirmation: "✓ Updated. New portfolio starts June 1st"
```

### Reactive Path: Ad-Hoc Question
```
1. User asks in DB App: "What if I travel to Berlin every 2 weeks?"
2. System:
   - Predicts demand impact
   - Regenerates cost/CO₂ scenarios
   - Shows "Bahncard 100 now saves €120/year vs. pay-per-trip"
3. User can approve change or dismiss
```

### Edge Case: Conflicting Signals
```
1. System detects:
   - High CO₂ priority (user setting)
   - Recent relocation email signal (moving to rural area)
   - Historical city-center travel patterns
2. System pauses recommendation, asks for clarification:
   - "We detected a possible move. What's your new primary location?"
   - "Your travel patterns changed. Should we re-analyze?"
3. User input → refined recommendation
```

---

## 5. TECHNICAL ARCHITECTURE DIRECTION

### Recommended Approach: Advanced Multi-Agent System
**Rationale:** 
- Pilot scope requires forward-looking demand prediction (not just reactive analysis)
- Life event detection + calendar integration demands separate forecasting logic
- Cost/CO₂ trade-offs require optimization agent (not simple sorting)
- Conversational interface + approval gates demand communicator with user state tracking

### Agent Roles (Preliminary)

| Agent | Responsibility | Key Tools | Output |
|-------|-----------------|-----------|--------|
| **Analyst** | Pattern detection in 12mo history; inefficiency identification | Travel history APIs, contract catalog RAG | Efficiency metrics, savings potential |
| **Forecaster** | 6-month demand prediction from calendar + life events + seasonality | Calendar API, event signals, historical patterns | Predicted trips by mode/month |
| **Optimizer** | Generate 2-3 portfolio scenarios; calculate cost/CO₂ trade-offs | Scenario solver, pricing catalog, CO₂ factors | Ranked recommendation list |
| **Communicator** | Deliver recommendations; capture approvals; execute contracts | DB App interface, user context, contract APIs | User dialogue log, approval state |

### Integration Architecture (Sketch)
```
┌─────────────────────────────────────────────────────────────┐
│                    DB APP (UI/Chat)                         │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│     ORCHESTRATION LAYER (Agent Coordinator)                 │
│     - User context management                               │
│     - Multi-turn state tracking                             │
│     - Approval gate enforcement                             │
└────────────────────┬────────────────────────────────────────┘
                     │
      ┌──────────────┼──────────────┐
      │              │              │
  ┌───▼──┐    ┌─────▼────┐    ┌───▼────┐
  │Agent │    │Forecaster│    │Optimizer│  ┌────────────┐
  │Analyst│   │  Agent   │    │ Agent   │──│ Scenario   │
  │      │    │          │    │         │  │ Solver (LP)│
  └──────┘    └──────────┘    └─────────┘  └────────────┘
      │              │              │
      └──────────────┼──────────────┘
                     │
      ┌──────────────┼──────────────────────────┐
      │              │                          │
  ┌───▼──────┐  ┌───▼─────┐  ┌───────────────┐ │
  │DB APIs   │  │Partner  │  │RAG: Contract  │ │
  │(Nav,Acc) │  │APIs     │  │Catalog & CO₂  │ │
  └──────────┘  └─────────┘  │Data           │ │
                              └───────────────┘ │
                              ┌────────────┐    │
                              │Consent/    │    │
                              │Config DB   │    │
                              └────────────┘    │
                     User Data & Integration Layer
```

---

## 6. CONSTRAINTS & CRITICAL DEPENDENCIES

### Hard Constraints
| Constraint | Impact | Mitigation |
|-----------|--------|-----------|
| **API Availability** | Partner APIs must be 99%+ available; DB internal APIs: 99.9% | Define fallback logic; cache partner data; graceful degradation |
| **Data Privacy** | GDPR compliance mandatory; no behavioral inference without consent | Explicit opt-in for email/calendar; anonymize for benchmarking; audit logs |
| **Real-time Execution** | Contract changes must execute within 24h via partner APIs | Async task queue; state machine for tracking; retry logic |
| **User Approval Gates** | All contract changes require explicit user approval | Implement state machine; timeout after 30 days for pending approvals |

### Dependencies (Must Resolve Before Dev Starts)
1. **DB Navigator API contract** - Must support 12-month historical export
2. **Partner API agreements** - Verify Miles, Lime, E-Scooter, Stadtrad APIs are available & stable
3. **DB App integration point** - Where does the agent chat UI live? Embedded vs. separate?
4. **Contract catalog** - Get current pricing & contract combinations (used in RAG)
5. **CO₂ emission factors** - Source authoritative data by mode (DB can provide or external source)
6. **Opt-in consent flow** - Design and test email/calendar permission flow

---

## 7. KEY OPEN QUESTIONS FOR NEXT CLARIFICATION

**Architecture Decisions**
- [ ] Should the agent system run synchronously (user waits) or async (notification-driven)?
- [ ] Where does conversational state persist? (User-specific vector DB? Session store?)
- [ ] How many recommendation scenarios to generate? (2-3 recommended; more = analysis paralysis)

**Data & Privacy**
- [ ] Is email opt-in for life events critical for MVP or Phase 2? (If MVP, when does user sign up?)
- [ ] Can we use anonymized travel data for peer benchmarking? (Legal/Privacy review needed)
- [ ] What's the SLA for syncing partner subscription data? (Real-time vs. daily batch?)

**Integration & Operations**
- [ ] Who owns the contract execution API calls? (DB central platform vs. partner integrations?)
- [ ] What's the escalation path if agent recommends contract change but partner API fails?
- [ ] Do we need a monitoring/alert dashboard for ops team to track recommendation quality?

**Business & Commercials**
- [ ] Pilot scope: 1,000 customers? Internal beta only or select customers?
- [ ] Success metrics: Revenue impact (retention ↑, ARPU ↑) or cost savings to customer?
- [ ] Post-MVP: Do we offer B2B variant? Timeline & investment?

---

## 8. SUCCESS CRITERIA & METRICS

### MVP Success Criteria (Pilot Phase, ~1K customers)
- ✅ **Functional:** Agent generates 2-3 scenarios for >95% of customer portfolios
- ✅ **Accuracy:** Recommendations match manual review by 90%+ (validated by 50-customer sample)
- ✅ **Performance:** Analysis <10s, recommendations <30s, 99%+ API success rate
- ✅ **Adoption:** 20% of offered customers accept recommendation (baseline: 15%)
- ✅ **Impact:** Average €50-80 savings per accepting customer; CO₂ reduction traceable

### Launch Success Criteria (Full Rollout, ~1M customers)
- ✅ **Churn Impact:** -0.5-1% churn reduction year-over-year from customers using agent
- ✅ **Revenue:** +2-3% ARPU growth from optimized portfolio attachment
- ✅ **Sustainability:** >100K tons CO₂ reduction achieved across customer base
- ✅ **Operational:** <2% manual escalations; <1% API failure rate

---

## 9. TIMELINE & GOVERNANCE

### Project Phase Timeline
| Phase | Duration | Key Deliverables | Go/No-Go Gate |
|-------|----------|------------------|--------------|
| **Discovery & Design** | May 20 - June 15 | Context locked, Architecture blueprint, ADRs, Dev plan | June 16 Progress review |
| **Development** | June 16 - July 20 | Working prototype, Agent system, API integrations, Docs | July 21 Final review |
| **Hardening & Testing** | July 21 - Aug 25 | Pilot testing (100 customers), monitoring setup | Aug 26 Internal go-live decision |
| **Delivery** | Aug 26 - Aug 31 | Final documentation, ops handover, training materials | Aug 31 Delivery |

### Governance & Decision Rights
- **Weekly:** Technical team standup (internal)
- **Bi-weekly:** Steering committee (DB stakeholders + Consultancy leads)
- **Monthly:** Executive sponsor review (CEO, Product, Data leadership)
- **Gate Reviews:** Progress meeting (June 16), Final presentation (July 22), Delivery (Aug 31)

---

## 10. RISK ASSESSMENT (Preliminary)

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| **Partner API instability** | Medium | High | Early integration testing; fallback to cached data; clear degradation mode |
| **Life event detection false positives** | Medium | Medium | Start with calendar only (Phase 1); email signals Phase 2; user feedback loop |
| **Complex edge cases** (contradictory signals, rare patterns) | High | Low | Design explicit "ask for clarification" mode; don't force recommendation |
| **Data privacy/consent issues** | Low | Critical | Engage legal/compliance early; audit trail for all data access; user controls |
| **Tight timeline (16 wks)** | High | High | Aggressive MVP scope; use LLM as fallback for non-critical agents; parallel work streams |

---

## NEXT STEPS

### Immediate (This Week)
1. **Lock dependencies:** Verify API availability (Navigator, partner APIs, DB App integration point)
2. **Clarify scope:** Resolve open questions (Section 7)
3. **Design onboarding:** Plan user opt-in flow for email/calendar signals

### Week of June 2
1. **Create detailed Architecture Blueprint** with ADRs
2. **Define Agent Interaction Protocol** (state machine, approval gates)
3. **Spec API contracts** for Analyst, Forecaster, Optimizer agents
4. **Plan integration testing strategy**

### Week of June 9
1. **Finalize Technology Stack** (LLM provider, agent framework, DB choices)
2. **Design working prototype** scaffold
3. **Begin parallel dev streams** (API integration, agent logic, UI mockups)

---

**Document Owner:** Senior Data Consultant (GenAI Project Lead)  
**Status:** Draft - Awaiting Client Clarifications  
**Next Review:** June 2, 2026 (Post-clarification call)
