# Observability & Evaluation (Langfuse)

This app is instrumented with [Langfuse](https://langfuse.com) for LLM
observability, prompt management, feedback capture, and automated evaluation.
Everything here is **additive and optional**: with no `LANGFUSE_*` keys set, every
hook is a no-op and the app runs exactly as before (mirroring how the app already
degrades without an LLM key).

This folder (`backend/eval/`) holds the offline evaluation tooling — the
LLM-as-a-Judge evaluators and the calibration harness. The runtime tracing lives
in [`../src/agent/observability.py`](../src/agent/observability.py); the one-off
seed/experiment scripts live in [`../scripts/`](../scripts/).

---

## What's instrumented

| Pillar | What you get | Where |
| --- | --- | --- |
| **Tracing** | Every memo (`analyst-memo`) and chat turn (`chat-response`) is one trace: model, tokens, cost, tool calls, latency, prompt version. Tagged by user, release, environment. | [`observability.py`](../src/agent/observability.py), used in [`analyst_agent.py`](../src/agent/analyst_agent.py) & [`communicator_agent.py`](../src/agent/communicator_agent.py) |
| **Prompt management** | The two system prompts are versioned in Langfuse and fetched at runtime — iterate in the UI without a redeploy. Local `.md` files are the offline fallback. | [`scripts/seed_prompts.py`](../scripts/seed_prompts.py), [`prompts/`](../src/agent/prompts/) |
| **Feedback → scores** | `recommendation-accepted` (approval) and `user-thumbs` (chat 👍/👎) attach to the trace that produced the output. | [`analysis_service.py`](../src/analysis_service.py), `POST /api/feedback` in [`main.py`](../src/main.py) |
| **Evaluation** | LLM judges score every memo for `memo-groundedness` and `memo-bilingual-complete`. | [`judges.py`](./judges.py), [`calibrate.py`](./calibrate.py) |
| **Experiments (manual)** | Re-generate memos over the 6 fixed personas and score them, to spot-check quality after changes. Run on demand — no CI gate (see below). | [`scripts/seed_dataset.py`](../scripts/seed_dataset.py), [`scripts/run_experiment.py`](../scripts/run_experiment.py) |

---

## Getting started

### 1. Get keys

Sign up for [Langfuse Cloud](https://cloud.langfuse.com) (EU region is the
default; free tier is enough) or self-host. Copy the **public** and **secret**
keys from **Settings → API Keys**.

### 2. Configure the environment

Add to `.env` (see [`../../.env.example`](../../.env.example)). The backend reads
these via docker-compose `env_file`:

```dotenv
LANGFUSE_PUBLIC_KEY = pk-lf-...
LANGFUSE_SECRET_KEY = sk-lf-...
LANGFUSE_BASE_URL   = https://cloud.langfuse.com   # US: https://us.cloud.langfuse.com
# optional
LANGFUSE_TRACING_ENVIRONMENT = development          # segments traces by env
LANGFUSE_RELEASE             =                      # e.g. git SHA; tags traces
```

> `LANGFUSE_BASE_URL` and `LANGFUSE_HOST` are both accepted — the app normalizes
> one to the other.

### 3. Seed the managed prompts (once)

```bash
cd backend
python scripts/seed_prompts.py
```

Creates `analyst-memo` and `communicator-chat` in Langfuse (label `production`).
From now on you can edit them in the Langfuse UI and the app picks up the
`production` version at runtime — no redeploy. The local `.md` files stay as the
offline fallback.

### 4. Run the app and watch traces

Start the app as usual (`./run.sh`), trigger an analysis (`/api/analyze`) and a
chat, then open **Traces** in Langfuse. You should see `analyst-memo` and
`chat-response` traces with model, token cost, latency, and the linked prompt
version. Explore a few before adding more — see what's captured and what you'd
want to filter by.

---

## Feature guides

### Feedback scores

- **Recommendation accepted (implicit, the north-star signal).** When a user
  approves a recommendation (`POST /api/recommendations/{id}/approve`), a
  `recommendation-accepted` = 1 BOOLEAN score is written to the memo's trace.
  This works because the memo's `trace_id` is persisted on the `recommendations`
  row (column `memo_trace_id`).
- **Chat thumbs (explicit).** `/api/chat` returns its `trace_id`; the chat widget
  shows 👍/👎 and calls `POST /api/feedback`, which writes a `user-thumbs`
  BOOLEAN score server-side (the secret key never reaches the browser).

Filter traces by these scores in the UI, or chart them over time under **Scores**.

> **Requires a fresh DB schema.** The `memo_trace_id` column is in
> [`database/init/01_create_table.sql`](../../database/init/01_create_table.sql).
> An existing Postgres volume won't have it — recreate the volume, or run
> `ALTER TABLE recommendations ADD COLUMN memo_trace_id TEXT;`.

### Evaluation (LLM-as-a-Judge)

Two judges in [`judges.py`](./judges.py), both returning a BOOLEAN score:

- **`memo-groundedness`** — the headline eval. Checks that every number and plan
  name in the memo comes from the provided grounding data, enforcing the analyst
  invariant ("never state a number you did not get from the provided data", see
  [`analyst_system.md`](../src/agent/prompts/analyst_system.md)).
- **`memo-bilingual-complete`** — the German memo is a faithful, complete
  translation of the English one.

The judge uses University GPT by default; override with `JUDGE_MODEL`,
`JUDGE_API_KEY`, `JUDGE_BASE_URL`.

**Calibrate before you trust it.** Using the same model family to judge itself is
a known limitation. Extend [`fixtures/memo_labeled.json`](./fixtures/memo_labeled.json)
to ~5–10 hand-labelled examples per judge and run:

```bash
cd backend
python -m eval.calibrate      # prints per-judge accuracy vs your labels
```

Record the accuracy in your deliverable before using the judge to gate merges.

### Experiments (manual)

Build a reusable evaluation set from the six seed personas, then run the memo
generator over it and score with the judges — a quick way to spot-check quality
after changing a prompt or the pipeline:

```bash
cd backend
python scripts/seed_dataset.py       # creates the `analyze-personas` dataset (needs the DB)
python scripts/run_experiment.py     # runs the experiment; exits non-zero if groundedness regresses
```

The dataset stores each persona's **grounding data**, so the experiment only
needs an LLM key — no database.

**No CI gate (intentionally).** While the pipeline is still changing a lot, an
automated PR gate would just create noise, so it isn't wired up. Re-enabling it
later is one file: add a GitHub Actions workflow that runs
[`run_experiment.py`](../scripts/run_experiment.py) via
[`langfuse/experiment-action`](https://github.com/langfuse/experiment-action) —
the `experiment(context)` entry point and `GROUNDEDNESS_THRESHOLD` gating are
already in place. You'd add these repository secrets: `LANGFUSE_PUBLIC_KEY`,
`LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL`, `UNI_GPT_API_KEY`.

---

## How graceful degradation works

`observability.py` gates everything on `langfuse_enabled()` (both keys present).
When disabled:

- `trace(...)` yields a handle whose `trace_id` is `None` and whose `config()` is
  `{}` — spreading it into `.invoke()` changes nothing.
- `get_prompt(...)` returns `None`, so agents use their local `.md` prompt.
- `create_score(...)` and `flush()` are no-ops.

So the app is fully functional offline, and any Langfuse or network error is
caught and logged rather than breaking an LLM call.

## SDK version note

Production runs on Python 3.13 → **Langfuse SDK 4.x**. The tracing helper uses
`start_as_current_observation` + the LangChain callback's `langfuse_*` metadata
keys (not the 3.x-only `span.update_trace`), so it works across SDK 3.x and 4.x.
When updating the SDK, verify tracing against the installed version rather than
the docs — the API has changed between majors.
