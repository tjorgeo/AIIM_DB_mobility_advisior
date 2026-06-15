# pipeline-refactor — What Changed and How to Get Started

This document covers all significant changes introduced on the `pipeline-refactor` branch.
It is the first thing to read if you are joining this branch or setting it up on a new machine.

---

## Overview of changes

| Area | What changed |
|---|---|
| **Data storage** | Replaced CSV files with a SQLite database as the shared data layer |
| **Data quality** | Fixed array field format, boolean types, stripped generation metadata, added CO2 column |
| **New tables** | Added `user_subscriptions` and `recommendations` tables (previously missing) |
| **`travel_analyst_agent`** | New agent — analyses one user's travel patterns from the database |
| **`pipeline_agent`** | Added `load_context_node` — no longer requires a hand-crafted input JSON |
| **`onboarding_agent`** | Now writes completed profiles to the database instead of just printing JSON |

---

## New folder: `db/`

```
db/
├── schema.sql                 ← canonical table definitions (single source of truth)
├── db_utils.py                ← shared SQLite helpers imported by all agents
├── migrate_csv_to_sqlite.py   ← one-time migration script (CSV → SQLite)
└── moveoptimizer.db           ← the database file (committed so colleagues can use it directly)
```

### `schema.sql` — tables

| Table | Purpose |
|---|---|
| `users` | User profiles, collected by the onboarding agent |
| `trips` | Full trip history per user |
| `trip_legs` | Individual legs within each trip (mode, station, distance) |
| `subscription_products` | DB product catalogue (BahnCard tiers, Deutschlandticket, etc.) |
| `user_subscriptions` | Which user holds which subscription and at what status |
| `recommendations` | Optimizer output and approval state per user |

### `db_utils.py` — shared helpers

All agents import from here. No agent calls `sqlite3` directly. Key functions:

```python
from db.db_utils import (
    get_user,                  # look up by user_id UUID
    get_user_by_username,      # look up by username (e.g. "mia.schmidt")
    get_trips,                 # all trips for a user, optional date range
    get_user_subscriptions,    # active subscriptions joined with product names
    get_subscription_products, # full product catalogue, optional type filter
    upsert_user,               # insert or replace a user row
    add_user_subscription,     # add a new subscription record
    save_recommendation,       # persist an optimizer recommendation
    update_recommendation_status,
)
```

---

## Setup instructions

### If you are on a new machine (first time)

```bash
# 1. Install dependencies
cd langgraph_module
uv sync

# 2. The database is already committed — no migration needed.
#    Verify it exists:
ls ../db/moveoptimizer.db
```

That is all. The database file is committed to the branch and ready to use.

### Do NOT run the migration script unless you know what you are doing

`db/migrate_csv_to_sqlite.py` re-creates the database from the raw CSVs. Running it will **overwrite** the committed database, including any user data added through the onboarding agent. Only run it if you need to rebuild from scratch.

---

## What changed in the agents

### `travel_analyst_agent.py` — new agent

Analyses the travel history of a single user and produces a structured summary.

**LangSmith Studio input** — select `travel_analyst`, enter a username in the `user_id` field:

```
mia.schmidt
```

Available usernames: `lea.mueller`, `max.braun`, `alex.kim`, `lena.schulz`, `tobias.wagner`,
`sophie.becker`, `jan.schulz`, `mia.schmidt`, `anna.schneider`, `markus.fischer`

**Graph:** `load_data → analyze`

The output (in `messages`) now includes CO2 totals, active subscriptions, and proper mode/route breakdowns.

---

### `pipeline_agent.py` — updated

Previously required a hand-crafted `travel_data` JSON as input. It now queries the database automatically.

**LangSmith Studio input** — select `analyst_optimizer_pipeline`, enter a username in `user_id`:

```
jan.schulz
```

Leave `travel_data`, `analyst_summary`, and `messages` empty.

**Graph:** `load_context → analyst → optimizer ⇄ tools`

The `load_context` node fetches the user profile, trip history, and active subscriptions from SQLite and passes them forward. The `lookup_subscriptions` tool also reads from SQLite instead of a CSV file.

---

### `onboarding_agent.py` — updated

Previously printed a JSON block in the chat and did nothing else with it.
Now includes a `save_profile_node` that fires automatically when the LLM outputs the final profile JSON, and writes the result to the `users` and `user_subscriptions` tables.

**LangSmith Studio input** — select `onboarding`, leave all fields empty, click Submit. Use the chat panel to answer the 6 steps. After Step 6, the profile is saved automatically.

**Graph:** `onboarding → (conditional) → save_profile → END`

The conditional edge only routes to `save_profile` when a ` ```json ` block is detected in the last assistant message, so intermediate turns route straight to END and wait for the next user message.

**To verify a profile was saved:**

```bash
cd langgraph_module
uv run python -c "
import sys; sys.path.insert(0, '..')
from db.db_utils import fetchall
rows = fetchall('SELECT username, home_city, job_industry, onboarding_completed_at FROM users')
for r in rows: print(r)
"
```

---

## Data quality fixes applied during migration

The original CSV files had several format issues. All of these are fixed in the database.

| Issue | Before (CSV) | After (SQLite) |
|---|---|---|
| Array fields | `{"subway","tram"}` (PostgreSQL syntax) | `["subway","tram"]` (valid JSON) |
| Boolean fields | `"true"` / `"False"` (strings) | `1` / `0` (integers) |
| Generation metadata | Columns like `generation_batch_index`, `generation_rationale`, `source_persona_id` mixed into data tables | Stripped — not present in the database |
| CO2 data | Missing | Added as `co2_kg` to `trips` and `trip_legs`, calculated from mode × distance |
| Subscription catalogue | No info on which modes a product covers, no cancellation notice period | `valid_modes`, `cancellation_notice_months`, `auto_renews`, `combinable_with` added |
| User subscriptions | Only a free-text `current_ticket_product` field on the user | Dedicated `user_subscriptions` table with status, dates, and FK to product catalogue |
