# Backend Review — main branch (2026-07-02)

Scope: re-evaluate the two open issues from the restructure, review the colleague's
two suggestions, and audit the codebase (now merged with the new frontend +
`/api/register` auth flow) for further vulnerabilities.

Branch: `main` @ `d400685`. All backend Python compiles.

---

## 1. Status of the two prior issues

### A. Optimizer combinatorial blow-up — STILL PRESENT
[optimization.py](backend/src/agent/engines/optimization.py) still enumerates
`itertools.product` over `[None] + plans` per category with no pruning. With the seeded
catalogue (25 public-transport plans) the candidate space is ~`26×11×11×10 ≈ 31k`
portfolios, each simulated over ~570 legs. It's also run **twice per `/api/analyze`**:
once in [pipeline.py](backend/src/agent/pipeline.py) for the contract, and again when the
Analyst agent calls the `optimize_portfolio` tool. This is the dominant cause of the
`/api/analyze` latency.
- **Fix:** before the product, keep only cost-dominant plan(s) per category (a plan that is
  both pricier and not broader-covering than another in the same category can never win).
  This preserves the cheapest/balanced result while cutting the space by orders of
  magnitude. Also compute the optimization once and hand it to the memo step instead of
  re-running it as a tool.

### B. LLM memo reliability/latency — PARTIALLY IMPROVED
[analyst_agent.py](backend/src/agent/analyst_agent.py) `_extract_json` was upgraded from a
greedy regex to `json.JSONDecoder().raw_decode` from the first `{` — genuinely more robust
parsing. But the structural problems remain: `run_briefing` is still on the `/api/analyze`
critical path, still runs a multi-hop ReAct loop (`recursion_limit=20`) that re-invokes the
slow optimizer as a tool. Graceful fallback to the template memo works, so `/analyze` still
returns — just slowly.
- **Fix:** keep the numbers path fully deterministic and give the memo LLM the already-computed
  figures in a single grounded call (no tool loop), or move the agentic memo off the
  synchronous request path.

---

## 2. Colleague's suggestions

### pytest suite for the deterministic engines — ENDORSED, and now DONE ✅
Endorsement stands (this was the highest-leverage suggestion). **Built this session:**
`backend/tests/` now holds a 37-test suite (`pytest.ini` with `pythonpath = src`,
`requirements-dev.txt`, and a dockerfile line baking dev deps into the image). It covers the
four pure engines (`analyze_portfolio`, deterministic `forecast`, `optimize`,
`template_memos`) + `schema_map`, with reproducibility assertions, plus an import/route smoke
test (`test_imports.py`) that asserts each handler's lazy-imported symbol still exists and the
key routes are registered. That smoke test was verified to catch the exact `run_chat`
regression below (rename it → the test fails). Run with `docker compose exec backend pytest -q`.

### dockerfile `COPY scr/` typo — NO LONGER RELEVANT
[backend/dockerfile](backend/dockerfile) now reads `COPY src/ ./src/` (correct). Already
fixed upstream; nothing to do.

---

## 3. New findings (this review)

### ✅ RESOLVED — `/api/chat` was broken (regression), now restored
`agent/communicator_agent.py` had been overwritten (commit `2576e3d "add maikes changes"`)
with the template-memo `CommunicatorAgent` class, dropping the chat ReAct implementation and
its `run_chat` function; [main.py](backend/src/main.py) `/api/chat` still did
`from agent.communicator_agent import run_chat`, so every chat request 500'd. **Fixed this
session:** `run_chat` (the ReAct agent with `lookup_subscriptions` + the tariff RAG tools,
grounded via `_load_user_context`) was restored from `f39404b`; endpoint verified HTTP 200
live. The new `test_imports.py` smoke test now guards against this class of regression.

