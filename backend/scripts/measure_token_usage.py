"""Measure real token usage per run for both pipelines, from Langfuse traces.

Runs the main pipeline (``agent.pipeline.run_analysis``) over the seed personas, then
reads the resulting ``analyze-pipeline`` traces back out of Langfuse and reports
measured input/output tokens per persona and per LLM step. Optionally does the same for
the baseline's ``baseline-recommendation`` traces, so the report's token/cost table can
quote measured numbers instead of offline character-count estimates.

Both pipelines must actually be traced for this to work: the main pipeline's two LLM
steps (``forecast-reasoner``, ``feasibility-judge``) get their callback config from
``agent.observability.llm_config``, and ``run_analysis`` opens the enclosing
``analyze-pipeline`` trace they nest under.

Note on cost: the university endpoint's model has no price configured in Langfuse, so
``total_cost`` comes back 0.0. Tokens are measured; euro cost is not available and has
to be derived externally if needed.

Env: DATABASE_URL, UNI_GPT_API_KEY, LANGFUSE_*.
Usage (from backend/):
    python scripts/measure_token_usage.py                  # main pipeline only
    python scripts/measure_token_usage.py --include-baseline
    python scripts/measure_token_usage.py --no-run         # only read back existing traces
"""

import argparse
import sys
import time
from collections import defaultdict
from pathlib import Path

_BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BACKEND / "src"))  # agent.*
sys.path.insert(0, str(_BACKEND))          # eval.*, scripts.*

try:
    from dotenv import load_dotenv

    load_dotenv(_BACKEND.parent / ".env")
except ImportError:
    pass

import os

if not os.getenv("LANGFUSE_HOST") and os.getenv("LANGFUSE_BASE_URL"):
    os.environ["LANGFUSE_HOST"] = os.environ["LANGFUSE_BASE_URL"]

# Langfuse ingestion is asynchronous; give it a moment before reading traces back.
_INGEST_WAIT_S = 10
_REQ = {"timeout_in_seconds": 300}


def _trace_tokens(client, trace_id) -> dict:
    """{observation_name: (input, output)} for every GENERATION on a trace."""
    t = client.api.trace.get(trace_id, request_options=_REQ)
    out = {}
    for o in t.observations:
        if o.type != "GENERATION":
            continue
        u = o.usage
        out[o.name or "?"] = (u.input or 0, u.output or 0)
    return out


