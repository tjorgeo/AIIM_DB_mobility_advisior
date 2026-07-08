# DB MoveOptimizer - Technical Architecture
## 4-Agent System Design for Prototype Phase

**Version:** 1.0 (Prototype) | **Date:** May 20, 2026  
**Audience:** Data Scientists, Engineers  
**Scope:** MVP Phase (Weeks 1-16); Phase 2+ sections deferred

---

## SYSTEM OVERVIEW

**4-Agent Architecture:**
```
User Request
    ↓
┌─────────────────────────────────────────────────────┐
│ Orchestrator (Python/FastAPI)                       │
│ • Multi-turn state management                       │
│ • Error handling & retry logic                      │
└────┬────────────────┬──────────────┬────────────────┘
     │                │              │
┌────▼───┐    ┌──────▼─────┐   ┌────▼────┐
│Analyst │    │ Forecaster │   │Optimizer│
│ Agent  │    │   Agent    │   │ Agent   │
└────┬───┘    └──────┬─────┘   └────┬────┘
     │                │              │
     └────────┬───────┴──────────────┘
              │
       ┌──────▼──────────┐
       │ Communicator    │
       │ Agent           │
       │ (Chat/Approval) │
       └─────────────────┘
              ↓
         User Response
```

---

## COMPONENT DETAILS

### 1. Analyst Agent
**Purpose:** Analyze 12-month travel history; identify patterns & inefficiencies

**Input:**
- Travel history (date, origin, destination, cost, mode) from simulated DB Navigator API sandbox
- Current subscriptions (Bahncard tier, memberships, costs)

**Process:**
- Parse trips: frequency by mode, distance distributions
- Calculate efficiency: cost per trip by subscription vs. alternatives
- Identify: unused subscriptions, over/under-provisioning

**Output:**
```json
{
  "total_trips": 25,
  "total_cost": 245,
  "efficiency_scores": {
    "bahncard_25": "good (used for 15/25 potential trips)",
    "miles": "unused (€10 wasted)"
  },
  "savings_potential": 50
}
```

**Tech Stack:**
- Python: pandas, numpy, scikit-learn (clustering)
- DB: PostgreSQL (travel history storage)
- Vector DB: Weaviate (pattern embeddings for future similarity search)

---

### 2. Forecaster Agent
**Purpose:** Predict demand for next 6 months

**Input:**
- Historical travel patterns (12-month data from Analyst)
- Calendar events (optional, if user shared)
- Seasonal patterns detected from history

**Process:**
- Detect seasonality: Q1 vs Q3 variations, holidays
- Forecast: trips/month for +6 months
- Confidence intervals: 70-95% range (based on data quality)

**Output:**
```json
{
  "forecast_6mo": [
    {"month": "June", "train_trips": 6, "confidence": 0.85},
    {"month": "July", "train_trips": 4, "confidence": 0.70}
  ],
  "total_predicted_trips": 32
}
```

**Tech Stack:**
- Time-series forecasting: Prophet or ARIMA (Python: statsmodels, prophet)
- Natural language: LLM reasoning for patterns (Claude API calls)

**Note:** Calendar & life event detection deferred to Phase 2

---

### 3. Optimizer Agent
**Purpose:** Generate 2 cost-optimized portfolio scenarios

**Input:**
- Analyst efficiency report (current inefficiencies)
- Forecaster demand prediction (expected trips next 6 months)
- Pricing catalog (all subscription options + rates)
- CO₂ factors (emission rates by mode)

**Process:**
1. Scenario A: Minimize cost for predicted demand
2. Scenario B: Balanced (cost + coverage + flexibility)
3. For each: Calculate annual cost, CO₂ impact
4. Rank by user priority (simple weighted scoring)

**Output:**
```json
{
  "scenarios": [
    {
      "id": "A",
      "label": "Cost-Optimized",
      "changes": [
        {"action": "cancel", "item": "Miles", "savings": "€120/year"}
      ],
      "annual_cost": 156,
      "co2_tons": 0.95,
      "explanation": "Cancel unused Miles; keep Bahncard 25 for flexibility"
    }
  ]
}
```

