# Deutsche Bahn Mobility Portfolio Management Agent
## Requirements Specification Document

**Prepared by:** Senior Data Consultant  
**For:** Deutsche Bahn AG  
**Date:** May 20, 2026  
**Classification:** Project Confidential

---

## EXECUTIVE SUMMARY

This document specifies all functional and non-functional requirements for the DB Mobility Portfolio Management Agent (DB MoveOptimizer). It serves as the binding contract between business stakeholders, technical architects, and the development team.

**Scope:** MVP Pilot Phase (1,000 customers, 16 weeks)  
**Baseline:** Current state = reactive, siloed (customer manually compares options)  
**Target State:** Proactive, integrated agent providing unified portfolio optimization

---

## SECTION 1: FUNCTIONAL REQUIREMENTS

### 1.1 Portfolio Analysis (FR-101 to FR-110)

**FR-101: Historical Travel Data Ingestion**
- **Requirement:** System shall ingest 12 months of travel history from DB Navigator API for each customer
- **Acceptance Criteria:**
  - ✓ All DB train trips (long-distance, regional, S-Bahn) captured
  - ✓ Each trip includes: date, route (origin/destination), class, cost, duration
  - ✓ Ingestion completes within 5 seconds per customer
  - ✓ 99.5% data completeness (missing <0.5% of trips)
- **Priority:** Must-Have (MVP)
- **Owner:** Data Integration Team

**FR-102: Partner Data Integration**
- **Requirement:** System shall sync subscription status and transaction history from partner APIs (Miles, Lime, Stadtrad, E-Scooter)
- **Acceptance Criteria:**
  - ✓ All active subscriptions visible in unified dashboard
  - ✓ Sync frequency: Daily for all partners (within 2h of data update)
  - ✓ Fallback to cached data if API fails (max 7 days stale)
  - ✓ Clear indicators when partner data is stale
- **Priority:** Must-Have (MVP)
- **Owner:** Integration Team

**FR-103: Cost Attribution and Breakdown**
- **Requirement:** System shall calculate total mobility cost and break down by service/subscription
- **Acceptance Criteria:**
  - ✓ Includes: subscription fees, per-trip costs, hidden fees (parking, etc.)
  - ✓ Accuracy: ±2% vs. bank/billing statements (validated on 50-customer sample)
  - ✓ Shows annual total + monthly average
  - ✓ Identifies unused or underutilized subscriptions
- **Priority:** Must-Have (MVP)
- **Owner:** Data Science Team

**FR-104: Travel Pattern Analysis**
- **Requirement:** System shall identify travel patterns (frequency, seasonality, geography, mode mix)
- **Acceptance Criteria:**
  - ✓ Detects: recurring routes, seasonal variations (20%+ difference flagged)
  - ✓ Segments trips by: weekday/weekend, short/medium/long distance, mode type
  - ✓ Clustering: groups similar trips; identifies outliers
  - ✓ Output: Interpretable patterns in natural language + visualizations
- **Priority:** Must-Have (MVP)
- **Owner:** Data Science Team

**FR-105: Inefficiency Detection**
- **Requirement:** System shall identify portfolio inefficiencies (unused subscriptions, over-provisioning, under-provisioning)
- **Acceptance Criteria:**
  - ✓ Flags unused services: <5% actual usage vs. potential (e.g., Miles membership)
  - ✓ Flags over-provisioning: Bahncard tier higher than needed for demand
  - ✓ Flags under-provisioning: Pay-per-trip costlier than optimal subscription
  - ✓ Quantifies savings potential for each inefficiency
  - ✓ Confidence score for each flag (70%+ accepted as actionable)
- **Priority:** Must-Have (MVP)
- **Owner:** Data Science Team

**FR-106: CO₂ Footprint Calculation**
- **Requirement:** System shall calculate customer's CO₂ footprint by mode and in total
- **Acceptance Criteria:**
  - ✓ Uses authoritative emission factors (DEFRA or equivalent)
  - ✓ Calculates per-trip and annual totals (in kg or tons CO₂eq)
  - ✓ Breaks down by mode: train 8g/km, car 250g/km, e-scooter 5g/km, etc.
  - ✓ Compares to baseline: "Your CO₂ is X% below German average"
- **Priority:** Should-Have (MVP)
- **Owner:** Data Science Team

