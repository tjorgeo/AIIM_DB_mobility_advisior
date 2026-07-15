"""Run the single-call LLM baseline pipeline and print/save its recommendations.

The evaluation counterpart to the main analyze pipeline: for each requested user it
runs ``agent.baseline_pipeline.run_baseline`` (one LLM call over the raw context,
no deterministic engines) and collects the recommended portfolio changes. Use the
output as the baseline side when judging the main pipeline's recommendations.

Usage (from backend/, with DATABASE_URL + UNI_GPT_API_KEY set):
    python scripts/run_baseline.py <user_id> [<user_id> ...]
    python scripts/run_baseline.py --all                 # every user in the DB
    python scripts/run_baseline.py --all --out baseline_results.json

Prints one JSON document: {"results": [<run_baseline output per user>]}. Users
that fail (missing, LLM error, unparseable reply) appear with an "error" field
instead of aborting the whole run.
"""

import argparse
import json
import sys
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))  # agent.*

# Running standalone (not via docker-compose, which injects env_file: .env), so
# load the repo-root .env ourselves before agent.llm reads UNI_GPT_API_KEY.
try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND.parent / ".env")
except ImportError:
    pass


def _all_user_ids() -> list:
    from database import get_connection

    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users ORDER BY user_id")
    ids = [dict(r)["user_id"] for r in cursor.fetchall()]
    conn.close()
    return ids


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("user_ids", nargs="*", help="user_id(s) to run the baseline for")
    parser.add_argument("--all", action="store_true", help="run for every user in the DB")
    parser.add_argument("--out", help="also write the JSON results to this file")
    parser.add_argument("--json", action="store_true", help="print the raw JSON instead of the text message")
    args = parser.parse_args()

    if bool(args.user_ids) == args.all:
        parser.error("pass either explicit user_id(s) or --all")

    from agent.baseline_pipeline import run_baseline
    from agent.llm import llm_available

    if not llm_available():
        print("UNI_GPT_API_KEY not set — the baseline requires an LLM.", file=sys.stderr)
        return 1

    user_ids = _all_user_ids() if args.all else args.user_ids

    results = []
    try:
        for user_id in user_ids:
            print(f"Running baseline for {user_id} ...", file=sys.stderr)
            try:
                results.append(run_baseline(user_id))
            except Exception as exc:  # keep going: one bad reply shouldn't kill the batch
                results.append({"pipeline": "baseline", "user_id": user_id, "error": str(exc)})
                print(f"  failed: {exc}", file=sys.stderr)
    finally:
        # This short-lived script can exit before Langfuse's background thread ships
        # the buffered baseline-recommendation traces, so drain them explicitly (no-op
        # when Langfuse is disabled). Matches scripts/seed_dataset.py + seed_prompts.py.
        from agent.observability import flush

        flush()

    doc = json.dumps({"results": results}, ensure_ascii=False, indent=2, default=str)
    if args.json:
        print(doc)
    else:
        # Default: the human-readable text message per user, blank-line separated.
        blocks = [
            r.get("message") or f"Baseline could not run: {r.get('error', 'unknown error')}"
            for r in results
        ]
        print(("\n\n" + "=" * 60 + "\n\n").join(blocks))
    if args.out:
        Path(args.out).write_text(doc, encoding="utf-8")
        print(f"Wrote {args.out}", file=sys.stderr)

    failed = sum(1 for r in results if r.get("error"))
    print(f"Done: {len(results) - failed}/{len(results)} succeeded.", file=sys.stderr)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
