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
