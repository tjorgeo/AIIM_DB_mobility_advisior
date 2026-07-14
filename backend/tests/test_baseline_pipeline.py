"""Tests for the single-call LLM baseline (agent/baseline_pipeline.py).

Everything here runs without a database or an LLM: the grounding builder is fed a
context dict shaped like ``load_context`` output, and the response parser is fed
canned LLM replies. The one LLM-touching path (``run_baseline``) is only checked
for its no-key guard.
"""

import json

import pytest

from agent.baseline_pipeline import (
    VALID_ACTIONS,
    build_grounding,
    parse_baseline_response,
    run_baseline,
)


@pytest.fixture
def ctx(subscriptions, travel_history, pricing_catalog):
    """A load_context-shaped context dict, reusing the shared engine fixtures."""
    return {
        "user": {
            "user_id": "u1",
            "name": "Julia Berger",
            "age": 31,
            "gender": "female",
            "life_stage": "working_professional",
            "home_city": "Köln",
        },
        "user_preferences": {"cost_sensitivity": 80},
        "subscriptions": subscriptions,
        "travel_history": travel_history,
        "pricing_catalog": pricing_catalog,
        "raw_calendar_entries": [
            {"summary": "Umzug nach Berlin", "date": "2026-09-01", "location": "Berlin", "description": ""}
        ],
    }


def test_build_grounding_carries_raw_data(ctx):
    grounding = build_grounding(ctx)

    # Raw inputs pass through un-derived.
    assert grounding["current_subscriptions"] is ctx["subscriptions"]
    assert grounding["subscription_catalog"] is ctx["pricing_catalog"]
    assert grounding["upcoming_calendar_entries"] == ctx["raw_calendar_entries"]
    assert grounding["user"]["age"] == 31
    # No PII beyond what the prompt needs, and no derived analysis fields.
    assert "email" not in grounding["user"]
    assert "analysis" not in grounding and "forecast" not in grounding

    # The whole payload must be JSON-serializable — it goes into the prompt verbatim.
    json.dumps(grounding, default=str)


def test_build_grounding_serializes_legs_as_csv(ctx):
    csv_block = build_grounding(ctx)["travel_history_csv"]
    lines = csv_block.splitlines()

    assert lines[0] == (
        "started_at,transport_mode,ticket_type,estimated_distance_km,duration_minutes,"
        "estimated_cost_eur,reference_cost_eur,estimated_co2_kg,user_subscription_id"
    )
    assert len(lines) == 1 + len(ctx["travel_history"])
    first_leg = ctx["travel_history"][0]
    assert lines[1].startswith(f"{first_leg['started_at']},{first_leg['transport_mode']},")
    # None fields become empty CSV cells, not the string "None".
    assert ",None," not in csv_block


def test_parse_accepts_fenced_json_with_prose():
    reply = (
        "Here is my analysis:\n```json\n"
        + json.dumps(
            {
                "recommended_changes": [
                    {
                        "category": "public_transport",
                        "action": "switch_to_alternative",
                        "from": ["Deutschlandticket"],
                        "to": "Deutschlandticket Jobticket",
                        "estimated_annual_savings_eur": 120.0,
                        "reasoning": "Cheaper for the same coverage.",
                    }
                ],
                "total_estimated_savings_eur": 120.0,
                "summary": "Switch the PT plan.",
            }
        )
        + "\n```\nLet me know if you need more."
    )

    result = parse_baseline_response(reply)
    assert result["recommended_changes"][0]["action"] == "switch_to_alternative"
    assert result["total_estimated_savings_eur"] == 120.0
    assert result["invalid_actions"] == []


def test_parse_flags_unknown_actions_without_rewriting():
    reply = json.dumps(
        {
            "recommended_changes": [
                {"category": "e_scooter", "action": "downgrade", "estimated_annual_savings_eur": 10},
                {"category": "bike_sharing", "action": "keep_current", "estimated_annual_savings_eur": 0},
            ],
            "total_estimated_savings_eur": 10,
        }
    )

    result = parse_baseline_response(reply)
    # The out-of-vocabulary action is reported but the change entry stays verbatim.
    assert result["invalid_actions"] == ["downgrade"]
    assert result["recommended_changes"][0]["action"] == "downgrade"
    assert "keep_current" in VALID_ACTIONS


@pytest.mark.parametrize(
    "reply",
    [
        "no json here at all",
        json.dumps({"summary": "missing the changes list"}),
        json.dumps({"recommended_changes": "not a list"}),
    ],
)
def test_parse_rejects_unusable_replies(reply):
    with pytest.raises(ValueError):
        parse_baseline_response(reply)


def test_run_baseline_requires_llm(monkeypatch):
    monkeypatch.setattr("agent.baseline_pipeline.llm_available", lambda: False)
    result = run_baseline("u1")
    assert "error" in result and "LLM" in result["error"]
