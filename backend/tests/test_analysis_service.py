"""``AnalysisService``'s enrichment lifecycle — the parts that need no database.

``get_enrichment`` and the payload shaper are pure functions of a session snapshot, so
they can be exercised by stubbing the session store. The persistence paths
(``_persist``, ``_enrich_in_background``) need real tables and are covered by running
the stack, not here.
"""

from datetime import datetime, timedelta

import pytest

import analysis_service
from analysis_service import (
    ENRICHMENT_FAILED,
    ENRICHMENT_PENDING,
    ENRICHMENT_READY,
    ENRICHMENT_UNKNOWN,
    AnalysisService,
)


@pytest.fixture
def service():
    return AnalysisService()


def _snapshot(**overrides):
    snap = {
        "created_at": datetime.now().isoformat(),
        "status": "ready",
        "enrichment_status": ENRICHMENT_PENDING,
        "user": {"user_id": "u1", "name": "Test Persona"},
        "analyst_out": {"modal_shift_suggestions": [{"from_category": "car_sharing"}]},
        "forecaster_out": {"scenarios": [{"label": "baseline"}]},
        "memos": {"english": "EN", "german": "DE"},
    }
    snap.update(overrides)
    return snap


def _patch_session(monkeypatch, snapshot):
    monkeypatch.setattr(
        "agent.session.get_session",
        lambda session_id: {
            "session_id": session_id, "user_id": "u1",
            "snapshot": snapshot, "created_at": "now",
        },
    )


def test_get_enrichment_reports_pending_while_the_worker_runs(service, monkeypatch):
    _patch_session(monkeypatch, _snapshot())
    out = service.get_enrichment("s1")
    assert out["status"] == ENRICHMENT_PENDING


def test_get_enrichment_returns_the_llm_half_once_ready(service, monkeypatch):
    _patch_session(monkeypatch, _snapshot(enrichment_status=ENRICHMENT_READY))
    out = service.get_enrichment("s1")
    assert out["status"] == ENRICHMENT_READY
    assert out["forecaster_out"] == {"scenarios": [{"label": "baseline"}]}
    assert out["modal_shift_suggestions"] == [{"from_category": "car_sharing"}]
    assert out["memos"] == {"english": "EN", "german": "DE"}


def test_a_long_pending_session_is_reported_failed_not_polled_forever(service, monkeypatch):
    """A worker that died mid-pass will never write its result; the dashboard has to be
    told to stop waiting rather than poll a session that can't complete."""
    stale = datetime.now() - timedelta(
        seconds=analysis_service._ENRICHMENT_TIMEOUT_SECONDS + 60
    )
    _patch_session(monkeypatch, _snapshot(created_at=stale.isoformat()))
    assert service.get_enrichment("s1")["status"] == ENRICHMENT_FAILED


def test_a_ready_session_is_never_aged_out(service, monkeypatch):
    """Staleness only applies to 'pending' — an old but completed analysis is fine."""
    old = datetime.now() - timedelta(days=30)
    _patch_session(
        monkeypatch, _snapshot(created_at=old.isoformat(), enrichment_status=ENRICHMENT_READY)
    )
    assert service.get_enrichment("s1")["status"] == ENRICHMENT_READY


def test_snapshot_from_before_the_split_reports_unknown(service, monkeypatch):
    snap = _snapshot()
    del snap["enrichment_status"]
    _patch_session(monkeypatch, snap)
    assert service.get_enrichment("s1")["status"] == ENRICHMENT_UNKNOWN


def test_get_enrichment_on_an_unknown_session(service, monkeypatch):
    monkeypatch.setattr("agent.session.get_session", lambda session_id: None)
    assert service.get_enrichment("nope") is None


@pytest.mark.parametrize("created_at", [None, "", "not-a-date", 12345])
def test_unparseable_timestamps_are_not_treated_as_stale(service, created_at):
    """Better to keep polling a session with a broken timestamp than to declare a
    perfectly healthy enrichment failed."""
    assert service._is_stale(created_at) is False


# --------------------------------------------------------------------------- #
# Payload shaping                                                              #
# --------------------------------------------------------------------------- #

def test_payload_carries_enrichment_status_and_empty_llm_fields_while_pending(service):
    state = {
        "user": {"user_id": "u1", "name": "Test Persona"},
        "user_preferences": {},
        "subscriptions": [],
        "travel_history": [],
        "pricing_catalog": [],
        "analyst_out": {
            "total_co2_kg": 12.5,
            "category_subscription_analysis": [{"category": "public_transport",
                                                "actual_annual_cost_eur": 588.0}],
            "mode_breakdown": {},
        },
        "forecaster_out": None,
        "communicator_out": {
            "memo_english": "EN", "memo_german": "DE", "memo_source": "template",
            "total_estimated_savings_eur": 120.0, "actions_required": [],
        },
    }
    payload = service._payload_from_state(state, "rec1", "2026-01-01T00:00:00", "ready",
                                          ENRICHMENT_PENDING)

    # The figures are all here already — that is the point of answering this early.
    assert payload["enrichment_status"] == ENRICHMENT_PENDING
    assert payload["summary"]["total_co2_kg"] == 12.5
    assert payload["summary"]["total_estimated_savings_eur"] == 120.0
    assert payload["summary"]["total_actual_annual_cost_eur"] == 588.0
    # ...and the LLM-derived fields are empty rather than missing, so the frontend can
    # render them unconditionally.
    assert payload["summary"]["modal_shift_suggestions"] == []
    assert payload["raw_agent_payloads"]["forecaster"]["output"] == {}


def test_total_actual_annual_cost_sums_every_analyzed_category(service):
    analyst_out = {"category_subscription_analysis": [
        {"actual_annual_cost_eur": 588.0},
        {"actual_annual_cost_eur": 111.11},
    ]}
    assert service._total_actual_annual_cost(analyst_out) == 699.11
