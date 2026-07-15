"""Normalize both pipelines' recommendations into one comparable per-category shape.

The baseline (one LLM call, ``agent.baseline_pipeline``) and the main pipeline's
deterministic engine (``agent.engines.analyze_portfolio``) describe the same decision
in different vocabularies. Both are mapped here to a single schema so an experiment can
score them against each other:

    { "category": str,             # public_transport | long_distance_rail | ...
      "action": str,               # the shared VALID_ACTIONS vocabulary
      "from": list[str] | None,    # currently-held plan name(s)
      "to": str | None,            # recommended catalog plan (switch/consider only)
      "annual_savings_eur": float, # >= 0 expected
      "reasoning": str | None }

The deterministic engine's output doubles as the ground truth in the comparison, since
its per-category ``recommendation`` already uses the same action vocabulary as the
baseline's ``recommended_changes[*].action``.
"""

# Actions where a specific target plan is meaningful; for everything else ``to`` is None.
_ACTIONS_WITH_TARGET = {"switch_to_alternative", "consider_subscribing"}
# Actions that never carry a saving (status quo is already best, or it can't be priced).
_ZERO_SAVING_ACTIONS = {"keep_current", "no_subscription_needed", "insufficient_cost_data"}


def _as_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def normalize_baseline(result: dict) -> list[dict]:
    """Map a ``run_baseline`` result's ``recommended_changes`` into the common schema.

    Near-passthrough: the baseline prompt already emits this vocabulary; only the
    savings field is renamed and coerced. ``from`` may be a list or None as the model
    produced it.
    """
    out = []
    for change in result.get("recommended_changes") or []:
        if not isinstance(change, dict):
            continue
        frm = change.get("from")
        if isinstance(frm, str):
            frm = [frm]
        out.append(
            {
                "category": change.get("category"),
                "action": change.get("action"),
                "from": frm or None,
                "to": change.get("to"),
                "annual_savings_eur": _as_float(change.get("estimated_annual_savings_eur")),
                "reasoning": change.get("reasoning"),
            }
        )
    return out


def normalize_main(analyst_out: dict) -> list[dict]:
    """Map the deterministic engine's ``category_subscription_analysis`` into the common
    schema. The engine produces no per-change prose, so ``reasoning`` is None; the saving
    is derived from the exposed ``best_option_cost_eur`` (see analysis.py)."""
    out = []
    for entry in analyst_out.get("category_subscription_analysis") or []:
        action = entry.get("recommendation")

        held = [
            s.get("provider_plan_name")
            for s in entry.get("current_subscriptions") or []
            if s.get("provider_plan_name")
        ]

        to = None
        if action in _ACTIONS_WITH_TARGET and entry.get("cheapest_alternative"):
            to = entry["cheapest_alternative"].get("provider_plan_name")

        savings = 0.0
        actual = entry.get("actual_annual_cost_eur")
        best = entry.get("best_option_cost_eur")
        if action not in _ZERO_SAVING_ACTIONS and actual is not None and best is not None:
            savings = max(0.0, _as_float(actual) - _as_float(best))

        out.append(
            {
                "category": entry.get("category"),
                "action": action,
                "from": held or None,
                "to": to,
                "annual_savings_eur": round(savings, 2),
                "reasoning": None,
            }
        )
    return out


def cost_table_from_analysis(analyst_out: dict) -> list[dict]:
    """Compact per-category cost table for the LLM soundness judge: the priced comparison
    (current vs pay-as-you-go vs cheapest alternative) without the raw leg history. Cheap
    to serialize, so the judge gets a small, well-grounded reference instead of hundreds of
    trip legs."""
    table = []
    for entry in analyst_out.get("category_subscription_analysis") or []:
        alt = entry.get("cheapest_alternative")
        table.append(
            {
                "category": entry.get("category"),
                "annual_trips": entry.get("annual_trips"),
                "held_plans": [
                    s.get("provider_plan_name")
                    for s in entry.get("current_subscriptions") or []
                    if s.get("provider_plan_name")
                ],
                "actual_annual_cost_eur": entry.get("actual_annual_cost_eur"),
                "no_subscription_annual_cost_eur": entry.get("no_subscription_annual_cost_eur"),
                "cheapest_alternative": (
                    {
                        "name": alt.get("provider_plan_name"),
                        "annual_cost_eur": alt.get("estimated_annual_cost_eur"),
                    }
                    if alt
                    else None
                ),
            }
        )
    return table


def analyze_context(ctx: dict) -> dict:
    """Run the deterministic engine over a ``load_context`` payload and return its full
    output. Deterministic, no LLM. Imports the engine lazily so importing this module
    stays cheap."""
    from agent.engines import analyze_portfolio

    return analyze_portfolio(
        ctx["travel_history"],
        ctx["subscriptions"],
        ctx["pricing_catalog"],
        user_age=ctx["user"].get("age"),
    )


def main_recommendations_from_context(ctx: dict) -> list[dict]:
    """Convenience: the deterministic engine's normalized recommendations for a context
    (the main arm + the comparison ground truth)."""
    return normalize_main(analyze_context(ctx))
