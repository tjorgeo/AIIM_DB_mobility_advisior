# Analyze-path performance: measurement and improvement plan

Scope: `POST /api/analyze` — `AnalysisService.run_analysis` → `agent/pipeline.py`
→ the deterministic engines — and how fast the dashboard fills with real numbers.

> **Status: implemented.** All five steps are in. What shipped, and the measured
> result, is in [§6](#6-what-shipped) at the bottom; §§1–5 are the original analysis
> that motivated it, kept as written.

---

## 1. What was measured

**Deterministic engines, isolated** (no DB, no LLM; synthetic legs; Python 3.13;
median of 5 runs). Every stage of the pipeline that produces a number:

| Legs | `analyze_portfolio` | modal-shift | seasonal fallback | project | memo | **total** |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 60 | 0.96 ms | 0.12 ms | 0.10 ms | 0.30 ms | 0.05 ms | **1.53 ms** |
| 250 | 1.80 ms | 0.12 ms | 0.13 ms | 0.29 ms | 0.06 ms | **2.42 ms** |
| 550 | 2.97 ms | 0.11 ms | 0.12 ms | 0.29 ms | 0.06 ms | **3.54 ms** |
| 2000 | 8.79 ms | 0.12 ms | 0.13 ms | 0.30 ms | 0.06 ms | **9.40 ms** |

550 legs is the largest seed persona (per `eval/README.md`). `load_context` is
already known to be negligible — the eval harness matched wall-clock `run_analysis`
to its Langfuse span within 0.1 s.

**End-to-end, measured** (`eval/README.md`, ten personas, `--max-concurrency 1`):

| | |
| --- | ---: |
| Latency per run, median | **28.3 s** |
| Latency per run, range | 4.9 – 64.6 s |
| LLM calls per run | 1–2 |
| `forecast-reasoner` tokens | 3,138 in / **3,824 out** (10/10 runs) |
| `feasibility-judge` tokens | 673 in / 1,093 out (5/10 runs) |

## 2. The finding

**Deterministic compute is ~0.01% of the analyze latency. The other ~99.99% is two
blocking LLM calls, and neither of them produces a number the dashboard shows.**

```
run_analysis, fresh (median 28.3 s)
│
├─ load_context ................... <0.1 s   DB reads
├─ analyze_portfolio .............. 0.003 s  ← every euro, kg CO₂ and trip count
├─ build_modal_shift_suggestions .. ~5 s     ← blocks on feasibility-judge (LLM)
├─ forecast ....................... ~20 s    ← blocks on forecast-reasoner (LLM)
├─ attach_projected_... ........... 0.0003 s
└─ template_memos ................. 0.0001 s
```

Three facts make this fixable rather than inherent:

1. **The dashboard's numbers do not depend on either LLM call.**
   `total_estimated_savings_eur` and `actions_required` come from `template_memos`,
   which derives both purely from `category_subscription_analysis`
   (`engines/memo.py:660-719`); the forecast only appends *textual* caveats. The
   overview page reads `current_annual_spend_eur`, `total_co2_kg`, `mode_breakdown`
   and `summary.total_*` — all deterministic. `forecaster.scenarios`,
   `projected_category_analysis` and `modal_shift_suggestions` are consumed **only**
   by `PortfolioDetail.jsx`, a sub-page the user has to navigate to.

2. **The two LLM calls are independent of each other, but run sequentially.**
   `feasibility_judge` needs `mode_breakdown` + `category_subscription_analysis` +
   onboarding; `forecast_reasoner` needs `forecaster_summary`. Both are available
   the moment `analyze_portfolio` returns (`pipeline.py:69` and `pipeline.py:78`).

3. **Output tokens dominate the slow call.** `forecast-reasoner` emits 3,824 output
   tokens — more than it reads. Generation, not prompt size, is the clock.

Secondary: the frontend gates the *entire* dashboard on one promise
(`Dashboard.jsx:262-273`), rendering `…` for every figure until the whole payload
lands. `SkeletonDashboard.jsx` exists but is never imported.

---

## 3. Plan

Ordered by measured impact per unit of effort. Levers A and B alone take the
perceived fill time from ~28 s to under a second without changing a single number.

### Lever A — Take the LLM off the critical path  ·  −28 s perceived  ·  M effort

Split `/api/analyze` into what is ready now and what needs a model.

- `run_analysis` returns after `analyze_portfolio` + `template_memos`: the full
  `summary`, `current_subscriptions`, `analyst_out` minus `modal_shift_suggestions`,
  and `forecaster_out: null`. Persist the session immediately with
  `status: "partial"`. This is a **~5 ms response**.
- Kick the two LLM steps onto a background worker keyed by `session_id`. When they
  finish, run `attach_projected_category_analysis` + re-run `template_memos` (for
  the forecast caveats), update the session snapshot in place, flip status to
  `"ready"`.
- Add `GET /api/analyze/{session_id}/enrichment` returning
  `{status, forecaster_out, modal_shift_suggestions, memos}`. The frontend polls it
  (or takes an SSE event — the SSE plumbing already exists for chat).
- `PortfolioDetail` renders its forecast/modal-shift blocks from that second
  payload, with a small "still forecasting" state instead of a blank.

Invariant preserved: no number moves. The deterministic engines still produce
everything the first response contains, and the enrichment only ever adds forecast
scenarios, modal-shift candidates and memo prose.

Cost: this reverses the deliberate "fully synchronous" decision documented in
`analysis_service.py`. The reason that decision was made — "the response always
reflects the final result, no follow-up call needed" — is exactly what costs 28 s.
Keep `force=true` synchronous if a guaranteed-complete payload is wanted for
scripts and the eval harness (add `?wait=true`).

### Lever B — Run the two LLM calls concurrently  ·  −5 s  ·  S effort

Standalone win, and still worth doing inside the background worker after Lever A.
`pipeline.py:69` and `pipeline.py:78` have no data dependency on each other.

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    ctxvars = contextvars.copy_context()
    shift = pool.submit(ctxvars.run, build_modal_shift_suggestions, ...)
    fc    = pool.submit(contextvars.copy_context().run, forecast, ...)
```

**`contextvars.copy_context()` is mandatory here.** `observability.llm_config` reads
`_trace_meta` — a `ContextVar` — to nest each generation under the run's
`analyze-pipeline` trace (`observability.py:104`). A bare `ThreadPoolExecutor`
worker starts with a fresh context, so both steps would become their own root
traces and the "one countable token total per analysis" property that
`eval/README.md` reports against would silently break.

### Lever C — Cut `forecast-reasoner` output tokens  ·  −8 to −12 s  ·  S effort

3,824 output tokens is the single largest latency component. Three cuts, none of
which touch a number:

1. **Drop the bilingual duplication.** `Scenario.description_en`/`description_de` and
   `rationale_en`/`rationale_de` (`engines/forecasting.py:72-93`) make the model
   write every piece of prose twice. Generate one language, translate on demand in
   the chat/advisor layer, or simply generate the UI's active language. Roughly a
   third of the output.
2. **Cap `predicted_demand`.** The prompt invites a row per mode per scenario, each
   with a free-text `basis`. Restrict to the modes actually present in
   `dominant_patterns` and cap `basis` to one short clause.
3. **Shrink the input too.** `forecaster_summary` is 13,097 chars, of which
   `monthly_mode_breakdown` is **12,233 (93%)**. Twelve months × 8 modes × 5 fields,
   sent so the model can spot seasonality. Send trips and distance only (drop
   `co2_kg`, `intrinsic_cost_eur`, `effective_cost_eur` — rule 7 of the prompt never
   asks about money or carbon), which cuts it roughly 60% at no loss of signal.

Also worth setting: an explicit `max_tokens` on the forecast call, so a runaway
generation fails fast instead of burning the full 30 s timeout.

### Lever D — Progressive fill in the UI  ·  perceived  ·  S effort

- Render each stat card as soon as its own field exists rather than gating all of
  them on `loadingData` (`Dashboard.jsx:311-324`).
- Wire up the already-written `SkeletonDashboard` — a shaped skeleton reads as
  "loading" far better than `…` in four places.
- Show the deterministic hero (savings + actions) immediately; let the forecast
  blocks fill in behind it.

### Lever E — Deterministic hygiene  ·  −60% of a 3 ms budget  ·  S effort

Real inefficiencies, honestly small. Do them for scale and cleanliness, not for
today's latency.

- **`_parse_dt` runs 4× per leg.** The 12-month windowing at `analysis.py:540-548`
  parses `started_at` three times (collect, filter, re-collect) and the main loop
  parses it a fourth. Profiled at **21% of `analyze_portfolio`** at 2,000 legs.
  Parse once into a `(dt, leg)` list and reuse.
- **`_simulate_consumption_annual_cost` re-walks the category's legs for every
  candidate plan** (`analysis.py:159`, called via `_rank_alternatives`). Profiled at
  **34% of `analyze_portfolio`**. The per-day distance/duration aggregation is
  plan-independent — hoist it to one pass per category and let each plan apply its
  rates to the aggregate.
- **`monthly_mode_breakdown` is serialized twice** in every response and every
  session snapshot: once at the top level of `analyst_out`, once nested inside
  `forecaster_summary`. 24,466 of 60,557 chars — **40% of `analyst_out`**. Keep the
  top-level copy; have `forecast()` read it from there.
- **`pricing_catalog` is re-read in full on every analysis** (`context.py:179`,
  `SELECT * FROM subscription_catalogs`). It is static reference data — cache it
  process-wide with a TTL.

### Lever F — Missing indexes  ·  future-proofing  ·  XS effort

`database/init/` creates indexes only on `analysis_sessions`, `chat_messages` and
`revisions`. Every `user_id` lookup in `load_context` is a sequential scan:

```sql
CREATE INDEX IF NOT EXISTS idx_trip_legs_user_started   ON trip_legs (user_id, started_at);
CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user  ON user_subscriptions (user_id);
CREATE INDEX IF NOT EXISTS idx_user_onboardings_user    ON user_onboardings (user_id);
CREATE INDEX IF NOT EXISTS idx_user_calendars_user      ON user_calendars (user_id, component_type);
CREATE INDEX IF NOT EXISTS idx_recommendations_user     ON recommendations (user_id, created_at DESC);
```

Invisible at seed scale. Add as a new `database/init/08_indexes.sql` — note that
init scripts only run on a fresh volume, so this needs `down -v` or a manual apply.

---

## 4. Sequencing

| Step | Lever | Effort | Effect on time-to-numbers |
| --- | --- | --- | --- |
| 1 | D — progressive fill + skeleton | S | perceived only |
| 2 | B — parallel LLM calls | S | 28.3 s → ~23 s |
| 3 | C — trim forecast prompt and output | S | ~23 s → ~13 s |
| 4 | A — LLM off the critical path | M | ~13 s → **<1 s** |
| 5 | E + F — hygiene and indexes | S | holds at scale |

Steps 1–3 are independent and safe to ship on their own. Step 4 is the one that
actually changes the shape of the system, and is much easier to land once 1–3 have
already shrunk what the background worker has to do.

## 5. What must not change

- **The number guard.** Every euro, kg of CO₂, minute and trip stays deterministic.
  Nothing here moves a figure; Lever A only changes *when* the non-numeric parts
  arrive.
- **Graceful degradation.** With no `UNI_GPT_API_KEY` the pipeline already falls
  back to `seasonal_projection` and feasible/low judgments. The background worker
  must keep that path, and the enrichment endpoint must resolve rather than hang.
- **One trace per analysis.** See the `contextvars` note in Lever B; the eval
  harness's per-run token totals depend on it.
- **The `/api/analyze` response contract.** `_shape_payload` is shared by the fresh
  and cached paths precisely so they cannot drift. A partial payload must go through
  the same function, with the LLM-derived fields nulled — not through a second
  shaper.


---

## 6. What shipped

All six levers are implemented. Verification method and outcome per lever:

| Lever | Where | Verified by |
| --- | --- | --- |
| A — LLM off the critical path | `pipeline.run_analysis` / `run_enrichment` split; `AnalysisService` background worker; `GET /api/analyze/{id}/enrichment`; `wait: true` | `tests/test_pipeline_split.py`, `tests/test_analysis_service.py` |
| B — concurrent LLM calls | `pipeline.run_enrichment`, `ThreadPoolExecutor` + `contextvars.copy_context()` | `test_llm_steps_run_concurrently`, `test_worker_threads_inherit_the_trace_context` |
| C — forecast token cuts | single-language prompt, `max_tokens`, trips/distance-only `monthly_mode_breakdown` | `tests/test_llm_steps.py` (5 new tests) |
| D — progressive fill | per-field gating in `Dashboard.jsx`, `SkeletonDashboard` wired up, `lib/useEnrichment.js` | `vite build` clean |
| E — deterministic hygiene | `daily_usage()` hoist, single `_parse_dt` per leg, slimmed forecaster summary, cached pricing catalog | 400-persona differential harness |
| F — indexes | `database/init/08_indexes.sql` | — (needs a fresh volume or manual apply) |

### The number guard held

The binding constraint was that no figure moves. A differential harness ran
`analyze_portfolio` → modal-shift → seasonal projection → projection → memo over
**400 randomized personas** (0–550 legs, 5–49 catalog plans, missing/unparseable
dates, absent rates, age-gated and travel-class-split plans) before and after the
engine refactor, and compared the full output tree.

Result: **byte-identical** for E1 (single `_parse_dt`) and E2 (hoisted consumption
simulator). E3 changed exactly one field, `forecaster_summary.monthly_mode_breakdown`,
by design and by 55%; everything else stayed identical.

### Measured effect

Deterministic engines, median of 5, same harness as §1:

| Legs | `analyze_portfolio` before | after | Total before | after |
| ---: | ---: | ---: | ---: | ---: |
| 550 (largest persona) | 2.97 ms | **2.19 ms** | 3.54 ms | **2.76 ms** |
| 2000 | 8.79 ms | **5.86 ms** | 9.40 ms | **6.44 ms** |
| 550 legs / 200 plans | 7.42 ms | **4.11 ms** | 8.54 ms | **5.22 ms** |

Response payload at 550 legs: **82.0 KB → 75.0 KB**.

The headline number is not in that table, though. It is that a fresh `/api/analyze`
now returns after the deterministic half — single-digit milliseconds plus the DB read
— instead of after two model calls. Lever E made a 3 ms budget 26% smaller; Lever A
removed ~28 s of waiting from in front of it.

### Not verified here

- **End-to-end latency and the new token counts.** Both need the Docker stack and a
  live `UNI_GPT_API_KEY`; neither was available in this environment. Re-run
  `scripts/measure_token_usage.py` and the comparison experiment to refresh the
  figures in `backend/eval/README.md` — that file now carries a note saying so.
- **The indexes.** `database/init/*.sql` only runs on a fresh volume. Apply with
  `docker compose down -v && docker compose up --build`, or by hand:
  `docker compose exec -T db psql -U postgres -d app_db < database/init/08_indexes.sql`.
- **The `langgraph.checkpoint.postgres` import test.** Two pre-existing failures in
  `tests/test_imports.py` are a package missing from the local environment, not from
  the Docker image. They failed identically before this work.

### Behaviour changes worth knowing

- `/api/analyze` gained `lang` and `wait`; the response gained `enrichment_status`.
  The old fully-synchronous behaviour is `{"wait": true}`.
- The forecast reasoner writes **one** language per call, not both. Read its prose
  through `engines.forecasting.localized()` (backend) or the equivalent fallback in
  `PortfolioDetail.jsx`, which prefer the requested language and fall back to
  whichever exists. The deterministic projection is still bilingual.
- `agent.pipeline.run_analysis` is now the deterministic half only. Callers that need
  everything — `scripts/seed_dataset.py`, `scripts/measure_token_usage.py` — were
  moved to `run_full_analysis`.
- A stale test stub (`_StubLLM.invoke` not accepting the `config=` kwarg the steps
  pass) was masking four `tests/test_llm_steps.py` assertions; fixed, since those
  tests were the safety net for this work.

Test suite: **171 passed**, up from 140, with the same two environment-only failures.


---

## 7. Follow-up: the 429s the split caused

Running the stack after a `docker compose down -v` produced
`429 too_many_concurrent_requests` on nearly every model call. This was a regression
introduced by Levers A and B, not a pre-existing condition.

### Cause

The synchronous request had been acting as an unintended rate limiter. `/api/analyze`
blocked for ~28 s and ran its two LLM steps sequentially, so a user could not have more
than one call in flight — and could not start a second analysis while the first was
running. Both properties disappeared at once:

| | Before | After |
| --- | ---: | ---: |
| Calls per analysis, concurrent | 1 (sequential) | 2 (Lever B) |
| Analyses a user can queue in a second | 1 | as many as they click |
| `ENRICHMENT_WORKERS` x inner pool | — | 4 x 2 = **8** |
| Plus one advisor briefing per dashboard mount | 1 | N (sync endpoint on a 40-thread pool) |

Observed: eight `POST /api/analyze` within four seconds, each a distinct persona, each
firing two enrichment calls plus a chat briefing — roughly 10–15 concurrent requests
against an endpoint whose limit is far lower.

`down -v` amplified it. The read-through cache lives in the database, so a fresh volume
means every persona visit is a cold full run; normally repeat mounts cost nothing.

The system degraded correctly throughout — every request returned 200, the forecast fell
back to the deterministic projection and the briefing to the template memo. Nothing
broke; the LLM output was simply being discarded, which defeats the point of having it.

### Fix

An explicit cap on in-flight model calls in `agent/llm.py`, replacing the backpressure
the blocking request used to provide for free:

- **`ConcurrencyLimited`** — a mixin on the client, capping concurrent calls
  (`LLM_MAX_CONCURRENCY`, default 2) and queueing the rest. Applied at the client rather
  than at the call sites, because the advisor's calls are issued by LangGraph inside
  `create_react_agent` and a call-site semaphore would miss them.
- **`LLM_MAX_RETRIES`** raised 1 → 2, so a residual 429 (the endpoint is university-wide;
  other users' bursts still reach us) backs off and retries instead of falling straight
  through to the deterministic path.
- **`ENRICHMENT_WORKERS`** 4 → 2, since each job fans out to two calls and workers beyond
  the cap only park on the semaphore.

The default of 2 is chosen so one analysis still runs its forecast and feasibility steps
in parallel — the single-user case keeps the full Lever B win, and only real contention
queues.

### Verified

16 tests in `tests/test_llm_concurrency.py`, exercising the real mixin over a stub
endpoint: the cap is never exceeded, it *is* fully used (a serialized implementation
would fail), calls queue rather than drop, and slots return on exception, on stream
exhaustion and on a stream abandoned mid-flight. Separate tests assert the real client is
built from the mixin and that `ConcurrencyLimited` precedes `ChatOpenAI` in the MRO —
reversed, the cap would silently do nothing.

Mutation-checked: removing the semaphore fails 3 tests, reversing the MRO fails 1, and
dropping the release fails the slot-return tests. Suite: **187 passed**, up from 171.

### Not verified

Whether a cap of 2 is the right number — the endpoint's actual limit is unknown, and it
is shared university-wide, so no single value is correct under all conditions. It is
env-tunable for that reason. Watch for `LLM call waited …s for one of N concurrency
slots` in the logs: frequent lines mean the cap is the bottleneck and can be raised;
continued 429s mean it should be lowered.

### Unrelated noise in the same logs

`Prompt 'advisor-chat' with label 'production' not found` is a Langfuse prompt that was
never seeded; the advisor falls back to the local `.md` file exactly as designed. Run
`scripts/seed_prompts.py` to clear it. It has nothing to do with the 429s.
