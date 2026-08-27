"""The analyze path's two halves: deterministic core vs. background LLM enrichment.

The point of the split is that every figure the dashboard shows is final in the fast
half, so these tests are mostly about proving that — the numbers a caller gets without
ever running a model must be identical to the ones they get with one. No DB and no LLM:
``load_context`` is stubbed with the shared fixtures and the two LLM steps are replaced
by recording fakes.
"""

import contextvars
import threading
import time

import pytest

from agent import pipeline
from agent.engines.forecasting import localized


@pytest.fixture
def ctx(travel_history, subscriptions, pricing_catalog):
    """What ``load_context`` returns, for the fixture persona."""
    return {
        "user": {"user_id": "u1", "name": "Test Persona", "age": 34},
        "user_preferences": {"cost_priority": 60, "co2_priority": 30, "convenience_priority": 10},
        "onboarding_raw": {"has_driving_license": True, "avoided_transport_modes": []},
        "subscriptions": subscriptions,
        "travel_history": travel_history,
        "pricing_catalog": pricing_catalog,
        "raw_calendar_entries": [],
    }


@pytest.fixture
def patched_context(monkeypatch, ctx):
    monkeypatch.setattr(pipeline, "load_context", lambda user_id: ctx)
    return ctx


# --------------------------------------------------------------------------- #
# The deterministic half stands alone                                          #
# --------------------------------------------------------------------------- #

def test_run_analysis_touches_no_llm_step(patched_context, monkeypatch):
    """The fast half must not call either model step — that is the entire latency win."""
    def boom(*a, **k):  # pragma: no cover - only runs if the split regresses
        raise AssertionError("run_analysis must not invoke an LLM step")

    monkeypatch.setattr(pipeline, "feasibility_judge", boom)
    monkeypatch.setattr(pipeline, "forecast", boom)

    state = pipeline.run_analysis("u1")
    assert state["forecaster_out"] is None
    assert "modal_shift_suggestions" not in state["analyst_out"]


def test_run_analysis_already_carries_every_dashboard_figure(patched_context):
    state = pipeline.run_analysis("u1")
    analyst = state["analyst_out"]
    communicator = state["communicator_out"]

    # The stat cards, the hero savings line and the per-category verdict.
    assert analyst["current_annual_spend_eur"] > 0
    assert analyst["total_co2_kg"] > 0
    assert analyst["category_subscription_analysis"]
    assert communicator["total_estimated_savings_eur"] is not None
    assert isinstance(communicator["actions_required"], list)
    assert communicator["memo_english"] and communicator["memo_german"]


def test_enrichment_never_moves_a_number(patched_context, monkeypatch):
    """The invariant the whole design rests on: folding the LLM half in must leave every
    figure exactly as the fast half computed it."""
    monkeypatch.setattr(pipeline, "feasibility_judge", lambda candidates, onboarding: {})
    monkeypatch.setattr(
        pipeline, "forecast",
        lambda summary, **kw: {
            "forecast_horizon_days": 365, "scenarios": [],
            "uncertainty_flags": {"life_event_detected": False},
            "rationale_de": "…", "rationale_en": "",
        },
    )

    state = pipeline.run_analysis("u1")
    before = {
        "categories": [dict(c) for c in state["analyst_out"]["category_subscription_analysis"]],
        "spend": state["analyst_out"]["current_annual_spend_eur"],
        "co2": state["analyst_out"]["total_co2_kg"],
        "savings": state["communicator_out"]["total_estimated_savings_eur"],
        "actions": [dict(a) for a in state["communicator_out"]["actions_required"]],
    }

    pipeline.apply_enrichment(state, pipeline.run_enrichment(state))

    assert state["analyst_out"]["category_subscription_analysis"] == before["categories"]
    assert state["analyst_out"]["current_annual_spend_eur"] == before["spend"]
    assert state["analyst_out"]["total_co2_kg"] == before["co2"]
    assert state["communicator_out"]["total_estimated_savings_eur"] == before["savings"]
    assert state["communicator_out"]["actions_required"] == before["actions"]


def test_run_full_analysis_matches_core_plus_enrichment(patched_context, monkeypatch):
    monkeypatch.setattr(pipeline, "feasibility_judge", lambda candidates, onboarding: {})
    monkeypatch.setattr(
        pipeline, "forecast",
        lambda summary, **kw: {
            "forecast_horizon_days": 365, "scenarios": [],
            "uncertainty_flags": {"life_event_detected": False},
            "rationale_de": "", "rationale_en": "",
        },
    )
    full = pipeline.run_full_analysis("u1")
    assert full["forecaster_out"] is not None
    assert "modal_shift_suggestions" in full["analyst_out"]


