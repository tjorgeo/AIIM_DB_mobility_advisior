"""Tests for agent.engines.modal_shift — cross-category modal-shift comparison.

All tests run with ``use_llm=False`` (the deterministic fallback path) so they never
touch the network — the LLM feasibility call itself is out of scope for these
(structured-output parsing follows the same pattern already covered by
test_forecasting.py's LLM tests).
"""

from agent.engines.modal_shift import _hard_exclusion_reason, _price_candidate, build_modal_shift_suggestions


# --------------------------------------------------------------------------- #
# _hard_exclusion_reason
# --------------------------------------------------------------------------- #

def test_hard_exclusion_excludes_avoided_mode():
    onboarding = {"avoided_transport_modes": ["e_scooter"], "has_driving_license": True}
    assert _hard_exclusion_reason("e_scooter", "e_scooter", onboarding, avg_trip_km=3.0) is not None


def test_hard_exclusion_excludes_car_sharing_without_license():
    onboarding = {"avoided_transport_modes": [], "has_driving_license": False}
    assert _hard_exclusion_reason("car_sharing", "car_sharing", onboarding, avg_trip_km=10.0) is not None


def test_hard_exclusion_allows_car_sharing_with_license():
    onboarding = {"avoided_transport_modes": [], "has_driving_license": True}
    assert _hard_exclusion_reason("car_sharing", "car_sharing", onboarding, avg_trip_km=10.0) is None


def test_hard_exclusion_empty_onboarding_excludes_nothing_but_car_sharing():
    # No has_driving_license info at all -> car_sharing conservatively excluded,
    # everything else allowed (distances chosen well inside each mode's plausible range).
    assert _hard_exclusion_reason("bike_sharing", "bike_sharing", {}, avg_trip_km=3.0) is None
    assert _hard_exclusion_reason("public_transport", "public_transport", {}, avg_trip_km=10.0) is None
    assert _hard_exclusion_reason("car_sharing", "car_sharing", {}, avg_trip_km=10.0) is not None


def test_hard_exclusion_rejects_short_trips_shifted_to_long_distance_rail():
    """Regression: a customer's short local bike-share/ÖPNV trips must never be
    'shifted' onto long-distance rail — no ICE/IC serves a 3km urban hop, even
    though the linear per-km pricing model would happily quote a number for it."""
    onboarding = {"avoided_transport_modes": [], "has_driving_license": True}
    reason = _hard_exclusion_reason("long_distance_rail", "long_distance_train", onboarding, avg_trip_km=3.0)
    assert reason is not None
    assert "distance" in reason.lower()


def test_hard_exclusion_allows_genuinely_long_trips_onto_long_distance_rail():
    onboarding = {"avoided_transport_modes": [], "has_driving_license": True}
    assert _hard_exclusion_reason("long_distance_rail", "long_distance_train", onboarding, avg_trip_km=250.0) is None


def test_hard_exclusion_rejects_long_trips_shifted_to_short_range_modes():
    """The inverse case: a genuinely long-distance trip shouldn't be 'shifted' onto
    bike-sharing or e-scooter either — no shared-bike/scooter network spans
    regional distances."""
    onboarding = {"avoided_transport_modes": [], "has_driving_license": True}
    assert _hard_exclusion_reason("bike_sharing", "bike_sharing", onboarding, avg_trip_km=200.0) is not None
    assert _hard_exclusion_reason("e_scooter", "e_scooter", onboarding, avg_trip_km=200.0) is not None


# --------------------------------------------------------------------------- #
# _price_candidate
# --------------------------------------------------------------------------- #

def test_price_candidate_prices_from_per_km_rate():
    rates = {"public_transport": (0.25, "per_km")}
    candidate = _price_candidate("car_sharing", "public_transport", "public_transport", 100.0, 1000.0, rates)
    assert candidate is not None
    assert candidate["annual_cost_eur"] == 250.0
    assert candidate["annual_co2_kg"] == 40.0  # 1000km * 0.04 kg/km
    # per-trip distance 10km -> (10/18)*60 + 5 ≈ 38.33 min/trip * 100 trips
    assert candidate["annual_time_minutes"] > 3800

def test_price_candidate_none_when_no_historical_rate():
    assert _price_candidate("car_sharing", "bike_sharing", "bike_sharing", 100.0, 1000.0, {}) is None


def test_price_candidate_none_when_no_trips():
    rates = {"public_transport": (0.25, "per_km")}
    assert _price_candidate("car_sharing", "public_transport", "public_transport", 0.0, 0.0, rates) is None


# --------------------------------------------------------------------------- #
# build_modal_shift_suggestions
# --------------------------------------------------------------------------- #

def _mode_breakdown():
    return {
        "car_sharing": {"trips": 100, "distance_km": 1000.0, "intrinsic_cost_eur": 500.0},
        "public_transport": {"trips": 200, "distance_km": 1600.0, "intrinsic_cost_eur": 400.0},
        # bike_sharing / e_scooter / long_distance_train deliberately absent -> no
        # historical rate to price a shift onto them.
    }


def _category_analysis():
    return [
        {
            "category": "car_sharing",
            "annual_trips": 100.0,
            "annual_distance_km": 1000.0,
            "actual_annual_cost_eur": 500.0,
            "annual_co2_kg": 150.0,
            "annual_time_minutes": 6000.0,
        },
        {
            "category": "public_transport",
            "annual_trips": 0.0,  # no usage this window -> omitted from the output entirely
            "annual_distance_km": 0.0,
            "actual_annual_cost_eur": 0.0,
            "annual_co2_kg": 0.0,
            "annual_time_minutes": 0.0,
        },
    ]


