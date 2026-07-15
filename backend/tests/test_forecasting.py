"""Unit tests for agent.engines.forecasting.forecast on the DETERMINISTIC path.

The LLM path is forced off with monkeypatch so these are fully reproducible and need
no API key. forecast() does ``from agent.llm import llm_available`` at call time, so
patching the attribute on ``agent.llm`` is sufficient.
"""

import json

import pytest

from agent.engines import forecast


@pytest.fixture(autouse=True)
def _force_deterministic(monkeypatch):
    monkeypatch.setattr("agent.llm.llm_available", lambda: False)


# Fixed anchor date for every test below. Its 90-day forecast window falls in
# Jul-Oct, which never coincides with the shared analyst_summary fixture's
# Jan-Mar 2026 data -- so the seasonal-override branch never triggers by accident
# for those tests, and tests stay reproducible regardless of the real wall-clock date.
_AS_OF = "2026-07-01"


def _month(trips, distance_km):
    return {
        "trips": trips, "distance_km": distance_km, "co2_kg": 0.0,
        "intrinsic_cost_eur": 0.0, "effective_cost_eur": 0.0,
    }


def test_output_shape(analyst_summary):
    out = forecast(analyst_summary, forecast_horizon_days=90, as_of_date=_AS_OF)
    assert out["forecast_horizon_days"] == 90
    assert len(out["scenarios"]) == 1
    assert out["scenarios"][0]["label"] == "baseline"
    assert "predicted_demand" in out["scenarios"][0]
    assert set(out["uncertainty_flags"]) >= {"life_event_detected"}
    assert isinstance(out["rationale_en"], str) and out["rationale_en"]
    assert isinstance(out["rationale_de"], str) and out["rationale_de"]
    assert isinstance(out["scenarios"][0]["description_en"], str) and out["scenarios"][0]["description_en"]
    assert isinstance(out["scenarios"][0]["description_de"], str) and out["scenarios"][0]["description_de"]


def test_one_prediction_per_dominant_pattern_mode(analyst_summary):
    out = forecast(analyst_summary, forecast_horizon_days=90, as_of_date=_AS_OF)
    modes = {p["mode"] for p in out["scenarios"][0]["predicted_demand"]}
    assert modes == {"public_transport", "regional_train"}


def test_full_window_average_used_when_no_seasonal_signal(analyst_summary):
    """public_transport's monthly_mode_breakdown (6, 12, 18 trips over Jan-Mar 2026)
    averages to 12/mo over its full 3-month window -> 36 trips over a 90-day horizon.
    (This fixture's full history happens to equal its most recent 3 months, so this
    alone doesn't prove full-window beats a recent-only window -- see
    test_full_window_average_smooths_a_short_recent_spike for that.) regional_train
    has no monthly data at all, so it falls back to the flat dominant_patterns
    average (4/mo -> 12)."""
    demand = {
        p["mode"]: p
        for p in forecast(analyst_summary, forecast_horizon_days=90, as_of_date=_AS_OF)["scenarios"][0]["predicted_demand"]
    }
    assert demand["public_transport"]["estimated_trips"] == 36
    assert "3 available month" in demand["public_transport"]["basis"]
    assert demand["regional_train"]["estimated_trips"] == 12
    assert "Historical monthly average" in demand["regional_train"]["basis"]


def test_full_window_average_smooths_a_short_recent_spike():
    """A mode with 4 quiet months (10 trips) followed by a 3-month spike (30 trips)
    must be forecast off the FULL 7-month average (~17.1/mo), not the recent
    3-month spike average (30/mo) -- a recency-window approach would extrapolate
    the spike as if it were the new normal, which is the exact bug this guards."""
    monthly = {
        "2026-01": {"commute": _month(10, 50.0)},
        "2026-02": {"commute": _month(10, 50.0)},
        "2026-03": {"commute": _month(10, 50.0)},
        "2026-04": {"commute": _month(10, 50.0)},
        "2026-05": {"commute": _month(30, 150.0)},
        "2026-06": {"commute": _month(30, 150.0)},
        "2026-07": {"commute": _month(30, 150.0)},
    }
    analyst_summary = {
        "dominant_patterns": [{"mode": "commute", "avg_trips_per_month": 17.14, "avg_distance_km": 5.0}],
        "detected_seasonality": "no significant seasonal variation detected",
        "current_contracts": [],
        "monthly_mode_breakdown": monthly,
    }
    # Window Aug-Oct: doesn't match any month above, so no seasonal override applies.
    out = forecast(analyst_summary, forecast_horizon_days=90, as_of_date="2026-08-01")
    demand = out["scenarios"][0]["predicted_demand"][0]

    full_window_avg = (10 * 4 + 30 * 3) / 7  # 17.14 trips/month
    assert demand["estimated_trips"] == int(full_window_avg * 3)
    assert demand["estimated_trips"] < 30 * 3  # must NOT just extrapolate the recent spike