### ✅ RESOLVED — point 4, Analyst memo off the tool loop; caught an unbounded tariff-doc fetch along the way
`run_briefing` in [analyst_agent.py](backend/src/agent/analyst_agent.py) used to spin up a
`create_react_agent` over six tools (`analyze_history`, `forecast_demand`,
`optimize_portfolio`, `lookup_subscriptions`, `list_tariff_docs`, `read_tariff_doc`) and let
the model re-derive, across 4-6 sequential LLM round-trips, numbers
[pipeline.py](backend/src/agent/pipeline.py) had already computed deterministically before
`run_briefing` was even called. **Fixed this session:** `run_briefing` now takes
`analyst_out`/`forecaster_out`/`optimizer_out` directly and makes **one** LLM call, with those
figures — plus the tariff docs relevant to the recommended plans — injected into the prompt as
grounding data instead of fetched live. The now-unused tool wrappers
(`agent/tools/analysis_tools.py`) were deleted; `communicator_agent.py`'s chat ReAct loop is
untouched.

Caught during implementation, before it shipped: the deterministic tariff-doc pre-fetch had no
per-document or per-plan cap. Some AGB files run 40k-100k characters, and a single recommended
plan name (e.g. "BahnCard 25") can match 6+ near-duplicate fare-class/discount variants — a naive
"first N matches" fetch would silently burn the entire doc budget on one plan's variants (and
blow the prompt up ~10x), starving any other recommended plan of a tariff doc and eroding the
latency win this change was for. Fixed with a 4000-char per-document cap and a 2-doc-per-plan-name
cap so the budget spreads across every recommended plan. Verified with a mocked-LLM dry run
(confirmed docs for multiple recommended plans now appear together) plus the full pytest suite.

### 🟠 MEDIUM — optimizer cost model uses `estimated_cost_eur` (already-paid), not `reference_cost_eur`
Surfaced by the empty-catalog test in the new suite. When scoring a candidate portfolio,
[optimization.py](backend/src/agent/engines/optimization.py) sums each leg's
`estimated_cost_eur` — the amount the user *actually paid*, which is **€0 for legs covered by
an existing pass** — instead of `reference_cost_eur` (the undiscounted fare, i.e. what the trip
would cost without the pass). Consequence: dropping a subscription looks free because the legs
it covered already show €0, so a scenario that *cancels a pass the user relies on* can score as
pure savings. The engine also can't see the value a pass provides, only its sticker price.
Analysis-side realized-savings already correctly uses `reference_cost_eur`; the optimizer
should too.
- **Fix:** cost a candidate portfolio as `sum(reference_cost_eur for legs not covered by the
  portfolio) + annual cost of the portfolio's plans`, so cancelling a pass restores the
  full-fare cost of the trips it used to cover. Add a regression test that cancelling a
  utilised pass never shows phantom savings.

### 🟠 MEDIUM — SQL built with f-strings in `register_endpoint._copy_user_table`
[register_endpoint.py:95-99,129-138](backend/src/register_endpoint.py) interpolate override
expressions and the table name directly into the SQL string
(`f"trip_id || '_' || '{suffix}'"`, `f"'{new_user_id}'"`, `f"INSERT INTO {table} ..."`).
Currently **not exploitable** — `new_user_id`/`suffix` are server-generated UUID hex and the
table names are hardcoded — but it's an injection-shaped pattern one refactor away from being
user-reachable.
- **Fix:** pass values as query parameters; keep only a fixed allowlist of table/column names.

### 🟠 MEDIUM — `/api/register` has no uniqueness/validation/rate-limit
`users.email` and `users.username` have **no UNIQUE constraint**
([01_create_table.sql](database/init/01_create_table.sql)). Registration writes the email into
both columns with no format check and no duplicate check, so two accounts can share an email;
login then matches `username = ? OR email = ?` and picks an arbitrary row via `ORDER BY`.
The endpoint is unauthenticated with no rate limit (mass account creation / DB fill).
- **Fix:** `UNIQUE` (or unique index) on `email`/`username`, validate/normalise email,
  return 409 on duplicate, add basic rate limiting.

### 🟡 LOW — `/api/register` copies a random real persona's trips to the new user
`_link_random_persona` clones another (seed) user's `user_trips`/`trip_legs` onto the new
account so the dashboard has data. Fine as a demo seeding trick, but in anything real it means
a user's "analysis" is built from **someone else's real travel history** — a privacy/data-
integrity smell worth a comment or a synthetic generator instead.

