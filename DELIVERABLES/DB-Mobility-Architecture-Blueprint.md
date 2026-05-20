# DB Mobility Portfolio Management Agent
## Architecture Blueprint

**Version:** 1.0  
**Prepared for:** Deutsche Bahn AG  
**Date:** May 20, 2026  
**Audience:** Technical architects, engineering leaders, decision-makers

---

## PART 1: STAKEHOLDER VIEW (What the System Does)

### High-Level System Overview

The **DB MoveOptimizer** is a conversational AI agent that helps DB customers optimize their mobility portfolio across all their subscriptions and services. Here's what it does:

```
CUSTOMER JOURNEY:
┌─────────────────────────────────────────────────────────────┐
│ Customer receives notification: "Your Mobility Review Ready" │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ Opens DB App → Agent summarizes 12 months of travel         │
│                                                             │
│ "You traveled 25K km in 2025:                              │
│  • 18K km by train (4 trips/mo)                            │
│  • 5K km by e-scooter (2K in Berlin)                       │
│  • 2K km carpooling                                        │
│                                                             │
│ Current spend: €245/year                                   │
│ CO₂ footprint: 1.2 tons (equivalent to 800km driving)"    │
└────────────────────┬────────────────────────────────────────┘
                     │
┌────────────────────▼────────────────────────────────────────┐
│ Agent presents 3 scenarios with trade-offs:                │
│                                                             │
│ ✓ Option A: Save €80/year, CO₂ -0.1t                     │
│   (Cancel Bahncard 25, use flex ticketing)                │
│   → Savings if: <3 trips/month                            │
│                                                             │
│ ✓ Option B: Save €35/year, CO₂ -0.3t (Recommended)      │
│   (Add Deutschlandticket, cancel Miles)                   │
│   → Best for: Balanced cost & sustainability             │
│                                                             │
│ ✓ Option C: +€50/year cost, CO₂ -0.8t (Sustainability)  │
│   (Add Bahncard 100, offset all travel via trees)        │
│   → Best for: Climate priorities                         │
└────────────────────┬────────────────────────────────────────┘
                     │
         User selects Option B (Recommended)
                     │
┌────────────────────▼────────────────────────────────────────┐
│ Agent confirms: "Approve these changes?"                   │
│ • Cancel Miles subscription (save €5/mo)                  │
│ • Add Deutschlandticket (€49/mo)                          │
│ • Bahncard 25 → stay                                      │
│                                                             │
│ Price impact: +€44/mo initially, then -€40/mo savings   │
│ Effective date: June 1, 2026                              │
│                                                             │
│ ☐ Confirm  ☐ Ask more  ☐ Reject                          │
└────────────────────┬────────────────────────────────────────┘
                     │
         User clicks "Confirm"
                     │
┌────────────────────▼────────────────────────────────────────┐
│ Agent executes:                                             │
│ ✓ Notified Miles to cancel subscription                  │
│ ✓ Added Deutschlandticket to DB account                  │
│ ✓ Sent you confirmation emails                            │
│                                                             │
│ "Your new portfolio is live! Expect to save €420 in      │
│  the next 12 months compared to your 2025 spend."        │
│                                                             │
│ Need help? Ask "How will this affect my Berlin trips?"   │
└─────────────────────────────────────────────────────────────┘
```

### Key Capabilities

1. **Analyze Your Mobility**
   - Reviews everything: DB train, S-Bahn, Lufthansa Miles, Lime, Flixbus, car rentals
   - Combines data from DB App, partner apps, credit card statements (optional)
   - Shows patterns: where you travel, when, by what mode
   - Calculates total cost and CO₂ footprint across all modes

2. **Predict Your Demand**
   - Learns from your calendar (if you share it): "I see 2 Berlin trips planned")
   - Detects life events (job change, moving, family) via email signals (if you opt-in)
   - Forecasts next 6 months: how many trips, where, which modes

3. **Generate Smart Scenarios**
   - Creates 2-3 portfolio options tuned to YOUR priorities:
     - **Cost Focus:** Cheapest portfolio for your actual demand
     - **Balanced:** Savings + sustainability
     - **Sustainability Focus:** Lowest CO₂, even if pricier
   - Explains the math: "This saves €X because Y"

4. **Get Approval Before Changes**
   - Shows exactly what will change (which subscriptions, what dates)
   - You approve each change before it happens (not automatic)
   - Agent cancels what's wasteful, adds what saves money/CO₂

5. **Track Results**
   - "DB Wrapped" annual review: "You saved €420 and reduced CO₂ by 0.5 tons"
   - Conversational help: Ask "What if I move to Hamburg?" and get instant re-analysis

### System Capabilities Overview

| Capability | Status | Details |
|-----------|--------|---------|
| **Portfolio Analysis** | ✓ MVP | Analyzes 12 months DB + partner history |
| **Demand Forecasting** | ✓ MVP | 6-month forward prediction from calendar + patterns |
| **Scenario Generation** | ✓ MVP | 2-3 optimized portfolios with cost/CO₂ trade-offs |
| **Human Approval** | ✓ MVP | Conversational approval gates for all changes |
| **Contract Execution** | ✓ MVP | Automatic cancellation/addition via partner APIs |
| **Results Tracking** | ✓ MVP | Annual review + savings/CO₂ dashboard |
| **Life Event Detection** | ⏳ Phase 2 | Email opt-in for job, move, family signals |
| **Peer Benchmarking** | ⏳ Phase 2 | Compare to similar users (anonymized) |
| **B2B Corporate Variant** | ⏳ Phase 3 | Multi-user corporate mobility management |

