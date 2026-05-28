# MVP Requirements & Backlog
## DB MoveOptimizer - Prototype Phase (Weeks 1-16)

**Focus:** 12 core user stories + acceptance criteria for data scientists to build and test.  
**Approach:** Backlog-first; refine acceptance criteria during sprint planning.

---

## CORE USER STORIES

### Story 1: Ingest Travel History (Analyst Agent)
**As a** data scientist building the Analyst agent  
**I need** to load 12 months of synthetic travel history from the simulated API sandbox gateway  
**So that** I can analyze patterns and identify inefficiencies

**Acceptance Criteria:**
- ✅ Can query simulated sandbox API endpoints representing the DB Navigator JSON schema
- ✅ Load 12-month synthetic travel logs for 5 core traveler personas (<1 second)
- ✅ Parse JSON response: date, origin, destination, cost, mode, duration
- ✅ Handle malformed or missing synthetic data fields gracefully (fill with zeros, log errors)
- ✅ 100% database parity between sandbox output and relational structure
- ✅ Store in PostgreSQL/SQLite for downstream analysis

**Definition of Done:**
- Sandbox client function successfully returns a clean pandas DataFrame
- Tested against 100 generated synthetic customer profiles without failure
- Unit tests pass with >80% coverage


---

### Story 2: Detect Travel Patterns & Inefficiencies (Analyst Agent)
**As a** data scientist  
**I need** to analyze travel history and flag inefficiencies (wasted subscriptions, wrong Bahncard tier)  
**So that** the system can recommend better portfolios

**Acceptance Criteria:**
- ✅ Calculate: trip frequency by mode (train, scooter, etc.)
- ✅ Identify: unused subscriptions (<5% usage vs. cost)
- ✅ Identify: Bahncard tier mismatch (overpaying or underpaying)
- ✅ Flag patterns: >20% efficiency gain possible
- ✅ Output: Structured list of inefficiencies + savings potential

**Definition of Done:**
- Manual validation on 10 customers: 90%+ pattern detection accuracy
- Code tested; 80%+ coverage

---

### Story 3: Calculate Cost for Current Portfolio (Analyst Agent)
**As a** data scientist  
**I need** to accurately calculate customer's annual mobility cost  
**So that** I can compare scenarios against baseline

**Acceptance Criteria:**
- ✅ Ingest: current subscriptions (Bahncard tier, memberships, pay-as-you-go)
- ✅ Calculate: annual cost from 12-month history
- ✅ Account for: subscription fees, per-trip charges, bundling
- ✅ Accuracy: ±5% vs. customer's actual spend (validated on sample)
- ✅ Output: Cost breakdown by service + total

**Definition of Done:**
- Validated against 10 real customers' billing statements
- Unit tests pass

---

### Story 4: Forecast Demand (Forecaster Agent)
**As a** data scientist  
**I need** to predict customer's trip count for the next 6 months  
**So that** I can generate appropriate portfolio scenarios

**Acceptance Criteria:**
- ✅ Use 12-month history to detect seasonal patterns
- ✅ Forecast trip count by mode/month for +6 months ahead
- ✅ Incorporate confidence intervals (70-90% typical)
- ✅ Accuracy: ±20% on holdout 3-month test set
- ✅ Output: JSON with forecast + confidence

**Definition of Done:**
- Backtested on 20 historical customers (holdout validation)
- Forecast reasonably aligns with seasonal patterns
- Code tested

---

### Story 5: Generate Portfolio Scenarios (Optimizer Agent)
**As a** data scientist  
**I need** to generate 1-2 optimized portfolio scenarios based on forecasted demand  
**So that** I can show customers better options

**Acceptance Criteria:**
- ✅ Generate "Cost-Optimized" scenario (minimize annual spend)
- ✅ Optional "Balanced" scenario (weighted cost + coverage)
- ✅ Each scenario covers 95%+ predicted demand
- ✅ Use pricing catalog: Bahncard tiers, Deutschlandticket, pay-as-you-go
- ✅ Generation time: <30 seconds per customer
- ✅ Output: JSON with contract mix + annual cost

