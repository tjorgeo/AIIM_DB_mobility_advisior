"""Unit tests for agent.engines.analysis.analyze_portfolio (pure, deterministic)."""

import json
from datetime import datetime, timedelta

from agent.engines import analyze_portfolio

_REQUIRED_KEYS = {
    "current_annual_spend_eur",
    "total_trips",
    "total_distance_km",
    "total_co2_kg",
    "mode_breakdown",
    "subscription_coverage",
    "uncovered_spend_by_category",
    "category_subscription_analysis",
    "dominant_patterns",
    "detected_seasonality",
    "inefficiencies",
    "savings_potential_estimate_eur",
    "forecaster_summary",
}


def _leg(i, gap_days, ref, paid, sub_id, mode="public_transport", start=datetime(2025, 7, 1)):
    return {
        "leg_id": f"l{i}", "trip_id": f"t{i}",
        "started_at": (start + timedelta(days=i * gap_days)).isoformat(),
        "user_subscription_id": sub_id, "transport_mode": mode,
        "estimated_cost_eur": paid, "reference_cost_eur": ref, "estimated_co2_emissions": 0.3,
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


def test_category_analysis_skips_categories_with_no_current_sub_and_no_priceable_alt(
    travel_history, subscriptions, pricing_catalog
):
    """car_sharing/e_scooter in the shared fixtures have no active subscription and
    their only catalog plans have no pricing_model (like most real car-sharing/
    e-scooter rows) — they must land in non_comparable_alternatives, never be guessed
    at as a cheapest_alternative, and the category recommendation must default to
    'no_subscription_needed' rather than silently recommending an unpriced plan."""
    out = analyze_portfolio(travel_history, subscriptions, pricing_catalog)
    by_cat = {e["category"]: e for e in out["category_subscription_analysis"]}
    for cat, plan_name in (("car_sharing", "Car Sharing Basic"), ("e_scooter", "E-Scooter Pass")):
        assert by_cat[cat]["cheapest_alternative"] is None
        assert by_cat[cat]["non_comparable_alternatives"] == [plan_name]
        assert by_cat[cat]["recommendation"] == "no_subscription_needed"


def test_underused_pass_recommends_cancelling(subscriptions):
    """A Deutschlandticket used on only 4 light trips over the window costs far more
    (€588/yr) than paying as you go for those same trips would — must recommend
    cancelling, the opposite of the old optimizer's 'any subscription covers its
    category for free' bug."""
    history = [_leg(i, 30, 15.0, 0.0, "us1") for i in range(10)]
    catalog = [{"id": "s1", "name": "Deutschlandticket", "category": "public_transport",
                "monthly_cost": 49.0, "annual_cost": None, "pricing_model": "flat_monthly"}]
    out = analyze_portfolio(history, subscriptions, catalog)
    entry = out["category_subscription_analysis"][0]
    assert entry["recommendation"] == "cancel_current_go_pay_as_you_go"
    assert entry["actual_annual_cost_eur"] > entry["no_subscription_annual_cost_eur"]


def test_heavily_used_pass_recommends_keeping_it(subscriptions):
    """Regression: a heavily-used pass must not look like a phantom-cancel
    opportunity — the exact case that motivated retiring the old optimizer."""
    history = [_leg(i, 6, 15.0, 0.0, "us1") for i in range(60)]  # ~year, 60 trips
    catalog = [{"id": "s1", "name": "Deutschlandticket", "category": "public_transport",
                "monthly_cost": 49.0, "annual_cost": None, "pricing_model": "flat_monthly"}]
    out = analyze_portfolio(history, subscriptions, catalog)
    entry = out["category_subscription_analysis"][0]
    assert entry["recommendation"] == "keep_current"
    assert entry["current_subscriptions"][0]["annual_net_savings_eur"] > 0


def test_discount_card_alternative_wins_only_when_cheaper_than_both(subscriptions):
    """A BahnCard 25 (25% discount, priced from its name — no pricing_model needed)
    must be recommended only when it beats *both* the current Deutschlandticket and
    plain pay-as-you-go — not merely when it beats the current subscription alone."""
    history = [_leg(i, 9, 10.0, 0.0, "us1") for i in range(40)]
    catalog = [
        {"id": "s1", "name": "Deutschlandticket", "category": "public_transport",
         "monthly_cost": 49.0, "annual_cost": None, "pricing_model": "flat_monthly"},
        {"id": "bc25", "name": "BahnCard 25, 2. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.90},
    ]
    out = analyze_portfolio(history, subscriptions, catalog)
    entry = out["category_subscription_analysis"][0]
    assert entry["recommendation"] == "switch_to_alternative"
    alt = entry["cheapest_alternative"]
    assert alt["provider_plan_name"] == "BahnCard 25, 2. Klasse"
    assert "25%" in alt["pricing_basis"]
    assert alt["estimated_annual_cost_eur"] < entry["actual_annual_cost_eur"]
    assert alt["estimated_annual_cost_eur"] < entry["no_subscription_annual_cost_eur"]


def test_consider_subscribing_when_no_current_sub_but_alternative_cheaper():
    """No current car-sharing subscription, but a flat-rate alternative would cost
    less than paying as you go for the trips actually taken."""
    history = [_leg(i, 4, 20.0, 20.0, None, mode="car_sharing") for i in range(80)]
    catalog = [{"id": "flat_car", "name": "Car Flat", "category": "car_sharing",
                "monthly_cost": 50.0, "annual_cost": None, "pricing_model": "flat_monthly"}]
    out = analyze_portfolio(history, [], catalog)
    entry = out["category_subscription_analysis"][0]
    assert entry["recommendation"] == "consider_subscribing"
    assert entry["cheapest_alternative"]["provider_plan_name"] == "Car Flat"


def test_ineligible_and_one_time_plans_never_offered(subscriptions):
    """Regression, carried over from the old optimizer: an age-gated variant the
    customer doesn't qualify for, and a one-time trial card, must never appear as
    cheapest_alternative *or* non_comparable_alternatives — they're excluded outright,
    not silently mislabeled as 'can't price this'."""
    history = [_leg(i, 30, 15.0, 0.0, "us1") for i in range(10)]
    catalog = [
        {"id": "s1", "name": "Deutschlandticket", "category": "public_transport",
         "monthly_cost": 49.0, "annual_cost": None, "pricing_model": "flat_monthly"},
        {"id": "senior", "name": "Senioren BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 5.0, "subscription_type_other": "Senior variant; ages 65+"},
        {"id": "probe", "name": "Probe BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 1.0, "billing_cycle": "one_time"},
    ]
    out = analyze_portfolio(history, subscriptions, catalog, user_age=30)
    entry = out["category_subscription_analysis"][0]
    assert entry["cheapest_alternative"] is None
    assert entry["non_comparable_alternatives"] == []
