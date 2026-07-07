"""Unit tests for agent.engines.optimization.optimize (pure, deterministic)."""

import json

from agent.engines import optimize


def test_returns_two_well_formed_scenarios(travel_history, subscriptions, pricing_catalog, preferences):
    out = optimize(travel_history, subscriptions, pricing_catalog, preferences)
    assert [s["id"] for s in out["scenarios"]] == ["A", "B"]
    for s in out["scenarios"]:
        assert {"id", "label", "annual_cost", "annual_savings", "changes", "portfolio"} <= set(s)
    assert out["best_recommendation_id"] in {"A", "B"}


def test_savings_equal_baseline_minus_cost(travel_history, subscriptions, pricing_catalog, preferences):
    out = optimize(travel_history, subscriptions, pricing_catalog, preferences)
    baseline = out["baseline_annual_cost"]
    for s in out["scenarios"]:
        assert s["annual_savings"] == round(baseline - s["annual_cost"], 2)


def test_changes_are_add_or_cancel_actions(travel_history, subscriptions, pricing_catalog, preferences):
    out = optimize(travel_history, subscriptions, pricing_catalog, preferences)
    for s in out["scenarios"]:
        for change in s["changes"]:
            assert change["action"] in {"add", "cancel"}
            assert "item" in change and "service_id" in change


def test_empty_catalog_returns_well_formed_scenarios_without_crashing(travel_history, subscriptions, preferences):
    # With no catalog the only candidate portfolios are empty (drop everything); the
    # engine must still return two well-formed scenarios rather than raising.
    out = optimize(travel_history, subscriptions, [], preferences)
    assert [s["id"] for s in out["scenarios"]] == ["A", "B"]
    assert out["best_recommendation_id"] in {"A", "B"}
    for s in out["scenarios"]:
        assert s["portfolio"] == []  # nothing to recommend from an empty catalog
        assert s["annual_cost"] >= 0


def test_reproducible(travel_history, subscriptions, pricing_catalog, preferences):
    a = optimize(travel_history, subscriptions, pricing_catalog, preferences)
    b = optimize(travel_history, subscriptions, pricing_catalog, preferences)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_utilised_pass_is_not_phantom_cancelled(preferences):
    """Regression: a heavily-used pass must not look free to cancel.

    The covered legs show estimated_cost_eur = 0 while the pass applies, but their
    reference_cost_eur (full fare) exceeds the pass price. Cancelling the pass should
    therefore *raise* cost, so the optimizer must keep it — not report the pass price
    as phantom savings (the old bug, which summed estimated_cost_eur and saw €0)."""
    history = [
        {"leg_id": f"l{i}", "user_subscription_id": "us1", "transport_mode": "public_transport",
         "estimated_cost_eur": 0.0, "reference_cost_eur": 15.0, "estimated_co2_emissions": 0.5}
        for i in range(60)  # 60 * €15 = €900 full-fare > €588 annual pass
    ]
    subs = [{
        "user_subscription_id": "us1", "subscription_status": "active", "subscription_id": "s1",
        "provider_plan_name": "Deutschlandticket", "subscription_category": "public_transport",
        "monthly_cost_eur": 49.0, "annual_cost_eur": None,
    }]
    catalog = [{"id": "s1", "name": "Deutschlandticket", "category": "public_transport",
                "monthly_cost": 49.0, "annual_cost": None}]

    out = optimize(history, subs, catalog, preferences)

    # The pass is utilised, so keeping it is cheapest; no scenario may show positive
    # savings from cancelling it.
    for s in out["scenarios"]:
        cancels_pass = any(c["action"] == "cancel" and c["service_id"] == "s1" for c in s["changes"])
        if cancels_pass:
            assert s["annual_savings"] <= 0, "cancelling a utilised pass showed phantom savings"


def test_pruning_ignores_dominated_plans(travel_history, subscriptions, pricing_catalog, preferences):
    """A pricier plan in a category that a cheaper plan already fully covers can never
    win, so adding it must not change the optimizer's output (pruning is exact)."""
    base = optimize(travel_history, subscriptions, pricing_catalog, preferences)

    dominated = pricing_catalog + [
        {"id": "s1_premium", "name": "Deutschlandticket Premium", "category": "public_transport",
         "monthly_cost": 99.0, "annual_cost": None},
    ]
    with_dominated = optimize(travel_history, subscriptions, dominated, preferences)

    assert json.dumps(base, sort_keys=True) == json.dumps(with_dominated, sort_keys=True)