**Definition of Done:**
- Manual review: recommended contracts are sensible
- Tested on 20 customers; no errors
- Code tested

---

### Story 6: Calculate Cost/CO₂ for Scenarios (Optimizer Agent)
**As a** data scientist  
**I need** to calculate estimated cost and CO₂ for each scenario  
**So that** I can rank them by user priorities

**Acceptance Criteria:**
- ✅ Cost: Subscription + per-trip charges (accuracy ±5%)
- ✅ CO₂: Use emission factors (train 8g/km, car 250g/km, e-scooter 5g/km)
- ✅ Output: Annual cost, annual CO₂ (tons), % savings vs. current
- ✅ Include confidence/assumptions

**Definition of Done:**
- CO₂ calculations match reference data
- Manual review: costs are reasonable
- Unit tests pass

---

### Story 7: Rank Scenarios (Communicator Agent)
**As a** data scientist  
**I need** to rank scenarios based on user preferences  
**So that** I can highlight the best recommendation

**Acceptance Criteria:**
- ✅ Ingest: user priorities (cost weight, CO₂ weight)
- ✅ Calculate: weighted score for each scenario
- ✅ Rank: top scenario marked "Recommended"
- ✅ Output: Ranked list with scores

**Definition of Done:**
- Ranking logic is simple & explainable
- Manual tests pass (reasonable rankings)

---

### Story 8: Generate Recommendation Text (Communicator Agent)
**As a** data scientist  
**I need** to generate conversational recommendation text using an LLM  
**So that** customers understand why we recommend a specific portfolio

**Acceptance Criteria:**
- ✅ Input: Customer profile, recommended scenario, trade-offs
- ✅ Output: Natural language explanation (2-3 sentences)
- ✅ Tone: Helpful, non-technical, transparent
- ✅ Include: Savings potential, key changes

**Definition of Done:**
- LLM integration working (Claude API callable)
- Manual QA: 5 sample recommendations sound good
- Response time: <5 seconds per customer

---

### Story 9: Capture User Approval (Communicator Agent)
**As a** data scientist  
**I need** to implement a state machine for user approvals  
**So that** I can track whether users accept or reject recommendations

**Acceptance Criteria:**
- ✅ States: pending → approved / rejected
- ✅ Store: user decision, timestamp, recommendation ID
- ✅ Optional: allow user to provide feedback ("Why did you reject?")
- ✅ Persist: in PostgreSQL for audit trail

**Definition of Done:**
- State machine logic is correct (no invalid transitions)
- Database schema designed & tested
- Unit tests pass

---

### Story 10: Orchestrate All Agents (Core System)
**As a** data scientist  
**I need** to wire all 4 agents together in a coordinated flow  
**So that** the system works end-to-end: data → analysis → recommendation

**Acceptance Criteria:**
- ✅ Flow: Customer ID → fetch history → analyze → forecast → optimize → rank → present
- ✅ Handle errors: API failures, timeouts, edge cases (graceful degradation)
- ✅ Logging: full audit trail (what was analyzed, what was recommended)
- ✅ End-to-end latency: <60 seconds for all agents

**Definition of Done:**
- E2E flow tested on 10 customers
- Can handle API failures (fallback to cached data)
- Logging captures all major steps
- No crashes on edge cases

---

### Story 11: Build Monitoring Dashboard (Validation)
**As a** data scientist  
**I need** to track system performance (latency, accuracy, API success rates)  
**So that** I can identify issues during the pilot

**Acceptance Criteria:**
- ✅ Dashboard shows: Response time, recommendation accuracy, API errors
- ✅ Alerts: If latency >40s or API success <99%
- ✅ Logs: All recommendations + user decisions for analysis
- ✅ Accessible: Simple web dashboard or logs you can query

