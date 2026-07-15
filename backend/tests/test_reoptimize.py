"""Tests for agent.engines.reoptimize — the chat re-optimisation feedback loop.

``_rederive_entry``'s unconstrained (no keep/drop/prefer_plans) fallback branch now
shares ``engines/scoring.py`` with ``analysis.py::_pick_recommendation`` instead of
its own inline three-way comparison — these tests confirm that switch stayed
behaviour-preserving for the default (no explicit weights) case, and that explicit
keep/drop/prefer_plans overrides still bypass scoring entirely regardless of weights.
"""

from agent.engines.reoptimize import reoptimize_from_analysis
from agent.engines.scoring import resolve_weights


def _entry(**overrides):
    base = {
        "category": "car_sharing",
        "actual_annual_cost_eur": 200.0,
        "no_subscription_annual_cost_eur": 300.0,
        "annual_co2_kg": 50.0,
        "annual_time_minutes": 120.0,
        "current_subscriptions": [{"provider_plan_name": "Old Plan", "annual_cost_eur": 200.0}],
        "alternatives": [
            {"provider_plan_name": "Cheap Plan", "estimated_annual_cost_eur": 150.0},
            {"provider_plan_name": "Pricier Plan", "estimated_annual_cost_eur": 180.0},
        ],
    }
    base.update(overrides)
    return base


def test_default_weights_reproduce_pure_cost_behaviour():
    """No weights passed -> equal thirds -> CO2/time are identical across
    current/no-subscription/every alternative within one category (same physical
    trips regardless of which plan pays), so the cheapest option still wins, exactly
    like the pre-scoring behaviour."""
    result = reoptimize_from_analysis([_entry()])
    revised = result["category_subscription_analysis"][0]
    assert revised["recommendation"] == "switch_to_alternative"
    assert revised["chosen_alternative"]["provider_plan_name"] == "Cheap Plan"
    assert revised["chosen_annual_cost_eur"] == 150.0


def test_explicit_weights_still_pick_cheapest_when_co2_time_are_category_invariant():
    """Even heavily CO2-weighted preferences can't change the winner here, because
    CO2/time are the same real category total for every option — matching
    analysis.py's identical invariant (see test_analysis.py's equivalent test)."""
    weights = resolve_weights(0, 100, 0)
    result = reoptimize_from_analysis([_entry()], weights=weights)
    revised = result["category_subscription_analysis"][0]
    assert revised["chosen_alternative"]["provider_plan_name"] == "Cheap Plan"


def test_keep_constraint_bypasses_scoring():
    result = reoptimize_from_analysis([_entry()], constraints={"keep": ["car_sharing"]})
    revised = result["category_subscription_analysis"][0]
    assert revised["recommendation"] == "keep_current"
    assert revised["chosen_annual_cost_eur"] == 200.0
    assert revised["chosen_alternative"] is None


def test_drop_constraint_bypasses_scoring():
    result = reoptimize_from_analysis([_entry()], constraints={"drop": ["car_sharing"]})
    revised = result["category_subscription_analysis"][0]
    assert revised["recommendation"] == "cancel_current_go_pay_as_you_go"
    assert revised["chosen_annual_cost_eur"] == 300.0


def test_prefer_plans_picks_named_plan_even_if_not_cheapest():
    result = reoptimize_from_analysis([_entry()], constraints={"prefer_plans": ["Pricier Plan"]})
    revised = result["category_subscription_analysis"][0]
    assert revised["recommendation"] == "switch_to_alternative"
    assert revised["chosen_alternative"]["provider_plan_name"] == "Pricier Plan"
    assert revised["chosen_annual_cost_eur"] == 180.0


def test_exclude_plans_removes_candidate_from_consideration():
    result = reoptimize_from_analysis([_entry()], constraints={"exclude_plans": ["Cheap Plan"]})
    revised = result["category_subscription_analysis"][0]
    assert revised["chosen_alternative"]["provider_plan_name"] == "Pricier Plan"


def test_totals_and_actions_required_roll_up():
    result = reoptimize_from_analysis([_entry()])
    assert result["total_actual_annual_cost_eur"] == 200.0
    assert result["total_revised_annual_cost_eur"] == 150.0
    assert result["total_estimated_savings_eur"] == 50.0
    assert len(result["actions_required"]) == 1
    assert result["actions_required"][0]["to"] == "Cheap Plan"


def test_missing_co2_time_fields_degrade_gracefully():
    """Older persisted rows computed before this feature won't have annual_co2_kg/
    annual_time_minutes at all — must fall back to pure cost, not crash."""
    entry = _entry()
    del entry["annual_co2_kg"]
    del entry["annual_time_minutes"]
    result = reoptimize_from_analysis([entry])
    revised = result["category_subscription_analysis"][0]
    assert revised["chosen_alternative"]["provider_plan_name"] == "Cheap Plan"
