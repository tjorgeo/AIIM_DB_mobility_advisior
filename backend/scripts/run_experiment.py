"""Run the memo-quality experiment over the `analyze-personas` dataset.

The task regenerates the recommendation briefing from each item's stored grounding
(LLM only — no database) using the **Advisor's opening briefing** (the production
narrative), and the LLM judges score it for groundedness and bilingual completeness.
Aggregate pass-rates become run-level scores.

Two entry points, sharing the same task/evaluators:

* ``main()`` — local run: ``python scripts/run_experiment.py`` (or ``-m``). Prints
  the report and exits non-zero if the groundedness pass-rate is below threshold.
* ``experiment(context)`` — the contract for ``langfuse/experiment-action`` in CI;
  raises ``RegressionError`` when the gate fails.

Env: UNI_GPT_API_KEY (memo + judge), LANGFUSE_* (dataset + tracing),
     GROUNDEDNESS_THRESHOLD (default 0.9).
"""

import os
import sys
from collections import defaultdict
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))  # agent.*
sys.path.insert(0, str(_BACKEND))          # eval.*

DATASET_NAME = "analyze-personas"
EXPERIMENT_NAME = "memo-quality"
GROUNDEDNESS_THRESHOLD = float(os.getenv("GROUNDEDNESS_THRESHOLD", "0.9"))

if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]


def task(*, item, **_):
    """Regenerate the briefing from the item's stored grounding via the Advisor's opening
    briefing (LLM only, no DB — the eval agent has no checkpointer and no DB-backed tools).
    Runs once per language so the judges get the same {english, german} shape as before."""
    from agent.advisor import briefing_from_snapshot

    inp = item.input
    snapshot = {
        "user": {"name": inp["name"]},
        "analyst_out": inp["analyst_out"],
        "forecaster_out": inp["forecaster_out"],
    }
    return {
        "memo_english": briefing_from_snapshot(snapshot, "en"),
        "memo_german": briefing_from_snapshot(snapshot, "de"),
        "grounding": {
            "analysis": inp["analyst_out"],
            "forecast": inp["forecaster_out"],
        },
    }


def _pass_rates(*, item_results, **_):
    """Aggregate each judge's BOOLEAN scores into a run-level pass-rate."""
    from langfuse import Evaluation

    agg = defaultdict(list)
    for r in item_results:
        for e in r.evaluations:
            if e.value is not None:
                agg[e.name].append(float(e.value))
    out = []
    for name, vals in agg.items():
        rate = sum(vals) / len(vals) if vals else 0.0
        out.append(
            Evaluation(
                name=f"{name}-pass-rate",
                value=rate,
                comment=f"{int(sum(vals))}/{len(vals)} passed",
            )
        )
    return out


def _evaluators():
    from eval.judges import groundedness_evaluator, bilingual_evaluator

    return [groundedness_evaluator, bilingual_evaluator]


def _groundedness_rate(result) -> float:
    for e in result.run_evaluations:
        if e.name == "memo-groundedness-pass-rate":
            return float(e.value)
    return 0.0


# --- CI entry point (langfuse/experiment-action) -----------------------------


def experiment(context):
    """Entry point for langfuse/experiment-action."""
    from langfuse import RegressionError

    result = context.run_experiment(
        name=EXPERIMENT_NAME,
        task=task,
        evaluators=_evaluators(),
        run_evaluators=[_pass_rates],
    )
    rate = _groundedness_rate(result)
    if rate < GROUNDEDNESS_THRESHOLD:
        raise RegressionError(
            result=result,
            metric="memo-groundedness-pass-rate",
            value=rate,
            threshold=GROUNDEDNESS_THRESHOLD,
        )
    return result


# --- Local entry point -------------------------------------------------------


def main() -> int:
    from langfuse import get_client

    client = get_client()
    dataset = client.get_dataset(DATASET_NAME)
    result = dataset.run_experiment(
        name=EXPERIMENT_NAME,
        task=task,
        evaluators=_evaluators(),
        run_evaluators=[_pass_rates],
    )
    print(result.format())

    rate = _groundedness_rate(result)
    print(f"\nmemo-groundedness pass-rate: {rate:.2f} (threshold {GROUNDEDNESS_THRESHOLD})")
    if rate < GROUNDEDNESS_THRESHOLD:
        print("REGRESSION: groundedness below threshold", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
