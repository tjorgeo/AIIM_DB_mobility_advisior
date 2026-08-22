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

    def invoke(self, _messages, **_kwargs):
        # **_kwargs absorbs the ``config=`` the steps pass (see agent.observability.llm_config).
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


# --------------------------------------------------------------------------- #
# Single-language prompt + bounded output (the forecast-reasoner latency cuts)  #
# --------------------------------------------------------------------------- #

class _RecordingLLM:
    """Stub that captures the prompt and the client kwargs it was built with, so the
    prompt-shaping assertions below don't need a network call."""

    calls: list = []

    def __init__(self, content, **kwargs):
        self._content = content
        self._kwargs = kwargs

    def invoke(self, messages, **_ignored):
        _RecordingLLM.calls.append({"messages": messages, "kwargs": self._kwargs})
        return SimpleNamespace(content=self._content)


def _patch_recording_llm(monkeypatch, content=_FORECAST_JSON):
    _RecordingLLM.calls = []
    monkeypatch.setattr("agent.llm.llm_available", lambda: True)
    monkeypatch.setattr("agent.llm.get_llm", lambda *a, **k: _RecordingLLM(content, **k))
    return _RecordingLLM.calls


def test_reason_demand_asks_for_one_language_only(monkeypatch):
    """Writing every sentence in both languages was ~a third of this step's output
    tokens, and output tokens are what the user waits on. The prompt must name exactly
    one language's fields."""
    calls = _patch_recording_llm(monkeypatch)
    forecast_reasoner.reason_demand(
        _EMPTY_SUMMARY, forecast_horizon_days=90,
        resolved_as_of_date=date(2026, 7, 1), lang="en",
    )
    system_prompt = calls[0]["messages"][0].content
    assert "rationale_en" in system_prompt
    assert "rationale_de" not in system_prompt
    assert "description_en" in system_prompt
    assert "description_de" not in system_prompt
    assert "English" in system_prompt


def test_reason_demand_defaults_to_german_and_rejects_unknown_langs(monkeypatch):
    for requested in (None, "", "fr", "klingon"):
        calls = _patch_recording_llm(monkeypatch)
        forecast_reasoner.reason_demand(
            _EMPTY_SUMMARY, forecast_horizon_days=90,
            resolved_as_of_date=date(2026, 7, 1), lang=requested,
        )
        system_prompt = calls[0]["messages"][0].content
        assert "rationale_de" in system_prompt, requested
        assert "rationale_en" not in system_prompt, requested


def test_reason_demand_caps_its_output_tokens(monkeypatch):
    """A runaway generation must fail fast into the deterministic projection rather
    than burn the whole request timeout."""
    calls = _patch_recording_llm(monkeypatch)
    forecast_reasoner.reason_demand(
        _EMPTY_SUMMARY, forecast_horizon_days=90, resolved_as_of_date=date(2026, 7, 1),
    )
    assert calls[0]["kwargs"]["max_tokens"] == forecast_reasoner._MAX_OUTPUT_TOKENS


def test_forecast_threads_lang_through_to_the_prompt(monkeypatch):
    calls = _patch_recording_llm(monkeypatch)
    forecast_reasoner.forecast(
        _EMPTY_SUMMARY, forecast_horizon_days=90, as_of_date="2026-07-01", lang="en",
    )
    assert "English" in calls[0]["messages"][0].content


def test_deterministic_projection_stays_bilingual(monkeypatch):
    """The fallback is templated text, so writing both languages costs nothing — only
    the LLM path narrows to one."""
    _patch_llm(monkeypatch, _FORECAST_JSON, available=False)
    summary = {
        "dominant_patterns": [{"mode": "public_transport", "avg_trips_per_month": 10, "avg_distance_km": 5.0}],
        "monthly_mode_breakdown": {},
    }
    out = forecast_reasoner.forecast(summary, forecast_horizon_days=90, as_of_date="2026-07-01", lang="en")
    assert out["rationale_en"] and out["rationale_de"]
    assert out["scenarios"][0]["description_en"] and out["scenarios"][0]["description_de"]