def test_strong_seasonal_signal_overrides_full_window_average():
    """A mode that spikes every year specifically in Aug-Oct (~40 trips/month) but
    is quiet the rest of the year (~5 trips/month) must, when forecasting an
    Aug-Oct window, use the matching prior-year Aug-Oct average instead of the flat
    full-year average -- the flat average would drastically under-forecast the
    real seasonal demand for exactly the months being forecast."""
    quiet_months = [
        "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07",
        "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04",
    ]
    monthly = {m: {"e_scooter": _month(5, 15.0)} for m in quiet_months}
    monthly["2025-08"] = {"e_scooter": _month(40, 120.0)}
    monthly["2025-09"] = {"e_scooter": _month(40, 120.0)}
    monthly["2025-10"] = {"e_scooter": _month(40, 120.0)}

    analyst_summary = {
        "dominant_patterns": [{"mode": "e_scooter", "avg_trips_per_month": 10.6, "avg_distance_km": 3.0}],
        "detected_seasonality": "peak travel in August/September/October",
        "current_contracts": [],
        "monthly_mode_breakdown": monthly,
    }
    out = forecast(analyst_summary, forecast_horizon_days=90, as_of_date="2026-08-01")
    demand = out["scenarios"][0]["predicted_demand"][0]

    assert demand["estimated_trips"] == 120  # 40 trips/month x 3, not the flat ~10.6/mo average
    assert "seasonal" in demand["basis"].lower()


def test_mild_seasonal_variation_does_not_override():
    """A mode with only a mild difference (well under the 20% deviation threshold)
    between its full-window average and the same calendar months a year ago must
    keep the full-window average -- overriding on every small wiggle would just
    recreate the original recency-overreaction bug in a different guise."""
    other_months = [
        "2025-01", "2025-02", "2025-03", "2025-04", "2025-05", "2025-06", "2025-07",
        "2025-11", "2025-12", "2026-01", "2026-02", "2026-03", "2026-04",
    ]
    monthly = {m: {"bike": _month(20, 40.0)} for m in other_months}
    # Aug-Oct last year only ~10% above the rest -- well under the override threshold.
    monthly["2025-08"] = {"bike": _month(22, 44.0)}
    monthly["2025-09"] = {"bike": _month(22, 44.0)}
    monthly["2025-10"] = {"bike": _month(22, 44.0)}

    analyst_summary = {
        "dominant_patterns": [{"mode": "bike", "avg_trips_per_month": 20.4, "avg_distance_km": 2.0}],
        "detected_seasonality": "no significant seasonal variation detected",
        "current_contracts": [],
        "monthly_mode_breakdown": monthly,
    }
    out = forecast(analyst_summary, forecast_horizon_days=90, as_of_date="2026-08-01")
    demand = out["scenarios"][0]["predicted_demand"][0]

    full_window_avg = (20 * 13 + 22 * 3) / 16  # ~20.375 trips/month
    assert demand["estimated_trips"] == int(full_window_avg * 3)
    assert "seasonal" not in demand["basis"].lower()


def test_calendar_entries_are_flagged_not_analyzed(analyst_summary):
    out = forecast(
        analyst_summary,
        raw_calendar_entries=[{"summary": "Umzug nach Berlin", "date": "2026-05-01", "location": "Berlin", "description": ""}],
        forecast_horizon_days=90,
        as_of_date=_AS_OF,
    )
    assert "not analyzed" in out["rationale_en"].lower()
    assert "nicht analysiert" in out["rationale_de"].lower()


def test_reproducible(analyst_summary):
    a = forecast(analyst_summary, forecast_horizon_days=90, as_of_date=_AS_OF)
    b = forecast(analyst_summary, forecast_horizon_days=90, as_of_date=_AS_OF)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