**FR-107: Baseline Scenario (Current Portfolio)**
- **Requirement:** System shall define current portfolio as baseline for comparison
- **Acceptance Criteria:**
  - ✓ Lists all active subscriptions (DB, partners)
  - ✓ Projects 6-month cost with historical demand patterns
  - ✓ Calculates implied CO₂ footprint
  - ✓ Used as reference for all optimization scenarios
- **Priority:** Must-Have (MVP)
- **Owner:** Data Analyst

---

### 1.2 Demand Forecasting (FR-201 to FR-220)

**FR-201: Historical Seasonality Detection**
- **Requirement:** System shall detect seasonal patterns in travel demand
- **Acceptance Criteria:**
  - ✓ Compares Q1 vs Q2 vs Q3 vs Q4; detects >15% variations
  - ✓ Identifies month-to-month trends
  - ✓ Flags annual events (summer vacation patterns, holidays)
  - ✓ Provides confidence intervals (70-95% ranges)
- **Priority:** Must-Have (MVP)
- **Owner:** Data Science Team

**FR-202: 6-Month Demand Forecast**
- **Requirement:** System shall forecast mobility demand for next 6 months
- **Acceptance Criteria:**
  - ✓ Predicts trip count by mode/month (e.g., 6 train trips in June)
  - ✓ Forecast horizon: +6 months ahead
  - ✓ Confidence level shown (70-90% typical)
  - ✓ Incorporates seasonality, historical patterns, calendar events
  - ✓ Updates forecast when new data arrives (calendar change, life event)
- **Priority:** Must-Have (MVP)
- **Owner:** Data Science Team

**FR-203: Calendar Integration (Opt-In)**
- **Requirement:** System shall ingest user calendar to improve demand forecast (if user shares)
- **Acceptance Criteria:**
  - ✓ Extracts travel-relevant events (flights, trains, business trips)
  - ✓ Parses event location to predict trips (e.g., "Berlin 3 days" → +3 rail trips Berlin)
  - ✓ Handles recurring events (e.g., "Every 2nd Friday: Berlin client meeting")
  - ✓ Explicit opt-in with OAuth consent
  - ✓ Data retention: 30-day max (deleted after processing)
- **Priority:** Must-Have (MVP), but optional for customer
- **Owner:** Integration Team

**FR-204: Life Event Detection (Email Opt-In)**
- **Requirement:** System shall detect life events via email opt-in to trigger re-forecasting
- **Acceptance Criteria:**
  - ✓ Detects keywords: "job", "moved", "relocation", "family", "promotion"
  - ✓ Triggers re-forecast on detection (e.g., "Job change detected → recommending new portfolio")
  - ✓ User can confirm or override event
  - ✓ Explicit opt-in with email scanning transparency
  - ✓ Data retention: Keyword only (no email body retained); deleted after processing
- **Priority:** Must-Have (MVP), but optional for customer
- **Owner:** Data Science Team

**FR-205: Moving Detection (Job Change Impact)**
- **Requirement:** If moving is detected, system shall forecast increased local mobility or reduced commute
- **Acceptance Criteria:**
  - ✓ Detects: "Moving to Hamburg", "New home in...", "Relocating"
  - ✓ Forecasts impact: If rural → expect fewer train trips; if urban → expect +scooter trips
  - ✓ Updates subscription recommendations
  - ✓ Confidence: <70% if signal weak; asks user for confirmation
- **Priority:** Should-Have (MVP); Phase 2 if not ready
- **Owner:** Data Science Team

**FR-206: Forecast Confidence Quantification**
- **Requirement:** All forecasts shall include confidence intervals and assumptions
- **Acceptance Criteria:**
  - ✓ Confidence range shown: "6 trips ±2 (60-90% confidence)"
  - ✓ Assumptions stated: "Based on 12mo history + Berlin event from calendar"
  - ✓ Automatically widen confidence if data sparse
  - ✓ Alert user if forecast unreliable: "Not enough data; forecast low confidence"
- **Priority:** Should-Have (MVP)
- **Owner:** Data Science Team

---

### 1.3 Portfolio Optimization (FR-301 to FR-330)

**FR-301: Contract Catalog & Pricing Database**
- **Requirement:** System shall maintain up-to-date catalog of all available mobility contracts and pricing
- **Acceptance Criteria:**
  - ✓ Includes: Bahncard 25/50/100, Deutschlandticket, partner memberships, pay-as-you-go rates
  - ✓ Updated quarterly (or on-demand if DB notifies)
  - ✓ Captures: Base price, discounts, bundling options, usage limits
  - ✓ Searchable by feature (e.g., "covers nationwide unlimited travel")
- **Priority:** Must-Have (MVP)
- **Owner:** Product Management

