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

### pytest suite for the deterministic engines — ENDORSED, highest leverage
There are **no Python tests** in the repo and no `pytest` dependency. `analyze_portfolio`,
`forecast` (deterministic fallback), `optimize`, and `template_memos` are pure functions —
cheap to test. This is exactly the class of defect that bit us this session (a missing
function only surfacing on a live curl), and it would also have caught the **broken
`/api/chat`** below. Recommend: `backend/tests/` with unit tests for the engines +
reproducibility assertions, plus a trivial "import app / all routes importable" smoke test
that would catch `run_chat`-style breakages instantly. Add `pytest` to requirements.

### dockerfile `COPY scr/` typo — NO LONGER RELEVANT
[backend/dockerfile](backend/dockerfile) now reads `COPY src/ ./src/` (correct). Already
fixed upstream; nothing to do.

---

## 3. New findings (this review)

### 🔴 HIGH — `/api/chat` is broken (regression)
`agent/communicator_agent.py` was overwritten (commit `2576e3d "add maikes changes"`) with
the **template-memo `CommunicatorAgent` class**; the chat ReAct implementation and its
`run_chat` function are **gone**. [main.py](backend/src/main.py) `/api/chat` still does
`from agent.communicator_agent import run_chat` → `ImportError` → **HTTP 500 on every chat
request** (with an API key; 503 without). `grep -rn 'def run_chat'` finds nothing. The
frontend's chat feature is dead, and the RAG-in-chat capability was lost with it.
- **Fix:** restore the `run_chat` ReAct agent (git has it at `f39404b:...communicator_agent.py`)
  or repoint `/api/chat`. A one-line import smoke test would have caught this.

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
1. **Restore `/api/chat` (`run_chat`)** — user-facing feature currently 500s. (HIGH)
2. **Add `backend/tests/` (pytest)** — engine unit tests + reproducibility + a route-import
   smoke test. Catches #1 and this session's class of bug. (HIGH leverage)
3. **Prune optimizer candidates + compute once** — fixes `/analyze` latency. (MEDIUM)
4. **Harden `/api/register`** — UNIQUE email/username, validation, parameterise
   `_copy_user_table`, rate limit. (MEDIUM)
5. **Single-call grounded memo** off the tool loop. (MEDIUM)
6. **Tighten CORS**; tidy the `?`/`%s` cursor shim. (LOW)