### 🟡 LOW — CORS wildcard + credentials
[main.py:37-43](backend/src/main.py) still sets `allow_origins=["*"]` with
`allow_credentials=True` — an invalid/permissive combination. Pin explicit origins before any
non-demo deployment.

### 🟡 LOW — `_CompatCursor` rewrites `?`→`%s` on the query string
[database.py:25-28](backend/src/database.py) does `query.replace("?", "%s")`. No current query
contains a literal `?` or `%` (e.g. no `LIKE '%x%'`), so it's safe today, but it will silently
corrupt any future query that does. Prefer using `%s` natively, or scope the replacement.

### ℹ️ Minor
- Optimizer runs twice per `/analyze` (see 1A) — wasted compute.
- `communicator_agent.py` has unused `os`/`urllib.request` imports; `main.py` line 7 import has
  a trailing space and `app.post("/api/register")(register)` sits oddly above the `/api/login`
  decorator (cosmetic).

---

## 4. Prioritised actions

**Done this session:** ✅ Restored `/api/chat` (`run_chat`) · ✅ Added `backend/tests/`
(37-test pytest suite: engines + reproducibility + route-import smoke test) · ✅ Single-call
grounded memo off the tool loop (point 4), including a per-plan tariff-doc budget fix caught
during implementation.

**Remaining:**
1. **Fix optimizer cost model** — score portfolios on `reference_cost_eur` for uncovered legs
   so cancelling a utilised pass stops looking free. (MEDIUM, correctness)
2. **Prune optimizer candidates + compute once** — fixes `/analyze` latency. (MEDIUM)
3. **Harden `/api/register`** — UNIQUE email/username, validation, parameterise
   `_copy_user_table`, rate limit. (MEDIUM)
4. **Tighten CORS**; tidy the `?`/`%s` cursor shim. (LOW)
5. **Analyst memo occasionally merges English/German into one field** — see addendum below. (MEDIUM)

---

## Addendum — 2026-07-08

Items 1–4 above are now done (verified against current code on `backend_bug_fixing`):
optimizer costs uncovered legs on `reference_cost_eur`
([optimization.py:104](backend/src/agent/engines/optimization.py)), candidates are pruned to
the cheapest plan per category before the `itertools.product`
([optimization.py:146](backend/src/agent/engines/optimization.py)), `/api/register` has a
rate limiter, parameterised `_copy_user_table` SQL and unique indexes
([register_endpoint.py](backend/src/register_endpoint.py)), and CORS origins are env-driven
([main.py:48](backend/src/main.py)).

### 🟠 MEDIUM — Analyst memo occasionally merges English/German into one field
While live-testing the age-aware tariff-doc retrieval change (commit `be0f295`) via
`/api/analyze` for the seeded persona Mara Vogel, two consecutive calls showed inconsistent
bilingual output from `run_briefing` ([analyst_agent.py](backend/src/agent/analyst_agent.py)):
- Call 1: `memo_english` contained the English memo **and** the German memo concatenated
  (joined by a markdown `---`); `memo_german` was a duplicate of the English text with no
  German content at all.
- Call 2 (same user, same request): `memo_english` and `memo_german` were correctly separated,
  each in its own language.

`_extract_json`'s JSON parsing (`json.JSONDecoder().raw_decode`) behaved identically both
times — the LLM itself didn't reliably keep `english`/`german` single-language and confined to
their own key, per the instruction in
[analyst_system.md](backend/src/agent/prompts/analyst_system.md). Not a regression from
`be0f295`: that commit only added the `pricing_catalog` argument and tariff-doc grounding to
`run_briefing`; the JSON-parsing and prompt path for language separation is untouched.
- **Fix:** strengthen the prompt (e.g. an explicit "do not mix languages within a single field"
  rule plus a short example), and/or validate post-parse that `german` isn't identical to
  `english` and doesn't read as English, re-prompting once or falling back to the deterministic
  template memo if the check fails.
