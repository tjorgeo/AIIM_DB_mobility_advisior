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
| **Subscription catalogue** | Expanded from 7 CSV products to 56 products across 4 mobility categories |

---

## New folder: `db/`

```
db/
├── schema.sql                     ← canonical table definitions (single source of truth)
├── db_utils.py                    ← shared SQLite helpers imported by all agents
├── seed_subscription_products.py  ← catalogue seeder — 56 products across 4 categories
├── migrate_csv_to_sqlite.py       ← one-time migration script (CSV → SQLite)
└── moveoptimizer.db               ← the database file (committed so colleagues can use it directly)
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

## Subscription product catalogue

The original CSV had 7 products (basic BahnCard tiers only). The catalogue has been expanded to **56 products** across four mobility categories, sourced from `data/subscription_overview.xlsx` and the markdown files in `data/Markdownfiles Abos/`.

### Products by category

| Category | Count | Products |
|---|---|---|
| ÖPNV / Bahn | 18 | Deutschlandticket, Jobticket, BahnCard 25/50/100 in all variants (standard, Probe, My, Senioren, Ermäßigt, Jugend) |
| Bike Sharing | 9 | Call a Bike (Starter, Member, Member Plus), Nextbike (PayG, Monat, Jahr), Swapfiets (Stadtrad, E-Bike P1/P7) |
| E-Scooter | 24 | Dott, Voi, Lime, Bolt — each with PayG, subscription, and time-pass variants |
| Car Sharing | 5 | Miles (per-km), Sixt Share (per-minute), teilAuto (Starttarif, Rahmentarif, Vielfahrertarif) |

### New columns added to `subscription_products`

| Column | Type | Description |
|---|---|---|
| `pricing_model` | TEXT | `flat_monthly` / `per_minute` / `per_km` / `per_km_and_time` / `time_pass` / `hybrid` |
| `cost_per_minute_eur` | REAL | Base per-minute rate (where applicable) |
| `cost_per_km_eur` | REAL | Base per-km rate (car sharing, BahnCard is nil) |
| `unlock_fee_eur` | REAL | One-time unlock / activation fee per ride |
| `free_minutes_per_ride` | INTEGER | Free minutes included per trip (bike/scooter plans) |
| `period_days` | INTEGER | Validity window: 1 / 3 / 7 / 30 / 90 / 365 |
| `eligibility_min_age` | INTEGER | Minimum age (e.g. 6 for Jugend BC, 21 for car sharing) |
| `eligibility_max_age` | INTEGER | Maximum age (e.g. 26 for My BahnCard, 64 for standard BahnCard) |
| `eligibility_notes` | TEXT | Human-readable eligibility conditions |
| `city_availability` | TEXT | Where the product is available |
| `markdown_ref` | TEXT | Path inside `data/` to the detailed pricing / AGB markdown file |

### Seeder script: `db/seed_subscription_products.py`

The seeder is safe to re-run at any time — it clears the table and re-inserts all 56 products. It also adds missing columns to existing databases automatically (via `PRAGMA table_info` + `ALTER TABLE`), so colleagues do not need to rebuild the DB from scratch.

```bash
cd langgraph_module
uv run python ../db/seed_subscription_products.py
```

The migrate script (`migrate_csv_to_sqlite.py`) now calls the seeder internally, so a full rebuild also uses the expanded catalogue.

### Detail files for pricing / AGB

Complex pricing (e.g. Sixt dynamic rates, teilAuto vehicle classes, BahnCard AGB) is kept in the original markdown files under `data/Markdownfiles Abos/`. The `markdown_ref` column points the LLM to the right file when a user needs detail beyond what is stored in the database.

### `lookup_subscriptions` tool — updated filters

The optimizer agent's tool now accepts nine filter values:

| Filter | Returns |
|---|---|
| `all` | All 56 products |
| `card` | BahnCard discount cards only |
| `subscription` | Monthly/annual subscriptions (DT, Jobticket, bike, car sharing) |
| `pass` | Single-use and time-pass products (scooter day passes, PayG) |
| `bahncard` | All BahnCard variants (BC25/50/100) |
| `deutschlandticket` | DT-49 and Jobticket only |
| `bike` | All bike-sharing products |
| `scooter` | All e-scooter products |
| `carsharing` | Miles, Sixt Share, teilAuto |

Use narrow filters in the optimizer to avoid sending the full 56-product list to the LLM.

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
