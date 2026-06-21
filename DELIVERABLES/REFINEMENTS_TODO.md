# Post-Merge Refinements — TODO

Minimal checklist of follow-ups after the backend merge. Detail in [BACKEND_MERGE_REPORT.md](BACKEND_MERGE_REPORT.md) (Post-Merge section).

## DB canonicalisation
- [ ] Load `database/init/` into Postgres (add `docker-entrypoint-initdb.d` mount).
- [ ] Replace `subscription_catalogs` / `recommendations` / `kpis` stubs with real tables.
- [ ] Port Maike's 56-product catalogue + recommendations schema (ref: `seed_subscription_products.py` + `schema.sql` at commit `e8db4cc`).
- [ ] Migrate app off tjorge's demo schema + 9-product `pricing_catalog`.
- [ ] Resolve name clash: `database/init/07_recommendations.sql` vs app's `recommendations` table.

## Optimizer
- [ ] Broaden optimizer beyond hardcoded BahnCard/DT/Miles (bike/scooter/car-sharing, per-minute/per-km) once 56-product catalogue lands — or let the LLM ReAct optimizer propose + deterministic layer cost it.

## Onboarding
- [ ] Wire onboarding into the frontend (UI currently logs in via fixed demo personas; onboarded users don't surface).
- [ ] Collect person name (currently occupation/placeholder) and seed trip history (so `/api/analyze` isn't thin for new users).

## Performance
- [ ] Cache latest recommendation per user (`recommendations` table already supports it) and/or generate memo lazily — `/api/analyze` auto-runs on mount and the LLM memo adds latency.

## Robustness
- [ ] Harden LLM memo output (try `with_structured_output`/function-calling once model support confirmed; today malformed JSON safely falls back to template but loses the LLM memo).

## Tests
- [ ] Add LLM-path tests with a mocked LLM: chat agent, onboarding save, memo JSON parsing (only deterministic/fallback paths covered today).

## Secrets & ops
- [ ] Rotate the leaked `JIRA_TOKEN` (and treat the UNI_GPT key as exposed); untrack `.env`.
- [ ] Add `.env.example`.
- [ ] Add Postgres healthcheck + `depends_on: condition: service_healthy` (currently a connect-retry loop).

## Forecaster
- [ ] Use forecaster output downstream (seasonal demand → plan choice / memo) or surface it in the UI — currently computed and returned but unused.