---

## PART 2: TECHNICAL ARCHITECTURE VIEW (How It's Built)

### System Architecture Diagram

```
LAYER 1: USER INTERFACE
┌──────────────────────────────────────────────────────────────┐
│ DB App - Chat Widget (React)                               │
│ • Recommendation presentation (cards, charts)              │
│ • Conversational approval flow                             │
│ • Results dashboard (DB Wrapped)                           │
│ • Ad-hoc Q&A interface                                     │
└───────────────┬──────────────────────────────────────────────┘
                │ WebSocket / REST API
                │
LAYER 2: ORCHESTRATION & COORDINATION
┌───────────────▼──────────────────────────────────────────────┐
│ Agent Orchestrator (Python/FastAPI)                        │
│ • Multi-turn conversation state management                 │
│ • User context retrieval from session store                │
│ • Multi-agent workflow routing                             │
│ • Approval gate enforcement (state machine)                │
│ • Contract execution coordination                          │
│ • Error handling & retry logic                             │
└───┬───────────┬──────────────┬──────────────┬───────────────┘
    │           │              │              │
    │     ┌─────▼─────┐  ┌────▼────┐  ┌────▼────┐
    │     │ Analyst   │  │Forecaster│  │Optimizer│
    │     │ Agent     │  │ Agent    │  │ Agent   │
    │     │           │  │          │  │         │
    │     │ Pattern   │  │ Demand   │  │Scenario │
    │     │ detection │  │ prediction  │ solver  │
    │     │ Efficiency│  │ Calendar    │Cost/CO2 │
    │     │ scoring   │  │ Life events │ranking  │
    │     └─────┬─────┘  └────┬────┘  └────┬────┘
    │           │              │            │
    │     ┌─────▼──────────────▼────────────▼──────────┐
    │     │ Tool Use & RAG Layer                       │
    │     │ • Travel history embedding                 │
    │     │ • Contract catalog vector search           │
    │     │ • CO₂ factor lookup                        │
    │     │ • Pricing simulation engine                │
    │     └────────────────────────────────────────────┘
    │
    └─────────────────────┬──────────────────────────────────────┐
                          │                                      │
LAYER 3: DATA & INTEGRATION
┌─────────────────────────▼──────────────────────────────────────┐
│ Data Integration Hub                                           │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ ┌────────────────┐  ┌──────────────┐  ┌─────────────────┐ │
│ │ DB APIs        │  │ Partner APIs │  │ External Data   │ │
│ ├────────────────┤  ├──────────────┤  ├─────────────────┤ │
│ │• Navigator     │  │• Miles       │  │• Google Maps    │ │
│ │• Account Mgmt  │  │• Lime        │  │• Google Cal     │ │
│ │• Current Subs  │  │• Scooter     │  │• CO₂ Factors    │ │
│ │                │  │• Stadtrad    │  │• Weather/Events │ │
│ └────────────────┘  └──────────────┘  └─────────────────┘ │
│         │                   │                    │         │
│         └───────────────────┼────────────────────┘         │
│                             │                              │
│  ┌──────────────────────────▼───────────────────────────┐ │
│  │ Data Sync Layer (ETL)                               │ │
│  │ • Scheduled sync (DB: real-time, Partners: daily)  │ │
│  │ • Error handling & fallback (cache if API down)    │ │
│  │ • Data quality checks & validation                 │ │
│  └──────────────────────────┬───────────────────────────┘ │
│                             │                              │
│  ┌──────────────────────────▼───────────────────────────┐ │
│  │ User Data Store (PostgreSQL)                        │ │
│  │ • Travel history + embeddings                       │ │
│  │ • Current subscriptions & costs                     │ │
│  │ • User preferences (cost vs CO₂ vs flexibility)    │ │
│  │ • Consent & opt-in status                          │ │
│  │ • Recommendation history & approvals               │ │
│  └──────────────────────┬─────────────────────────────┘  │
│                         │                                │
│  ┌──────────────────────▼────────────────────────────┐  │
│  │ Vector Store (Weaviate)                          │  │
│  │ • User context embeddings (for retrieval)        │  │
│  │ • Contract catalog (for scenario search)         │  │
│  │ • Historical patterns (anomaly detection)        │  │
│  └──────────────────────┬────────────────────────────┘  │
│                         │                               │
│  ┌──────────────────────▼────────────────────────────┐  │
│  │ Cache Layer (Redis)                              │  │
│  │ • User session state (real-time)                 │  │
│  │ • Travel history cache (24h TTL)                 │  │
│  │ • Scenario results (30min TTL)                   │  │
│  └──────────────────────────────────────────────────┘  │
│                                                        │
└────────────────────────────────────────────────────────┘

LAYER 4: SUPPORT SYSTEMS
┌───────────────────────────────────────────────────────────────┐
│ Monitoring, Logging, Audit                                  │
├───────────────────────────────────────────────────────────────┤
│ • Agent performance metrics (latency, accuracy, cost)       │
│ • API health & rate limiting monitoring                     │
│ • Recommendation quality dashboard                          │
│ • User feedback loop (accuracy validation)                  │
│ • Complete audit trail (all decisions logged)               │
└───────────────────────────────────────────────────────────────┘
```

### Component Details

#### **1. User Interface Layer (React in DB App)**

**Responsibility:** Present recommendations, capture approvals, show results

