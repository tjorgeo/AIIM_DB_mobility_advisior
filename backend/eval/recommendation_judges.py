"""Evaluators for the baseline-vs-main recommendation comparison.

Each experiment task returns ``{"pipeline", "recommendations", ...}`` where
``recommendations`` is the common per-category schema from :mod:`eval.normalize`. These
evaluators match the Langfuse signature ``(*, input, output, expected_output, metadata,
**_) -> Evaluation`` (same as :mod:`eval.judges`). ``input`` is the dataset item's raw
``load_context`` payload; ``expected_output`` is the deterministic engine's normalized
recommendations (the ground truth).

Four are deterministic code checks; ``recommendation_soundness_evaluator`` is an LLM
judge that reuses the judge client + JSON helpers from :mod:`eval.judges`.
"""

import json

from langfuse import Evaluation


def _recs(output) -> list:
    """The normalized recommendation list from a task output (defensive against None)."""
    if isinstance(output, dict):
        recs = output.get("recommendations")
        if isinstance(recs, list):
            return recs
    return []


# --- Deterministic code evaluators -------------------------------------------


def plan_in_catalog_evaluator(*, input=None, output=None, expected_output=None, metadata=None, **_):
    """`plan-in-catalog` — every recommended target plan (`to`) must exist by exact
    name in the pricing catalog. Catches plans a bare LLM invents."""
    catalog = {
        c.get("name")
        for c in ((input or {}).get("pricing_catalog") or [])
        if c.get("name")
    }
    offending = [r.get("to") for r in _recs(output) if r.get("to") and r.get("to") not in catalog]
    ok = not offending
    return Evaluation(
        name="plan-in-catalog",
        value=int(ok),
        data_type="BOOLEAN",
        comment="all target plans in catalog" if ok else f"not in catalog: {offending[0]}",
    )


def action_in_vocabulary_evaluator(*, input=None, output=None, expected_output=None, metadata=None, **_):
    """`action-in-vocabulary` — every action must be in the shared VALID_ACTIONS set."""
    from agent.baseline_pipeline import VALID_ACTIONS

    offending = sorted(
        {r.get("action") for r in _recs(output) if r.get("action") not in VALID_ACTIONS}
    )
    ok = not offending
    return Evaluation(
        name="action-in-vocabulary",
        value=int(ok),
        data_type="BOOLEAN",
        comment="all actions valid" if ok else f"invalid actions: {offending}",
    )


def savings_non_negative_evaluator(*, input=None, output=None, expected_output=None, metadata=None, **_):
    """`savings-non-negative` — no recommendation may claim a negative annual saving."""
    offending = [
        r for r in _recs(output)
        if isinstance(r.get("annual_savings_eur"), (int, float)) and r["annual_savings_eur"] < 0
    ]
    ok = not offending
    return Evaluation(
        name="savings-non-negative",
        value=int(ok),
        data_type="BOOLEAN",
        comment="all savings >= 0" if ok else f"{len(offending)} negative saving(s)",
    )


def category_agreement_evaluator(*, input=None, output=None, expected_output=None, metadata=None, **_):
    """`category-agreement` (NUMERIC 0-1) — fraction of ground-truth categories whose
    action matches the deterministic recommendation. The headline closeness metric; the
    main arm scores 1.0 by construction (it *is* the ground truth)."""
    expected = {
        e.get("category"): e.get("action")
        for e in (expected_output or [])
        if e.get("category")
    }
    actual = {r.get("category"): r.get("action") for r in _recs(output) if r.get("category")}

    if not expected:
        return Evaluation(
            name="category-agreement", value=1.0, data_type="NUMERIC",
            comment="no ground-truth categories",
        )

    matches, mismatches = 0, []
    for cat, exp_action in expected.items():
        if actual.get(cat) == exp_action:
            matches += 1
        else:
            mismatches.append(f"{cat} (expected {exp_action}, got {actual.get(cat)})")

    rate = matches / len(expected)
    comment = f"{matches}/{len(expected)} categories agree"
    if mismatches:
        comment += "; mismatch: " + mismatches[0]
    return Evaluation(name="category-agreement", value=rate, data_type="NUMERIC", comment=comment)


# --- LLM judge ---------------------------------------------------------------

_SOUNDNESS_PROMPT = """You are a strict evaluator of mobility subscription recommendations.

You are given COST_TABLE (per travel category: annual trips, currently-held plans, the \
annual cost of the current setup, the annual pay-as-you-go cost, and the cheapest catalog \
alternative with its annual cost) and RECOMMENDATIONS (per-category portfolio changes, each \
with an action, the plan(s) it moves from/to, an estimated annual saving, and optional \
reasoning).

Decide whether ALL recommendations are sound given the COST_TABLE:
- the action picks the genuinely cheapest option for that category (keep current only when \
it is cheapest; cancel/switch only when it actually costs less; do not add a plan that \
costs more than paying as you go);
- the stated annual saving is consistent with the COST_TABLE and non-negative;
- any plan named in `to` appears in the COST_TABLE (as a held plan or the cheapest \
alternative);
- if reasoning is given, it must not contradict the COST_TABLE figures.

If every recommendation passes, it is sound. If any one fails, it is NOT sound.

Respond with STRICT JSON and nothing else:
{"sound": true|false, "reason": "<one sentence, cite the first offending category if any>"}
"""


def recommendation_soundness_evaluator(*, input=None, output=None, expected_output=None, metadata=None, **_):
    """`recommendation-soundness` (BOOLEAN, LLM judge) — are the recommendations sound
    given the deterministic per-category cost table? Reads the compact cost table embedded
    in the dataset item at seed time (``_deterministic_cost_table``) so the judge prompt
    stays small and fast. Reuses the judge client and JSON helpers from :mod:`eval.judges`;
    returns ``value=None`` on judge failure so the row is marked invalid rather than failed
    (same convention as the memo judges)."""
    from eval.judges import _judge

    cost_table = (input or {}).get("_deterministic_cost_table") or []
    payload = (
        "COST_TABLE:\n"
        + json.dumps(cost_table, ensure_ascii=False, default=str)
        + "\n\nRECOMMENDATIONS:\n"
        + json.dumps(_recs(output), ensure_ascii=False, default=str)
    )
    verdict, reason = _judge(_SOUNDNESS_PROMPT, payload, "sound")
    return Evaluation(
        name="recommendation-soundness",
        value=None if verdict is None else int(verdict),
        data_type="BOOLEAN",
        comment=reason,
    )


def all_evaluators() -> list:
    """The evaluator list shared by both experiment arms."""
    return [
        plan_in_catalog_evaluator,
        action_in_vocabulary_evaluator,
        savings_non_negative_evaluator,
        category_agreement_evaluator,
        recommendation_soundness_evaluator,
    ]
