"""Deterministic catalog-driven portfolio optimisation.

Pure function, no LLM, no I/O. Enumerates candidate portfolios (at most one plan
per category) over the production ``subscription_catalogs`` and simulates the
annual cost of each. This is the authoritative source of every recommended plan
and savings figure — the Analyst agent calls it as a tool but never recomputes.
"""

import itertools
import re

from agent.schema_map import category_covers_mode

# BahnCard-style catalog rows encode their eligibility band as free text in
# subscription_type_other, e.g. "Ages 27-64", "Youth variant; ages 6-26", "Senior
# variant; ages 65+". Parsed so the optimizer never proposes an age-gated variant the
# customer doesn't qualify for.
_AGE_RANGE_RE = re.compile(r"ages?\s+(\d+)\s*-\s*(\d+)", re.IGNORECASE)
_AGE_MIN_RE = re.compile(r"ages?\s+(\d+)\s*\+", re.IGNORECASE)
# Discount variants gated on a condition we have no data field to verify (disability /
# reduced earning capacity pension) — excluded outright rather than assumed, since
# recommending a plan we can't confirm eligibility for is worse than not recommending it.
_UNVERIFIABLE_ELIGIBILITY_RE = re.compile(r"disability|reduced earning capacity|pension", re.IGNORECASE)


def _is_eligible(plan: dict, user_age) -> bool:
    """Whether ``plan`` may be proposed to a customer of ``user_age`` (``None`` if
    unknown, in which case age-gated plans are not excluded — there's nothing to check
    them against)."""
    text = plan.get("subscription_type_other") or ""
    if _UNVERIFIABLE_ELIGIBILITY_RE.search(text):
        return False
    if user_age is None:
        return True
    match = _AGE_RANGE_RE.search(text)
    if match:
        lo, hi = int(match.group(1)), int(match.group(2))
        return lo <= user_age <= hi
    match = _AGE_MIN_RE.search(text)
    if match:
        return user_age >= int(match.group(1))
    return True


def _is_ongoing_candidate(plan: dict) -> bool:
    """Excludes one-time trial cards (e.g. "Probe BahnCard") from the candidate space.

    Their introductory one-time price (``billing_cycle == "one_time"``) would otherwise
    be compared directly against other plans' *annual* cost by :func:`_plan_annual` and
    almost always look like the cheapest option in its category — even though a 3-month
    trial isn't a substitute for an ongoing annual subscription.
    """
    return plan.get("billing_cycle") != "one_time"


def _plan_annual(plan: dict) -> float:
    """Annual cost of a catalog plan — prefer an explicit annual price, else 12x
    the monthly price."""
    annual = plan.get("annual_cost")
    if annual is not None:
        return float(annual)
    return float(plan.get("monthly_cost") or 0.0) * 12