**Components:**
- **Recommendation Card UI:** Cost/CO₂ trade-off visualization
  - 3 scenario cards: Cost Focus | Balanced | Sustainability
  - Each card shows: monthly cost, CO₂ impact, key changes
  - Action buttons: Approve | More Info | Decline
  
- **Approval Flow:** State machine UI
  - Confirm changes screen (exact subscription changes)
  - Execution status (pending → approved → executing → confirmed)
  - Rollback/undo if things go wrong
  
- **Results Dashboard:** DB Wrapped experience
  - Annual summary (cost saved, CO₂ reduced)
  - Trend charts (monthly cost, CO₂ trajectory)
  - Comparison vs. previous year

- **Conversational Interface:** Chat widget
  - User asks questions: "What if I move to Hamburg?"
  - Agent responds with real-time re-analysis
  - Quick question suggestions (FAQ-driven)

**Tech Stack:** React 18, TypeScript, Material-UI or custom design system

---

#### **2. Orchestration Layer (Python/FastAPI)**

**Responsibility:** Coordinate multi-agent workflow, manage state, enforce governance

**Components:**

*Agent Coordinator*
- Routes user request → {Analyst, Forecaster} (parallel) → Optimizer → Communicator
- Manages context passing between agents (selective information flow)
- Timeout handling (Analyst: 10s, Optimizer: 30s max)
- Error handling: If agent fails, returns best-effort recommendation or "Ask user"

*State Machine for Approvals*
```
States:
  NEW → ANALYZING → RECOMMENDATION_READY → 
    PENDING_APPROVAL → APPROVED → EXECUTING → 
    EXECUTED → CONFIRMED
  
  (Any state can → DECLINED or → EXPIRED if 30+ days)
  
Events:
  user_approves, user_declines, execution_success, 
  execution_failed, approval_timeout, system_error
  
Action:
  APPROVED → Trigger contract execution async task
  EXECUTING → Poll partner APIs for status
  EXECUTED → Send user confirmation
```

*User Context Manager*
- Loads user preferences from session store
- Tracks multi-turn conversation state
- Manages consent status (email opt-in? calendar shared?)
- Caches frequently accessed data (travel history, current subs)

*Error & Retry Logic*
- Partner API fails: Retry 3x with exponential backoff; use cached scenario
- Agent timeout: Return partial result (e.g., "Analyst confidence: 75%")
- Data inconsistency: Log issue, flag for manual review, suggest manual approval
- Contract execution fails: Alert ops, provide rollback instructions

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, async/await for concurrency

---

#### **3. Agent Layer (Multi-Agent System)**

**Analyst Agent: Pattern Detection & Efficiency Scoring**

*Input:* 12-month travel history, current subscriptions, costs

*Process:*
1. Ingest travel history: Parse trips (date, mode, cost, route)
2. Build travel patterns: Frequency by mode, distance distributions, seasonal trends
3. Calculate efficiency scores:
   - "Train trips: 25/year @ €245/year → avg €9.80/trip"
   - "vs. pay-as-you-go: 25 trips × €15 avg = €375/year → 35% overspend"
   - "vs. Bahncard 50: €299/year + €7.50/trip × 25 = €486 → better than current?"
4. Surface inefficiencies: Unused services, over-provisioning, under-provisioning
5. Output: Efficiency report + savings potential (organized by subscription type)

*Tools Used:*
- Travel history vector search (find similar historical periods)
- Pricing lookup (current costs for all subscriptions)
- Clustering algorithm (group trips by characteristics)

*Example Output:*
```json
{
  "analysis": {
    "total_trips": 25,
    "total_cost": 245,
    "breakdown": {
      "bahncard_25": { "cost": 120, "trips_used": 15, "efficiency": "good" },
      "miles_membership": { "cost": 10, "trips_used": 0, "efficiency": "unused" },
      "lime_scooter": { "cost": 35, "trips_used": 20, "efficiency": "good" }
    },
    "inefficiencies": [
      { "item": "Miles membership", "reason": "unused", "annual_savings": 10 },
      { "item": "Bahncard 25", "reason": "only 15/25 potential trips used", "upgrade_potential": 50 }
    ]
  }
}
```

---

**Forecaster Agent: Demand Prediction & Life Event Detection**

*Input:* Calendar events (if shared), email signals (if opted-in), historical patterns, user preferences

*Process:*
1. **Historical Seasonality:** "Q1 has 20% more trips than Q3"
2. **Calendar Events:** Parse user calendar for travel-related events
   - Recurring: "Every 2nd Friday: Berlin business trip"
   - Holidays: "Summer vacation likely → 4 long trips"
   - Life signals: Extract keywords (job, move, family) from email opt-in
3. **Demand Forecast:** Predict trips/month for next 6 months
   - Input: seasonality + calendar events + life changes
   - Output: Expected trips by mode, confidence intervals
4. **Scenario Modeling:** "If you move to Hamburg, expect +40% rail trips"

*Tools Used:*
- Time-series forecasting (ARIMA or LLM-based reasoning)
- Natural language parsing (email keywords, calendar titles)
- External data: Holiday calendar, traffic patterns, transit disruptions

*Example Output:*
```json
{
  "forecast": {
    "next_6_months": [
      { "month": "June", "train_trips": 6, "scooter_trips": 15, "confidence": 0.85 },
      { "month": "July", "train_trips": 4, "scooter_trips": 8, "confidence": 0.70 },
      { "month": "Aug", "train_trips": 8, "scooter_trips": 12, "confidence": 0.75 }
    ],
    "life_events_detected": [
      { "event": "job_change", "signal": "email mention", "impact": "+20% Berlin trips", "confidence": 0.60 }
    ],
    "demand_summary": { "total_train_trips": 32, "total_scooter_trips": 80 }
  }
}
```

