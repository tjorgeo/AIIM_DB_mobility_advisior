"""Tests for agent.engines.scoring — the shared multi-criteria (cost/CO2/time)
weighting used by both the within-category recommendation (analysis.py,
reoptimize.py) and the cross-category modal-shift ranking (modal_shift.py)."""

import pytest

from agent.engines.scoring import pick_best_category_option, resolve_weights, score_candidates


# --------------------------------------------------------------------------- #
# resolve_weights
# --------------------------------------------------------------------------- #

def test_resolve_weights_all_none_falls_back_to_equal_thirds():
    weights = resolve_weights(None, None, None)
    assert weights["cost"] == pytest.approx(1 / 3)
    assert weights["co2"] == pytest.approx(1 / 3)
    assert weights["time"] == pytest.approx(1 / 3)


def test_resolve_weights_all_zero_falls_back_to_equal_thirds():
    weights = resolve_weights(0, 0, 0)
    assert weights == pytest.approx({"cost": 1 / 3, "co2": 1 / 3, "time": 1 / 3})


def test_resolve_weights_normalizes_to_sum_one():
    weights = resolve_weights(80, 50, 50)
    assert sum(weights.values()) == pytest.approx(1.0)
    assert weights["cost"] == pytest.approx(80 / 180)
    assert weights["co2"] == pytest.approx(50 / 180)
    assert weights["time"] == pytest.approx(50 / 180)


def test_resolve_weights_single_dominant_priority():
    weights = resolve_weights(0, 100, 0)
    assert weights == pytest.approx({"cost": 0.0, "co2": 1.0, "time": 0.0})


def test_resolve_weights_non_numeric_treated_as_zero():
    weights = resolve_weights("n/a", 50, None)
    assert weights == pytest.approx({"cost": 0.0, "co2": 1.0, "time": 0.0})


# --------------------------------------------------------------------------- #
# score_candidates
# --------------------------------------------------------------------------- #

def test_score_candidates_degenerate_range_is_neutral():
    """Identical values on an axis (the common within-category case: same physical
    trips regardless of which plan pays) must not produce an arbitrary ordering."""
    candidates = [
        {"annual_cost_eur": 100.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0},
        {"annual_cost_eur": 80.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0},
    ]
    scored = score_candidates(candidates, {"cost": 1 / 3, "co2": 1 / 3, "time": 1 / 3})
    assert scored[0]["score_breakdown"]["co2"] == 0.5
    assert scored[1]["score_breakdown"]["co2"] == 0.5
    assert scored[0]["score_breakdown"]["time"] == 0.5
    # cost axis has real variance (100 vs 80) -> not neutral, cheaper wins
    assert scored[1]["score"] > scored[0]["score"]


def test_score_candidates_missing_axis_dropped_and_weight_redistributed():
    """When an axis is absent for even one candidate, it's dropped for the whole
    decision (not treated as 0/worst for the candidates that do have it), and its
    weight redistributes proportionally across the remaining axes."""
    candidates = [
        {"annual_cost_eur": 100.0, "annual_co2_kg": 10.0, "annual_time_minutes": None},
        {"annual_cost_eur": 50.0, "annual_co2_kg": 20.0, "annual_time_minutes": None},
    ]
    scored = score_candidates(candidates, {"cost": 1 / 3, "co2": 1 / 3, "time": 1 / 3})
    assert "time" not in scored[0]["score_breakdown"]
    assert "time" not in scored[1]["score_breakdown"]
    # weight redistributed equally across cost+co2 -> 0.5 each
    assert scored[0]["score"] == pytest.approx(0.5 * 0.0 + 0.5 * 1.0)  # pricier, cleaner
    assert scored[1]["score"] == pytest.approx(0.5 * 1.0 + 0.5 * 0.0)  # cheaper, dirtier


def test_score_candidates_real_variance_ranks_by_weighted_score():
    candidates = [
        {"annual_cost_eur": 100.0, "annual_co2_kg": 50.0, "annual_time_minutes": 60.0, "id": "current"},
        {"annual_cost_eur": 110.0, "annual_co2_kg": 5.0, "annual_time_minutes": 60.0, "id": "green_alt"},
    ]
    # Heavily CO2-weighted -> the pricier-but-much-greener candidate should win.
    scored = score_candidates(candidates, {"cost": 0.1, "co2": 0.8, "time": 0.1})
    by_id = {c["id"]: c for c in scored}
    assert by_id["green_alt"]["score"] > by_id["current"]["score"]


# --------------------------------------------------------------------------- #
# pick_best_category_option
# --------------------------------------------------------------------------- #