def test_missing_user_short_circuits(monkeypatch):
    monkeypatch.setattr(pipeline, "load_context", lambda user_id: {"error": "nope"})
    assert pipeline.run_analysis("ghost") == {"error": "nope"}
    assert pipeline.run_full_analysis("ghost") == {"error": "nope"}


# --------------------------------------------------------------------------- #
# The two LLM steps run concurrently, in a context that carries the trace       #
# --------------------------------------------------------------------------- #

def test_llm_steps_run_concurrently(patched_context, monkeypatch):
    """Both steps sleep; if they were sequential the pass would take ~2x one sleep."""
    delay = 0.3
    barrier = threading.Barrier(2, timeout=2.0)

    def slow_judge(candidates, onboarding):
        barrier.wait()  # raises BrokenBarrierError if the other step isn't also running
        time.sleep(delay)
        return {}

    def slow_forecast(summary, **kw):
        barrier.wait()
        time.sleep(delay)
        return {
            "forecast_horizon_days": 365, "scenarios": [],
            "uncertainty_flags": {"life_event_detected": False},
            "rationale_de": "", "rationale_en": "",
        }

    monkeypatch.setattr(pipeline, "feasibility_judge", slow_judge)
    monkeypatch.setattr(pipeline, "forecast", slow_forecast)

    state = pipeline.run_analysis("u1")
    started = time.perf_counter()
    pipeline.run_enrichment(state)
    elapsed = time.perf_counter() - started

    # The barrier already proves overlap; this guards the wall-clock claim too.
    assert elapsed < delay * 1.8


def test_worker_threads_inherit_the_trace_context(patched_context, monkeypatch):
    """Both steps run through ``contextvars.copy_context()``, so a ContextVar set by the
    enclosing trace is visible inside them.

    Without that, ``observability.llm_config`` would read an empty ``_trace_meta`` in the
    worker and each step would detach into its own root trace — splitting a run's token
    total, which the evaluation harness reports against.
    """
    probe = contextvars.ContextVar("probe", default=None)
    probe.set("set-on-the-calling-thread")
    seen = {}

    def capture_judge(candidates, onboarding):
        seen["judge"] = probe.get()
        return {}

    def capture_forecast(summary, **kw):
        seen["forecast"] = probe.get()
        return {
            "forecast_horizon_days": 365, "scenarios": [],
            "uncertainty_flags": {"life_event_detected": False},
            "rationale_de": "", "rationale_en": "",
        }

    monkeypatch.setattr(pipeline, "feasibility_judge", capture_judge)
    monkeypatch.setattr(pipeline, "forecast", capture_forecast)

    pipeline.run_enrichment(pipeline.run_analysis("u1"))
    assert seen == {
        "judge": "set-on-the-calling-thread",
        "forecast": "set-on-the-calling-thread",
    }


def test_lang_reaches_the_forecast_step(patched_context, monkeypatch):
    seen = {}

    def capture(summary, **kw):
        seen["lang"] = kw.get("lang")
        return {
            "forecast_horizon_days": 365, "scenarios": [],
            "uncertainty_flags": {"life_event_detected": False},
            "rationale_de": "", "rationale_en": "",
        }

    monkeypatch.setattr(pipeline, "feasibility_judge", lambda c, o: {})
    monkeypatch.setattr(pipeline, "forecast", capture)

    pipeline.run_enrichment(pipeline.run_analysis("u1"), lang="en")
    assert seen["lang"] == "en"


# --------------------------------------------------------------------------- #
# Single-language forecast prose                                               #
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize(
    "obj, lang, expected",
    [
        ({"rationale_de": "DE", "rationale_en": "EN"}, "de", "DE"),
        ({"rationale_de": "DE", "rationale_en": "EN"}, "en", "EN"),
        # The reasoner narrates one language per call — asking for the other one must
        # fall back to the text that exists, not render nothing.
        ({"rationale_de": "DE", "rationale_en": ""}, "en", "DE"),
        ({"rationale_de": "", "rationale_en": "EN"}, "de", "EN"),
        ({}, "de", ""),
        (None, "de", ""),
    ],
)
def test_localized_prefers_requested_then_whatever_exists(obj, lang, expected):
    assert localized(obj, "rationale", lang) == expected