def _print_latency(trace_lat: dict, wall: dict) -> None:
    """Per-persona latency, from two clocks.

    `trace` is the Langfuse `analyze-pipeline` span, which covers the pipeline itself
    (engines plus the one or two LLM steps) and is the figure directly comparable with
    the baseline's `baseline-recommendation` span. `wall` additionally includes
    `load_context`, i.e. what a caller of `run_analysis` actually waits for.
    """
    names = sorted(set(trace_lat) | set(wall))
    if not names:
        return
    print(f"\n{'=' * 60}\nMain pipeline — latency per analysis run\n{'=' * 60}")
    print(f"{'persona':20s}{'trace (s)':>14s}{'wall (s)':>14s}")
    print("-" * 48)
    for n in names:
        t = trace_lat.get(n)
        w = wall.get(n)
        print(f"{n:20s}{(f'{t:.1f}' if t else '-'):>14s}{(f'{w:.1f}' if w else '-'):>14s}")

    def _stats(label, d):
        vals = sorted(d.values())
        if not vals:
            return
        n = len(vals)
        median = vals[n // 2] if n % 2 else (vals[n // 2 - 1] + vals[n // 2]) / 2
        print(f"  {label:12s} n={n:2d}  median={median:6.1f}s  "
              f"mean={sum(vals) / n:6.1f}s  min={vals[0]:.1f}s  max={vals[-1]:.1f}s")

    print("-" * 48)
    _stats("trace", trace_lat)
    _stats("wall", wall)


def _print_table(title: str, rows: list, steps: list) -> None:
    """rows: [(persona, {step: (in, out)})]"""
    print(f"\n{'=' * 78}\n{title}\n{'=' * 78}")
    header = f"{'persona':20s}" + "".join(f"{s[:18]:>20s}" for s in steps) + f"{'total':>12s}"
    print(header)
    print("-" * len(header))
    grand = []
    for name, per_step in rows:
        line = f"{name:20s}"
        total = 0
        for s in steps:
            i, o = per_step.get(s, (0, 0))
            line += f"{(str(i) + '/' + str(o)):>20s}"
            total += i + o
        grand.append(total)
        print(line + f"{total:>12d}")
    if grand:
        print("-" * len(header))
        print(f"{'MEAN':20s}" + "".join(" " * 20 for _ in steps) + f"{sum(grand) // len(grand):>12d}")
        print(f"{'MIN / MAX':20s}" + "".join(" " * 20 for _ in steps)
              + f"{str(min(grand)) + '/' + str(max(grand)):>12s}")
    print("\n(cells are input/output tokens per LLM step)")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--include-baseline", action="store_true",
                        help="also report the baseline's traces (run scripts/run_comparison.py first)")
    parser.add_argument("--baseline-dataset", default="dummy-users",
                        help="dataset whose baseline experiment run to read (default: dummy-users)")
    parser.add_argument("--baseline-run", default="dummy-set-baseline-baseline",
                        help="name prefix of the baseline dataset run to read")
    parser.add_argument("--no-run", action="store_true",
                        help="skip running the pipeline; only read back existing traces")
    args = parser.parse_args()

    from langfuse import get_client
    from agent.observability import flush
    from scripts.seed_comparison_dataset import ALL_PERSONAS

    client = get_client()

    wall = {}
    run_start = None
    if not args.no_run:
        from datetime import datetime, timezone

        from agent.pipeline import run_analysis

        # Traces older than this belong to a previous run. Without the cut-off, a trace
        # that has not finished ingesting yet silently resolves to the *last* run's
        # trace for that persona, mixing two runs in one table.
        run_start = datetime.now(timezone.utc)

        for user_id, name in ALL_PERSONAS.items():
            print(f"-> {name} ...", file=sys.stderr)
            t0 = time.perf_counter()
            out = run_analysis(user_id)
            elapsed = time.perf_counter() - t0
            if out.get("error"):
                print(f"! {name}: {out['error']}", file=sys.stderr)
                continue
            wall[user_id] = elapsed
            print(f"   {elapsed:6.1f}s", file=sys.stderr)
        flush()
        print(f"Waiting {_INGEST_WAIT_S}s for Langfuse ingestion ...", file=sys.stderr)
        time.sleep(_INGEST_WAIT_S)

    # Read back the most recent analyze-pipeline trace per persona, restricted to this
    # run when we just did one (see run_start above).
    res = client.api.trace.list(
        name="analyze-pipeline", limit=50, from_timestamp=run_start, request_options=_REQ
    )
    by_user = {}
    for t in res.data:  # newest first
        if t.user_id and t.user_id not in by_user:
            by_user[t.user_id] = t.id
    if run_start and len(by_user) < len(wall):
        print(f"! only {len(by_user)}/{len(wall)} traces ingested yet; the wall column "
              "is complete and authoritative, the trace column is not.", file=sys.stderr)

    rows, steps, trace_lat = [], [], {}
    for user_id, name in ALL_PERSONAS.items():
        tid = by_user.get(user_id)
        if not tid:
            print(f"! no analyze-pipeline trace for {name}", file=sys.stderr)
            continue
        per_step = _trace_tokens(client, tid)
        for s in per_step:
            if s not in steps:
                steps.append(s)
        rows.append((name, per_step))
        lat = next((t.latency for t in res.data if t.id == tid), None)
        if lat:
            trace_lat[name] = lat
    _print_table("Main pipeline — measured tokens per analysis run", rows, sorted(steps))
    _print_latency(trace_lat, {ALL_PERSONAS[u]: v for u, v in wall.items()})

    if args.include_baseline:
        # The baseline's own `trace()` opens a *span* under the experiment runner's root
        # trace, so listing traces by name finds only standalone `run_baseline.py` runs,
        # not experiment ones. Go through the dataset run's items instead.
        runs = [
            r for r in client.api.datasets.get_runs(
                dataset_name=args.baseline_dataset, request_options=_REQ
            ).data
            if r.name.startswith(args.baseline_run)
        ]
        if not runs:
            print(f"! no dataset run starting with '{args.baseline_run}' on "
                  f"'{args.baseline_dataset}'", file=sys.stderr)
            return 1
        run = client.api.datasets.get_run(
            dataset_name=args.baseline_dataset, run_name=runs[0].name, request_options=_REQ
        )
        print(f"\nBaseline run: {run.name}", file=sys.stderr)

        brows = []
        for it in run.dataset_run_items:
            # Dataset item ids are namespaced `<dataset>:<user_id>` (see seed script).
            uid = (it.dataset_item_id or "").split(":")[-1]
            per_step = _trace_tokens(client, it.trace_id)
            # Keep only the baseline generation; the runner also traces the LLM judge,
            # which is evaluation overhead rather than pipeline cost.
            per_step = {k: v for k, v in per_step.items() if "judge" not in k.lower()}
            brows.append((ALL_PERSONAS.get(uid, uid[:18]), per_step))
        bsteps = sorted({s for _, d in brows for s in d})
        _print_table("Baseline — measured tokens per run", brows, bsteps)

    # Per-step aggregate across personas, the figure the report quotes.
    agg = defaultdict(lambda: [0, 0, 0])
    for _, per_step in rows:
        for s, (i, o) in per_step.items():
            a = agg[s]
            a[0] += i
            a[1] += o
            a[2] += 1
    print("\nMain pipeline — mean per LLM step:")
    for s, (i, o, n) in sorted(agg.items()):
        print(f"  {s:22s} n={n:2d}  mean_in={i // n:6d}  mean_out={o // n:6d}  mean_total={(i + o) // n:6d}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
