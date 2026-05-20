# Deutsche Bahn Mobility Portfolio Management Agent
## Comprehensive Project Charter & Plan

**Prepared by:** Senior Data Consultant (GenAI Project Leadership)  
**For:** Deutsche Bahn AG  
**Date:** May 20, 2026  
**Project Duration:** 16 weeks (May 20 - Aug 31, 2026)

---

## EXECUTIVE SUMMARY

### Strategic Opportunity
Deutsche Bahn can capture significant value by proactively optimizing each customer's mobility portfolio across DB and partner services. The **Mobility Portfolio Management Agent** (codename: *DB MoveOptimizer*) will:

- **For DB:** Reduce churn (projected -0.5-1% YoY), increase ARPU (+2-3%), strengthen ecosystem defensibility
- **For Customers:** Save €50-80/year, measurable CO₂ reduction, time reclaimed
- **For Sustainability:** Track and reduce customer-driven emissions at scale (100K+ tons CO₂ potential)

### Why Now?
1. **Technology maturity:** Multi-agent LLM systems proven in production; tool use frameworks stable
2. **Data readiness:** DB has consolidated travel history + subscription data; partner APIs increasingly available
3. **Market momentum:** Rising customer appetite for personalized recommendations + sustainability tracking
4. **Competitive urgency:** Standalone comparison apps lack DB ecosystem depth; defensible moat available

### Proposed Solution
An **advanced multi-agent system** (Analyst → Forecaster → Optimizer → Communicator) that:
- Analyzes 12 months of real mobility behavior across modes
- Predicts 6-month forward demand from calendar + life events
- Generates 2-3 portfolio scenarios with cost/CO₂ trade-offs
- Presents recommendations via DB App with human-in-the-loop approval
- Executes approved changes via DB + partner APIs
- Delivers annual "DB Wrapped" review with results

### Expected Business Impact (Pilot: 1,000 customers)
| Metric | Target | Confidence |
|--------|--------|-----------|
| Recommendation acceptance rate | 20% (+5% vs. baseline) | High |
| Average savings per accepting customer | €60-80 | Medium |
| Portfolio revenue impact | +€30-40K pilot → €3-5M scaled | Medium |
| CO₂ reduction tracked | 500-1000 tons/year pilot | High |
| Customer satisfaction (NPS) | +15-20 points | Medium |

### Budget & Resource Estimate (16 weeks)
- **Team:** 8 FTE (2 architects, 3 engineers, 1 data scientist, 1 ops/infra, 1 PM)
- **External:** LLM API costs (~€15-25K for pilot), partner API integrations
- **Total:** ~€480-600K (consulting + implementation + testing)

---

## PROJECT STRUCTURE & WORKSTREAMS

### Phase 1: Discovery & Architecture (May 20 - June 15, 4 weeks)

**Objective:** Lock context, design architecture, validate technical feasibility

**Workstream 1A: Requirements Engineering & Data Mapping**
- Finalize data requirements (Tier 1/2/3 prioritization)
- Map current state integrations (APIs, data models, latency SLAs)
- Design onboarding flow (consent management, preference capture)
- **Deliverable:** Data Architecture Document + Integration Dependency Map
- **Owner:** Data Architect
- **Resource:** 2 data engineers, 1 analyst
- **Duration:** 2 weeks

**Workstream 1B: Agent Architecture & Design**
- Design 4-agent system (Analyst, Forecaster, Optimizer, Communicator)
- Define agent roles, tools, state management, and interaction protocols
- Create state machine for approval gates and contract execution
- **Deliverable:** Architecture Blueprint (stakeholder + technical views) + ADRs (4-5 key decisions)
- **Owner:** Solution Architect
- **Resource:** 1 architect, 1 ML engineer
- **Duration:** 2 weeks (parallel with 1A)

**Workstream 1C: Technology Stack & Framework Evaluation**
- Evaluate agent frameworks (LangChain, AutoGen, LlamaIndex)
- Select LLM provider (Claude, GPT-4, Llama-via-BedRock)
- Design vector DB strategy (user context embeddings, contract catalog RAG)
- Design state store (user session, approval history, recommendations log)
- **Deliverable:** Tech Stack Recommendation + POC setup script
- **Owner:** Engineering Lead
- **Resource:** 1 architect, 1 senior engineer
- **Duration:** 1 week (parallel)