---

**Optimizer Agent: Scenario Generation & Cost/CO₂ Trade-off Analysis**

*Input:* Analyst efficiency report, Forecaster demand prediction, pricing catalog, CO₂ factors

*Process:*
1. **Scenario Solver:** For predicted demand, generate feasible portfolio options
   - Constraint: Must cover predicted demand (no stranded plans)
   - Objective: Minimize cost (Scenario A), balanced (B), or minimize CO₂ (C)
   - Method: Linear programming solver (CPLEX/Pyomo) or greedy heuristic
2. **Cost Calculation:** For each scenario, calculate annual cost
   - Bahncard cost + pay-per-trip cost (for uncovered trips)
   - Partner subscription costs (only include if beneficial)
3. **CO₂ Calculation:** For each scenario, estimate carbon footprint
   - CO₂ per trip by mode (train: 10g CO₂eq/km, car: 250g, scooter: 5g)
   - Multiply by predicted trips
4. **Ranking:** Rank scenarios by user priority (cost, CO₂, flexibility)

*Tools Used:*
- Scenario solver (constraint satisfaction engine)
- Pricing catalog lookup (contracts + pricing tiers)
- CO₂ database lookup (emission factors per mode)
- User preference retrieval (cost vs CO₂ priority)

*Example Output:*
```json
{
  "scenarios": [
    {
      "id": "A",
      "label": "Cost Focus",
      "changes": [
        { "action": "cancel", "item": "Miles membership", "monthly_impact": -€10 },
        { "action": "keep", "item": "Bahncard 25", "monthly_impact": €10 },
        { "action": "keep", "item": "Lime scooter", "monthly_impact": €3 }
      ],
      "annual_cost": €156,
      "co2_tons": 0.95,
      "savings_vs_current": €89,
      "risk": "Low flex if travel patterns change"
    },
    {
      "id": "B",
      "label": "Balanced (Recommended)",
      "changes": [
        { "action": "cancel", "item": "Miles membership", "monthly_impact": -€10 },
        { "action": "add", "item": "Deutschlandticket", "monthly_impact": €49 },
        { "action": "keep", "item": "Lime scooter", "monthly_impact": €3 }
      ],
      "annual_cost": €204,
      "co2_tons": 0.65,
      "savings_vs_current": €41,
      "reasoning": "Deutschlandticket covers 80% of predicted train trips; Lime for local urban mobility"
    }
  ]
}
```

---

**Communicator Agent: Recommendations & Execution**

*Input:* Orchestrator context, Optimizer scenarios, user preferences, approval status

*Process:*
1. **Recommendation Presentation:** 
   - Present top 3 scenarios in natural language (not just JSON)
   - Explain trade-offs in user terms ("Save €X, reduce CO₂ by Y")
   - Highlight which scenario is "recommended" and why
2. **Approval Capture:**
   - "Does this look good?" (yes/no/more questions)
   - If user asks questions: Re-analyze with updated constraints
   - If user approves: Transition to PENDING_APPROVAL state
3. **Execution Orchestration:**
   - Contract execution: API calls to DB, Miles, Lime, etc.
   - Track status: pending → confirmed
   - Provide user confirmation (email + in-app)
4. **Conversational Interface:**
   - Handle follow-up questions: "What if I don't use my Bahncard 25?"
   - Re-run Analyst/Optimizer with new constraints
   - Explain reasoning in conversational tone

*Tools Used:*
- LLM for natural language generation (Claude for explanations)
- User preference lookup (risk tolerance, communication style)
- Contract execution APIs (DB, partner systems)
- Notification system (email, push, in-app)

*Example Dialog:*
```
Agent: "I found a way to save you €41/year while reducing CO₂ by 35%.

Here's what I recommend (Option B - Balanced):
• Cancel Miles membership (unused, save €10/mo)
• Add Deutschlandticket (€49/mo, covers 80% of your train trips)
• Keep your Lime scooter subscription (€3/mo, great for local mobility)

Your new annual cost: €204 vs €245 today.
Your CO₂: 0.65 tons vs 1.0 tons today.

This is my #1 recommendation because it balances your cost savings
with sustainability goals, and gives you flexibility if your travel
patterns change.

Should I go ahead with these changes?"

User: "What about the Bahncard 25? Do I still need it?"

Agent: "Good question. With Deutschlandticket, you'd get unlimited
trains nationwide. Your Bahncard 25 would give you no additional
benefit—just duplication. I recommended canceling it.

However, if you value the flexibility to buy single tickets
(e.g., for day trips), keeping Bahncard 25 adds €10/mo for peace
of mind. Up to you."

User: "OK, cancel the Bahncard 25 and add Deutschlandticket. Do it."

Agent: "✓ Approving these changes:
  • Cancel Miles (€10/mo savings)
  • Cancel Bahncard 25 (€10/mo savings)
  • Add Deutschlandticket (€49/mo cost)
  • Net: -€29/mo, -€348/year vs today

Effective June 1. I'm notifying Miles and updating your DB account now...
✓ Done! You're all set."
```

---

#### **4. Data Integration Hub**

**DB Navigator API Integration**
- Purpose: Ingest 12-month travel history (all DB train trips)
- Format: Time-series of trips (date, departure, arrival, class, cost, points earned)
- Sync: Real-time on user login; daily batch sync for all active users
- Error handling: If API down, use cached history; flag user for manual review
- Rate limiting: 1K req/sec; implement queue + exponential backoff