_EQUAL_WEIGHTS = {"cost": 1 / 3, "co2": 1 / 3, "time": 1 / 3}


def test_pick_best_category_option_keeps_cheapest_current():
    current = {"annual_cost_eur": 100.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    no_subscription = {"annual_cost_eur": 150.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    alternatives = [
        {"annual_cost_eur": 120.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0, "_ref": {"provider_plan_name": "Alt"}},
    ]
    result = pick_best_category_option(current, no_subscription, alternatives, True, _EQUAL_WEIGHTS)
    assert result["recommendation"] == "keep_current"
    assert result["best_cost"] == 100.0
    assert result["winning_alternative"] is None


def test_pick_best_category_option_cancels_when_payg_cheapest():
    current = {"annual_cost_eur": 200.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    no_subscription = {"annual_cost_eur": 80.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    alternatives = [
        {"annual_cost_eur": 150.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0, "_ref": {"provider_plan_name": "Alt"}},
    ]
    result = pick_best_category_option(current, no_subscription, alternatives, True, _EQUAL_WEIGHTS)
    assert result["recommendation"] == "cancel_current_go_pay_as_you_go"
    assert result["best_cost"] == 80.0


def test_pick_best_category_option_switches_to_pricier_greener_alternative():
    """The core new behaviour: under CO2-heavy weights, a pricier alternative that
    dominates on CO2 (and matches on cost/time closely enough) outranks the cheapest
    one — this could never happen under the old pure-cost comparison."""
    current = {"annual_cost_eur": 100.0, "annual_co2_kg": 50.0, "annual_time_minutes": 60.0}
    no_subscription = {"annual_cost_eur": 200.0, "annual_co2_kg": 50.0, "annual_time_minutes": 60.0}
    cheap_alt = {"annual_cost_eur": 90.0, "annual_co2_kg": 50.0, "annual_time_minutes": 60.0,
                 "_ref": {"provider_plan_name": "Cheap"}}
    green_alt = {"annual_cost_eur": 110.0, "annual_co2_kg": 5.0, "annual_time_minutes": 60.0,
                 "_ref": {"provider_plan_name": "Green"}}
    weights = {"cost": 0.2, "co2": 0.7, "time": 0.1}

    result = pick_best_category_option(current, no_subscription, [cheap_alt, green_alt], True, weights)
    assert result["recommendation"] == "switch_to_alternative"
    assert result["winning_alternative"] == {"provider_plan_name": "Green"}
    assert result["best_cost"] == 110.0


def test_pick_best_category_option_insufficient_cost_data_when_nothing_priced():
    result = pick_best_category_option(None, None, [], True, _EQUAL_WEIGHTS)
    assert result == {
        "best_cost": None,
        "winning_alternative": None,
        "recommendation": "insufficient_cost_data",
        "score_breakdown": None,
    }


def test_pick_best_category_option_unheld_labels():
    no_subscription = {"annual_cost_eur": 80.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    alternatives = [
        {"annual_cost_eur": 60.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0, "_ref": {"provider_plan_name": "Alt"}},
    ]
    result = pick_best_category_option(None, no_subscription, alternatives, False, _EQUAL_WEIGHTS)
    assert result["recommendation"] == "consider_subscribing"
    assert result["winning_alternative"] == {"provider_plan_name": "Alt"}


def test_pick_best_category_option_deterministic_tie_break_prefers_current():
    """Exact ties (same score, same cost) resolve to 'current' over 'no_subscription'
    over alternatives — reproducing the historical pure-cost tie-break."""
    current = {"annual_cost_eur": 100.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    no_subscription = {"annual_cost_eur": 100.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    alternatives = [
        {"annual_cost_eur": 100.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0, "_ref": {"provider_plan_name": "Tied"}},
    ]
    result = pick_best_category_option(current, no_subscription, alternatives, True, _EQUAL_WEIGHTS)
    assert result["recommendation"] == "keep_current"


def test_pick_best_category_option_ignores_unpriced_current():
    """A held subscription whose cost can't be projected (forecast path, cost=None)
    must not win by default — it's simply excluded from the comparison."""
    current = {"annual_cost_eur": None, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    no_subscription = {"annual_cost_eur": 80.0, "annual_co2_kg": 10.0, "annual_time_minutes": 60.0}
    result = pick_best_category_option(current, no_subscription, [], True, _EQUAL_WEIGHTS)
    assert result["recommendation"] == "cancel_current_go_pay_as_you_go"
    assert result["best_cost"] == 80.0