**Tech Stack:**
- Scenario solver: Greedy heuristic or linear programming (Python: PuLP, Pyomo)
- Pricing logic: Rule engine (Python functions)

---

### 4. Communicator Agent
**Purpose:** Present recommendations; capture user approval

**Input:**
- Optimizer scenarios (ranked by preference)
- User context (cost vs. CO₂ priorities)

**Process:**
1. Generate natural language explanation (LLM)
2. Display recommendation in chat UI
3. Capture user decision (approve/decline/more questions)
4. Track approval state in database

**Output:**
```
"I analyzed your travel. Here's what I found:
 
 You spent €245 on train travel in 2025. I found a way to save €41/year:
 Cancel unused Miles membership (€10/year savings) and keep your
 Bahncard 25 for flexibility.
 
 Should I make this change?"
 
User Decision: [Approve] [More Info] [Decline]
```

**Tech Stack:**
- LLM: Claude API (for natural language generation)
- State machine: Python async/await (track approval states)
- UI: React chat widget in DB App

---

## DATA FLOW (HAPPY PATH)

```
1. User opens DB App → Load user context (PostgreSQL)

2. User requests: "Analyze my mobility"

3. Orchestrator routes to ANALYST (parallel with FORECASTER):
   ANALYST:
   ├─ Query Simulated API Gateway (synthetic travel history, 12 months)
   ├─ Parse into DataFrame
   ├─ Store in PostgreSQL
   ├─ Calculate patterns + efficiency
   └─ Return: Efficiency report
   
   FORECASTER:
   ├─ Load travel history from PostgreSQL  
   ├─ Detect seasonality
   ├─ Predict next 6 months
   └─ Return: Demand forecast

4. Orchestrator routes to OPTIMIZER:
   ├─ Ingest Analyst + Forecaster outputs
   ├─ Query pricing catalog (PostgreSQL)
   ├─ Generate 2 scenarios (cost-optimized, balanced)
   ├─ Calculate cost/CO₂ for each
   └─ Return: Ranked scenarios

5. Orchestrator routes to COMMUNICATOR:
   ├─ LLM generates natural language explanation
   ├─ Present to user via chat
   └─ Await user decision

6. USER APPROVES:
   ├─ Store approval in PostgreSQL
   ├─ Log audit trail
   └─ Display confirmation

Total latency: <60 seconds for all agents
```

---

## DATA STORAGE

### PostgreSQL Schema (Core Tables)

```sql
-- Users & Context
CREATE TABLE users (
  id UUID PRIMARY KEY,
  db_customer_id VARCHAR,
  created_at TIMESTAMP,
  preferences JSONB (cost_priority: 0-100, co2_priority: 0-100),
  consent_status JSONB (email_opted_in: bool, calendar_shared: bool)
);

-- Travel History (implemented as a two-level trips → legs model; see
-- database/init/01_create_table.sql for the authoritative schema)
CREATE TABLE user_trips (
  trip_id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  trip_date DATE,
  main_transport_mode VARCHAR,  -- CHECK-constrained enum (see below)
  ...
);

CREATE TABLE trip_legs (
  leg_id UUID PRIMARY KEY,
  trip_id UUID REFERENCES user_trips,
  -- Regional vs. long-distance rail is encoded directly in this enum (AMB-01),
  -- not via a separate train_type/is_regional field:
  transport_mode VARCHAR,  -- public_transport | regional_train | long_distance_train
                           -- | e_scooter | car | car_sharing | ride_hailing
                           -- | taxi | bike_sharing
  origin_label VARCHAR, origin_city VARCHAR, origin_postal_code VARCHAR,
  destination_label VARCHAR, destination_city VARCHAR, destination_postal_code VARCHAR,
  estimated_cost_eur FLOAT,
  reference_cost_eur FLOAT,        -- pay-as-you-go price (savings baseline)
  estimated_co2_emissions FLOAT,
  ticket_class INTEGER
);

-- Current Subscriptions
CREATE TABLE subscriptions (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  service VARCHAR (bahncard_25/deutschlandticket/miles/lime),
  status VARCHAR (active/cancelled),
  monthly_cost_eur FLOAT,
  renewal_date DATE
);

-- Recommendations & Approvals
CREATE TABLE recommendations (
  id UUID PRIMARY KEY,
  user_id UUID REFERENCES users,
  created_at TIMESTAMP,
  scenarios JSONB,
  status VARCHAR (analyzing/ready/approved/executed/rejected),
  approval_timestamp TIMESTAMP
);

-- Audit Trail
CREATE TABLE audit_log (
  id UUID PRIMARY KEY,
  user_id UUID,
  action VARCHAR,
  details JSONB,
  timestamp TIMESTAMP,
  INDEX (user_id, timestamp)
);
```

