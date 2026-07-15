"""Constraint-aware re-optimisation — the chat feedback loop's number engine.

Pure function, no LLM, no I/O. Re-derives the per-category keep/switch/drop verdict
under user-supplied constraints ("keep my car", "drop the BahnCard", "prefer the
Deutschlandticket", "don't offer plan X"), reusing the fully-priced ``alternatives``
list that ``analyze_portfolio`` already computed for each category. Every euro figure
therefore still comes from the deterministic analysis engine — the chat LLM only parses
the user's wish into constraints and narrates the result, it never computes money.

Mirrors the three-way comparison in ``analysis.py::_build_category_entry`` (current
setup vs. pay-as-you-go vs. cheapest priceable alternative), but over the constrained
candidate set, so a re-optimisation is consistent with a fresh analysis.

Optionally also re-derives the same constrained verdict against the forecaster's
life-event scenario (``forecaster_out``, when supplied) — the same "Looking ahead"
caveat the memo shows, just applied to the constrained re-optimisation instead of the
plain historical one. Purely informational: never changes ``chosen_annual_cost_eur`` or
``actions_required``, which stay grounded in the historical re-derivation only.

The unconstrained (no keep/drop/prefer_plans) fallback comparison uses the same
weighted cost/CO2/time score as ``analysis.py::_pick_recommendation`` (see
``engines/scoring.py``), so a re-optimisation without explicit constraints reproduces
exactly what a fresh analysis would have recommended for that category.
"""

from agent.engines.scoring import pick_best_category_option, resolve_weights


def _rederive_entry(entry: dict, constraints: dict, weights: dict) -> dict:
    """Return a shallow copy of ``entry`` with its recommendation re-derived under
    ``constraints`` plus a ``chosen_annual_cost_eur`` for the picked option."""
    category = entry["category"]
    held = bool(entry.get("current_subscriptions"))
    actual = entry["actual_annual_cost_eur"]
    payg = entry["no_subscription_annual_cost_eur"]
    alternatives = entry.get("alternatives") or []
    category_co2_kg = entry.get("annual_co2_kg")
    category_time_minutes = entry.get("annual_time_minutes")

    keep = category in set(constraints.get("keep", []))
    drop = category in set(constraints.get("drop", []))
    exclude = {n.lower() for n in constraints.get("exclude_plans", [])}
    prefer = {n.lower() for n in constraints.get("prefer_plans", [])}

    # Candidate alternatives after honouring exclusions.
    candidates = [
        a for a in alternatives
        if (a.get("provider_plan_name") or "").lower() not in exclude
    ]
    preferred = [a for a in candidates if (a.get("provider_plan_name") or "").lower() in prefer]

    revised = dict(entry)

    if held and keep:
        rec, chosen, chosen_alt = "keep_current", actual, None
    elif held and drop:
        rec, chosen, chosen_alt = "cancel_current_go_pay_as_you_go", payg, None
    elif preferred:
        # The user explicitly asked for one of these plans — honour it even if it isn't
        # the strict cost winner (it's their stated wish). Pick the cheapest that matches.
        chosen_alt = min(preferred, key=lambda a: a["estimated_annual_cost_eur"])
        chosen = chosen_alt["estimated_annual_cost_eur"]
        rec = "switch_to_alternative" if held else "consider_subscribing"
    else:
        # Same weighted cost/CO2/time comparison analysis.py's _pick_recommendation
        # uses (see engines/scoring.py), over the constrained candidate set.
        current = (
            {
                "annual_cost_eur": actual,
                "annual_co2_kg": category_co2_kg,
                "annual_time_minutes": category_time_minutes,
            }
            if actual is not None else None
        )
        no_subscription = (
            {
                "annual_cost_eur": payg,
                "annual_co2_kg": category_co2_kg,
                "annual_time_minutes": category_time_minutes,
            }
            if payg is not None else None
        )
        scored_candidates = [
            {
                "annual_cost_eur": a["estimated_annual_cost_eur"],
                "annual_co2_kg": category_co2_kg,
                "annual_time_minutes": category_time_minutes,
                "_ref": a,
            }
            for a in candidates
        ]
        result = pick_best_category_option(current, no_subscription, scored_candidates, held, weights)
        rec = result["recommendation"]
        chosen = result["best_cost"]
        chosen_alt = result["winning_alternative"]

    revised["recommendation"] = rec
    revised["chosen_annual_cost_eur"] = round(chosen, 2) if chosen is not None else None
    revised["chosen_alternative"] = chosen_alt
    return revised