def test_build_modal_shift_suggestions_only_covers_categories_with_trips():
    suggestions = build_modal_shift_suggestions(
        _mode_breakdown(), _category_analysis(), {}, {}, use_llm=False,
    )
    assert [s["from_category"] for s in suggestions] == ["car_sharing"]


def test_build_modal_shift_suggestions_excludes_avoided_and_unpriceable_targets():
    onboarding = {"avoided_transport_modes": ["e_scooter"], "has_driving_license": True}
    suggestions = build_modal_shift_suggestions(
        _mode_breakdown(), _category_analysis(), onboarding, {}, use_llm=False,
    )
    entry = suggestions[0]
    excluded_targets = {e["to_category"] for e in entry["excluded_candidates"]}
    # e_scooter: hard-excluded (avoided). bike_sharing: no historical rate in
    # mode_breakdown to price it from. long_distance_rail: car_sharing's ~10km/trip
    # average also isn't a realistic long-distance-rail trip (see the dedicated
    # distance-plausibility test below for the case where a rate WOULD exist).
    assert excluded_targets == {"e_scooter", "bike_sharing", "long_distance_rail"}


def test_build_modal_shift_suggestions_never_shifts_short_trips_onto_long_distance_rail():
    """End-to-end regression for the reported bug: a customer with short local
    bike-sharing trips AND a real historical long-distance-rail rate (e.g. from an
    unrelated BahnCard) must never see 'shift your bike-sharing trips to
    long-distance rail' — even though a rate exists to price it with, the distance
    makes it physically nonsensical."""
    mode_breakdown = {
        "bike_sharing": {"trips": 15, "distance_km": 45.0, "intrinsic_cost_eur": 96.0},  # 3km/trip
        # A real historical rate for long_distance_train IS present here (unlike the
        # fixture above) — without the distance-plausibility filter, this candidate
        # would get priced and could win on time/cost alone.
        "long_distance_train": {"trips": 2, "distance_km": 610.0, "intrinsic_cost_eur": 200.0},
    }
    category_analysis = [
        {
            "category": "bike_sharing", "annual_trips": 15.0, "annual_distance_km": 45.0,
            "actual_annual_cost_eur": 96.0, "annual_co2_kg": 0.2, "annual_time_minutes": 300.0,
        },
    ]
    onboarding = {"avoided_transport_modes": [], "has_driving_license": True}
    suggestions = build_modal_shift_suggestions(
        mode_breakdown, category_analysis, onboarding, {}, use_llm=False,
    )
    entry = suggestions[0]
    priced_targets = {c.get("to_category") for c in entry["candidates"] if c["candidate_id"] != "stay"}
    assert "long_distance_rail" not in priced_targets
    excluded = {e["to_category"]: e["excluded_reason"] for e in entry["excluded_candidates"]}
    assert "long_distance_rail" in excluded
    assert "distance" in excluded["long_distance_rail"].lower()


def test_build_modal_shift_suggestions_picks_dominant_shift():
    """public_transport is cheaper, greener AND faster than car_sharing for the same
    volume in this fixture — it should win regardless of weighting."""
    onboarding = {"avoided_transport_modes": [], "has_driving_license": True}
    suggestions = build_modal_shift_suggestions(
        _mode_breakdown(), _category_analysis(), onboarding, {}, use_llm=False,
    )
    entry = suggestions[0]
    assert entry["suggested_shift"] is not None
    assert entry["suggested_shift"]["to_category"] == "public_transport"
    assert entry["suggested_shift"]["annual_cost_eur"] < entry["stay_annual_cost_eur"]
    assert entry["suggested_shift"]["annual_co2_kg"] < entry["stay_annual_co2_kg"]


def test_build_modal_shift_suggestions_use_llm_false_marks_low_confidence():
    onboarding = {"avoided_transport_modes": [], "has_driving_license": True}
    suggestions = build_modal_shift_suggestions(
        _mode_breakdown(), _category_analysis(), onboarding, {}, use_llm=False,
    )
    shift = suggestions[0]["suggested_shift"]
    assert shift["feasibility"]["feasible"] is True
    assert shift["feasibility"]["confidence"] == "low"


def test_build_modal_shift_suggestions_no_dominant_shift_stays():
    """When the shift candidate loses on 2 of 3 axes (cost and time here — only CO2
    favors switching), staying wins under equal weights; suggested_shift is None but
    the priced candidate still shows up in `candidates` for transparency."""
    mode_breakdown = {
        "car_sharing": {"trips": 100, "distance_km": 1000.0, "intrinsic_cost_eur": 500.0},
        # A much more expensive public_transport rate this time, so shifting costs
        # far more than staying.
        "public_transport": {"trips": 200, "distance_km": 1600.0, "intrinsic_cost_eur": 4000.0},
    }
    category_analysis = [
        {
            "category": "car_sharing",
            "annual_trips": 100.0,
            "annual_distance_km": 1000.0,
            "actual_annual_cost_eur": 500.0,
            "annual_co2_kg": 150.0,
            # Faster than the shift candidate's ~3833 min/year (public_transport's
            # 18km/h is slower than car_sharing's 28km/h at this distance) — so the
            # shift candidate also loses on time, not just cost.
            "annual_time_minutes": 3000.0,
        },
        {"category": "public_transport", "annual_trips": 0.0, "annual_distance_km": 0.0,
         "actual_annual_cost_eur": 0.0, "annual_co2_kg": 0.0, "annual_time_minutes": 0.0},
    ]
    onboarding = {"avoided_transport_modes": [], "has_driving_license": True}
    suggestions = build_modal_shift_suggestions(
        mode_breakdown, category_analysis, onboarding, {}, use_llm=False,
    )
    entry = suggestions[0]
    assert entry["suggested_shift"] is None
    assert any(c["candidate_id"] == "stay" for c in entry["candidates"])
