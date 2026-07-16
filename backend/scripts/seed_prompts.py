"""Seed the Langfuse-managed prompts from the local prompt files.

Run once (and again whenever you want to push the local .md text as a new
version) to create/update the `analyst-memo` and `advisor-chat` prompts in
Langfuse with the `production` label. After seeding, iterate on the prompts in
the Langfuse UI — the app fetches the `production` label at runtime, so changes
take effect without a redeploy. The local .md files remain the offline fallback.

Usage:
    # from backend/ with LANGFUSE_* env vars set (see .env.example)
    python scripts/seed_prompts.py

Requires: LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY, LANGFUSE_BASE_URL/HOST.
"""

import os
import sys
from pathlib import Path

# Allow importing nothing from the app — this script only needs the SDK.
PROMPTS_DIR = Path(__file__).resolve().parent.parent / "src" / "agent" / "prompts"

# name -> (source file, type). Both are single system-prompt templates: the
# analyst-memo has no variables (grounding data is passed in the human message; kept for
# the eval memo-comparison experiment); the advisor uses {{context}} (filled from the
# session snapshot).
PROMPTS = {
    "analyst-memo": ("analyst_system.md", "text"),
    "advisor-chat": ("advisor_system.md", "text"),
}


def main() -> int:
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        print("LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY not set — aborting.", file=sys.stderr)
        return 1
    if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
        os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

    from langfuse import get_client

    client = get_client()
    for name, (filename, ptype) in PROMPTS.items():
        text = (PROMPTS_DIR / filename).read_text(encoding="utf-8")
        client.create_prompt(
            name=name,
            prompt=text,
            type=ptype,
            labels=["production"],
            commit_message=f"Seed from {filename}",
        )
        print(f"✓ seeded prompt '{name}' (production) from {filename}")

    client.flush()
    print("Done. Edit these prompts in the Langfuse UI to iterate without a redeploy.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
