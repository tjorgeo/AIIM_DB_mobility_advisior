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


def test_output_shape(analyst_summary):
    out = forecast(analyst_summary, forecast_horizon_days=90)
    assert out["forecast_horizon_days"] == 90
    assert len(out["scenarios"]) == 1
    assert out["scenarios"][0]["label"] == "baseline"
    assert "predicted_demand" in out["scenarios"][0]
    assert set(out["uncertainty_flags"]) >= {"life_event_detected"}
    assert isinstance(out["rationale"], str) and out["rationale"]


def test_one_prediction_per_dominant_pattern_mode(analyst_summary):
    out = forecast(analyst_summary, forecast_horizon_days=90)
    modes = {p["mode"] for p in out["scenarios"][0]["predicted_demand"]}
    assert modes == {"public_transport", "regional_train"}


def test_recent_month_weighting_beats_flat_average(analyst_summary):
    """public_transport trends up in monthly_mode_breakdown (6→12→18 = avg 12/mo),
    above its flat dominant_patterns average of 10/mo. Over a 90-day (3-month) horizon
    the recent-weighted estimate is 36, not the flat 30. regional_train has no monthly
    data, so it uses the flat average (4/mo -> 12)."""
    demand = {p["mode"]: p for p in forecast(analyst_summary, forecast_horizon_days=90)["scenarios"][0]["predicted_demand"]}
    assert demand["public_transport"]["estimated_trips"] == 36
    assert "last 3 month" in demand["public_transport"]["basis"]
    assert demand["regional_train"]["estimated_trips"] == 12
    assert "Historical monthly average" in demand["regional_train"]["basis"]


def test_calendar_entries_are_flagged_not_analyzed(analyst_summary):
    out = forecast(
        analyst_summary,
        raw_calendar_entries=[{"summary": "Umzug nach Berlin", "date": "2026-05-01", "location": "Berlin", "description": ""}],
        forecast_horizon_days=90,
    )
    assert "not analyzed" in out["rationale"].lower()


def test_reproducible(analyst_summary):
    a = forecast(analyst_summary, forecast_horizon_days=90)
    b = forecast(analyst_summary, forecast_horizon_days=90)
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)