### Redis (Caching) — Phase 2 (NOT implemented in Phase 1)
> Phase 1 persistence is **PostgreSQL-only**; there is no Redis container. Session state is
> simply the `recommendations` row id returned to the frontend (see AMB-09). The following is
> the Phase-2 caching target:
- Session state: Multi-turn conversation (24h TTL)
- User context: Cached preferences + consent (1h TTL)
- Travel history cache: 12-month summary (24h TTL)

### Vector Store (Weaviate - Optional for MVP, Add if Time)
- Travel pattern embeddings (for future similarity search)
- Contract catalog search (not critical for MVP)

---

## API INTEGRATIONS

### Simulated DB Navigator API (Sandbox Gateway)
**Endpoint:** `GET /v1/sandbox/travel-history?from_date=YYYY-MM-DD&to_date=YYYY-MM-DD`

**Response:**
```json
{
  "trips": [
    {
      "date": "2025-01-15",
      "from": {"city": "Berlin", "station": "Hauptbahnhof"},
      "to": {"city": "Munich", "station": "Hauptbahnhof"},
      "mode": "long_distance_train",
      "_comment_mode": "ingestion maps this to trip_legs.transport_mode; rail is split into regional_train | long_distance_train (AMB-01)",
      "distance_km": 600,
      "cost_eur": 89.90,
      "class": "2",
      "duration_minutes": 360
    }
  ]
}
```

**Error Handling:** Retry 3× with exponential backoff; use cached data if API down

### Google Maps API
**Endpoint:** `GET /maps/api/directions` (optional for Phase 2, not MVP)

**For MVP:** Not required; use simple distance calculations from travel history

### Pricing Catalog (Internal DB)
**Schema:**
```json
{
  "contracts": [
    {
      "id": "bahncard_25",
      "name": "Bahncard 25",
      "monthly_cost": 10,
      "discount_percent": 25,
      "coverage": "Nationwide trains"
    },
    {
      "id": "deutschlandticket",
      "name": "Deutschlandticket",
      "monthly_cost": 49,
      "unlimited_trips": true,
      "coverage": "All trains (5th person free)"
    }
  ]
}
```

**Maintenance:** Updated quarterly (or on-demand if DB notifies)

---

## TECH STACK DECISIONS

| Component | Choice | Rationale |
|-----------|--------|-----------|
| **Language** | Python 3.11 | Team expertise; ML libraries; agent frameworks |
| **Agent Framework** | LangChain | Mature ecosystem; good tool integration |
| **LLM** | Claude 3.5 (Anthropic) | Strong reasoning; cost-effective |
| **Web Framework** | FastAPI | Async support; type safety; docs auto-generated |
| **Database** | PostgreSQL | Relational data; JSONB support for flexibility |
| **Cache** | Redis | Fast session state; TTL support |
| **Vector DB** | Weaviate (Phase 2) | For pattern/contract search (defer if time-constrained) |
| **Async Execution** | Python asyncio | Built-in; works with FastAPI |