**Partner API Integration (Lime, Miles, Stadtrad, Scooter)**
- Purpose: Sync current subscription status + usage
- Format: Subscription state, last activity, points balance
- Sync: Daily batch (1am UTC)
- Error handling: Graceful degradation (use last known state if API down)
- Authentication: OAuth 2.0 with refresh token rotation

**Google Maps & Calendar APIs**
- Purpose: Multi-modal trip routing (for scenario simulation), user calendar events
- Format: Trip itinerary (start/end location, mode, time), calendar events
- Sync: On-demand (user shares calendar); privacy: 30-day retention max
- Authentication: OAuth 2.0 with user consent checkpoints

**CO₂ Emission Data**
- Source: UK DEFRA Greenhouse Gas Conversion Factors (or equivalent EU source)
- Updates: Quarterly refresh
- Format: g CO₂ eq. per km by mode (train, bus, car, plane, e-scooter)
- Deployment: Lookup table in database

**User Data Store (PostgreSQL)**

Schema (simplified):
```sql
-- Core tables
users (id, db_account_id, preferences, consent_status)
travel_history (id, user_id, timestamp, origin, destination, mode, cost_eur, co2_kg)
subscriptions (id, user_id, service, status, monthly_cost, renewal_date)
user_embeddings (id, user_id, embedding_vector, pattern_type)
recommendations (id, user_id, timestamp, scenario_id, status, approval_status)
approvals (id, recommendation_id, user_decision, timestamp, execution_status)
```

**Vector Store (Weaviate)**
- Purpose: Fast semantic search for:
  - User context embeddings (similarity-based recommendations)
  - Contract catalog search (find contracts matching user pattern)
  - Travel pattern clustering (find similar users for benchmarking)
- Size: ~1M user embeddings (32-dim), 500 contract embeddings
- Query latency: <100ms p95

**Cache Layer (Redis)**
- Session state: Multi-turn conversation context (24h TTL)
- Travel history cache: 12-month summary (24h TTL)
- Scenario results: Generated scenarios (30min TTL)
- User preferences: Cached from DB (1h TTL)

---

### Data Flow Example: Happy Path

```
1. USER OPENS DB APP
   └─> Orchestrator loads user context from PostgreSQL
       • Current subscriptions
       • Consent status (email opted in? calendar shared?)
       • Previous recommendations (don't repeat)

2. USER REQUESTS: "Generate my mobility review"
   └─> Orchestrator routes to Analyst Agent (async)
       
   Analyst:
   ├─> Query DB Navigator API: Get 12-month travel history
   ├─> Parse trips into vector embeddings (travel pattern)
   ├─> Store in PostgreSQL + Vector store
   ├─> Compare vs. current subscriptions
   ├─> Calculate efficiency scores
   └─> Return: Efficiency report (inefficiencies found, savings potential)

3. ANALYST RESULT → FORECASTER (parallel with Analyst)
   Forecaster:
   ├─> Query Google Calendar API (if user shared)
   ├─> Extract trip-related events (Berlin every 2nd Friday)
   ├─> Query email signals (if user opted in)
   ├─> Extract life events (job mention, move mention)
   ├─> Apply seasonality from historical patterns
   ├─> Forecast next 6 months demand
   └─> Return: Demand forecast (trip volumes by mode/month)

4. ANALYST + FORECASTER RESULT → OPTIMIZER
   Optimizer:
   ├─> Load contract pricing catalog from PostgreSQL
   ├─> Load CO₂ factors from PostgreSQL
   ├─> Input: Efficiency + demand forecast
   ├─> Solve constraint satisfaction for 3 scenarios
   │   ├─> Scenario A: Minimize cost
   │   ├─> Scenario B: Balanced (weighted cost + CO₂)
   │   ├─> Scenario C: Minimize CO₂
   ├─> Calculate annual cost + CO₂ for each
   ├─> Rank by user preference (cost priority: 70%, CO₂: 30%)
   └─> Return: 3 ranked scenarios with trade-offs

5. OPTIMIZER RESULT → COMMUNICATOR
   Communicator:
   ├─> Generate natural language explanation for each scenario
   ├─> Highlight recommended option (Option B)
   ├─> Prepare approval flow
   └─> Display in DB App UI

6. USER APPROVES SCENARIO B
   └─> Orchestrator:
       ├─> Transition state: PENDING_APPROVAL → APPROVED
       ├─> Queue async execution task:
       │   ├─> Call Miles API: Cancel subscription
       │   ├─> Call DB Account API: Add Deutschlandticket
       │   ├─> Confirm each change
       ├─> Log approval in audit table
       └─> Return: "Changes executing, I'll confirm when done"

7. EXECUTION COMPLETE
   └─> Orchestrator:
       ├─> Update user subscriptions in PostgreSQL
       ├─> Transition state: EXECUTING → EXECUTED → CONFIRMED
       ├─> Send confirmation email
       ├─> Display success in DB App
       └─> Store results for future reference (DB Wrapped)
```

---

### Error Scenarios & Resilience

**Scenario: Miles API fails during cancellation**
```
1. Agent calls Miles API: "Cancel subscription"
2. Timeout after 30s (no response)
3. Fallback: Log error, retry once async
4. User notification: "Miles cancellation pending. I'm working on it."
5. If retry succeeds: Send confirmation
6. If retry fails: Alert ops team + user is asked to confirm manual cancellation
7. Audit: All steps logged with timestamps for dispute resolution
```