**Definition of Done:**
- Dashboard working & queryable
- Can see recommendation accuracy metrics
- Alerts firing correctly

---

### Story 12: Document System (Knowledge Transfer)
**As a** data scientist  
**I need** to document the architecture, API contracts, and troubleshooting  
**So that** the team can maintain and extend the system

**Acceptance Criteria:**
- ✅ Architecture overview (4-page doc with diagrams)
- ✅ API contracts (each agent's input/output spec)
- ✅ Troubleshooting guide (common errors + fixes)
- ✅ Code comments (all major functions documented)

**Definition of Done:**
- All docs written & reviewed
- Team can understand system from docs
- New team member could onboard using these docs

---

## ACCEPTANCE CRITERIA: SUMMARY TABLE

| Story | Must-Have | Definition of Done | Estimated Effort |
|-------|-----------|------------------|------------------|
| 1. Ingest History | Sandbox client working | 100 profiles, 100% completeness | 2 days |
| 2. Detect Patterns | Pattern detection logic | 90%+ accuracy on 10 samples | 3 days |
| 3. Calculate Cost | Cost calculation | ±5% accuracy on 10 customers | 2 days |
| 4. Forecast Demand | Demand model | ±20% accuracy on holdout test | 3 days |
| 5. Generate Scenarios | Scenario solver | <30s latency, sensible contracts | 3 days |
| 6. Calculate Metrics | Cost/CO₂ calc | Reasonable results | 1 day |
| 7. Rank Scenarios | Ranking logic | Correct ordering | 1 day |
| 8. Generate Text | LLM integration | Natural language output | 2 days |
| 9. Capture Approvals | State machine | Correct state transitions | 1 day |
| 10. Orchestrate Flow | End-to-end system | <60s latency, error handling | 4 days |
| 11. Monitoring | Dashboard | Performance metrics visible | 2 days |
| 12. Documentation | Docs complete | Team can understand system | 2 days |

---

## PHASE 2+ BACKLOG (DEFER)

These are NOT in MVP; keep for future phases:

- ❌ CO₂ footprint (Story 6 only calculates; no full analysis)
- ❌ Calendar integration (Story 4 uses history only; no calendar)
- ❌ Life event detection (Story 4 uses history only; no email signals)
- ❌ Production Partner API integration (Miles, Lime, Stadtrad)
- ❌ Live contract execution (no actual DB/partner API changes)
- ❌ "DB Wrapped" annual review dashboard
- ❌ Autonomous decisions (all changes require user approval)
- ❌ Multi-scenario approval (only top 1-2 scenarios)

---

## TESTING STRATEGY

### Unit Tests
- Each agent (Analyst, Forecaster, Optimizer, Communicator) has unit tests
- Goal: >80% code coverage

### Integration Tests
- Test end-to-end flow on 10 synthetic customers
- Test Sandbox API error handling (simulated failures)

### Validation Tests
- Manual review: 10 customers
  - Pattern detection accuracy: 90%+ vs. manual analysis
  - Cost calculation: ±5% vs. statements
  - Demand forecast: ±20% on historical data
  - Recommendations: Do they make sense?

---

## SUCCESS CRITERIA (Prototype Phase)

| Criterion | Target | Validation |
|-----------|--------|-----------|
| **All stories complete** | 12/12 | Code passing acceptance criteria |
| **Accuracy** | Pattern 90%, Cost ±5%, Forecast ±20% | Manual validation on 10 customers |
| **Performance** | <60s E2E, <30s per scenario | Latency monitoring |
| **Stability** | No crashes on 100 customers | Error logs clean |
| **Documentation** | All 12 stories documented | Team can understand |

---

## NOTE: Backlog Refinement

This is your working backlog. As you build:
- Move stories from "MVP" → "In Progress" → "Done"
- Refine acceptance criteria as you learn (no big surprises expected)
- Adjust effort estimates after Sprint 1
- Surface blocking issues early (sandbox schema mismatches, data quality)