**Workstream 1D: API Integration Planning & Contracts**
- Finalize contracts with DB Navigator, partner APIs (Miles, Lime, Stadtrad)
- Design API contract specifications (error handling, rate limiting, retry logic)
- Plan OAuth integration for Google Calendar/Email
- **Deliverable:** API Contract Matrix + Integration Test Plan
- **Owner:** Integration Architect
- **Resource:** 1 integration engineer, 1 DB API liaison
- **Duration:** 2 weeks

**Workstream 1E: User Research & Interaction Design**
- Conduct 10-15 customer interviews (usage patterns, priorities, concerns)
- Design conversational flows (recommendation presentation, approval gates, FAQs)
- Create DB App UI mockups (chat, scenario comparison, approval buttons)
- **Deliverable:** User Personas + Interaction Design Spec + UI Wireframes
- **Owner:** Product Manager
- **Resource:** 1 UX researcher, 1 designer
- **Duration:** 2 weeks

**Phase 1 Gate Review:** June 15 (Progress Meeting with Client)
- Context fully locked ✓
- Architecture approved by DB technical & business stakeholders ✓
- Dependencies resolved; APIs ready for integration ✓
- **Go/No-Go Decision:** Proceed to development

---

### Phase 2: Development & Integration (June 16 - July 20, 5 weeks)

**Objective:** Build working prototype with all agents integrated end-to-end

**Workstream 2A: Agent Development (Core Logic)**

*Analyst Agent (Week 1-2)*
- Implement pattern detection algorithm (clustering, anomaly detection, efficiency scoring)
- Build travel history ingestion pipeline (DB Navigator API → vector embeddings)
- Create RAG interface to contract catalog (query: "inefficient patterns" → recommendations)
- **Deliverable:** Analyst agent callable, tested with 100-customer sample data

*Forecaster Agent (Week 2-3)*
- Implement demand prediction model (time-series forecasting + calendar events + seasonality)
- Integrate calendar API (opt-in flow, event extraction, privacy handling)
- Build life event signal processor (email keywords, relocation detection)
- **Deliverable:** Forecaster agent callable, 6-month demand predictions validated

*Optimizer Agent (Week 3-4)*
- Implement scenario solver (constraint satisfaction + cost/CO₂ optimization)
- Connect to pricing catalog (Bahncard tiers, Deutschlandticket, partner memberships)
- Build scenario ranking logic (user preferences: cost vs. sustainability vs. flexibility)
- **Deliverable:** Optimizer generates 2-3 scenarios with rankings

*Communicator Agent (Week 4-5)*
- Implement conversational interface (recommendation presentation, Q&A handling)
- Build approval state machine (pending → approved → executed → confirmed)
- Integrate user context management (preference tracking, decision history)
- **Deliverable:** Communicator agent with sample dialogs

**Owner:** ML Engineering Lead + 2 ML Engineers  
**Resource:** 3 FTE, continuous pairing with data scientist  
**Outputs:** 4 callable agent modules, integration test suite

---

**Workstream 2B: API Integration & Data Pipelines**

*DB API Integration (Week 1-2)*
- Implement DB Navigator API client (travel history extraction, error handling, caching)
- Build DB Account System integration (current subscriptions, Bahncard status)
- Create data ingestion pipeline (scheduled daily sync, delta updates)

*Partner API Integration (Week 2-3)*
- Implement Miles, Lime, E-Scooter, Stadtrad API clients
- Build fallback/degradation logic (if partner API down, use cached data)
- Design partner contract execution flow (approval → API call → confirmation)

*External Data Integration (Week 3-4)*
- Integrate Google Maps API (multi-modal trip routing, historical routing)
- Integrate CO₂ emission factors (source: DEFRA/BEIS or equivalent; build lookup table)
- Build consent/OAuth flow (calendar, email opt-in with user controls)

