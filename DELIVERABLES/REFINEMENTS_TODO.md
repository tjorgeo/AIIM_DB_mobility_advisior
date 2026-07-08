# Post-Merge Refinements — TODO

Follow-ups after the backend merge. Detail in [BACKEND_MERGE_REPORT.md](BACKEND_MERGE_REPORT.md) (Post-Merge section).

> Status reconciled 2026-07: most items shipped. Remaining work is either done in this
> pass (see ✅ below) or deliberately deferred to Phase 2 (see the bottom section).

## DB canonicalisation — ✅ done
- [x] Load `database/init/` into Postgres — auto-loaded via the `docker-entrypoint-initdb.d` mount (`docker-compose.yml`).
- [x] Replace `subscription_catalogs` / `recommendations` stubs with real tables — full schemas in `database/init/01_create_table.sql`.
- [x] Port Maike's catalogue + recommendations schema — 54-product catalogue seeded (`database/seed/subscription_catalogs_v1.csv`); the old 9-product `pricing_catalog` is gone.
- [x] Migrate app off tjorge's demo schema + 9-product `pricing_catalog` — done.
- [x] Resolve name clash `07_recommendations.sql` vs app's `recommendations` — no such file exists; single unified `recommendations` table, backend columns all match.
- [x] Replace the `kpis` stub — removed the empty `kpis` view (`database/init/03_create_views.sql` deleted). Nothing read it; runtime metrics live in Langfuse. (Existing dev DBs: `DROP VIEW IF EXISTS kpis;` — harmless if skipped.)

## Optimizer
- [x] **Free-coverage guard** — pay-as-you-go plans with no flat fee (`_plan_annual == 0`) are excluded from candidates (`optimization.py:_has_flat_price`), so a €0 plan can no longer be picked as "free coverage" that zeroes a whole category for nothing.
- [ ] Usage-based / discount pricing (`per_minute` / `per_km` / hybrid; BahnCard % discounts) — **deferred (Phase 2)**. Flat-rate-only is documented in `backend/README.md`; the deeper rate/discount engine is future work.

## Onboarding — ✅ done
- [x] Wire onboarding into the frontend — `frontend/src/pages/Login.jsx` survey → `POST /api/register` (`register_endpoint.py`); the new user auto-logs in and surfaces in the app.
- [x] Collect person name + seed trip history — real first/last name stored; `_link_random_persona` seeds `user_trips`/`trip_legs` so `/api/analyze` isn't thin for new users.

## Performance — ✅ done
- [x] Cache latest recommendation per user + generate memo lazily — `/api/analyze` now reuses the user's latest `recommendations` row (read-through cache in `Orchestrator._load_cached`; `force=true` to refresh). A fresh run returns the deterministic numbers + template memo immediately and schedules the slow LLM memo as a FastAPI `BackgroundTask` (`Orchestrator.generate_memo`); the next cached mount serves the upgraded prose.

## Secrets & ops — ✅ partly done
- [x] Untrack `.env` + add `.env.example` — done (`.env` is git-ignored; `.env.example` tracked).
- [x] Postgres healthcheck + `depends_on: condition: service_healthy` — added to `docker-compose.yml` (`pg_isready`); the app-side connect-retry loop stays as belt-and-suspenders.

## Deferred (Phase 2)
- [ ] Harden LLM memo output with `with_structured_output`/function-calling (today a raw-JSON extractor + template fallback covers malformed output safely).
- [ ] LLM-path tests with a mocked LLM: chat agent, onboarding save, memo malformed-JSON fallback (only deterministic/fallback paths + one well-formed memo test covered today).
- [ ] Secrets: rotate the leaked `JIRA_TOKEN` (still retrievable from git history, commit `218c144`) and treat the UNI_GPT key as exposed. `.env` is already untracked and `.env.example` exists; rotation + history purge are manual/external actions, intentionally out of scope here.
- [ ] Use the forecaster output more widely — it feeds the memo grounding today but not the optimizer's euro/CO₂ numbers, and it isn't surfaced in the UI.
