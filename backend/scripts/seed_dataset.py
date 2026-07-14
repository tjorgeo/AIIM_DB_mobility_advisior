"""Seed the Langfuse `analyze-personas` evaluation dataset from the seed personas.

For each of the four fixed personas we run the deterministic pipeline once (no LLM
needed) and store its grounding data — the analyst output (including its per-category
current-vs-alternative-vs-no-subscription analysis) and forecaster output, plus the
pricing catalog — as the dataset item input. The experiment (scripts/run_experiment.py)
then only has to call the memo LLM on that stored grounding, so it needs no database
and can run in CI with just an LLM key.

Usage (from backend/, with DATABASE_URL + LANGFUSE_* set):
    python scripts/seed_dataset.py
"""

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))  # agent.*
sys.path.insert(0, str(_BACKEND))          # eval.* (unused here, kept consistent)

DATASET_NAME = "analyze-personas"

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
    from agent.pipeline import run_analysis

    client = get_client()
    client.create_dataset(
        name=DATASET_NAME,
        description="Four fixed seed personas — grounding data for memo-quality experiments.",
    )

    for user_id, name in PERSONAS.items():
        state = run_analysis(user_id)
        if state.get("error"):
            print(f"! skipping {name} ({user_id}): {state['error']}", file=sys.stderr)
            continue
        client.create_dataset_item(
            dataset_name=DATASET_NAME,
            id=user_id,  # deterministic id → re-running upserts instead of duplicating
            input={
                "name": name,
                "analyst_out": state["analyst_out"],
                "forecaster_out": state["forecaster_out"],
                "pricing_catalog": state["pricing_catalog"],
            },
            metadata={"user_id": user_id},
        )
        print(f"✓ dataset item for {name}")

    client.flush()
    print(f"Done. Dataset '{DATASET_NAME}' seeded with {len(PERSONAS)} personas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
