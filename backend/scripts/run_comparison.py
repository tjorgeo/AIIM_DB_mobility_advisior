"""Compare the baseline and main pipelines' recommendations over one dataset.

Runs two experiment runs on the `recommendation-comparison` dataset — one per pipeline —
sharing the same evaluators, so Langfuse shows them side-by-side:

* ``baseline`` — the single-LLM-call baseline (``run_baseline_from_context``) on each
  item's stored raw context.
* ``main`` — the deterministic engine's recommendations, echoed from the item's
  ``expected_output`` (computed fresh from the DB at seed time; re-running the engine here
  would fault on JSON-round-tripped dates). This arm is the ground-truth ceiling.

Both arms are scored by ``eval.recommendation_judges``: four deterministic code checks plus
one LLM soundness judge. Run-level aggregates (pass-rate for boolean scores, mean for the
numeric agreement score) are printed as a combined baseline-vs-main table.

This is a comparison, not a regression gate — it does not fail CI. ``--assert-main-agreement``
adds a smoke check that the main arm scores perfect agreement (it should, by construction).

Env: UNI_GPT_API_KEY (baseline + judge), LANGFUSE_* (dataset + tracing).
Usage (from backend/):
    python scripts/run_comparison.py
    python scripts/run_comparison.py --assert-main-agreement
"""

import argparse
import os
import sys
from collections import defaultdict
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))  # agent.*
sys.path.insert(0, str(_BACKEND))          # eval.*

try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND.parent / ".env")
except ImportError:
    pass

if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

DATASET_NAME = "recommendation-comparison"

# Scores aggregated as a mean rather than a pass-rate (all others are BOOLEAN 0/1).
_NUMERIC_SCORES = {"category-agreement"}


# --- Tasks (one per pipeline arm) --------------------------------------------


def baseline_task(*, item, **_):
    """Run the baseline (one LLM call) over the item's stored raw context."""
    from agent.baseline_pipeline import run_baseline_from_context
    from eval.normalize import normalize_baseline

    res = run_baseline_from_context(item.input, user_id=(item.metadata or {}).get("user_id"))
    return {"pipeline": "baseline", "recommendations": normalize_baseline(res), "raw": res}


def main_task(*, item, **_):
    """Echo the deterministic ground truth stored as the item's expected_output."""
    return {"pipeline": "main", "recommendations": item.expected_output or []}


# --- Run-level aggregation ---------------------------------------------------


def _aggregate(*, item_results, **_):
    """Aggregate each item-level score into a run-level number: mean for numeric scores
    (suffix ``-mean``), pass-rate for boolean scores (suffix ``-pass-rate``). Rows whose
    judge returned None (invalid) are skipped."""
    from langfuse import Evaluation

    agg = defaultdict(list)
    for r in item_results:
        for e in r.evaluations:
            if e.value is not None:
                agg[e.name].append(float(e.value))

    out = []
    for name, vals in agg.items():
        mean = sum(vals) / len(vals) if vals else 0.0
        if name in _NUMERIC_SCORES:
            out.append(Evaluation(name=f"{name}-mean", value=mean,
                                   comment=f"mean over {len(vals)} items"))
        else:
            out.append(Evaluation(name=f"{name}-pass-rate", value=mean,
                                  comment=f"{int(round(sum(vals)))}/{len(vals)} passed"))
    return out


def _run_evaluations(result) -> dict:
    """{name: value} of a run's run-level evaluations."""
    return {e.name: float(e.value) for e in result.run_evaluations}


def _print_comparison(scores_by_arm: dict) -> None:
    """Combined baseline-vs-main table over the union of run-level score names."""
    names = sorted({n for arm in scores_by_arm.values() for n in arm})
    arms = list(scores_by_arm.keys())
    width = max((len(n) for n in names), default=10) + 2

    print("\n" + "=" * (width + 12 * len(arms)))
    print("Baseline vs main — run-level scores")
    print("=" * (width + 12 * len(arms)))
    header = "score".ljust(width) + "".join(a.ljust(12) for a in arms)
    print(header)
    print("-" * len(header))
    for name in names:
        row = name.ljust(width)
        for arm in arms:
            val = scores_by_arm[arm].get(name)
            row += ("—".ljust(12) if val is None else f"{val:.2f}".ljust(12))
        print(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--assert-main-agreement", action="store_true",
        help="exit non-zero if the main arm's category-agreement-mean is not 1.0 (smoke check)",
    )
    args = parser.parse_args()

    from agent.llm import llm_available

    if not llm_available():
        print("UNI_GPT_API_KEY not set — the comparison needs the baseline + judge LLM.",
              file=sys.stderr)
        return 1

    from langfuse import get_client
    from eval.recommendation_judges import all_evaluators

    scores_by_arm = {}
    try:
        client = get_client()
        dataset = client.get_dataset(DATASET_NAME)
        evaluators = all_evaluators()

        for arm, task in (("baseline", baseline_task), ("main", main_task)):
            print(f"\n### Running '{arm}' arm ...", file=sys.stderr)
            result = dataset.run_experiment(
                name=f"{DATASET_NAME}-{arm}",
                task=task,
                evaluators=evaluators,
                run_evaluators=[_aggregate],
            )
            print(result.format())
            scores_by_arm[arm] = _run_evaluations(result)
    finally:
        from agent.observability import flush

        flush()

    _print_comparison(scores_by_arm)

    if args.assert_main_agreement:
        main_agreement = scores_by_arm.get("main", {}).get("category-agreement-mean", 0.0)
        if main_agreement < 1.0:
            print(f"\nSMOKE CHECK FAILED: main category-agreement-mean = {main_agreement:.2f} "
                  "(expected 1.0)", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
