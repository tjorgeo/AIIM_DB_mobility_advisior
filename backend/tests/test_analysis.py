"""Unit tests for agent.engines.analysis.analyze_portfolio (pure, deterministic)."""

import json
from datetime import date, datetime, timedelta

from agent.engines import analyze_portfolio
from agent.engines.analysis import _simulate_consumption_annual_cost

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


def test_category_entries_carry_co2_and_time_totals(travel_history, subscriptions, pricing_catalog):
    """New multi-criteria fields: every category entry must carry its own real
    annual CO2/time/distance totals (not just cost), sourced from the same per-leg
    aggregation as total_co2_kg."""
    out = analyze_portfolio(travel_history, subscriptions, pricing_catalog)
    for entry in out["category_subscription_analysis"]:
        assert "annual_co2_kg" in entry
        assert "annual_time_minutes" in entry
        assert "annual_distance_km" in entry
        assert "recommended_alternative" in entry
        assert "score_breakdown" in entry


def test_recommended_alternative_matches_cheapest_when_co2_time_are_invariant(
    travel_history, subscriptions, pricing_catalog,
):
    """Within one category, CO2/time are the SAME real total regardless of which
    plan is chosen (same physical trips/mode) — so even heavily CO2-weighted
    preferences must not change which alternative wins; recommended_alternative
    stays the cost-cheapest one, exactly like the old pure-cost behaviour."""
    cost_only = analyze_portfolio(
        travel_history, subscriptions, pricing_catalog,
        preferences={"cost_priority": 100, "co2_priority": 0, "convenience_priority": 0},
    )
    co2_heavy = analyze_portfolio(
        travel_history, subscriptions, pricing_catalog,
        preferences={"cost_priority": 0, "co2_priority": 100, "convenience_priority": 0},
    )
    for a, b in zip(cost_only["category_subscription_analysis"], co2_heavy["category_subscription_analysis"]):
        assert a["recommendation"] == b["recommendation"]
        assert a["recommended_alternative"] == b["recommended_alternative"]
        assert a["recommended_alternative"] == a["cheapest_alternative"]


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


