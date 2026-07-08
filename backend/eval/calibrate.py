"""Calibrate the LLM judges against hand-labelled examples (simple-accuracy mode).

Runs each judge over the labelled fixture and reports, per judge: valid rows,
invalid-label count, and accuracy vs the human label. Follow the judge-calibration
guide: extend fixtures/memo_labeled.json with ~5-10 labelled examples per judge and
record the resulting accuracy in your deliverable before trusting the judge for
gating (Phase 4).

Usage (from backend/, with a judge LLM key set, e.g. UNI_GPT_API_KEY):
    python -m eval.calibrate
"""

import json
from collections import defaultdict
from pathlib import Path

from eval.judges import groundedness_evaluation, bilingual_evaluation

_FIXTURE = Path(__file__).with_name("fixtures") / "memo_labeled.json"


def _run_case(case: dict):
    judge = case["judge"]
    if judge == "memo-groundedness":
        return groundedness_evaluation(case["memo_english"], case["grounding"]).value
    if judge == "memo-bilingual-complete":
        return bilingual_evaluation(case["memo_english"], case["memo_german"]).value
    raise ValueError(f"unknown judge {judge!r}")


def main() -> int:
    cases = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    per_judge = defaultdict(lambda: {"valid": 0, "invalid": 0, "correct": 0})

    for case in cases:
        actual = _run_case(case)
        stats = per_judge[case["judge"]]
        if actual is None:  # judge could not produce a valid label
            stats["invalid"] += 1
            continue
        stats["valid"] += 1
        if int(actual) == int(case["expected"]):
            stats["correct"] += 1

    print("Judge calibration (simple accuracy)\n" + "=" * 36)
    for judge, s in per_judge.items():
        acc = s["correct"] / s["valid"] if s["valid"] else float("nan")
        print(f"{judge}: accuracy={acc:.2f}  (valid={s['valid']}, invalid={s['invalid']})")
    print("\nExtend fixtures/memo_labeled.json to ~5-10 labels/judge before gating.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
