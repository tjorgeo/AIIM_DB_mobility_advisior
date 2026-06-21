# API Contract (FROZEN) — DB MoveOptimizer Backend

**Status:** Frozen as of Phase 0 (2026-06-21). The frontend is fixed and consumes exactly this shape.
Any backend merge (deterministic → LangGraph/LLM) **must keep returning these payloads unchanged.**
Source of truth in the frontend: `frontend/src/api/client.js`, `frontend/src/pages/Dashboard.jsx`, `frontend/src/components/chat/useChat.js`.

Base: same origin, proxied by Vite `/api` → backend `:8000`.

---

## `GET /api/personas`
Returns the list of selectable demo personas.
```jsonc
[
  {
    "id": "persona_max_commuter",          // == frontend persona id (personas.js)
    "db_customer_id": "DB-992-MAX",
    "name": "Max Commuter",
    "preferences": { "cost_priority": 90, "co2_priority": 60, "convenience_priority": 50, "class_preference": "2nd" },
    "subscriptions": [ { "service": "deutschlandticket", "monthly_cost_eur": 49.0 } ]
  }
]
```

## `POST /api/analyze`
Request: `{ "user_id": "persona_max_commuter" }`
Response (the dashboard reads `summary.*` and `raw_agent_payloads.analyst.output`):
```jsonc
{
  "session_id": "<uuid>",                  // used by /approve
  "status": "ready",
  "user_id": "persona_max_commuter",
  "customer_name": "Max Commuter",
  "summary": {
    "baseline_cost": 6820.80,
    "baseline_co2": 234.1,
    "recommended_scenario": "A",           // "A" | "B"  → Dashboard recOf()
    "scenarios": [
      {
        "id": "A",
        "label": "Cost-Optimized Portfolio",
        "annual_cost": 588.0,
        "annual_savings": 6232.8,
        "co2_impact_kg": 206.0,
        "co2_savings_kg": 28.1,
        "changes": [ { "action": "add", "item": "Deutschlandticket" } ],  // action: add|cancel
        "explanation": "…"
      }
      // … scenario B
    ],
    "memos": { "english": "<markdown memo>", "german": "<markdown memo>" }
  },
  "raw_agent_payloads": {
    "analyst": {
      "output": {
        "total_trips": 468,
        "mode_breakdown": { "train": { "trips": 468, "cost": 6646.8, "distance_km": 28641.6, "co2_kg": 229.1 } },
        "inefficiencies": [ { "type": "...", "service": "...", "annual_waste": 0.0, "details": "…" } ],
        "savings_potential_estimate": 1994.0
      }
    }
    // forecaster / optimizer / communicator payloads also present (Technical Inspector)
  }
}
```
**Frontend-critical fields:** `session_id`, `summary.recommended_scenario`, `summary.scenarios[].{id,label,annual_cost,annual_savings,co2_savings_kg,changes[].{action,item}}`, `summary.memos.{english,german}`, `raw_agent_payloads.analyst.output.{mode_breakdown,inefficiencies}`.

## `POST /api/recommendations/{session_id}/approve`
Request: `{ "scenario_id": "A" }`
Response: `{ "status": "success", "recommendation_id": "...", "scenario_id": "A" }`
(Dashboard checks `res.status === 'success'`.)

## `POST /api/chat`  — NOT YET IMPLEMENTED (Phase 4)
Request: `{ "user_id": "...", "messages": [ { "role": "user|assistant", "content": "…" } ] }`
Expected response: `{ "reply": "<assistant text>" }`
Until this exists, `useChat.js` falls back to a scripted client-side assistant — so a 404/500 here is non-fatal but the chat is not LLM-powered.

---

### Frozen decisions
- **Engine:** target = LangGraph/LLM (from `backend_maike`); transplanted behind this contract.
- **API shell:** = `backend_tjorge` (FastAPI), promoted into `backend/`.
- **Store:** target = docker Postgres `db` (Phase 2+). Phase 1 keeps the bundled SQLite to stay green.
- **Persona ids** must stay identical to `frontend/src/data/personas.js`.
