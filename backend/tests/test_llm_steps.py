"""Unit tests for the extracted single-call LLM steps (agent.llm_steps).

The LLM client is stubbed (no network, no key) so these are fully reproducible: each
test injects a canned model reply via monkeypatch and asserts the step parses it, and
that each step degrades to its deterministic fallback when the model is unavailable or
the reply can't be parsed.
"""

import json
from datetime import date
from types import SimpleNamespace

from agent.llm_steps import feasibility_judge, forecast_reasoner


class _StubLLM:
    def __init__(self, content):
        self._content = content

    def invoke(self, _messages):
        return SimpleNamespace(content=self._content)


def _patch_llm(monkeypatch, content, available=True):
    """Both steps do ``from agent.llm import ...`` at call time, so patching the
    attributes on ``agent.llm`` is what the step actually resolves."""
    monkeypatch.setattr("agent.llm.llm_available", lambda: available)
    monkeypatch.setattr("agent.llm.get_llm", lambda *a, **k: _StubLLM(content))


# --------------------------------------------------------------------------- #
# forecast_reasoner
# --------------------------------------------------------------------------- #

_FORECAST_JSON = json.dumps({
    "forecast_horizon_days": 90,
    "scenarios": [{
        "label": "baseline",
        "description_en": "EN description",
        "description_de": "DE Beschreibung",
        "predicted_demand": [
            {"mode": "public_transport", "estimated_trips": 30, "estimated_km": 240.0,
             "confidence": "high", "basis": "historical average"},
        ],
    }],
    "uncertainty_flags": {"life_event_detected": False, "life_event_type": None,
                          "recommend_re_evaluation_in_days": None},
    "rationale_en": "R EN",
    "rationale_de": "R DE",
})

_EMPTY_SUMMARY = {"dominant_patterns": [], "monthly_mode_breakdown": {}}


def test_reason_demand_parses_llm_json(monkeypatch):
    _patch_llm(monkeypatch, _FORECAST_JSON)
    out = forecast_reasoner.reason_demand(
        _EMPTY_SUMMARY, forecast_horizon_days=90, resolved_as_of_date=date(2026, 7, 1),
    )
    assert out is not None
    assert out["rationale_en"] == "R EN"
    assert out["scenarios"][0]["description_de"] == "DE Beschreibung"


def test_reason_demand_returns_none_on_unparseable(monkeypatch):
    _patch_llm(monkeypatch, "sorry, no JSON here")
    out = forecast_reasoner.reason_demand(
        _EMPTY_SUMMARY, forecast_horizon_days=90, resolved_as_of_date=date(2026, 7, 1),
    )
    assert out is None


def test_forecast_orchestrator_prefers_llm(monkeypatch):
    _patch_llm(monkeypatch, _FORECAST_JSON)
    out = forecast_reasoner.forecast(_EMPTY_SUMMARY, forecast_horizon_days=90, as_of_date="2026-07-01")
    assert out["rationale_en"] == "R EN"


def test_forecast_orchestrator_falls_back_to_projection(monkeypatch):
    _patch_llm(monkeypatch, _FORECAST_JSON, available=False)  # no key -> deterministic
    summary = {
        "dominant_patterns": [{"mode": "public_transport", "avg_trips_per_month": 10, "avg_distance_km": 5.0}],
        "monthly_mode_breakdown": {},
    }
    out = forecast_reasoner.forecast(summary, forecast_horizon_days=90, as_of_date="2026-07-01")
    assert "Deterministic fallback" in out["rationale_en"]
    assert out["scenarios"][0]["predicted_demand"][0]["mode"] == "public_transport"


# --------------------------------------------------------------------------- #
# feasibility_judge
# --------------------------------------------------------------------------- #

_JUDGE_JSON = json.dumps({
    "judgments": [
        {"candidate_id": "car_sharing->public_transport", "feasible": False, "confidence": "high",
         "reasoning": "customer states they need a car for caregiving",
         "excluded_reason": "onboarding says a car is needed for caregiving"},
    ],
    "rationale": "one candidate blocked by free text",
})


def _candidates():
    return [{
        "candidate_id": "car_sharing->public_transport",
        "from_category": "car_sharing", "to_category": "public_transport", "annual_trips": 100.0,
    }]


def test_judge_parses_llm_json(monkeypatch):
    _patch_llm(monkeypatch, _JUDGE_JSON)
    out = feasibility_judge.judge(_candidates(), {"travel_statement": "I need my car for the kids"})
    j = out["car_sharing->public_transport"]
    assert j["feasible"] is False
    assert j["excluded_reason"] == "onboarding says a car is needed for caregiving"


def test_judge_falls_back_without_key(monkeypatch):
    _patch_llm(monkeypatch, _JUDGE_JSON, available=False)
    out = feasibility_judge.judge(_candidates(), {})
    j = out["car_sharing->public_transport"]
    assert j["feasible"] is True
    assert j["confidence"] == "low"


def test_judge_partial_reply_falls_back_per_candidate(monkeypatch):
    # LLM only covers one of two candidates -> the uncovered one gets a fallback.
    _patch_llm(monkeypatch, _JUDGE_JSON)
    candidates = _candidates() + [{
        "candidate_id": "car_sharing->bike_sharing",
        "from_category": "car_sharing", "to_category": "bike_sharing", "annual_trips": 20.0,
    }]
    out = feasibility_judge.judge(candidates, {})
    assert out["car_sharing->public_transport"]["feasible"] is False
    assert out["car_sharing->bike_sharing"]["confidence"] == "low"  # fallback


def test_judge_empty_candidates_returns_empty():
    assert feasibility_judge.judge([], {}) == {}