def _bahncard_50_sub_and_catalog():
    subs = [{
        "user_subscription_id": "us1", "subscription_status": "active", "subscription_id": "bc50",
        "provider_plan_name": "BahnCard 50, 2. Klasse", "subscription_category": "public_transport",
        "monthly_cost_eur": None, "annual_cost_eur": 244.0,
    }]
    catalog = [
        {"id": "bc50", "name": "BahnCard 50, 2. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 244.0, "subscription_type": "subscription"},
        {"id": "bc25", "name": "BahnCard 25, 2. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.90, "subscription_type": "subscription"},
        {"id": "dt", "name": "Deutschlandticket", "category": "public_transport",
         "monthly_cost": 49.0, "annual_cost": None, "pricing_model": "flat_monthly",
         "subscription_type": "subscription"},
    ]
    return subs, catalog


def _find_entry(out, category):
    return next(e for e in out["category_subscription_analysis"] if e["category"] == category)


def test_discount_card_alternative_wins_only_when_cheaper_than_both():
    """A BahnCard 25 (25% discount, priced from its name — no pricing_model needed)
    must be recommended only when it beats *both* the current BahnCard 50 and plain
    pay-as-you-go — not merely when it beats the current subscription alone. Uses a
    light long-distance traveler, where BahnCard 50's bigger annual fee isn't justified
    by its bigger discount for someone who barely travels long-distance."""
    history = [_leg(i, 20, 30.0, 15.0, "us1", mode="long_distance_train") for i in range(15)]
    subs, catalog = _bahncard_50_sub_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    entry = _find_entry(out, "long_distance_rail")
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


def test_ineligible_and_one_time_plans_never_offered():
    """Regression, carried over from the old optimizer: an age-gated variant the
    customer doesn't qualify for, and a one-time trial card, must never appear as
    cheapest_alternative *or* non_comparable_alternatives — they're excluded outright,
    not silently mislabeled as 'can't price this'. Uses long_distance_train legs since
    all three plans here are BahnCard-family (routed to the long_distance_rail bucket)."""
    history = [_leg(i, 30, 80.0, 80.0, None, mode="long_distance_train") for i in range(10)]
    catalog = [
        {"id": "adult", "name": "BahnCard 25, 2. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.90, "subscription_type_other": "Ages 27-64"},
        {"id": "senior", "name": "Senioren BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 5.0, "subscription_type_other": "Senior variant; ages 65+"},
        {"id": "probe", "name": "Probe BahnCard 25", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 1.0, "billing_cycle": "one_time"},
    ]
    out = analyze_portfolio(history, [], catalog, user_age=30)
    entry = _find_entry(out, "long_distance_rail")
    alt_names = {a["provider_plan_name"] for a in entry["alternatives"]}
    assert alt_names == {"BahnCard 25, 2. Klasse"}
    assert entry["non_comparable_alternatives"] == []


def _mixed_public_transport_history():
    """Local bus/tram trips (unattributed — no subscription covers them) plus regional
    trips (also unattributed) and long-distance trips attributed to a held BahnCard 50
    (50% off)."""
    def block(n, mode, sub_id, ref, paid):
        return [
            {"leg_id": f"{mode}{i}", "trip_id": f"t_{mode}{i}",
             "started_at": (datetime(2025, 7, 1) + timedelta(days=i * 6)).isoformat(),
             "user_subscription_id": sub_id, "transport_mode": mode,
             "estimated_cost_eur": paid, "reference_cost_eur": ref, "estimated_co2_emissions": 0.2}
            for i in range(n)
        ]
    return (
        block(20, "public_transport", None, 3.0, 3.0)
        + block(20, "regional_train", None, 10.0, 10.0)
        + block(20, "long_distance_train", "us1", 80.0, 40.0)
    )


def _mixed_public_transport_subs_and_catalog():
    subs = [{
        "user_subscription_id": "us1", "subscription_status": "active", "subscription_id": "bc50",
        "provider_plan_name": "BahnCard 50, 2. Klasse", "subscription_category": "public_transport",
        "monthly_cost_eur": None, "annual_cost_eur": 244.0,
    }]
    catalog = [
        {"id": "bc50", "name": "BahnCard 50, 2. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 244.0, "subscription_type": "subscription"},
        {"id": "bc25", "name": "BahnCard 25, 2. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.90, "subscription_type": "subscription"},
        {"id": "dt", "name": "Deutschlandticket", "category": "public_transport",
         "monthly_cost": 49.0, "annual_cost": None, "pricing_model": "flat_monthly",
         "subscription_type": "subscription"},
        {"id": "jobticket", "name": "Deutschlandticket Jobticket", "category": "public_transport",
         "monthly_cost": 44.10, "annual_cost": None, "pricing_model": "flat_monthly",
         "subscription_type": "employer_benefit"},
    ]
    return subs, catalog


def test_public_transport_and_long_distance_rail_are_separate_entries():
    """Local/regional and long-distance rail must be two independent entries, not one
    combined 'public_transport' bucket — a Deutschlandticket and a BahnCard are
    complements a customer can hold both of, not competing alternatives."""
    history = _mixed_public_transport_history()
    subs, catalog = _mixed_public_transport_subs_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    categories = {e["category"] for e in out["category_subscription_analysis"]}
    assert categories == {"public_transport", "long_distance_rail"}

    pt = _find_entry(out, "public_transport")
    ldr = _find_entry(out, "long_distance_rail")
    assert pt["applies_to_modes"] == ["public_transport", "regional_train"]
    assert ldr["applies_to_modes"] == ["long_distance_train"]


def test_regional_train_belongs_to_public_transport_not_long_distance_rail():
    """Regional trips are scoped exclusively to the public_transport bucket — a
    BahnCard's alternatives/current-subscription entries in long_distance_rail must
    never reflect regional_train spend (that would double-count against the
    public_transport bucket, which already owns regional_train). The fixture has 40
    raw legs (public_transport + regional_train) feeding public_transport and 20 raw
    legs (long_distance_train) feeding long_distance_rail — both scaled by the same
    annualization factor, so the ratio between them must stay ~2:1 regardless of
    regional_train leaking into the wrong bucket."""
    history = _mixed_public_transport_history()
    subs, catalog = _mixed_public_transport_subs_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    pt = _find_entry(out, "public_transport")
    ldr = _find_entry(out, "long_distance_rail")
    assert abs(pt["annual_trips"] - 2 * ldr["annual_trips"]) < 0.5


def test_bahncard_alternative_never_offered_in_public_transport_bucket():
    """A BahnCard-family plan must only ever appear as an alternative in
    long_distance_rail, never in public_transport (they're routed to different
    buckets entirely, not ranked against each other as substitutes)."""
    history = _mixed_public_transport_history()
    subs, catalog = _mixed_public_transport_subs_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    pt = _find_entry(out, "public_transport")
    ldr = _find_entry(out, "long_distance_rail")

    pt_names = {a["provider_plan_name"] for a in pt["alternatives"]}
    ldr_names = {a["provider_plan_name"] for a in ldr["alternatives"]}
    assert "BahnCard 25, 2. Klasse" not in pt_names
    assert "BahnCard 25, 2. Klasse" in ldr_names
    assert "Deutschlandticket" in pt_names
    assert "Deutschlandticket" not in ldr_names


def test_held_bahncard_discounts_regional_train_when_no_flat_pass_held():
    """A BahnCard's %-discount applies to regional_train fares too, not just
    long-distance ones -- but only when no Deutschlandticket-style flat pass is also
    held (otherwise regional trips are already free/covered by that pass, and which
    product is "really" discounting a given regional trip becomes ambiguous -- see
    the "8b."/BahnCard-on-regional-train comments in analysis.py).

    The fixture holds BahnCard 50 only (no Deutschlandticket) with regional_train
    legs left deliberately unattributed/undiscounted at the per-leg level (same
    convention as a real BahnCard: it discounts whatever fare you buy rather than
    being "checked into" a trip the way a flat pass is), so this exercises the
    category-level credit rather than any pre-existing per-leg discount.

    Local public_transport (bus/tram) legs are priced 3.0/leg, regional_train legs
    10.0/leg, 20 of each -- so regional_train is 10/13 of the bucket's
    no-subscription cost, and BahnCard 50 should halve exactly that slice:
    actual = no_subscription * (1 - 0.5 * 10/13).
    """
    history = _mixed_public_transport_history()
    subs, catalog = _mixed_public_transport_subs_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    pt = _find_entry(out, "public_transport")

    expected_actual = round(pt["no_subscription_annual_cost_eur"] * (1 - 0.5 * 10 / 13), 2)
    assert abs(pt["actual_annual_cost_eur"] - expected_actual) < 0.5
    assert pt["actual_annual_cost_eur"] < pt["no_subscription_annual_cost_eur"]
    # has_held_subs must reflect the BahnCard's real (if indirect) role here --
    # "no_subscription_needed" would misleadingly imply the low cost has nothing to
    # do with holding a subscription at all.
    assert pt["recommendation"] != "no_subscription_needed"


def test_bahncard_regional_discount_not_applied_when_flat_pass_also_held():
    """With a Deutschlandticket (or any flat_monthly public_transport pass) also
    held, regional trips are already fully covered by it -- the BahnCard's regional
    discount must NOT additionally apply (that would double-discount an already-free
    trip and reintroduce the exact ambiguity this feature deliberately avoids)."""
    history = _mixed_public_transport_history()
    subs, catalog = _mixed_public_transport_subs_and_catalog()
    subs = subs + [{
        "user_subscription_id": "us2", "subscription_status": "active", "subscription_id": "dt",
        "provider_plan_name": "Deutschlandticket", "subscription_category": "public_transport",
        "monthly_cost_eur": 49.0, "annual_cost_eur": None,
    }]
    out = analyze_portfolio(history, subs, catalog)
    pt = _find_entry(out, "public_transport")
    # No regional discount credited: actual cost is exactly effective spend (all
    # legs here are unattributed to the DT, since none carry its sub id) plus the
    # DT's own annual fee -- not reduced any further by the BahnCard.
    assert pt["actual_annual_cost_eur"] == round(
        pt["no_subscription_annual_cost_eur"] + 49.0 * 12, 2
    )


def test_heavy_long_distance_traveler_keeps_bahncard_50_over_alternatives():
    """A heavy long-distance traveler's BahnCard 50 should beat both BahnCard 25 (worse
    discount) and no-subscription — mirrors the real persona this whole redesign was
    checked against (Tobias Hahn, be6f3d9a-...)."""
    history = _mixed_public_transport_history()
    subs, catalog = _mixed_public_transport_subs_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    ldr = _find_entry(out, "long_distance_rail")
    assert ldr["recommendation"] == "keep_current"
    assert ldr["current_subscriptions"][0]["annual_net_savings_eur"] > 0
    alt = ldr["cheapest_alternative"]
    assert alt["provider_plan_name"] == "BahnCard 25, 2. Klasse"
    assert alt["estimated_annual_cost_eur"] > ldr["actual_annual_cost_eur"]


def test_employer_and_student_benefit_plans_never_offered():
    """An employer-sponsored Jobticket can't be verified as something this user
    actually has access to (no employer field on the user profile) — it must be
    excluded outright, like the disability/pension discount cards, not offered as a
    switch/pickup target."""
    history = _mixed_public_transport_history()
    subs, catalog = _mixed_public_transport_subs_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    pt = _find_entry(out, "public_transport")
    alt_names = {a["provider_plan_name"] for a in pt["alternatives"]}
    assert "Deutschlandticket Jobticket" not in alt_names
    assert "Deutschlandticket Jobticket" not in pt["non_comparable_alternatives"]


def test_full_alternatives_list_is_ranked_and_cheapest_matches_first():
    """The full comparison must be visible (not just the winner), so a rejected
    alternative like BahnCard 25 is verifiably considered, not silently dropped."""
    history = _mixed_public_transport_history()
    subs, catalog = _mixed_public_transport_subs_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    ldr = _find_entry(out, "long_distance_rail")
    names = [a["provider_plan_name"] for a in ldr["alternatives"]]
    assert names == ["BahnCard 25, 2. Klasse"]
    assert ldr["cheapest_alternative"] == ldr["alternatives"][0]


def test_alternative_cost_breakdown_sums_to_estimated_and_reports_savings():
    """Each alternative must show its own breakdown (fixed plan price + remaining
    pay-as-you-go cost) summing to estimated_annual_cost_eur, plus savings vs both
    pay-as-you-go and whatever's currently held — not just the final number."""
    history = [_leg(i, 20, 30.0, 15.0, "us1", mode="long_distance_train") for i in range(15)]
    subs, catalog = _bahncard_50_sub_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    entry = _find_entry(out, "long_distance_rail")
    alt = entry["cheapest_alternative"]
    assert alt["provider_plan_name"] == "BahnCard 25, 2. Klasse"
    assert round(alt["plan_annual_cost_eur"] + alt["estimated_pay_as_you_go_remainder_eur"], 2) == (
        alt["estimated_annual_cost_eur"]
    )
    assert alt["annual_savings_vs_no_subscription_eur"] == round(
        entry["no_subscription_annual_cost_eur"] - alt["estimated_annual_cost_eur"], 2
    )
    assert alt["annual_savings_vs_current_eur"] == round(
        entry["actual_annual_cost_eur"] - alt["estimated_annual_cost_eur"], 2
    )
    assert alt["annual_savings_vs_current_eur"] > 0


def test_no_current_subscription_alternative_vs_current_equals_vs_no_subscription():
    """With nothing currently held in this category, 'what you actually pay today'
    IS the pay-as-you-go cost — actual_annual_cost_eur is a real, known number
    either way (subscription or not), so annual_savings_vs_current_eur must be
    computed, not withheld as None. It necessarily equals
    annual_savings_vs_no_subscription_eur in this case, since actual_annual_cost_eur
    == no_subscription_annual_cost_eur when nothing is held."""
    history = [_leg(i, 4, 20.0, 20.0, None, mode="car_sharing") for i in range(80)]
    catalog = [{"id": "flat_car", "name": "Car Flat", "category": "car_sharing",
                "monthly_cost": 50.0, "annual_cost": None, "pricing_model": "flat_monthly"}]
    out = analyze_portfolio(history, [], catalog)
    entry = out["category_subscription_analysis"][0]
    alt = entry["cheapest_alternative"]
    assert entry["actual_annual_cost_eur"] == entry["no_subscription_annual_cost_eur"]
    assert alt["annual_savings_vs_current_eur"] == alt["annual_savings_vs_no_subscription_eur"]
    assert alt["annual_savings_vs_current_eur"] > 0


def _bahncard_50_1st_class_sub_and_catalog():
    subs = [{
        "user_subscription_id": "us1", "subscription_status": "active", "subscription_id": "bc50_1kl",
        "provider_plan_name": "BahnCard 50, 1. Klasse", "subscription_category": "public_transport",
        "monthly_cost_eur": None, "annual_cost_eur": 487.0,
    }]
    catalog = [
        {"id": "bc50_1kl", "name": "BahnCard 50, 1. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 487.0, "subscription_type": "subscription"},
        {"id": "bc25_1kl", "name": "BahnCard 25, 1. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 125.0, "subscription_type": "subscription"},
        {"id": "bc25_2kl", "name": "BahnCard 25, 2. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.90, "subscription_type": "subscription"},
    ]
    return subs, catalog


def test_bahncard_alternative_in_different_travel_class_is_not_comparable():
    """A 1st-class BahnCard holder must never be compared against a 2nd-class
    alternative (or vice versa) — trip legs don't record which class a historical
    fare was actually priced in, so mixing classes would silently understate or
    overstate the real saving. The cross-class plan must land in
    non_comparable_alternatives, never in alternatives."""
    history = [_leg(i, 20, 80.0, 40.0, "us1", mode="long_distance_train") for i in range(15)]
    subs, catalog = _bahncard_50_1st_class_sub_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    entry = _find_entry(out, "long_distance_rail")
    alt_names = {a["provider_plan_name"] for a in entry["alternatives"]}
    assert alt_names == {"BahnCard 25, 1. Klasse"}
    assert "BahnCard 25, 2. Klasse" in entry["non_comparable_alternatives"]


def test_subscription_coverage_labels_bahncard_as_long_distance_rail():
    """subscription_coverage must report a BahnCard's *display* category, not the raw
    DB row it shares with Deutschlandticket ("public_transport") — otherwise it reads
    as if the BahnCard covered local/regional trips, which it doesn't."""
    history = [_leg(i, 20, 30.0, 15.0, "us1", mode="long_distance_train") for i in range(15)]
    subs, catalog = _bahncard_50_sub_and_catalog()
    out = analyze_portfolio(history, subs, catalog)
    cov = out["subscription_coverage"]
    assert len(cov) == 1
    assert cov[0]["provider_plan_name"] == "BahnCard 50, 2. Klasse"
    assert cov[0]["subscription_category"] == "long_distance_rail"
    # ...and category_subscription_analysis must still attribute it to that same
    # bucket's current_subscriptions (the filter that reads subscription_coverage
    # must be updated in lockstep with the relabeling above).
    ldr = _find_entry(out, "long_distance_rail")
    assert [c["provider_plan_name"] for c in ldr["current_subscriptions"]] == ["BahnCard 50, 2. Klasse"]


def test_no_held_subscription_defaults_to_2nd_class_alternatives_only():
    """With no subscription held at all, there's no per-leg evidence of which class
    the recorded fares are priced in — 1st-class cards must not be silently offered
    against what might be 2nd-class reference costs."""
    history = [_leg(i, 20, 80.0, 80.0, None, mode="long_distance_train") for i in range(15)]
    catalog = [
        {"id": "bc25_2kl", "name": "BahnCard 25, 2. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 62.90, "subscription_type": "subscription"},
        {"id": "bc25_1kl", "name": "BahnCard 25, 1. Klasse", "category": "public_transport",
         "monthly_cost": None, "annual_cost": 125.0, "subscription_type": "subscription"},
    ]
    out = analyze_portfolio(history, [], catalog)
    entry = _find_entry(out, "long_distance_rail")
    alt_names = {a["provider_plan_name"] for a in entry["alternatives"]}
    assert alt_names == {"BahnCard 25, 2. Klasse"}
    assert "BahnCard 25, 1. Klasse" in entry["non_comparable_alternatives"]


# --------------------------------------------------------------------------- #
# Consumption-based alternative pricing (car-/bike-sharing, e-scooter plans   #
# with a linear per-km/per-hour/per-minute rate on file)                     #
# --------------------------------------------------------------------------- #

def test_simulate_consumption_cost_linear_rate():
    """Per-km + per-hour linear rate, no unlock fee/free-minutes/cap: a straightforward
    sum across legs, annualized the same way the rest of the engine annualizes."""
    legs = [
        {"distance": 10.0, "duration": 30.0, "day": date(2026, 1, 1)},
        {"distance": 10.0, "duration": 30.0, "day": date(2026, 2, 1)},
    ]
    plan = {"per_km_eur": 0.30, "per_hour_eur": 2.00}
    months_of_data = 1.0  # isolates the per-leg formula from annualization scaling
    per_leg = 2.00 * 0.5 + 0.30 * 10.0  # 1.00 + 3.00 = 4.00
    assert _simulate_consumption_annual_cost(plan, legs, months_of_data) == round(
        2 * per_leg / months_of_data * 12, 2
    )


def test_simulate_consumption_cost_returns_none_without_a_linear_rate():
    """A plan with no per-km/per-hour/per-minute rate on file (tiered per-ride pricing
    like Lime Prime, or no published rate at all like Bolt's bare PAYG) can't be
    honestly simulated — must return None, not silently price it as free."""
    no_rate_plan = {"per_km_eur": None, "per_hour_eur": None, "per_minute_eur": None}
    assert _simulate_consumption_annual_cost(no_rate_plan, [], 1.0) is None
    some_legs = [{"distance": 5.0, "duration": 5.0, "day": date(2026, 1, 1)}]
    assert _simulate_consumption_annual_cost({}, some_legs, 1.0) is None


def test_simulate_consumption_cost_deducts_free_minutes_before_billing():
    """Call a Bike Member Plus style: 30 free minutes per ride, then a per-minute
    rate — a 20-minute ride (under the free allowance) must cost nothing, and a
    50-minute ride must only be billed for the 20 minutes over the allowance."""
    plan = {"per_minute_eur": 0.10, "free_minutes_included": 30}
    short_ride = [{"distance": 2.0, "duration": 20.0, "day": date(2026, 1, 1)}]
    long_ride = [{"distance": 2.0, "duration": 50.0, "day": date(2026, 1, 1)}]
    assert _simulate_consumption_annual_cost(plan, short_ride, 1.0) == 0.0
    assert _simulate_consumption_annual_cost(plan, long_ride, 1.0) == round(2.00 / 1.0 * 12, 2)


def test_simulate_consumption_cost_applies_daily_cap_per_day_not_per_leg():
    """Call a Bike Starter style: three same-day rides would cost far more than the
    daily cap if summed independently — the cap must apply to each *day's* total, and
    a separate day's ride must be capped (or not) independently of other days."""
    plan = {"unlock_fee_eur": 1.00, "per_minute_eur": 0.12, "daily_cap_eur": 13.00}
    same_day_legs = [
        {"distance": 0.0, "duration": 60.0, "day": date(2026, 1, 1)} for _ in range(3)
    ]  # 1.00 + 0.12*60 = 8.20 each -> 24.60 raw for the day, capped down to 13.00
    assert _simulate_consumption_annual_cost(plan, same_day_legs, 1.0) == round(13.00 / 1.0 * 12, 2)

    two_days_one_leg_each = [
        {"distance": 0.0, "duration": 10.0, "day": date(2026, 1, 1)},
        {"distance": 0.0, "duration": 10.0, "day": date(2026, 1, 2)},
    ]  # 1.00 + 0.12*10 = 2.20 each, well under the cap on each of their own days
    assert _simulate_consumption_annual_cost(plan, two_days_one_leg_each, 1.0) == round(
        2 * 2.20 / 1.0 * 12, 2
    )


def _car_leg(i, gap_days, distance_km, duration_min, sub_id=None, start=datetime(2025, 7, 1)):
    """A car_sharing leg priced like MILES pay-as-you-go (1 EUR unlock + 0.79 EUR/km),
    carrying the estimated_distance_km/duration_minutes a consumption-based
    alternative needs to be simulated against."""
    ref = round(1.0 + distance_km * 0.79, 2)
    return {
        "leg_id": f"cl{i}", "trip_id": f"ct{i}",
        "started_at": (start + timedelta(days=i * gap_days)).isoformat(),
        "user_subscription_id": sub_id, "transport_mode": "car_sharing",
        "estimated_distance_km": distance_km, "duration_minutes": duration_min,
        "estimated_cost_eur": ref, "reference_cost_eur": ref,
        "estimated_co2_emissions": round(distance_km * 0.15, 3),
    }


def test_consumption_based_alternative_priced_and_not_non_comparable():
    """A car-sharing plan with a linear per-km/per-hour rate on file (e.g. a teilAuto-
    style membership) must be simulated leg-by-leg from actual distance/duration and
    surface as a real cheapest_alternative — not dumped into
    non_comparable_alternatives just because it isn't flat-rate or a BahnCard."""
    n, gap_days = 24, 15
    history = [_car_leg(i, gap_days, distance_km=10.0, duration_min=30.0) for i in range(n)]
    catalog = [{
        "id": "car_x", "name": "Car X", "category": "car_sharing",
        "monthly_cost": 20.0, "annual_cost": None, "pricing_model": "per_km_and_time",
        "per_km_eur": 0.30, "per_hour_eur": 2.00,
    }]
    out = analyze_portfolio(history, [], catalog)
    entry = _find_entry(out, "car_sharing")
    assert entry["non_comparable_alternatives"] == []
    alt = entry["cheapest_alternative"]
    assert alt["provider_plan_name"] == "Car X"
    assert "per-km/per-hour/per-minute rate" in alt["pricing_basis"]

    months_of_data = ((n - 1) * gap_days) / 30.44
    per_leg_cost = 2.00 * 0.5 + 0.30 * 10.0
    expected_remainder = round(n * per_leg_cost / months_of_data * 12, 2)
    assert alt["estimated_pay_as_you_go_remainder_eur"] == expected_remainder
    assert alt["plan_annual_cost_eur"] == 240.0  # 20 EUR/month * 12
    assert round(alt["plan_annual_cost_eur"] + alt["estimated_pay_as_you_go_remainder_eur"], 2) == (
        alt["estimated_annual_cost_eur"]
    )


def test_consumption_based_alternative_can_trigger_consider_subscribing():
    """The new simulated pricing must feed into the same recommendation logic as
    flat-rate/discount-card alternatives — a cheap-enough consumption-based plan must
    flip the recommendation to consider_subscribing, not just appear as an inert
    number nobody acts on."""
    n, gap_days = 40, 9
    history = [_car_leg(i, gap_days, distance_km=5.0, duration_min=15.0) for i in range(n)]
    catalog = [{
        "id": "car_cheap", "name": "Car Cheap", "category": "car_sharing",
        "monthly_cost": 5.0, "annual_cost": None, "pricing_model": "per_km_and_time",
        "per_km_eur": 0.10, "per_hour_eur": 0.50,
    }]
    out = analyze_portfolio(history, [], catalog)
    entry = _find_entry(out, "car_sharing")
    assert entry["recommendation"] == "consider_subscribing"
    assert entry["cheapest_alternative"]["provider_plan_name"] == "Car Cheap"