**Owner:** Integration/Data Engineer  
**Resource:** 1 integration engineer + 1 data engineer  
**Outputs:** All APIs live and tested; data pipelines running in staging

---

**Workstream 2C: State Management & Orchestration**

*User Context Store*
- Design & implement user session store (preferences, consent status, recommendation history)
- Build vector embeddings for user context (travel patterns, lifestyle, priorities)
- Implement context isolation between agents (no full history passed to each agent)

*Orchestration Layer*
- Implement agent coordinator (routes to Analyst → Forecaster → Optimizer → Communicator)
- Build approval state machine (pending, approved, executed, failed, rolled-back)
- Implement error handling & retry logic (API failures, timeouts, edge cases)

*Conversation & Memory Management*
- Implement multi-turn conversation state tracking
- Build approval timeout logic (30 days for pending recommendations)
- Create audit log (all recommendations, approvals, executions, errors)

**Owner:** Backend Engineer  
**Resource:** 1-2 backend engineers  
**Outputs:** Orchestration layer callable, state machine tested

---

**Workstream 2D: DB App Integration & UI Implementation**

*Chat Interface Integration*
- Embed conversational agent in DB App (chat widget vs. new screen)
- Build recommendation presentation UI (scenario cards, cost/CO₂ comparisons)
- Implement approval flow (confirm changes, schedule execution date)

*Results Visualization*
- Build annual review dashboard ("DB Wrapped" style summary)
- Implement cost/CO₂ trend tracking (charts, metrics, achievements)
- Create ad-hoc Q&A interface (user asks questions about recommendations)

**Owner:** Frontend/UX Engineer  
**Resource:** 1 frontend engineer + 1 UX designer  
**Outputs:** UI implemented in staging DB App; end-to-end flow testable

---

**Workstream 2E: Testing, Quality & Documentation**

*Unit & Integration Testing*
- Agent logic tests (pattern detection accuracy, forecasting performance)
- API integration tests (all external APIs mocked + live staging)
- State machine tests (approval flows, edge cases, rollback scenarios)
- End-to-end tests (10 complete customer flows with synthetic data)

*Documentation*
- System architecture documentation (technical reference)
- Agent protocols & tool specifications (for future extensions)
- API integration guide (for ops handover)
- Troubleshooting & runbook (common issues, escalation paths)

**Owner:** QA Lead + Documentation Owner  
**Resource:** 1 QA engineer, 1 technical writer  
**Outputs:** Test suite (>80% coverage), comprehensive docs, runbook

---

**Phase 2 Gate Review:** July 21 (Final Presentation + Technical Review)
- All agents integrated end-to-end ✓
- APIs tested with staging data ✓
- UI mockups → implementation complete ✓
- Documentation + runbooks ready ✓
- **Go/No-Go Decision:** Proceed to pilot testing

---

### Phase 3: Pilot Testing & Hardening (July 21 - Aug 25, 5 weeks)

**Objective:** Validate system in production with 100-1000 real customers; measure accuracy & impact

**Workstream 3A: Pilot Launch (Cohort 1: 100 customers)**
- Soft launch to internal DB employees + select customers (high engagement)
- Monitor agent recommendation quality (accuracy vs. manual review)
- Capture user feedback (NPS, feature requests, bug reports)
- **Duration:** Week 1-2
- **Success Criteria:** <5% critical bugs, 90%+ recommendation accuracy, 15%+ acceptance rate

**Workstream 3B: Scale to 1,000 customers**
- Expand pilot to broader segment (representative portfolio diversity)
- Monitor system performance (latency, API success rate, error handling)
- Track business impact (churn, ARPU, CO₂ reduction)
- **Duration:** Week 3-4
- **Success Criteria:** 99%+ API availability, <10s analysis time, 18%+ acceptance rate

**Workstream 3C: Production Hardening**
- Identify and fix edge cases discovered in pilot
- Tune performance (agent latency, API caching, batch processing)
- Build monitoring & alerting (recommendation quality metrics, API failures, user issues)
- **Duration:** Week 4-5

