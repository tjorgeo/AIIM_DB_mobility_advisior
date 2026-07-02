"""Unit tests for agent.engines.analysis.analyze_portfolio (pure, deterministic)."""

import json

from agent.engines import analyze_portfolio

_REQUIRED_KEYS = {
    "current_annual_spend_eur",
    "total_trips",
    "total_distance_km",
    "total_co2_kg",
    "mode_breakdown",
    "subscription_coverage",
    "uncovered_spend_by_category",
    "dominant_patterns",
    "detected_seasonality",
    "inefficiencies",
    "savings_potential_estimate_eur",
    "forecaster_summary",
}


def test_returns_required_contract_keys(travel_history, subscriptions):
    out = analyze_portfolio(travel_history, subscriptions)
    assert _REQUIRED_KEYS <= set(out)


def test_total_trips_matches_window_leg_count(travel_history, subscriptions):
    out = analyze_portfolio(travel_history, subscriptions)
    # all fixture legs fall within the 12-month window, so every leg is counted
    assert out["total_trips"] == len(travel_history)


def test_forecaster_summary_is_shaped_for_the_forecaster(travel_history, subscriptions):
    fs = analyze_portfolio(travel_history, subscriptions)["forecaster_summary"]
    assert set(fs) >= {
        "dominant_patterns",
        "detected_seasonality",
        "current_contracts",
        "detected_inefficiencies",
        "monthly_mode_breakdown",
    }
    assert isinstance(fs["dominant_patterns"], list)


def test_attributed_subscription_reports_positive_realized_savings(travel_history, subscriptions):
    """Legs attributed to us1 have reference_cost_eur > estimated_cost_eur (paid 0),
    so the Deutschlandticket must show positive realized savings."""
    cov = analyze_portfolio(travel_history, subscriptions)["subscription_coverage"]
    assert len(cov) == 1
    dt = cov[0]
    assert dt["provider_plan_name"] == "Deutschlandticket"
    assert dt["realized_savings_eur"] > 0
    # l1, l2, l3, l6 carry user_subscription_id == "us1"
    assert dt["trips"] == 4


def test_reproducible(travel_history, subscriptions):
    a = analyze_portfolio(travel_history, subscriptions)
    b = analyze_portfolio(travel_history, subscriptions)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


def test_empty_history_returns_zeros_without_raising():
    out = analyze_portfolio([], [])
    assert out["total_trips"] == 0
    assert out["total_distance_km"] == 0
    assert out["mode_breakdown"] == {}
    assert out["subscription_coverage"] == []
