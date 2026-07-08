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


def test_age_ineligible_cheaper_plan_is_skipped(travel_history, subscriptions, preferences):
    """Regression: an age-gated variant the customer doesn't qualify for must not win
    'cheapest per category' just because it's the cheapest row in the category — e.g. a
    Senioren BahnCard must not be proposed to a 30-year-old just because it undercuts
    the regular adult card."""
    catalog = [
        {"id": "adult", "name": "BahnCard 25 Adult", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.9, "subscription_type_other": "Ages 27-64"},
        {"id": "senior", "name": "Senioren BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 40.9, "subscription_type_other": "Senior variant; ages 65+"},
    ]
    out = optimize(travel_history, subscriptions, catalog, preferences, user_age=30)
    recommended = {name for s in out["scenarios"] for name in s["portfolio"]}
    assert "Senioren BahnCard 25" not in recommended


def test_age_eligible_variant_is_still_a_candidate(travel_history, subscriptions, preferences):
    """The flip side: a 70-year-old should still get the (cheaper) senior variant, not
    be forced onto the pricier adult card."""
    catalog = [
        {"id": "adult", "name": "BahnCard 25 Adult", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.9, "subscription_type_other": "Ages 27-64"},
        {"id": "senior", "name": "Senioren BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 40.9, "subscription_type_other": "Senior variant; ages 65+"},
    ]
    out = optimize(travel_history, subscriptions, catalog, preferences, user_age=70)
    recommended = {name for s in out["scenarios"] for name in s["portfolio"]}
    assert "BahnCard 25 Adult" not in recommended


def test_unverifiable_eligibility_variant_never_recommended(travel_history, subscriptions, preferences):
    """A disability/reduced-earning-capacity discount card has no data field to confirm
    eligibility against, so it must never be proposed — regardless of age, and even
    though it's the cheapest row in its category."""
    catalog = [
        {"id": "adult", "name": "BahnCard 25 Adult", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.9, "subscription_type_other": "Ages 27-64"},
        {"id": "erm", "name": "Ermäßigte BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 40.9,
         "subscription_type_other": "For people with full reduced earning capacity pension or severe disability >= 70%"},
    ]
    out = optimize(travel_history, subscriptions, catalog, preferences, user_age=40)
    recommended = {name for s in out["scenarios"] for name in s["portfolio"]}
    assert "Ermäßigte BahnCard 25" not in recommended


def test_one_time_trial_plan_excluded_from_candidates(travel_history, subscriptions, preferences):
    """Regression: a one-time trial card's introductory price must not be compared as
    if it were an ongoing annual cost — it would otherwise almost always look like the
    'cheapest' option in its category despite not being a real annual subscription."""
    catalog = [
        {"id": "adult", "name": "BahnCard 25 Adult", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.9, "billing_cycle": "yearly"},
        {"id": "probe", "name": "Probe BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 19.9, "billing_cycle": "one_time"},
    ]
    out = optimize(travel_history, subscriptions, catalog, preferences, user_age=40)
    recommended = {name for s in out["scenarios"] for name in s["portfolio"]}
    assert "Probe BahnCard 25" not in recommended


def test_zero_priced_payg_plan_is_not_free_coverage(preferences):
    """Regression: a pay-as-you-go plan with no flat fee (monthly/annual 0/NULL) must
    not be selected as 'free coverage'. Otherwise it would be the cheapest row in its
    category (annual cost €0) and zero out every leg it covers for nothing — proposing
    it as a subscription that eliminates all car-sharing cost at no charge."""
    history = [
        {"leg_id": f"l{i}", "transport_mode": "car_sharing",
         "estimated_cost_eur": 12.0, "reference_cost_eur": 12.0, "estimated_co2_emissions": 1.0}
        for i in range(10)
    ]
    subs = []
    catalog = [
        # per-minute PAYG: no flat price → must be excluded from candidates
        {"id": "miles", "name": "MILES Pay-as-you-go", "category": "car_sharing",
         "monthly_cost": 0.0, "annual_cost": None},
    ]
    out = optimize(history, subs, catalog, preferences)

    recommended = {name for s in out["scenarios"] for name in s["portfolio"]}
    assert "MILES Pay-as-you-go" not in recommended
    # With no cost-able plan, the car-sharing legs stay out-of-pocket (10 * €12 = €120),
    # not zeroed for free.
    for s in out["scenarios"]:
        assert s["annual_cost"] == 120.0
        assert s["annual_savings"] == 0.0


def test_no_user_age_does_not_filter_by_age(travel_history, subscriptions, preferences):
    """Without a known age (user_age=None, the default), age-gated plans aren't
    excluded — there's nothing to check them against."""
    catalog = [
        {"id": "senior", "name": "Senioren BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 40.9, "subscription_type_other": "Senior variant; ages 65+"},
    ]
    out = optimize(travel_history, subscriptions, catalog, preferences)
    recommended = {name for s in out["scenarios"] for name in s["portfolio"]}
    assert "Senioren BahnCard 25" in recommended


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
