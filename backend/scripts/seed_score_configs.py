"""Create the Langfuse score configs for the recommendation-comparison scores.

Score configs define each score's type (and numeric range) so the Langfuse UI renders and
validates them consistently across the baseline and main experiment runs. The scores work
without configs, but the configs make the comparison dashboards well-typed.

Idempotent: the API has no upsert for configs, so existing names (matched case-sensitively)
are skipped rather than duplicated.

Usage (from backend/, with LANGFUSE_* set):
    python scripts/seed_score_configs.py
"""

import os
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))

try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND.parent / ".env")
except ImportError:
    pass

# (name, data_type, min_value, max_value). NUMERIC gets a 0-1 range; BOOLEAN ignores range.
CONFIGS = [
    ("plan-in-catalog", "BOOLEAN", None, None),
    ("action-in-vocabulary", "BOOLEAN", None, None),
    ("savings-non-negative", "BOOLEAN", None, None),
    ("category-agreement", "NUMERIC", 0, 1),
    ("recommendation-soundness", "BOOLEAN", None, None),
]

_DESCRIPTIONS = {
    "plan-in-catalog": "1 if every recommended target plan exists in the pricing catalog.",
    "action-in-vocabulary": "1 if every action is in the shared recommendation vocabulary.",
    "savings-non-negative": "1 if no recommendation claims a negative annual saving.",
    "category-agreement": "Fraction of ground-truth categories whose action matches the "
    "deterministic pipeline (1.0 = full agreement).",
    "recommendation-soundness": "LLM judge: 1 if all recommendations are sound and grounded "
    "in the raw data.",
}


def main() -> int:
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        print("LANGFUSE_* not set — aborting.", file=sys.stderr)
        return 1
    if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

    from langfuse import get_client

    client = get_client()
    existing = {c.name for c in client.api.score_configs.get().data}

    for name, data_type, min_value, max_value in CONFIGS:
        if name in existing:
            print(f"= score config '{name}' already exists — skipping")
            continue
        client.api.score_configs.create(
            name=name,
            data_type=data_type,
            min_value=min_value,
            max_value=max_value,
            description=_DESCRIPTIONS.get(name),
        )
        print(f"✓ created score config '{name}' ({data_type})")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