**FR-302: Scenario Generation (Constraint Satisfaction)**
- **Requirement:** System shall generate optimal portfolio scenarios for given demand forecast
- **Acceptance Criteria:**
  - ✓ Generates 2-3 distinct scenarios:
    - Scenario A: Minimize cost
    - Scenario B: Balanced (weighted cost + CO₂)
    - Scenario C: Minimize CO₂
  - ✓ Each scenario must cover predicted demand (no stranded trips)
  - ✓ Uses: Contract solver (e.g., linear programming) or greedy heuristic
  - ✓ Generation time: <30 seconds per customer
- **Priority:** Must-Have (MVP)
- **Owner:** Data Science Team

**FR-303: Cost Calculation for Scenarios**
- **Requirement:** For each scenario, system shall calculate annual total cost
- **Acceptance Criteria:**
  - ✓ Includes: Subscription fees + per-trip costs for uncovered trips
  - ✓ Accounts for: Bundling discounts, partner integrations, membership fees
  - ✓ Accuracy: ±5% vs. projected real cost (validated after pilot)
  - ✓ Shows: Annual total, monthly average, cost per trip by scenario
- **Priority:** Must-Have (MVP)
- **Owner:** Data Science Team

**FR-304: CO₂ Calculation for Scenarios**
- **Requirement:** For each scenario, system shall calculate annual CO₂ impact
- **Acceptance Criteria:**
  - ✓ Uses predicted demand + emission factors by mode
  - ✓ Calculates: Total tons CO₂eq, savings vs. current portfolio
  - ✓ Shown: Annual CO₂, % reduction, trees-planted equivalent
- **Priority:** Should-Have (MVP)
- **Owner:** Data Science Team

**FR-305: Scenario Ranking & Recommendation**
- **Requirement:** System shall rank scenarios based on user priorities and highlight recommendation
- **Acceptance Criteria:**
  - ✓ User priorities captured: Cost weight (0-100%), CO₂ weight (0-100%), Flexibility (0-100%)
  - ✓ Ranking algorithm: Weighted sum (e.g., 70% cost + 20% CO₂ + 10% flexibility)
  - ✓ Top-ranked scenario marked as "Recommended"
  - ✓ Explanation shown: "This scenario balances your cost and sustainability goals"
- **Priority:** Must-Have (MVP)
- **Owner:** Data Science Team

**FR-306: Trade-Off Analysis & Explanation**
- **Requirement:** System shall explain trade-offs between scenarios in user-friendly language
- **Acceptance Criteria:**
  - ✓ For each scenario, explains: "What you gain / What you give up"
  - ✓ Examples:
    - A: "Save €80/year but less flexible (fewer premium seat options)"
    - B: "Save €35/year AND reduce CO₂; added Deutschlandticket"
    - C: "Costs €50 more but 35% lower CO₂ footprint (sustainability focus)"
  - ✓ Clear, non-technical language
- **Priority:** Must-Have (MVP)
- **Owner:** Product Manager

**FR-307: Sensitivity Analysis (What-If)**
- **Requirement:** System shall support what-if scenarios (user changes constraints)
- **Acceptance Criteria:**
  - ✓ User asks: "What if I only take 3 trips per month?" → Regenerate scenarios
  - ✓ User asks: "What if I move to Hamburg?" → Reforecast + regenerate
  - ✓ Latency: <30 seconds for recomputation
  - ✓ Show delta: "Original savings: €40; With new constraint: €25"
- **Priority:** Should-Have (MVP); Nice-to-Have if time limited
- **Owner:** Data Science Team

---

### 1.4 Recommendation & Approval (FR-401 to FR-430)

**FR-401: Recommendation Presentation (Conversational)**
- **Requirement:** System shall present top recommendation in conversational, non-technical language
- **Acceptance Criteria:**
  - ✓ Natural language explanation (generated by LLM)
  - ✓ Example:
    ```
    "I analyzed your 2025 travel. Here's what I found:
     
     You took 25 train trips averaging €9.80/trip. Your current 
     Bahncard 25 (€120/year) is good, but I also found an opportunity:
     
     With the new Deutschlandticket (€49/month), you'd save €35/year
     AND reduce your CO₂ footprint by 30% because trains are cleaner
     than your current mix.
     
     This is my #1 recommendation. Should I set this up for you?"
    ```
  - ✓ Tone: Helpful, not overwhelming; transparent about assumptions
- **Priority:** Must-Have (MVP)
- **Owner:** Product Manager / ML Engineer