def optimize(
    travel_history: list,
    current_subscriptions: list,
    pricing_catalog: list,
    preferences: dict,
    user_age: int | None = None,
) -> dict:
    """
    Catalog-driven, flat-rate portfolio optimisation over the production
    ``subscription_catalogs``. Every *eligible* catalog plan is a candidate; a plan
    covers a leg when its ``category`` covers the leg's ``transport_mode``
    (``category_covers_mode``). A covered leg costs nothing; an uncovered leg keeps
    its intrinsic ``estimated_cost_eur``. There are no hardcoded product ids — the
    recommendation space is whatever the catalog contains.

    Eligibility (``_is_eligible``/``_is_ongoing_candidate``) excludes plans this
    customer can't actually hold — age-gated BahnCard variants they don't qualify for,
    discount variants gated on a condition we can't verify, and one-time trial cards —
    *before* the "cheapest per category" pruning runs, so those plans can never win a
    slot just for looking cheap.

    Cost model: every total (including the baseline) is produced by the same
    ``simulate()``; the baseline is simply the simulation of the user's *current*
    subscriptions, so adding or removing a plan is symmetric.
    """
    baseline_co2 = sum((leg.get("estimated_co2_emissions") or 0.0) for leg in travel_history)

    def simulate(portfolio):
        """Return (total, sub_annual, legs_cost) for a set of catalog plans."""
        sub_annual = sum(_plan_annual(p) for p in portfolio)
        legs_cost = 0.0
        for leg in travel_history:
            mode = leg.get("transport_mode")
            covered = any(category_covers_mode(p.get("category"), mode) for p in portfolio)
            if not covered:
                # Uncovered legs cost their intrinsic full fare. reference_cost_eur is
                # the pay-as-you-go price regardless of any subscription (falls back to
                # estimated_cost_eur), so cancelling a pass restores the real cost of the
                # legs it covered instead of the €0 they show while the pass applies.
                legs_cost += leg.get("reference_cost_eur") or leg.get("estimated_cost_eur") or 0.0
        return round(legs_cost + sub_annual, 2), round(sub_annual, 2), round(legs_cost, 2)

    def covered_count(portfolio):
        n = 0
        for leg in travel_history:
            mode = leg.get("transport_mode")
            if any(category_covers_mode(p.get("category"), mode) for p in portfolio):
                n += 1
        return n

    # --- current portfolio (active subscriptions, shaped like catalog plans) ---
    current_plans = [
        {
            "id": s.get("subscription_id"),
            "name": s.get("provider_plan_name"),
            "category": s.get("subscription_category"),
            "monthly_cost": s.get("monthly_cost_eur"),
            "annual_cost": s.get("annual_cost_eur"),
        }
        for s in current_subscriptions
        if s.get("subscription_status") == "active"
    ]
    current_ids = {p["id"] for p in current_plans}

    baseline_total, baseline_sub, baseline_oop = simulate(current_plans)

    # --- candidate portfolios: pick at most one plan per category ---
    eligible_catalog = [
        plan
        for plan in pricing_catalog
        if _is_ongoing_candidate(plan) and _is_eligible(plan, user_age)
    ]
    by_category = {}
    for plan in eligible_catalog:
        by_category.setdefault(plan.get("category"), []).append(plan)

    # Coverage is category-based (category_covers_mode), so every plan within a
    # category covers the exact same legs — only price differs. Only the cheapest
    # plan per category can ever be in an optimal or balanced portfolio, so pruning
    # to it is exact and collapses the candidate space from ~product(sizes) to
    # 2**(#categories).
    pruned = {cat: min(plans, key=_plan_annual) for cat, plans in by_category.items()}
    option_lists = [[None, plan] for plan in pruned.values()]
    seen = set()
    candidates = []
    for combo in itertools.product(*option_lists) if option_lists else [()]:
        portfolio = [p for p in combo if p]
        key = frozenset(p["id"] for p in portfolio)
        if key in seen:
            continue
        seen.add(key)
        candidates.append(portfolio)

    # --- simulate every candidate ---
    results = []
    for portfolio in candidates:
        total, sub_annual, legs_cost = simulate(portfolio)
        results.append(
            {
                "portfolio": portfolio,
                "ids": frozenset(p["id"] for p in portfolio),
                "total": total,
                "sub_cost": sub_annual,
                "covered": covered_count(portfolio),
            }
        )
    results.sort(key=lambda r: (r["total"], -r["covered"]))

    cheapest = results[0]

    # Balanced: best coverage within 15% of the cheapest total, else 2nd cheapest.
    balanced = None
    threshold = cheapest["total"] * 1.15
    for r in results:
        if r["ids"] == cheapest["ids"]:
            continue
        if r["total"] <= threshold and r["covered"] > cheapest["covered"]:
            if balanced is None or r["covered"] > balanced["covered"]:
                balanced = r
    if balanced is None:
        balanced = results[1] if len(results) > 1 else cheapest

    def changes_for(portfolio):
        portfolio_ids = {p["id"] for p in portfolio}
        changes = []
        for p in portfolio:
            if p["id"] not in current_ids:
                changes.append({"action": "add", "item": p["name"], "service_id": p["id"]})
        for s in current_plans:
            if s["id"] not in portfolio_ids:
                changes.append({"action": "cancel", "item": s["name"], "service_id": s["id"]})
        return changes

    def scenario(scen_id, label, res, explanation):
        savings = round(baseline_total - res["total"], 2)
        return {
            "id": scen_id,
            "label": label,
            "portfolio": [p["name"] for p in res["portfolio"]],
            "annual_cost": res["total"],
            "annual_savings": savings,
            "co2_impact_kg": round(baseline_co2, 2),
            "co2_savings_kg": 0.0,  # flat plans don't shift emissions in this model
            "changes": changes_for(res["portfolio"]),
            "explanation": explanation,
        }

    savings_a = round(baseline_total - cheapest["total"], 2)
    savings_b = round(baseline_total - balanced["total"], 2)

    scenario_a = scenario(
        "A",
        "Cost-Optimized Portfolio",
        cheapest,
        f"The lowest-cost mix for how you travel — an estimated €{savings_a} less per year than your current setup.",
    )
    scenario_b = scenario(
        "B",
        "Balanced Mobility Portfolio",
        balanced,
        "Broader coverage across your travel modes while staying close to the cheapest option.",
    )

    return {
        "baseline_annual_cost": round(baseline_total, 2),
        "baseline_out_of_pocket": round(baseline_oop, 2),
        "baseline_sub_cost": round(baseline_sub, 2),
        "baseline_co2_kg": round(baseline_co2, 2),
        "scenarios": [scenario_a, scenario_b],
        "best_recommendation_id": "A" if savings_a >= savings_b else "B",
    }


if __name__ == "__main__":
    history = [
        {"transport_mode": "regional_train", "estimated_cost_eur": 12.0, "estimated_co2_emissions": 1.2},
        {"transport_mode": "car_sharing", "estimated_cost_eur": 18.0, "estimated_co2_emissions": 2.1},
    ]
    subs = [{"subscription_status": "active", "subscription_id": "s1", "provider_plan_name": "Deutschlandticket",
             "subscription_category": "public_transport", "monthly_cost_eur": 49.0, "annual_cost_eur": None}]
    catalog = [
        {"id": "s1", "name": "Deutschlandticket", "category": "public_transport", "monthly_cost": 49.0, "annual_cost": None},
        {"id": "s2", "name": "Car Sharing Basic", "category": "car_sharing", "monthly_cost": 0.0, "annual_cost": 0.0},
    ]
    print(optimize(history, subs, catalog, {}))