**Owner:** Product Manager + QA + Ops  
**Resource:** 1 PM, 1 QA, 1 ops engineer, 1 data analyst  
**Outputs:** Pilot results dashboard, issue log (prioritized), ops playbook

---

### Phase 4: Delivery & Ops Handover (Aug 26 - Aug 31, 1 week)

**Objective:** Finalize documentation, train ops team, hand off to DB for full rollout

**Workstream 4A: Finalization**
- Incorporate pilot learnings (bug fixes, performance tuning)
- Finalize all documentation (runbook, troubleshooting, escalation paths)
- Create ops training materials (dashboard interpretation, alert response)

**Workstream 4B: Knowledge Transfer**
- Conduct ops team training (system architecture, common issues, monitoring)
- Document decision logs (why this architecture, trade-offs accepted)
- Create post-launch support plan (weeks 1-4 after full rollout)

**Workstream 4C: Delivery**
- Final system verification (all tests passing, monitoring active)
- Deliver all artifacts (code, docs, runbooks, training materials)
- Brief executive sponsor (results, next steps, post-MVP roadmap)

**Owner:** Project Manager + Engineering Lead  
**Resource:** Full team, 50% allocation  
**Outputs:** Production-ready system, fully documented, ops team trained

---

## RESOURCE PLAN & TEAM STRUCTURE

### Core Team (FTE Allocation Over 16 Weeks)

**Leadership & Architecture (2 FTE)**
- Senior Solutions Architect (1.0 FTE) - Design, decision-making, stakeholder management
- Project Manager (1.0 FTE) - Timeline, budget, risk, communication

**Engineering (3.5 FTE)**
- ML Engineering Lead (1.0 FTE) - Agent development oversight, quality
- ML Engineers (2.0 FTE) - Analyst, Forecaster, Optimizer agent implementation
- Backend/Integration Engineer (0.5 FTE) - Orchestration, state management

**Data & Infra (1.5 FTE)**
- Data Architect (0.5 FTE) - Data pipeline, RAG design, vector DB
- Data Engineer (0.5 FTE) - API integration, data pipelines
- DevOps/Infra (0.5 FTE) - Staging/production environment, monitoring

**Product & UX (1.0 FTE)**
- Product Manager (0.5 FTE) - User research, requirements, feature prioritization
- UX Designer (0.5 FTE) - Interaction design, UI mockups, user testing

**Quality & Docs (0.5 FTE)**
- QA Engineer (0.5 FTE) - Test planning, end-to-end testing

**Stakeholder Support (1.0 FTE)**
- DB Liaison / Integration Manager (1.0 FTE) - API contracts, partner coordination, internal alignment
- Technical Writer (0.5 FTE) - Architecture docs, runbooks, training materials (part-time; ramp up Phase 2+)

**Total Core Team: 8.5 FTE over 16 weeks**

### Extended Team & Dependencies
- **DB API Owners:** Navigator, Account System (available for integration support)
- **Partner Liaisons:** Miles, Lime, Stadtrad, E-Scooter (API availability, SLAs)
- **Legal/Compliance:** Privacy review for email opt-in, GDPR audit
- **Sponsor:** VP Product/Data (decisions, go/no-go gates, escalation)

---

## BUDGET ESTIMATE

### Cost Breakdown (Consulting + Engineering + Infrastructure)

**Personnel Costs (16 weeks, 8.5 FTE @ €6.5K/week avg.)**
- Core team: 8.5 FTE × 16 weeks × €6.5K/FTE/week = **€884K**
- (Blended rate: architects €8K/week, engineers €7K/week, ops €5K/week)

**Technology & Infrastructure**
- LLM API costs (Claude, GPT-4): ~€1.5K/week (pilot volumes) = **€24K**
- Vector DB (Weaviate/Pinecone): ~€500/mo setup + €2K/mo ops = **€10K**
- AWS/GCP cloud infra (staging + prod): ~€3K/month = **€12K**
- Development tools & licenses: **€5K**
- **Subtotal Tech:** €51K

**External Services & Integrations**
- Partner API contracts/integration fees: ~€10-20K (estimate, varies)
- Legal/compliance review: ~€5K
- **Subtotal External:** €25K