**FR-402: Scenario Card Visualization**
- **Requirement:** System shall display 2-3 scenarios as visual cards for easy comparison
- **Acceptance Criteria:**
  - ✓ Each card shows:
    - Scenario name (Cost Focus / Balanced / Sustainability)
    - Annual cost
    - CO₂ impact
    - Key changes (what's added/removed)
    - Action button (Approve / More Info)
  - ✓ Recommended scenario highlighted (gold badge, top position)
  - ✓ Mobile-friendly layout
- **Priority:** Must-Have (MVP)
- **Owner:** UX/Frontend Team

**FR-403: Detailed Change Breakdown**
- **Requirement:** Before approval, system shall show exactly what changes will be made
- **Acceptance Criteria:**
  - ✓ Lists each change:
    - "Cancel Miles (save €10/month)"
    - "Add Deutschlandticket (new cost €49/month)"
    - "Keep Bahncard 25 (no change)"
  - ✓ Shows net impact: "Total net impact: -€29/month starting June 1"
  - ✓ Effective date clear
  - ✓ Terms & conditions link for each service change
- **Priority:** Must-Have (MVP)
- **Owner:** UX/Frontend Team

**FR-404: Multi-Turn Approval Flow**
- **Requirement:** System shall support conversational approval with user questions
- **Acceptance Criteria:**
  - ✓ After recommendation shown, user can:
    - ✓ Approve ("OK, do it")
    - ✓ Ask questions ("Why cancel Miles?")
    - ✓ Request alternatives ("Show me cost-first option")
    - ✓ Decline ("Not now")
  - ✓ System answers follow-up questions & regenerates if needed
  - ✓ State preserved across multi-turn: "Earlier I recommended X; based on your question, here's Y"
- **Priority:** Must-Have (MVP)
- **Owner:** ML/Backend Team

**FR-405: Approval Timeout**
- **Requirement:** Pending approvals shall expire after 30 days
- **Acceptance Criteria:**
  - ✓ User sees: "Approval expires in 28 days"
  - ✓ Reminder after 21 days: "Your recommendation expires soon"
  - ✓ Auto-expire on day 30: Status → EXPIRED
  - ✓ User can request re-analysis after expiry
- **Priority:** Should-Have (MVP)
- **Owner:** Backend Team

---

### 1.5 Execution & Contract Management (FR-501 to FR-530)

**FR-501: Contract Cancellation Execution**
- **Requirement:** System shall execute approved subscription cancellations via partner APIs
- **Acceptance Criteria:**
  - ✓ After approval, system calls partner API (Miles, Lime, Stadtrad, etc.)
  - ✓ Cancellation confirmation received from partner
  - ✓ User notified via email: "✓ Miles canceled. Final billing on June 30."
  - ✓ Timing: Effective date honored (e.g., "Effective June 1st")
  - ✓ Retry logic: If API fails, retry 3x; escalate to ops if persistent
- **Priority:** Must-Have (MVP)
- **Owner:** Integration Team

**FR-502: Contract Addition Execution**
- **Requirement:** System shall execute approved subscription additions via DB Account System
- **Acceptance Criteria:**
  - ✓ After approval, system adds subscription to DB account (Deutschlandticket, Bahncard upgrade, etc.)
  - ✓ Confirmation received: "✓ Deutschlandticket added to your account"
  - ✓ User notified: "Your new ticket is active starting June 1"
  - ✓ Account dashboard updated in real-time
- **Priority:** Must-Have (MVP)
- **Owner:** Integration Team

**FR-503: Execution Status Tracking**
- **Requirement:** System shall track execution status of all contract changes
- **Acceptance Criteria:**
  - ✓ Status states: Pending → In Progress → Executed → Confirmed
  - ✓ User can see status: "Updating your subscriptions... (2/3 complete)"
  - ✓ Handles partial failures: "Miles canceled ✓; Deutschlandticket pending (retry in progress)"
  - ✓ Rollback support: If execution fails, reverse previous changes
- **Priority:** Must-Have (MVP)
- **Owner:** Backend Team

**FR-504: Audit Trail for All Changes**
- **Requirement:** Every contract change shall be logged with full audit trail
- **Acceptance Criteria:**
  - ✓ Logged: User ID, timestamp, recommended scenario, approval, execution status, API responses
  - ✓ Retained: 7+ years (compliance)
  - ✓ Accessible: To DB ops/compliance for dispute resolution
  - ✓ Format: Structured logs (queryable)
- **Priority:** Must-Have (MVP)
- **Owner:** Compliance/Security Team

---

### 1.6 Results & Tracking (FR-601 to FR-630)

**FR-601: Annual Mobility Review (DB Wrapped)**
- **Requirement:** System shall generate annual review showing results of recommendations
- **Acceptance Criteria:**
  - ✓ Shows:
    - "2025 Mobility Summary: 25 trips, €245 spent, 1.2 tons CO₂"
    - "After your portfolio changes: €211 spent, 0.9 tons CO₂"
    - "You saved: €34/year, 0.3 tons CO₂"
  - ✓ Comparison: "vs. peer customers with similar travel patterns, you're 15% more efficient"
  - ✓ Visualizations: Cost trend, CO₂ trend, mode breakdown
  - ✓ Shareable: User can share summary (anonymized)
- **Priority:** Must-Have (MVP)
- **Owner:** Product Manager / Data Science

**FR-602: Savings Tracking**
- **Requirement:** System shall track actual cost savings vs. projected savings from recommendations
- **Acceptance Criteria:**
  - ✓ Projected: "We estimated €35/year savings"
  - ✓ Actual (after 6 months): "You saved €32 (91% of projection)"
  - ✓ Variance explained: "Higher usage of Deutschlandticket than expected"
  - ✓ Feedback loop: Actual data feeds back into forecaster (model improvement)
- **Priority:** Should-Have (MVP)
- **Owner:** Data Science Team

**FR-603: CO₂ Reduction Tracking**
- **Requirement:** System shall track actual CO₂ reduction vs. projected reduction
- **Acceptance Criteria:**
  - ✓ Projected: "Deutschlandticket saves 0.3 tons CO₂/year"
  - ✓ Actual (after 6 months): "You avoided 0.15 tons CO₂ (50% projected)"
  - ✓ Shown: In trees planted equivalent ("Your changes = planting 10 trees")
  - ✓ Certification: Can user share achievement? ("I offset 0.15 tons via DB MoveOptimizer")
- **Priority:** Should-Have (MVP)
- **Owner:** Product Manager

**FR-604: Ad-Hoc Q&A Interface**
- **Requirement:** System shall support conversational Q&A about recommendations and portfolio
- **Acceptance Criteria:**
  - ✓ User asks: "How will this affect my Berlin trips?"
  - ✓ System: "Deutschlandticket covers all Berlin trips. You'll save €5/trip vs. your current Bahncard 25"
  - ✓ System asks clarifying questions if needed
  - ✓ Sessions logged for ops review (quality monitoring)
- **Priority:** Should-Have (MVP)
- **Owner:** ML/Backend Team

---

## SECTION 2: NON-FUNCTIONAL REQUIREMENTS

### 2.1 Performance (NF-101 to NF-120)

**NF-101: Portfolio Analysis Latency**
- **Requirement:** Portfolio analysis shall complete in <10 seconds for 95th percentile of customers
- **Acceptance Criteria:**
  - ✓ p50: <5 seconds
  - ✓ p95: <10 seconds
  - ✓ p99: <20 seconds (acceptable upper bound)
- **Testing:** Load test with 1,000 concurrent customers
- **Owner:** Engineering Team

**NF-102: Recommendation Generation Latency**
- **Requirement:** Recommendation generation (Analyst → Forecaster → Optimizer → Communicator) shall complete in <30 seconds
- **Acceptance Criteria:**
  - ✓ p50: <15 seconds
  - ✓ p95: <25 seconds
  - ✓ p99: <30 seconds
  - ✓ User sees "Analyzing..." progress indicator if >3 seconds
- **Testing:** Load test with 100 concurrent recommendation requests
- **Owner:** Engineering Team

**NF-103: Approval Execution Latency**
- **Requirement:** Approval execution (contract changes) shall initiate within <2 seconds of user confirmation
- **Acceptance Criteria:**
  - ✓ API calls queued and sent within 2 seconds
  - ✓ User sees "Updating..." status immediately
  - ✓ Actual execution may be async (background); user sees status updates
- **Owner:** Backend Team

**NF-104: Database Query Performance**
- **Requirement:** All database queries shall complete in <500ms (p95)
- **Acceptance Criteria:**
  - ✓ Travel history retrieval: <200ms for 12-month dataset
  - ✓ Subscription lookup: <50ms
  - ✓ Vector search (contract catalog): <100ms
  - ✓ Complex joins: <500ms
  - ✓ Query plans indexed and optimized
- **Testing:** Benchmark with 1M row datasets
- **Owner:** Data Engineering Team

---

### 2.2 Reliability & Availability (NF-201 to NF-230)

**NF-201: System Uptime**
- **Requirement:** System shall be available 99% of the time (excluding planned maintenance)
- **Acceptance Criteria:**
  - ✓ Monthly uptime: ≥99% (max 7 hours downtime/month)
  - ✓ Planned maintenance: Scheduled during low-traffic windows (2am-4am CET)
  - ✓ Failover: Auto-failover to secondary in <5 minutes if primary down
  - ✓ Monitoring: Dashboards + alerting for uptime tracking
- **Owner:** DevOps Team

**NF-202: API Resilience (Partner APIs)**
- **Requirement:** System shall gracefully handle partner API failures (Miles, Lime, etc.)
- **Acceptance Criteria:**
  - ✓ Fallback strategy: Use cached data if API down
  - ✓ Cache staleness: Alert user if data >7 days old
  - ✓ Retry logic: Exponential backoff (3 retries max)
  - ✓ User impact: Recommendations still generated (with fallback data)
  - ✓ Ops alert: Notify ops team if partner API down >30 min
- **Owner:** Integration Team

**NF-203: Data Consistency**
- **Requirement:** User data shall be consistent across all layers (PostgreSQL, Redis, Weaviate)
- **Acceptance Criteria:**
  - ✓ Consistency model: Strong for audit trail (PostgreSQL), eventual for cache (<100ms lag acceptable)
  - ✓ Conflict resolution: Last-write-wins for cache; user-initiated for data conflicts
  - ✓ Sync verification: Daily check (audit log vs. cache); alerts on mismatch
  - ✓ User-facing: No data loss; user sees consistent state
- **Owner:** Data Engineering Team

**NF-204: Error Recovery**
- **Requirement:** System shall automatically recover from transient errors without user intervention
- **Acceptance Criteria:**
  - ✓ Automatic retry: Network timeouts, API 5xx errors (3x with backoff)
  - ✓ Graceful degradation: If one agent fails, partial result returned with confidence
  - ✓ User notification: If error user-facing, clear message + suggested action
  - ✓ Logging: All errors logged for ops review + root cause analysis
- **Owner:** Engineering Team

---

### 2.3 Data Privacy & Security (NF-301 to NF-340)

**NF-301: GDPR Compliance**
- **Requirement:** System shall comply with GDPR regulations
- **Acceptance Criteria:**
  - ✓ Data minimization: Collect only necessary data for recommendations
  - ✓ User consent: Explicit opt-in for calendar/email signals
  - ✓ Data retention: Delete personal data after 12 months (or user request)
  - ✓ Data export: User can export all personal data in standard format
  - ✓ Right to be forgotten: User can request full deletion (within 30 days)
  - ✓ Privacy policy: Clear, transparent explanation of data usage
- **Owner:** Legal/Compliance + Engineering Team

**NF-302: Encryption**
- **Requirement:** All personal data shall be encrypted at rest and in transit
- **Acceptance Criteria:**
  - ✓ At rest: AES-256 encryption (PostgreSQL, backups, logs)
  - ✓ In transit: TLS 1.2+ for all API calls
  - ✓ Key management: Keys rotated quarterly; secure key storage (AWS KMS)
  - ✓ Verification: Penetration testing annually
- **Owner:** Security Team

**NF-303: Access Control**
- **Requirement:** Only authorized personnel/systems shall access customer data
- **Acceptance Criteria:**
  - ✓ Role-based access: Developers, ops, compliance have different access levels
  - ✓ Audit logging: All data access logged (who, when, what)
  - ✓ Multi-factor authentication: Required for production access
  - ✓ Segregation: Development, staging, production databases fully isolated
- **Owner:** Security Team

**NF-304: API Security**
- **Requirement:** All APIs shall be secured against common attacks
- **Acceptance Criteria:**
  - ✓ Authentication: OAuth 2.0 for user APIs, API keys for service-to-service
  - ✓ Rate limiting: 1K req/min per user (prevent abuse)
  - ✓ Input validation: All inputs validated; SQL injection/XSS prevented
  - ✓ CORS: Strict origin checking (only DB App domain allowed)
  - ✓ Security testing: OWASP top 10 covered in test plan
- **Owner:** Security Team

**NF-305: Data Residency**
- **Requirement:** Customer data shall reside in Germany (GDPR requirement for DB)
- **Acceptance Criteria:**
  - ✓ All databases: AWS EU-Central-1 (Frankfurt)
  - ✓ Backups: Replicated within EU
  - ✓ Logs: Stored in EU; no transfer outside EU
  - ✓ Third-party services: Data processing agreements signed (for APIs, cloud services)
- **Owner:** Security + DevOps Team

---

### 2.4 Scalability (NF-401 to NF-430)

**NF-401: Horizontal Scalability**
- **Requirement:** System shall scale horizontally from 1K to 1M customers
- **Acceptance Criteria:**
  - ✓ Agent services: Stateless; can add/remove instances dynamically
  - ✓ Database: Read replicas for analytics; write optimized for transaction volume
  - ✓ Cache: Redis cluster mode for distributed caching
  - ✓ Load balancer: Distributes requests evenly across agent instances
  - ✓ Testing: Verified with load test (1M concurrent user sessions simulated)
- **Owner:** DevOps + Engineering Team

**NF-402: Data Volume Scaling**
- **Requirement:** System shall handle increasing data volume (travel history, recommendations, audit logs)
- **Acceptance Criteria:**
  - ✓ Database growth: 100GB/year per 1M users (manageable)
  - ✓ Indexing: Strategic indexes for hot queries (no full table scans)
  - ✓ Partitioning: Travel history partitioned by date (monthly) for query optimization
  - ✓ Archival: Recommendations >2 years old archived (rarely accessed)
- **Owner:** Data Engineering Team

**NF-403: Vector Store Scaling**
- **Requirement:** Vector store (Weaviate) shall scale to 1M+ user embeddings
- **Acceptance Criteria:**
  - ✓ Capacity: 50M+ vector capacity for contract catalog + user embeddings
  - ✓ Query latency: <500ms even at 1M embeddings
  - ✓ Sharding: Distribute vectors across nodes if needed
  - ✓ Testing: Verified with 1M embedding dataset
- **Owner:** ML Ops Team

---

### 2.5 Monitoring & Observability (NF-501 to NF-530)

**NF-501: Agent Performance Monitoring**
- **Requirement:** All agent metrics shall be monitored and exposed for analysis
- **Acceptance Criteria:**
  - ✓ Metrics tracked: Latency (p50, p95, p99), success rate, token usage, cost
  - ✓ Dashboards: Real-time agent performance visible to ops team
  - ✓ Alerts: Trigger if p95 latency >30s or error rate >5%
  - ✓ Historical: Metrics retained for 90 days
- **Owner:** DevOps + ML Ops Team

**NF-502: Recommendation Quality Monitoring**
- **Requirement:** Recommendation quality shall be tracked and monitored
- **Acceptance Criteria:**
  - ✓ Metrics: Recommendation acceptance rate, savings achieved vs. projected, user satisfaction (NPS)
  - ✓ Feedback: Users can rate recommendation quality ("Was this helpful?")
  - ✓ Baseline: Establish target (90%+ accuracy vs. manual review)
  - ✓ Alerts: If accuracy drops below 85%, alert data science team
  - ✓ Model refresh: Quarterly model updates based on feedback
- **Owner:** Data Science + Product Team

**NF-503: API Health Monitoring**
- **Requirement:** All external APIs (DB Navigator, partners, Google) shall be monitored for health
- **Acceptance Criteria:**
  - ✓ Ping: Regular health checks (every 5 minutes)
  - ✓ Metrics: Uptime %, latency, error rates per API
  - ✓ Alerts: If API down or slow, notify ops immediately
  - ✓ Dashboards: API health page for team visibility
- **Owner:** Integration Team

**NF-504: Error Rate & Incident Tracking**
- **Requirement:** System errors shall be tracked and triaged
- **Acceptance Criteria:**
  - ✓ Error categorization: By severity (P1=service down, P2=degraded, P3=minor)
  - ✓ Incident response: P1 incidents → ops on-call immediately
  - ✓ Root cause analysis: Post-incident reviews for all P1/P2 incidents
  - ✓ Trend analysis: Monthly review of error patterns
- **Owner:** DevOps + Engineering Team

---

## SECTION 3: CONSTRAINTS & DEPENDENCIES

### 3.1 Technical Constraints

| Constraint | Details | Impact |
|-----------|---------|--------|
| **API Availability** | Partner APIs availability (Miles, Lime, etc.) | If any partner API down >1hr, fallback to cache; user impact: reduced accuracy |
| **Data Freshness** | Travel history sync lag (max 24h) | Forecast based on data up to 24h old; acceptable for MVP |
| **Vector Search Latency** | Contract catalog search must be <100ms | Impacts scenario generation latency; indexed vectors required |
| **User Consent** | Calendar/email signals require explicit opt-in | ~30-40% customer adoption expected; Phase 1 must support non-opted users |

### 3.2 Business Constraints

| Constraint | Details | Impact |
|-----------|---------|--------|
| **Budget** | €1.1M for 16-week project | No scope creep; prioritize MVP ruthlessly |
| **Timeline** | Delivery Aug 31, 2026 | Pilot testing must start by July 21; limited iteration cycles |
| **Customer Privacy** | No passive behavioral inference | Limits life event detection quality; requires explicit signals |
| **Partner Agreements** | API integrations depend on partner contracts | Must be signed before development starts |

---

## SECTION 4: OUT-OF-SCOPE (For Phase 2+)

1. Real-time dynamic pricing recommendations
2. Multi-user household optimization
3. Autonomous contract execution without approval
4. B2B corporate mobility management variant
5. Third-party comparison/switching recommendations
6. Behavioral inference from location data (privacy-first)
7. Integration with credit card/banking app (expensive, risky)
8. Peer benchmarking with detailed profiles (privacy concern)

---

## SECTION 5: SUCCESS CRITERIA & ACCEPTANCE

### MVP Acceptance Criteria (Aug 31, 2026 Delivery)

**Functional:**
- [ ] Analyst agent accurately identifies inefficiencies (90%+ accuracy vs. manual review, 50-customer sample)
- [ ] Forecaster agent generates reasonable 6-month demand forecast (70%+ accuracy, validated vs. actual demand in pilot)
- [ ] Optimizer agent generates 2-3 scenarios covering all demand; cost within 5% of realistic scenarios
- [ ] Communicator agent presents recommendations clearly; average user satisfaction 4/5 stars
- [ ] Contract execution: 99%+ success rate (approved changes executed within 24h)
- [ ] All 4 agents callable and integrated end-to-end

**Performance:**
- [ ] Portfolio analysis <10s (p95)
- [ ] Recommendation generation <30s (p95)
- [ ] API success rate 99%+
- [ ] 99% uptime (excluding planned maintenance)

**Data Quality:**
- [ ] Travel history ingestion: 99.5%+ completeness
- [ ] Cost accuracy: ±2% vs. actual billing
- [ ] Forecast confidence: 70-90% range (documented assumptions)

**User Experience:**
- [ ] Recommendation acceptance rate: ≥20% (vs. 15% baseline)
- [ ] NPS improvement: +15 points (customers who use agent vs. baseline)
- [ ] Customer satisfaction: 4+/5 stars average

**Compliance:**
- [ ] GDPR compliance verified (legal review)
- [ ] Data encryption: AES-256 at rest, TLS in transit
- [ ] Audit trail: All recommendations/approvals logged
- [ ] Privacy: Opt-in confirmed for calendar/email; no passive tracking

---

## SECTION 6: OPEN QUESTIONS FOR CLARIFICATION

1. **FR-205 (Life Event Detection):** Should email keyword scanning include mail body or just subject? Privacy trade-off.
2. **FR-302 (Scenario Generation):** Should scenarios prioritize user demand satisfaction (must cover all trips) or cost reduction (might leave gaps)? Current spec assumes satisfaction; confirm.
3. **FR-601 (Annual Review):** When should "annual" snapshot be taken? Jan 1? Or anniversary of first recommendation?
4. **NF-201 (Uptime SLA):** 99% is ambitious for MVP with complex integrations. Acceptable? Or should we start with 95%?
5. **Out-of-Scope:** Should we explicitly reserve tokens/budget for Phase 2 features? Or assume separate project?

---

## APPENDIX A: Glossary

| Term | Definition |
|------|-----------|
| **Bahncard** | DB subscription (25/50/100); discounts train fares or unlimited travel |
| **Deutschlandticket** | National monthly ticket (€49) covering all trains nationwide |
| **Miles** | Lufthansa frequent flyer program; partnership with DB |
| **Scenario** | Portfolio option with specific subscriptions + projected cost/CO₂ |
| **Efficiency Score** | Metric quantifying how well current subscriptions match actual demand |
| **Forecast Confidence** | Probability range for demand predictions (70-95% typical) |
| **Approval Gate** | User confirmation step required before contract execution |

---

**Document Owner:** Senior Data Consultant  
**Version:** 1.0 - Draft  
**Status:** Ready for Client Review  
**Next Review:** May 24, 2026
