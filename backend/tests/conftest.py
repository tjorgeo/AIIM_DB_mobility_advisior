"""Shared pytest fixtures for the deterministic-engine tests.

All fixtures are plain dicts/lists shaped exactly like what
``agent.context.load_context`` produces, so the engines are exercised the same way
the pipeline calls them — no DB, no LLM.

Dates are absolute and span < 365 days: ``analyze_portfolio`` windows relative to the
latest leg date (not "now"), so these stay deterministic whenever the suite runs.
"""

import pytest


@pytest.fixture
def subscriptions():
    """One active public-transport subscription (Deutschlandticket), shaped like the
    user_subscriptions ⋈ subscription_catalogs join in load_context."""
    return [
        {
            "user_subscription_id": "us1",
            "subscription_status": "active",
            "subscription_id": "s1",
            "provider_name": "Deutsche Bahn",
            "provider_plan_name": "Deutschlandticket",
            "subscription_category": "public_transport",
            "monthly_cost_eur": 49.0,
            "annual_cost_eur": None,
        }
    ]


@pytest.fixture
def travel_history():
    """Leg-level history: two modes covered by the active sub (attributed via
    user_subscription_id, with reference_cost_eur > estimated_cost_eur so realized
    savings are positive), plus uncovered car_sharing / e_scooter legs, spread over
    four months so seasonality + monthly breakdown have something to work with."""
    def leg(leg_id, month, mode, sub_id, paid, reference, dist, co2):
        return {
            "leg_id": leg_id,
            "trip_id": f"trip_{leg_id}",
            "user_subscription_id": sub_id,
            "started_at": f"2026-0{month}-05T08:00:00+02:00",
            "transport_mode": mode,
            "ticket_type": "single",
            "ticket_class": 2,
            "estimated_distance_km": dist,
            "estimated_cost_eur": paid,
            "reference_cost_eur": reference,
            "estimated_co2_emissions": co2,
        }

    return [
        leg("l1", 1, "public_transport", "us1", 0.0, 12.0, 8.0, 0.5),
        leg("l2", 1, "regional_train", "us1", 0.0, 9.0, 30.0, 1.2),
        leg("l3", 2, "public_transport", "us1", 0.0, 12.0, 8.0, 0.5),
        leg("l4", 2, "car_sharing", None, 18.0, 18.0, 12.0, 2.1),
        leg("l5", 3, "e_scooter", None, 5.0, 5.0, 3.0, 0.3),
        leg("l6", 3, "regional_train", "us1", 0.0, 9.0, 30.0, 1.2),
        leg("l7", 4, "car_sharing", None, 18.0, 18.0, 12.0, 2.1),
    ]


@pytest.fixture
def pricing_catalog():
    """A handful of catalog plans across three categories (the optimizer's candidate
    space). ``id`` matches the active sub's subscription_id so 'keep current' is a
    candidate."""
    return [
        {"id": "s1", "name": "Deutschlandticket", "category": "public_transport", "monthly_cost": 49.0, "annual_cost": None},
        {"id": "s2", "name": "Car Sharing Basic", "category": "car_sharing", "monthly_cost": 0.0, "annual_cost": 0.0},
        {"id": "s3", "name": "E-Scooter Pass", "category": "e_scooter", "monthly_cost": 5.0, "annual_cost": 60.0},
    ]


@pytest.fixture
def preferences():
    return {"cost_priority": 80, "co2_priority": 50, "convenience_priority": 50, "class_preference": "2nd"}


@pytest.fixture
def analyst_summary():
    """A forecaster_summary-shaped dict with monthly_mode_breakdown, so the
    forecaster's recent-month weighting (vs the flat dominant_patterns average) can
    be exercised. public_transport trends UP across the recent months; regional_train
    only has flat data (no monthly breakdown) to exercise the fallback branch."""
    return {
        "dominant_patterns": [
            {"mode": "public_transport", "avg_trips_per_month": 10.0, "avg_distance_km": 8.0},
            {"mode": "regional_train", "avg_trips_per_month": 4.0, "avg_distance_km": 30.0},
        ],
        "detected_seasonality": "no significant seasonal variation detected",
        "current_contracts": ["Deutschlandticket (€49/mo)"],
        "detected_inefficiencies": [],
        "monthly_mode_breakdown": {
            "2026-01": {"public_transport": {"trips": 6, "distance_km": 48.0, "co2_kg": 3.0, "intrinsic_cost_eur": 0.0, "effective_cost_eur": 0.0}},
            "2026-02": {"public_transport": {"trips": 12, "distance_km": 96.0, "co2_kg": 6.0, "intrinsic_cost_eur": 0.0, "effective_cost_eur": 0.0}},
            "2026-03": {"public_transport": {"trips": 18, "distance_km": 144.0, "co2_kg": 9.0, "intrinsic_cost_eur": 0.0, "effective_cost_eur": 0.0}},
        },
    }