**Scenario: User asks conflicting question before approval**
```
1. Agent generates scenarios for current demand forecast
2. User asks: "What if I move to Hamburg?"
3. Communicator captures new constraint: "location = Hamburg"
4. Re-runs Forecaster + Optimizer with updated assumptions
5. Updates recommendation scenarios (may change due to different trip patterns)
6. Presents new results: "Here's what changes with a Hamburg move..."
7. User can now approve updated scenario
```

**Scenario: Analyst detects conflicting signals**
```
1. Analyst detects: User traveled 4x/month average (consistent)
2. Calendar shows: No trips next month (summer vacation)
3. Email signals: "Promoted to Berlin office" (moving cities)
4. Forecaster can't reconcile these signals (contradiction)
5. Communicator surfaces uncertainty: "I found something unexpected..."
6. Asks user clarification: "Are you definitely moving to Berlin? When?"
7. User provides explicit answer → Forecaster retrains model
8. Scenarios regenerated with confirmed constraints
```

---

## PART 3: ARCHITECTURE DECISION RECORDS (ADRs)

### ADR-001: Multi-Agent Decomposition (Analyst + Forecaster + Optimizer + Communicator)

**Status:** Accepted  
**Date:** May 20, 2026

**Context:**
The system must analyze historical patterns, forecast future demand, optimize portfolio scenarios, and present recommendations to users. These are distinct cognitive tasks with different data inputs and time constraints.

**Options Considered:**
1. **Monolithic LLM:** Single LLM call with all data dumped in prompt
   - Pros: Simplicity, no orchestration needed
   - Cons: Context window limited, reasoning mixed, hard to debug, poor latency (100+ tokens generated)
   - Estimated latency: 30-45 seconds
   - Rejection reason: Too slow, not interpretable

2. **Two-Agent (Analyzer + Recommender):**
   - Pros: Simpler than 4-agent, still separates concerns
   - Cons: Forecasting and optimization mixed; hard to iterate
   - Estimated latency: 20 seconds
   - Rejection reason: Demand prediction needs own logic; optimization separate

3. **Four-Agent (Analyst + Forecaster + Optimizer + Communicator):** ✓ **CHOSEN**
   - Pros: Clear separation of concerns; each agent is interpretable; can parallelize
   - Cons: More complexity, state management required
   - Estimated latency: 12 seconds (Analyst & Forecaster in parallel)
   - Selected because: Modular, testable, extensible

**Decision:**
Implement four-agent system with clear role separation and async parallelization. Analyst and Forecaster run in parallel; Optimizer consumes both; Communicator ranks and presents.

**Trade-offs:**
- **Complexity vs. Interpretability:** 4-agent system is more complex but each agent is testable and debuggable
- **Latency vs. Accuracy:** Parallel execution saves time; each agent optimized for latency (Analyst: <10s, Optimizer: <30s)
- **Flexibility vs. Simplicity:** Monolithic would be simpler but harder to iterate or fix

**Consequences:**
- Must build orchestration layer (state management, routing, error handling)
- Each agent must be independently tested
- Can easily swap/upgrade agents (e.g., replace Forecaster with ML model later)

---

### ADR-002: Human-in-the-Loop Approval Gates for Contract Changes

**Status:** Accepted  
**Date:** May 20, 2026

**Context:**
The system generates recommendations that result in contract changes (cancellations, additions). Users must trust the system before approving financial changes. Risk of erroneous recommendations, API failures, or user regret must be mitigated.

**Options Considered:**
1. **Full Autonomy:** Agent executes changes automatically
   - Pros: Frictionless UX, user doesn't need to think
   - Cons: High risk of user regret, regulatory concerns, trust erosion
   - Rejection reason: Too risky for MVP; user control is essential

2. **Multi-Step Approval:** Recommendation → User approval → Execution confirmation
   - Pros: User maintains full control, audit trail clear
   - Cons: Friction in UX, potential for "approval fatigue"
   - Estimated adoption: 18-22%

3. **Risk-Based Approval:** Small changes auto-approve; large changes need approval ✓ **CHOSEN**
   - Pros: Balance friction + safety; reduces approval fatigue
   - Cons: Requires risk classification logic; users may feel system is too autonomous
   - Estimated adoption: 20-25%
   - Threshold: Changes <€20/mo → auto-approve; >€20/mo → ask user

**Decision:**
Implement risk-based approval: Small changes (<€20/mo impact) automatically execute after user sees results; large changes require explicit approval before execution. All changes logged with audit trail.

**Trade-offs:**
- **Autonomy vs. Control:** Balances user comfort with frictionless experience
- **Adoption vs. Safety:** Slightly more friction but higher trust = better adoption

**Consequences:**
- Must implement risk classifier (impact < €20/mo is "safe")
- State machine for approvals must support both auto and manual paths
- Clear audit trail required for all changes (compliance)

---

### ADR-003: Agent Framework Selection (LangChain vs AutoGen vs LlamaIndex)

**Status:** Tentative (Final decision after POC)  
**Date:** May 20, 2026

**Context:**
The project requires a framework for multi-agent orchestration, tool use, RAG, and state management. Candidates: LangChain (production-ready, largest community), AutoGen (multi-agent focus, Microsoft), LlamaIndex (RAG focus).

**Options Considered:**
1. **LangChain (v0.2+)**
   - Pros: Mature (1,000+ repos using), good tool use abstractions, active community, strong multi-step reasoning
   - Cons: Can feel "over-engineered" for simple tasks; tight coupling to LLM providers
   - Estimated learning curve: 1 week
   - Risk: API changes (history of breaking changes)

