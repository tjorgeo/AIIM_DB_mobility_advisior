"""Seed the Langfuse `recommendation-comparison` dataset from the seed personas.

For each fixed persona we store the raw ``load_context`` payload as the dataset item
input — the same data both pipelines consume, so the comparison experiment
(scripts/run_comparison.py) can run the baseline (one LLM call) and the deterministic
engine over stored context without touching the database. The item's ``expected_output``
is the deterministic engine's normalized recommendations, which serve as the ground truth
the baseline is scored against (its per-category action uses the same vocabulary).

Usage (from backend/, with DATABASE_URL + LANGFUSE_* set):
    python scripts/seed_comparison_dataset.py                                # 4 personas
    python scripts/seed_comparison_dataset.py --dataset dummy-users --personas all
"""

import argparse
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

# All ten seed personas, in database/seed/PERSONAS.md order. 1-5 were the original
# dataset; 6-10 were added to cover the decision paths the first five left untested
# (BahnCard-only commuter, too-little-data user, 1st class, mobility constraint,
# a subscription in every category).
ALL_PERSONAS = {
    "ce92d8e0-065e-589b-a60e-c692ef2d2ff9": "Julia Berger",
    "e1eb9483-d268-57cf-9b5f-0ef5e1a7fed2": "Jonas Keller",
    "725be174-ba53-516d-8beb-a4056cbac517": "Simone Wagner",
    "932d3626-708a-596b-a1fc-99c2fa1ce9b3": "Elif Yildiz",
    "c0533b37-8d16-5c9a-b16c-8cdbac66ee7e": "Maja Hoffmann",
    "9a9617f8-5780-5004-8b72-c5bd6a52536c": "Michael Voss",
    "fcbeb8f0-20fe-5070-89ed-b6024b6f8abe": "Vera Neumann",
    "7455f3a7-6592-5612-b69a-bdf133597f75": "Claudia Herrmann",
    "9ef16060-525f-5a42-a9a5-0ad99d95d204": "Sabine Krüger",
    "5f6d733a-2132-5cb8-9dec-ddb5420df922": "Jan Albrecht",
}

# The four personas the original comparison dataset was built from.
ORIGINAL_PERSONAS = dict(list(ALL_PERSONAS.items())[:4])

PERSONA_SETS = {"original": ORIGINAL_PERSONAS, "all": ALL_PERSONAS}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dataset", default=DATASET_NAME, help="Langfuse dataset name")
    parser.add_argument(
        "--personas", choices=sorted(PERSONA_SETS), default="original",
        help="which seed personas to include (default: the original four)",
    )
    parser.add_argument("--description", help="dataset description (default: derived)")
    args = parser.parse_args()

    personas = PERSONA_SETS[args.personas]
    description = args.description or (
        f"{len(personas)} seed personas — raw context input + deterministic ground-truth "
        "recommendations, for the baseline-vs-main comparison experiment."
    )

    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        print("LANGFUSE_* not set — aborting.", file=sys.stderr)
        return 1
    if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

    from langfuse import get_client
    from agent.context import load_context
    from eval.normalize import analyze_context, normalize_main, cost_table_from_analysis

    client = get_client()
    client.create_dataset(name=args.dataset, description=description)

    seeded = 0
    for user_id, name in personas.items():
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
            dataset_name=args.dataset,
            # Deterministic id → re-running upserts instead of duplicating. Item ids are
            # unique per *project*, not per dataset, so every dataset but the original
            # namespaces them; `recommendation-comparison` keeps its bare user_ids so
            # re-seeding it still upserts the items it already has.
            id=user_id if args.dataset == DATASET_NAME else f"{args.dataset}:{user_id}",
            input=ctx,
            expected_output=normalize_main(analyst_out),
            metadata={"user_id": user_id, "name": name},
        )
        seeded += 1
        print(f"✓ dataset item for {name}")

    client.flush()
    print(f"Done. Dataset '{args.dataset}' seeded with {seeded} personas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