def _life_event_scenario(forecaster_out: dict | None) -> dict | None:
    """The forecast scenario worth re-deriving the constrained verdict against: the
    life-event scenario, when one was detected. Mirrors ``memo.py``'s
    ``_forecast_caveat_scenario`` — per forecasting.py's own rules, a baseline scenario
    is always first and a second scenario is only ever added when
    ``uncertainty_flags.life_event_detected`` is true, so the last scenario is that one.
    """
    if not forecaster_out:
        return None
    if not (forecaster_out.get("uncertainty_flags") or {}).get("life_event_detected"):
        return None
    scenarios = forecaster_out.get("scenarios") or []
    return scenarios[-1] if len(scenarios) > 1 else None


def reoptimize_from_analysis(
    category_analysis: list, constraints: dict | None = None, forecaster_out: dict | None = None,
    weights: dict | None = None,
) -> dict:
    """Re-derive every category's verdict under ``constraints`` and roll up the totals.

    ``category_analysis`` is ``analyst_out["category_subscription_analysis"]`` (each entry
    already carries the priced ``alternatives``, ``actual_annual_cost_eur`` and
    ``no_subscription_annual_cost_eur``). ``constraints`` keys (all optional):

    * ``keep``          — category names whose current subscription must be kept
    * ``drop``          — category names whose current subscription must be cancelled
    * ``exclude_plans`` — plan names never to propose as an alternative
    * ``prefer_plans``  — plan names to choose where available, even if not the cheapest

    ``weights`` (optional) is a ``{"cost", "co2", "time"}`` dict from
    ``scoring.resolve_weights`` — the same weighting the original analysis used, so a
    re-optimisation without explicit keep/drop/prefer constraints is consistent with
    it. Defaults to an equal three-way split when omitted (neutral, cost-dominated in
    practice — see scoring.py).

    ``forecaster_out`` (optional) adds a ``forecast_note`` to any category whose
    constrained verdict would differ under the life-event forecast scenario's own
    ``projected_category_analysis`` (same category-comparison shape as
    ``category_analysis``, so ``_rederive_entry`` applies unchanged) — purely
    informational, see module docstring.
    """
    constraints = constraints or {}
    weights = weights or resolve_weights(None, None, None)
    revised_entries = [_rederive_entry(e, constraints, weights) for e in category_analysis]

    scenario = _life_event_scenario(forecaster_out)
    if scenario:
        life_event_type = ((forecaster_out or {}).get("uncertainty_flags") or {}).get("life_event_type")
        projected_by_category = {
            e["category"]: e for e in scenario.get("projected_category_analysis", [])
        }
        for revised in revised_entries:
            projected_entry = projected_by_category.get(revised["category"])
            if (
                not projected_entry
                or projected_entry.get("incomplete_cost_basis")
                or projected_entry["recommendation"] == "insufficient_cost_data"
            ):
                continue
            try:
                projected_revised = _rederive_entry(projected_entry, constraints, weights)
            except Exception:
                # actual_annual_cost_eur can legitimately be None on a projected entry
                # whose held plan needs duration data the forecast doesn't have (e.g. a
                # metered car-sharing plan) — best-effort, skip this category's note
                # rather than let one unpriceable category break the whole response.
                continue
            if projected_revised["recommendation"] != revised["recommendation"]:
                revised["forecast_note"] = {
                    # The life event as detected from the calendar (e.g. "relocation"),
                    # not the forecaster's internal scenario label (e.g.
                    # "post_relocation") — the chat LLM narrates this to the customer,
                    # who should read about their calendar, not internal naming.
                    "life_event_type": life_event_type,
                    "recommendation": projected_revised["recommendation"],
                    "chosen_annual_cost_eur": projected_revised["chosen_annual_cost_eur"],
                    "chosen_alternative": projected_revised.get("chosen_alternative"),
                }

    baseline_total = round(sum(e["actual_annual_cost_eur"] for e in category_analysis), 2)
    revised_total = round(sum(e["chosen_annual_cost_eur"] for e in revised_entries), 2)

    actions_required = []
    for e in revised_entries:
        rec = e["recommendation"]
        if rec in ("switch_to_alternative", "cancel_current_go_pay_as_you_go", "consider_subscribing"):
            current_names = " + ".join(
                c["provider_plan_name"] for c in e.get("current_subscriptions", [])
                if c.get("provider_plan_name")
            )
            alt = e.get("chosen_alternative")
            actions_required.append({
                "category": e["category"],
                "action": rec,
                "from": current_names or None,
                "to": alt["provider_plan_name"] if alt else None,
                "estimated_annual_savings_eur": round(
                    e["actual_annual_cost_eur"] - e["chosen_annual_cost_eur"], 2
                ),
            })

    return {
        "category_subscription_analysis": revised_entries,
        "total_actual_annual_cost_eur": baseline_total,
        "total_revised_annual_cost_eur": revised_total,
        "total_estimated_savings_eur": round(baseline_total - revised_total, 2),
        "actions_required": actions_required,
        "applied_constraints": constraints,
    }