2. **AutoGen (Microsoft)**
   - Pros: Purpose-built for multi-agent, excellent inter-agent communication patterns, strong conversational mode
   - Cons: Newer (less battle-tested), smaller community, some alpha features
   - Estimated learning curve: 1.5 weeks
   - Risk: API stability

3. **LlamaIndex**
   - Pros: Excellent for RAG (perfect for contract catalog), modular, composable
   - Cons: Less focused on multi-agent orchestration, still evolving
   - Estimated learning curve: 1 week
   - Risk: Missing multi-agent patterns

4. **Custom Built** ✓ **HYBRID APPROACH CHOSEN**
   - Use LangChain for core agent loops + tool use
   - Use LlamaIndex for RAG queries (contract catalog)
   - Custom orchestration layer for multi-agent coordination
   - Rationale: Best of both worlds; maximum control

**Decision:**
Use LangChain + LlamaIndex hybrid stack:
- LangChain for Analyst, Forecaster, Optimizer agent loops (tool use)
- LlamaIndex for contract catalog RAG queries
- Custom FastAPI orchestration layer for multi-agent workflow + state machine

**Trade-offs:**
- **Simplicity vs. Control:** More custom code, but full visibility + control
- **Community Support vs. Flexibility:** Smaller audience for hybrid approach, but less locked-in

**Consequences:**
- Must build custom orchestration layer (~1-2 weeks engineering)
- Integration testing more complex (multiple frameworks)
- Upgrade path is managed (each framework can be upgraded independently)

---

### ADR-004: State Persistence (PostgreSQL + Redis + Vector DB)

**Status:** Accepted  
**Date:** May 20, 2026

**Context:**
The system must persist user data (12-month travel history, subscriptions, preferences, recommendations) and maintain fast access to conversational state. Multi-layer storage required: relational (audit), cache (performance), vector (semantic search).

**Options Considered:**
1. **Single Database (PostgreSQL only)**
   - Pros: Simplicity, strong ACID guarantees, good for audit trails
   - Cons: Slow for vector similarity (not optimized), session state latency
   - Query time for "find similar users": 500ms+ (not acceptable)
   - Rejection reason: Performance

2. **Single NoSQL (MongoDB + vector extensions)**
   - Pros: Flexible schema, better vector support than PG, good for time-series
   - Cons: Weaker consistency guarantees, harder for audit trails
   - Estimated adoption by team: Low (less familiar)
   - Rejection reason: Audit/compliance concerns

3. **Multi-Layer (PG + Redis + Weaviate)** ✓ **CHOSEN**
   - PostgreSQL: Persistent audit trail, user master data, subscriptions
   - Redis: Fast session state (conversation context, approval status)
   - Weaviate: Vector search (user embeddings, contract catalog, pattern matching)
   - Pros: Optimal for each use case, best latency, strong audit trail
   - Cons: More complex, must manage consistency between layers
   - Estimated consistency lag: <100ms (acceptable for recommendations)

**Decision:**
Three-layer storage:
1. **PostgreSQL (Primary Store):** User master data, audit logs, subscriptions, all historical data
2. **Redis (Cache Layer):** Session state, conversation context, approval status (30s → 5m TTL)
3. **Weaviate (Vector Store):** User embeddings, contract catalog embeddings, pattern clustering

**Trade-offs:**
- **Consistency vs. Performance:** Eventual consistency at cache layer (acceptable for recommendations)
- **Operational Complexity vs. Optimal Performance:** More to manage, but best latency per use case

**Consequences:**
- Must implement cache invalidation logic (especially on subscription changes)
- Consistency model: Strong for audit trail, eventual for cache
- Need database migration strategy (PostgreSQL schema versioning)

---

### ADR-005: Life Event Detection Approach (Opt-In Only, Phase 1)

**Status:** Accepted  
**Date:** May 20, 2026

**Context:**
Life events (job change, relocation, family changes) are strong signals for portfolio optimization. Detecting these could significantly improve recommendation relevance. However, privacy concerns and technical feasibility vary greatly.

**Options Considered:**
1. **Behavioral Inference from Location Data**
   - Pros: Fully passive, no user action required, very accurate signals
   - Cons: Severe privacy concerns (location tracking), regulatory risk (GDPR), user trust erosion
   - Rejection reason: Privacy / compliance risk too high

2. **Calendar + Email Opt-In** ✓ **MVP APPROACH (Phase 1)**
   - Pros: Explicit user consent, clear signals, moderate accuracy (80%+), strong trust
   - Cons: Requires active user opt-in, only works if users share calendar/email
   - Adoption: Estimated 30-40% of users will opt-in
   - Accuracy for job detection: 70-80% (some noise, user can override)

3. **Manual User Input**
   - Pros: No privacy concerns, explicit, accurate
   - Cons: High friction, low adoption (<5%), user burden
   - Rejection reason: Poor UX

4. **Third-Party Data (Crunchbase, LinkedIn)**
   - Pros: High accuracy for job changes (if available)
   - Cons: Privacy concerns, data freshness (weeks old), cost
   - Rejection reason: Privacy + cost not justified for MVP

**Decision:**
Phase 1 MVP: Calendar + Email opt-in ONLY. No passive behavioral inference.
- Google Calendar: Explicit OAuth (user shares calendar)
- Email opt-in: Secure scanning for keywords ("job", "moved", "family")
  - No full email storage; keyword matches → immediate action + deletion
  - Transparent: User sees exactly what triggered the event detection
- User override: Can always tell system "Actually, I'm not moving"