**Contingency (15% for unknowns & overruns)**
- **Contingency:** €138K

**TOTAL PROJECT BUDGET: €1,098K (~€1.1M)**

### Cost Optimization Opportunities
- **Use open-source LLMs** instead of paid APIs (Llama-2/3 via AWS Bedrock) → Save €20-30K
- **Phase out external consulting** at Aug 15 (not full delivery week) → Save €20-30K
- **Partner API fee waivers** (negotiate pilot rates) → Save €10-15K
- **Aggressive cloud cost optimization** → Save €5-10K
- **Target realistic cost: €950-1050K**

---

## RISK MANAGEMENT MATRIX

### High-Priority Risks & Mitigation

| # | Risk | Prob. | Impact | Mitigation | Owner |
|---|------|-------|--------|-----------|-------|
| **R1** | Partner APIs unstable/unavailable | M | H | Early integration POC (Week 1); fallback to cached data; clear degradation mode | Integration Lead |
| **R2** | Life event detection generates false positives | M | M | Start with calendar only (Phase 1); email Phase 2; explicit user feedback loop | ML Lead |
| **R3** | Customer privacy concerns (email opt-in) | M | M | Legal/compliance review early (Week 1); transparent consent flow; clear data deletion | PM + Legal |
| **R4** | Tight 16-week timeline | H | H | Aggressive MVP scope; parallel workstreams; no scope creep; weekly burn-down | PM |
| **R5** | Complex edge cases (contradictory signals) | H | L | Design "ask user" mode explicitly; don't force recommendation; user override | ML Lead |
| **R6** | Cost/CO₂ solver generates sub-optimal scenarios | M | M | Validate solver logic early (Week 2); use reference implementations (CPLEX/Pyomo) | Data Sci |
| **R7** | Contract execution API fails after user approval | L | H | Build retry/rollback logic; detailed audit log; manual escalation process | Backend Lead |
| **R8** | Recommendation accuracy below 90% threshold | M | H | Iterate on Analyst logic; gather manual review feedback; adjust feature engineering | ML Lead |

### Risk Monitoring & Escalation
- **Weekly:** Risk scorecard reviewed in standup (likelihood, impact, mitigation status)
- **Bi-weekly:** Risk review in steering committee (escalate red items)
- **Monthly:** Executive sponsor notified of major risks + contingency plans

---

## SUCCESS METRICS & KPIs

### Phase 1: Design Success (June 15 Gate)
- [ ] Architecture blueprint approved by DB technical leads
- [ ] All dependencies identified and on track (APIs, data, integrations)
- [ ] Budget & timeline accepted by sponsor
- [ ] Kickoff with full team completed

### Phase 2: Development Success (July 21 Gate)
- [ ] All 4 agents integrated end-to-end (callable)
- [ ] Core APIs tested with staging data (Nav, Partners, Google)
- [ ] UI mockups → implementation (first version in DB App)
- [ ] Test suite >80% coverage; critical bugs: 0
- [ ] Full documentation delivered

### Phase 3: Pilot Success (Aug 25 Completion)
- [ ] 1,000 customers active in pilot
- [ ] Recommendation accuracy: ≥90% (vs. manual review of 50 customers)
- [ ] System performance: <10s analysis, <30s recommendations, 99%+ API success
- [ ] User adoption: ≥20% recommendation acceptance
- [ ] Business impact: ≥€30K pilot customer savings, ≥500 tons CO₂ reduction tracked
- [ ] NPS: +15 points vs. baseline (customer satisfaction)

### Phase 4: Delivery Success (Aug 31 Completion)
- [ ] Production system live & stable (99%+ uptime Week 1)
- [ ] Ops team trained & confident (runbook comprehension test: 90%+)
- [ ] All docs delivered (architecture, APIs, runbooks, troubleshooting)
- [ ] Post-launch support plan active (first 4 weeks covered)

### Post-Launch KPIs (Ongoing)
- **Revenue Impact:** +€500K-1M/year from ARPU + reduced churn (projected)
- **Sustainability:** 100K+ tons CO₂ reduction tracked annually
- **Customer Experience:** NPS +20-30 points among active users
- **Operational:** <2% manual escalations, <1 hour mean resolution time