---

## ERROR HANDLING & RESILIENCE

### API Failures
- **Simulated Sandbox Gateway down:** Use cached synthetic travel history (log warning)
- **Partner API Sandbox down:** Use last known subscription state
- **Google Maps mock down:** Skip routing optimization (MVP doesn't need it anyway)

### Agent Failures
- **Analyst timeout:** Return partial efficiency report with low confidence
- **Forecaster timeout:** Use naive forecast (historical average)
- **Optimizer timeout:** Return single "cost-optimized" scenario
- **LLM timeout:** Use template-based explanation instead

### Data Quality Issues
- **Missing travel data:** Log gaps; flag customer for manual review
- **Cost inconsistencies:** Use best-estimate; show confidence intervals
- **API data format changes:** Add schema validation; fail loudly

---

## KEY DECISIONS (Architecture Decision Records)

### ADR-1: Multi-Agent Decomposition
**Decision:** Split into 4 agents (Analyst, Forecaster, Optimizer, Communicator) vs. single agent

**Rationale:**
- ✅ Separation of concerns (each agent has clear responsibility)
- ✅ Testability (test each agent independently)
- ✅ Reusability (Analyst output used by Optimizer)
- ✅ Latency (can run Analyst + Forecaster in parallel)

---

### ADR-2: Synchronous Agent Flow vs. Async/Event-Driven
**Decision:** Synchronous orchestration (user waits <60s) vs. async (notification after analysis)

**Rationale:**
- ✅ Better UX (user gets immediate feedback)
- ✅ Simpler error handling (know result right away)
- ✅ MVP doesn't need long-running async (16-week timeline)

**Tradeoff:** Requires aggressive performance tuning (<30s per agent)

---

### ADR-3: LLM for Natural Language vs. Template-Based
**Decision:** Use Claude API for generating recommendations vs. templates

**Rationale:**
- ✅ More natural, personalized explanations
- ✅ Can handle edge cases (templates too rigid)
- ✅ Cost acceptable for MVP scale (1K customers)

**Risk:** LLM failures require fallback to templates

---

### ADR-4: Scenario Solver Approach
**Decision:** Greedy heuristic vs. Linear Programming

**Rationale:**
- **MVP:** Start with greedy (faster, simpler to debug)
- **Phase 2:** Upgrade to LP if scenario quality inadequate
- Can implement both; choose at runtime based on complexity

---

## WHAT'S DEFERRED TO PHASE 2

❌ **Deployment & Infrastructure** (AWS EKS, load balancing, CDN)  
❌ **Monitoring & Observability** (Prometheus, Grafana, DataDog)  
❌ **Vector DB for Contract Search** (Can use keyword search MVP)  
❌ **Life Event Detection** (Calendar + email signals)  
❌ **CO₂ Footprint Detailed Analysis** (Basic calculation only MVP)  
❌ **Contract Execution via APIs** (Mock only for MVP)  
❌ **Production Security & Compliance** (Defer to hardening phase)  

---

## NEXT STEPS FOR IMPLEMENTATION

**Week 1:** 
- [ ] Set up local dev environment (PostgreSQL, Redis)
- [ ] Implement Simulated Sandbox API client
- [ ] Define data schemas (synthetic JSON payloads)

**Weeks 2-4:**
- [ ] Implement Analyst agent (pattern detection)
- [ ] Implement Forecaster agent (demand forecasting)
- [ ] Integrate Optimizer (scenario generation)
- [ ] Wire up Communicator (LLM + chat)

**Weeks 5-8:**
- [ ] Integration testing (E2E flow)
- [ ] Performance optimization (<60s latency)
- [ ] Error handling & edge cases

**Weeks 9-16:**
- [ ] Run 100-profile simulation pilot with synthetic logs
- [ ] Monitoring dashboard
- [ ] Polish & documentation
