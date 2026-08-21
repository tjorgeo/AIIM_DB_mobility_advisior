# Observability and evaluation (Langfuse)

The app is instrumented with [Langfuse](https://langfuse.com) for LLM
observability, prompt management, feedback capture and automated evaluation.

Everything here is **additive and optional**. With no `LANGFUSE_*` keys set every
hook is a no-op and the app behaves exactly as before, mirroring how it already
degrades without an LLM key.

> [!NOTE]
> Architecture and the pipeline itself are in [`../README.md`](../README.md).
> The figures this document measures are the ones quoted in the managerial
> report — see [`../../report/README.md`](../../report/README.md).

**Where the code lives.** This folder (`backend/eval/`) holds the offline
evaluation tooling: the LLM judges and the calibration harness. Runtime tracing
is in [`../src/agent/observability.py`](../src/agent/observability.py); the
one-off seed and experiment scripts are in [`../scripts/`](../scripts/).

---

## What is instrumented

| Pillar | What you get | Where |
| --- | --- | --- |
| **Tracing** | Each analysis is one `analyze-pipeline` trace with its nested LLM steps, so a run has a single countable token total. Advisor turns trace as `advisor-briefing`, `advisor-chat` and `advisor-confirm`. All carry model, tokens, cost, tool calls, latency and prompt version, tagged by user, release and environment. | [`observability.py`](../src/agent/observability.py), used in [`pipeline.py`](../src/agent/pipeline.py) and [`advisor/agent.py`](../src/agent/advisor/agent.py) |
| **Prompt management** | The advisor system prompt is versioned in Langfuse as `advisor-chat` and fetched at runtime, so it can be iterated in the UI without a redeploy. The local `.md` file is the offline fallback. | [`scripts/seed_prompts.py`](../scripts/seed_prompts.py), [`prompts/`](../src/agent/prompts/) |
| **Feedback → scores** | `recommendation-accepted` (approval) and `user-thumbs` (chat 👍/👎) attach to the trace that produced the output. | [`analysis_service.py`](../src/analysis_service.py), `POST /api/feedback` in [`main.py`](../src/main.py) |
| **Briefing quality** | LLM judges score each briefing for `memo-groundedness` and `memo-bilingual-complete`. | [`judges.py`](./judges.py), [`calibrate.py`](./calibrate.py) |
| **Pipeline comparison** | The agent pipeline against a single-LLM-call baseline, scored by five evaluators. | [`recommendation_judges.py`](./recommendation_judges.py), [`normalize.py`](./normalize.py) |

---

## Getting started

### 1. Get keys

Sign up for [Langfuse Cloud](https://cloud.langfuse.com) (the free tier is
enough) or self-host, then copy the public and secret keys from
**Settings → API Keys**.

### 2. Configure the environment

Add to the repo-root `.env`; the backend reads these via Compose `env_file`, and
all the scripts below auto-load that file, so no manual `export` is needed.

```dotenv
LANGFUSE_PUBLIC_KEY = pk-lf-...
LANGFUSE_SECRET_KEY = sk-lf-...
LANGFUSE_BASE_URL   = https://cloud.langfuse.com   # US: https://us.cloud.langfuse.com
# optional
LANGFUSE_TRACING_ENVIRONMENT = development          # segments traces by environment
LANGFUSE_RELEASE             =                      # e.g. a git SHA; tags traces
```

`LANGFUSE_BASE_URL` and `LANGFUSE_HOST` are both accepted — the app normalizes
one to the other.

### 3. Seed the managed prompt (once)

```bash
cd backend
python scripts/seed_prompts.py
```

Creates `advisor-chat` in Langfuse with the label `production`. From then on it
can be edited in the UI and the app picks up the `production` version at
runtime. The local `.md` file remains the offline fallback.

### 4. Run the app and watch traces

Start the app as usual (`./run.sh`), trigger an analysis and a chat, then open
**Traces**. You should see `analyze-pipeline` and `advisor-*` traces with model,
token cost, latency and the linked prompt version.

---

## Feedback scores

- **Recommendation accepted** — the implicit north-star signal. Approving a
  recommendation (`POST /api/recommendations/{id}/approve`) writes a
  `recommendation-accepted` = 1 BOOLEAN score to the analysis trace. This works
  because the trace id is persisted on the `recommendations` row in the
  `memo_trace_id` column.
- **Chat thumbs** — explicit. `/api/chat` returns its `trace_id`; the chat widget
  shows 👍/👎 and calls `POST /api/feedback`, which writes a `user-thumbs`
  BOOLEAN score server-side, so the secret key never reaches the browser.

Both can be filtered on in the trace list or charted over time under **Scores**.

> [!WARNING]
> **Needs a current schema.** The `memo_trace_id` column ships in
> [`database/init/01_create_table.sql`](../../database/init/01_create_table.sql)
> with a migration in `03_migrate_memo_trace_id.sql`. An older Postgres volume
> will not have it — recreate the volume, or run
> `ALTER TABLE recommendations ADD COLUMN memo_trace_id TEXT;`.

---

## Briefing quality (LLM-as-a-judge)

Two judges in [`judges.py`](./judges.py), both returning a BOOLEAN score:

- **`memo-groundedness`** — the headline eval. Checks that every number and plan
  name in the briefing comes from the provided grounding data, enforcing the
  invariant that the model never states a figure it was not given.
- **`memo-bilingual-complete`** — the German briefing is a faithful, complete
  translation of the English one.

The judge uses University GPT by default; override with `JUDGE_MODEL`,
`JUDGE_API_KEY`, `JUDGE_BASE_URL`.

**Calibrate before trusting it.** Using the same model family to judge itself is
a known limitation. Extend
[`fixtures/memo_labeled.json`](./fixtures/memo_labeled.json) to roughly 5–10
hand-labelled examples per judge, then:

```bash
cd backend
python -m eval.calibrate      # prints per-judge accuracy against your labels
```

Record that accuracy before using the judge to gate anything.

### The memo-quality experiment

Regenerates briefings over the fixed personas and scores them — a quick
spot-check after changing a prompt or the pipeline:

```bash
cd backend
python scripts/seed_dataset.py       # creates the `analyze-personas` dataset (needs the DB)
python scripts/run_experiment.py     # runs it; exits non-zero if groundedness regresses
```

The dataset stores each persona's **grounding data**, so seeding needs the
database but the experiment itself only needs an LLM key.

---

## Agent pipeline versus naive baseline

This is the headline experiment: it quantifies **how close a bare LLM gets to
the deterministic pipeline**, comparing the two *pipelines* rather than their
prose.

### What is being compared

[`../src/agent/baseline_pipeline.py`](../src/agent/baseline_pipeline.py) is the
evaluation counterpart to the main pipeline. The same raw context `load_context`
produces — profile, preferences, subscriptions, full leg-level travel history,
catalog and calendar — is handed to the LLM in **one call**, and the LLM derives
the recommended portfolio changes itself. No deterministic engines, no
forecaster, no number guard.

Its output uses the same six-value action vocabulary as the main pipeline's
`category_subscription_analysis[*].recommendation` (`keep_current`,
`switch_to_alternative`, `cancel_current_go_pay_as_you_go`,
`consider_subscribing`, `no_subscription_needed`, `insufficient_cost_data`), so
both can be judged against one rubric. [`normalize.py`](./normalize.py) maps the
two into a single shape.

The baseline is not wired into any endpoint or the frontend. To run it alone:

```bash
cd backend
python scripts/run_baseline.py <user_id> [...]   # or --all, optionally --out results.json
```

**The deterministic engine is the ground truth by construction** — the main arm
echoes recommendations computed from the database at seed time, so it scores 1.0
on agreement by definition. That is the ceiling; the number to read is the
baseline's.

### The evaluators

Five, in [`recommendation_judges.py`](./recommendation_judges.py) — four
deterministic code checks and one LLM judge:

| Evaluator | Type | Fails when |
| --- | --- | --- |
| `plan-in-catalog` | deterministic, BOOLEAN | a recommended plan name does not exist in the catalog (a hallucinated tariff) |
| `action-in-vocabulary` | deterministic, BOOLEAN | an action falls outside the six-value vocabulary |
| `savings-non-negative` | deterministic, BOOLEAN | a recommendation claims a negative annual saving |
| `category-agreement` | deterministic, NUMERIC 0–1 | fraction of ground-truth categories whose action does not match |
| `recommendation-soundness` | LLM judge, BOOLEAN | any action, saving or plan contradicts the deterministic cost table |

### Running it

Seeding reads persona context from the database, so Postgres must be up
(`docker compose up -d db`). The comparison run itself needs no database — it
uses the context stored in the dataset — but does need `UNI_GPT_API_KEY` for the
baseline and the judge.

```bash
cd backend

# 1. one-time: create the score configs (types and ranges) in Langfuse — idempotent
python scripts/seed_score_configs.py

# 2. seed the dataset — the original four-persona set
python scripts/seed_comparison_dataset.py
python scripts/run_comparison.py

# ...or all ten seed personas
python scripts/seed_comparison_dataset.py --dataset dummy-users --personas all
python scripts/run_comparison.py --dataset dummy-users --experiment dummy-set-baseline
```

Re-run the seed step whenever the personas or the analysis engine change. Each
run registers two dataset runs, `<experiment>-baseline` and `<experiment>-main`,
so Langfuse shows them side by side. **Every run creates a fresh run**, so
repeat it a few times to average out the baseline's run-to-run variance.

**Where results appear.** The evaluators run locally inside the script and
attach scores to the experiment runs. See them under
**Datasets → Runs** and **Evaluation → Scores**; the score configs are under
**Settings → Scores**.

### Measured results

The `dummy-set-baseline` experiment over the ten seed personas, both arms
completing all ten items. These are the reference figures quoted in the project
report; regenerate them with the commands above plus
`scripts/measure_token_usage.py`.

| Metric | Agent system (main) | Naive baseline |
| --- | ---: | ---: |
| Items completed | 10/10 | 10/10 |
| `category-agreement` (mean) | 1.00 (definitional) | **0.61 / 0.65 / 0.69** |
| `recommendation-soundness` (pass rate) | 1.00 (definitional) | **0.00** |
| `plan-in-catalog` (pass rate) | 1.00 | 1.00 |
| `action-in-vocabulary` (pass rate) | 1.00 | 1.00 |
| `savings-non-negative` (pass rate) | 1.00 | 1.00 |
| Tokens per run, mean (measured) | **7,845** | **46,619** |
| Tokens per run, range | 2,110 – 11,592 | 12,946 – 69,963 |
| LLM calls per run | 1–2 | 1 |
| Latency per run (median) | **28.3 s** | **71.1 s** |
| Latency per run (range) | 4.9 – 64.6 s | 11.1 – 878.5 s |

`category-agreement` is given for three independent runs of the baseline arm;
every other score was identical across all three.

Per-step token counts, read back from Langfuse traces:

| LLM step | Runs | Mean input | Mean output | Mean total |
| --- | ---: | ---: | ---: | ---: |
| Baseline: whole leg history and catalog, one call | 10/10 | 32,280 | 14,340 | **46,619** |
| Ours: `forecast-reasoner` | 10/10 | 3,138 | 3,824 | 6,962 |
| Ours: `feasibility-judge` | 5/10 | 673 | 1,093 | 1,766 |
| **Ours: per analysis run** | | ~3,475 | ~4,370 | **7,845** |

`feasibility-judge` covers five of ten personas because the deterministic hard
filter in `modal_shift.py` resolves the other five candidates before any model
call — so an analysis costs one or two LLM calls depending on the customer.

### Reading these numbers carefully

**Latency is only comparable when both arms run sequentially.** The figures above
come from a `--max-concurrency 1` run of each. At the default of 4 the baseline's
per-item latency inflates badly through contention on the shared university
endpoint (median 74 s, with a 1,105 s worst case), which measures the endpoint's
queue rather than the pipeline. The main pipeline's numbers are wall-clock around
`run_analysis` and matched its Langfuse span latency to within 0.1 s, so
`load_context` is negligible. Both distributions are right-skewed, the baseline's
far more so (mean 160.9 s against a 71.1 s median), because a timed-out call is
retried up to `BASELINE_LLM_MAX_RETRIES`.

**The baseline sends a persona's entire leg history in one prompt** — around 550
legs for the largest. It runs on its own timeout (`BASELINE_LLM_TIMEOUT_S`,
default 300 s) rather than the 30 s interactive budget, and `run_comparison.py`
caps `--max-concurrency` at 4. At the SDK default of 50 the shared endpoint
rate-limits and most items fail with `Request timed out`. The printed table's
**items completed** row reports coverage — treat any arm below the full item
count as an incomplete result, not a score.

---

## Token usage

```bash
cd backend
python scripts/measure_token_usage.py --include-baseline
```

Runs the main pipeline over the ten seed personas and reads the resulting
`analyze-pipeline` traces back out of Langfuse, reporting measured input and
output tokens per persona and per LLM step. `--no-run` skips the run and only
reads existing traces; `--include-baseline` adds the same for baseline traces, so
the two can be compared on measured tokens rather than estimates.

Two caveats:

- **All LLM steps are traced.** `forecast-reasoner` and `feasibility-judge` take
  their callback config from `observability.llm_config()`, and `run_analysis`
  opens the enclosing `analyze-pipeline` trace they nest under, so one analysis
  is one trace with one countable total. Before this was wired up both steps ran
  untraced and their usage was simply absent.
- **Euro cost is not available.** The university endpoint's model has no price
  configured in Langfuse, so `total_cost` is always `0.0`. Tokens are real; cost
  has to be derived externally from a per-token rate.

---

## No CI gate (intentionally)

While the pipeline is still changing a lot, an automated PR gate would mostly
create noise, so it is not wired up. Re-enabling it is one file: a GitHub Actions
workflow running [`run_experiment.py`](../scripts/run_experiment.py) via
[`langfuse/experiment-action`](https://github.com/langfuse/experiment-action).
The `experiment(context)` entry point and `GROUNDEDNESS_THRESHOLD` gating are
already in place; you would add `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`,
`LANGFUSE_BASE_URL` and `UNI_GPT_API_KEY` as repository secrets.

---

## How graceful degradation works

`observability.py` gates everything on `langfuse_enabled()`, true only when both
keys are present. When disabled:

- `trace(...)` yields a handle whose `trace_id` is `None` and whose `config()` is
  `{}`, so spreading it into `.invoke()` changes nothing.
- `get_prompt(...)` returns `None`, so agents use their local `.md` prompt.
- `create_score(...)` and `flush()` are no-ops.

The app is therefore fully functional offline, and any Langfuse or network error
is caught and logged rather than breaking an LLM call.

## SDK version note

The backend image runs Python 3.12 with **Langfuse SDK 3.x or newer**
(`requirements.txt` pins `langfuse>=3.0.0`). The tracing helper uses
`start_as_current_observation` plus the LangChain callback's `langfuse_*`
metadata keys rather than the 3.x-only `span.update_trace`, so it works across
SDK 3.x and 4.x. When updating the SDK, verify tracing against the installed
version rather than the docs — the API has changed between majors.