---

## GOVERNANCE & DECISION FRAMEWORK

### Steering Committee (Bi-weekly)
**Attendees:** DB VP Product, DB Data Lead, Consultancy Lead, Project Sponsor, Architect  
**Format:** 1-hour review; decision-log maintained  
**Decisions:** Scope changes, major trade-offs, risk escalations, go/no-go gates

### Technical Working Group (Weekly)
**Attendees:** Engineering leads, architects, ops representative  
**Format:** 30-min standup; issue triage; dependency mgmt  
**Decisions:** Technical trade-offs, architecture refinement, issue prioritization

### Escalation Path (Priority Order)
1. **Technical:** Engineering Lead → Solution Architect → Steering Committee
2. **Schedule:** Project Manager → Sponsor → Executive Steering Committee
3. **Budget:** Project Manager → Finance Lead → Executive Steering Committee
4. **Risk/Scope:** Solution Architect → Sponsor → Executive Steering Committee

---

## NEXT STEPS (IMMEDIATE)

### By May 22 (This Week)
- [ ] **Kickoff meeting** with DB sponsor & stakeholders (align on scope, timeline, budget)
- [ ] **Clarification call** to resolve Section 7 open questions (15 minutes per question)
- [ ] **Confirm team assignments** from both DB and Consultancy
- [ ] **Finalize API contracts** (Navigator, Partners, Google OAuth)

### By May 29 (Next Week)
- [ ] **Workstream 1D starts** (API integration planning)
- [ ] **Workstream 1E starts** (user research interviews)
- [ ] **Technology stack decisions** finalized
- [ ] **Data infrastructure** (staging environment) provisioned

### By June 5
- [ ] Context lock document validated & signed off by DB
- [ ] Architecture blueprint 70% complete
- [ ] ADRs (4-5 key decisions) drafted

### By June 15 (Progress Meeting with Client)
- [ ] Full context locked & documented ✓
- [ ] Architecture approved & signed ✓
- [ ] Development can start immediately ✓
- [ ] **Go/No-Go Decision** to proceed

---

## APPENDICES

### Appendix A: Suggested Technology Stack
- **LLM Provider:** Claude 3 Opus (via Anthropic API) or GPT-4 Turbo (via Azure OpenAI)
- **Agent Framework:** LangChain (v0.2+) with ReAct prompting for multi-step reasoning
- **Vector DB:** Weaviate (self-hosted on AWS EC2) for contract catalog RAG
- **State Store:** PostgreSQL with custom session management + Redis for fast caching
- **Backend:** Python/FastAPI (agent logic) + Node.js/Express (orchestration + API gateway)
- **Frontend:** React (DB App integration), WebSocket for real-time agent updates
- **Deployment:** Docker + Kubernetes (EKS) for agent services, Lambda for async tasks
- **Monitoring:** DataDog or New Relic + custom dashboards for agent performance

### Appendix B: Dependency Checklist (Before Dev Starts)
- [ ] DB Navigator API: Contract signed, 12-month historical export confirmed
- [ ] Partner APIs: Miles, Lime, Stadtrad, E-Scooter APIs documented & available
- [ ] Google API: Maps + Calendar OAuth flows documented
- [ ] DB App: Integration point defined (chat embed vs. new screen)
- [ ] Pricing Data: Current BC tiers, Deutschlandticket, partner pricing documented
- [ ] CO₂ Data: Emission factors by mode sourced & validated
- [ ] Legal/Compliance: Email opt-in flow reviewed & approved
- [ ] Consent Flow: Design & UX review complete
- [ ] Pilot Customer List: 1,000 representative customers identified

### Appendix C: Phase 1 Detailed Workstream Timeline
*(See separate Phase 1 Detailed Schedule document)*

---

**Document Owner:** Senior Data Consultant  
**Version:** 1.0 - Draft  
**Status:** Ready for Client Clarification & Approval  
**Next Review:** May 24, 2026 (Post-clarification)
