"""Seed the Langfuse `recommendation-comparison` dataset from the seed personas.

For each fixed persona we store the raw ``load_context`` payload as the dataset item
input — the same data both pipelines consume, so the comparison experiment
(scripts/run_comparison.py) can run the baseline (one LLM call) and the deterministic
engine over stored context without touching the database. The item's ``expected_output``
is the deterministic engine's normalized recommendations, which serve as the ground truth
the baseline is scored against (its per-category action uses the same vocabulary).

Usage (from backend/, with DATABASE_URL + LANGFUSE_* set):
    python scripts/seed_comparison_dataset.py
"""

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))  # agent.*
sys.path.insert(0, str(_BACKEND))          # eval.*

# Load repo-root .env when run standalone (docker-compose injects it for the app).
try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND.parent / ".env")
except ImportError:
    pass

DATASET_NAME = "recommendation-comparison"

# The four seed personas with travel data (see main.py::test_analyst docstring).
PERSONAS = {
    "ce92d8e0-065e-589b-a60e-c692ef2d2ff9": "Julia Berger",
    "e1eb9483-d268-57cf-9b5f-0ef5e1a7fed2": "Jonas Keller",
    "725be174-ba53-516d-8beb-a4056cbac517": "Simone Wagner",
    "932d3626-708a-596b-a1fc-99c2fa1ce9b3": "Elif Yildiz",
}


def main() -> int:
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        print("LANGFUSE_* not set — aborting.", file=sys.stderr)
        return 1
    if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

    from langfuse import get_client
    from agent.context import load_context
    from eval.normalize import analyze_context, normalize_main, cost_table_from_analysis

    client = get_client()
    client.create_dataset(
        name=DATASET_NAME,
        description="Four seed personas — raw context input + deterministic ground-truth "
        "recommendations, for the baseline-vs-main comparison experiment.",
    )

    seeded = 0
    for user_id, name in PERSONAS.items():
        ctx = load_context(user_id)
        if ctx.get("error"):
            print(f"! skipping {name} ({user_id}): {ctx['error']}", file=sys.stderr)
            continue
        # One deterministic engine run: its normalized output is the ground truth, and its
        # compact cost table is embedded in the stored context so the LLM soundness judge
        # has a small priced reference instead of the full leg history.
        analyst_out = analyze_context(ctx)
        ctx["_deterministic_cost_table"] = cost_table_from_analysis(analyst_out)
        client.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=user_id,  # deterministic id → re-running upserts instead of duplicating
            input=ctx,
            expected_output=normalize_main(analyst_out),
            metadata={"user_id": user_id, "name": name},
        )
        seeded += 1
        print(f"✓ dataset item for {name}")

    client.flush()
    print(f"Done. Dataset '{DATASET_NAME}' seeded with {seeded} personas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