**Trade-offs:**
- **Privacy vs. Relevance:** Opt-in approach reduces some relevance but strengthens privacy
- **Adoption vs. Accuracy:** Lower adoption (30-40% opt-in) but high accuracy
- **MVP Scope vs. Future Extensibility:** Phase 1 conservative; can extend to other signals Phase 2

**Consequences:**
- Phase 1: ~30-40% of users get life event signals
- Phase 2 (later): Can add behavioral signals with additional privacy mechanisms
- Privacy/compliance review REQUIRED before launch (email scanning review)

---

## PART 4: INTEGRATION ARCHITECTURE

### API Integration Checklist

| API | Purpose | Frequency | Latency SLA | Fallback Strategy |
|-----|---------|-----------|-------------|-------------------|
| **DB Navigator** | Travel history (12mo) | Daily batch | <30s | Cache + alert ops |
| **DB Account System** | Current subscriptions | Real-time on change | <10s | Session cache (24h) |
| **Miles API** | Subscription status + cancellation | Daily sync + on-demand for exec | <20s | Cached status; manual escalation for cancel |
| **Lime API** | Scooter subscription + status | Daily sync | <20s | Cache; manual escalation |
| **Stadtrad API** | Bike subscription + status | Daily sync | <20s | Cache; manual escalation |
| **Google Maps** | Trip routing (for scenario simulation) | On-demand | <10s | Fallback to straight-line distance + generic mode factors |
| **Google Calendar** | User events (if shared) | On-demand | <5s | Skip event signals if unavailable |
| **Email Opt-In Processor** | Life event keywords | On-demand (user approval) | <2s | Skip if user denies |

### Security & Data Privacy

**Data Classification:**
- **PII:** User name, email, location, calendar contents → Encrypted at rest, minimal retention
- **Financial:** Subscription costs, spending patterns → Encrypted, audit logged
- **Behavioral:** Travel history, patterns → Pseudonymized after 6 months (for benchmarking)

**API Authentication:**
- DB APIs: OAuth 2.0 with DB service account
- Partner APIs: API key + secret (rotated monthly) OR OAuth 2.0
- Google: OAuth 2.0 with user consent + scopes (Calendar, Email - limited)

**Audit Trail:**
- All recommendations logged (timestamp, agent versions, assumptions, results)
- All approvals logged (user, timestamp, execution status)
- All API errors logged (for ops review)
- Data access logged (compliance + dispute resolution)

---

## PART 5: DEPLOYMENT & OPERATIONS

### Infrastructure Architecture

**Staging Environment (Development + Testing)**
- AWS EC2: t3.xlarge (4 CPU, 16GB RAM)
- PostgreSQL RDS: db.t4g.large
- Redis: ElastiCache (cache.t4g.medium)
- Weaviate: Docker container on EC2
- Estimated monthly cost: €800

**Production Environment (Pilot: 1K users)**
- AWS Kubernetes (EKS): 3 nodes (m5.xlarge)
- PostgreSQL RDS: db.r5.2xlarge (multi-AZ)
- Redis: ElastiCache (cache.r5.xlarge) with failover
- Weaviate: Managed Weaviate Cloud (50M vectors capacity)
- Load balancer: AWS ALB
- Estimated monthly cost: €3K-4K

**Scaling (Full Rollout: 1M users)**
- EKS: Auto-scaling to 10-20 nodes based on load
- PostgreSQL: Read replicas for analytics
- Redis: Cluster mode for distributed caching
- Weaviate: Distributed deployment
- Estimated monthly cost: €25-35K (scales with user load)

### Monitoring & Observability

**Key Metrics:**
- Agent latency (p50, p95, p99)
- API success rate by endpoint
- Recommendation quality (accuracy vs. manual review)
- User approval rate (feedback on recommendation quality)
- System error rate (<1% target)
- Database query latency

**Alerting:**
- High error rate (>1%): Alert ops team immediately
- API failures (>5 consecutive failures): Alert + fallback to cache
- Recommendation quality drops (<85% accuracy): Flag for ML review
- Slow performance (p95 >30s): Investigate + optimize

**Logging:**
- Structured logs (JSON) for all events
- Centralized logging: ELK stack or CloudWatch
- 30-day retention (minimum); 90-day archive to S3

---

## SUMMARY: Architecture Decision Matrix

| Decision Area | Choice | Rationale | Risk Level |
|---------------|--------|-----------|-----------|
| Agent Decomposition | 4-agent (Analyst, Forecaster, Optimizer, Communicator) | Clear separation + parallelization | Low |
| Approval Model | Risk-based (auto <€20/mo, ask for >€20/mo) | Balance UX + safety | Low |
| Framework Stack | LangChain + LlamaIndex + Custom Orchestration | Best of both, full control | Medium |
| State Persistence | PostgreSQL + Redis + Weaviate | Optimal for each use case | Medium |
| Life Event Detection | Opt-in only (Calendar + Email); Phase 1 | Privacy-first | Low |
| User Interface | Chat widget in DB App (React) | Native to existing product | Low |
| Deployment | AWS (EKS, RDS, ElastiCache, Weaviate) | Mature, scalable, team familiar | Low |

---

**Next Steps:**
1. ADRs to be reviewed by DB technical leads (May 23)
2. Stakeholder feedback incorporated (May 24-29)
3. Final architecture approval (May 29)
4. Development kickoff (May 30)

**Document Owner:** Senior Solutions Architect  
**Version:** 1.0 - Draft  
**Status:** Ready for Technical Review  
**Last Updated:** May 20, 2026
