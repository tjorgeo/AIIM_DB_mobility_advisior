"""Unit tests for agent.engines.memo.template_memos (deterministic template fallback)."""

import pytest

from agent.engines import analyze_portfolio, optimize, template_memos


@pytest.fixture
def analysis_and_optimizer(travel_history, subscriptions, pricing_catalog, preferences):
    analysis = analyze_portfolio(travel_history, subscriptions)
    analysis["preferences"] = preferences  # the pipeline attaches this before the memo
    optimizer = optimize(travel_history, subscriptions, pricing_catalog, preferences)
    return analysis, optimizer


def test_returns_expected_keys(analysis_and_optimizer):
    analysis, optimizer = analysis_and_optimizer
    memo = template_memos("Alex Keller", analysis, optimizer)
    assert {
        "memo_english",
        "memo_german",
        "annual_savings_eur",
        "co2_savings_kg",
        "actions_required",
        "recommended_scenario_id",
    } <= set(memo)


def test_both_memos_nonempty_and_name_scenario_present(analysis_and_optimizer):
    analysis, optimizer = analysis_and_optimizer
    best = next(s for s in optimizer["scenarios"] if s["id"] == optimizer["best_recommendation_id"])
    memo = template_memos("Alex Keller", analysis, optimizer)
    for text in (memo["memo_english"], memo["memo_german"]):
        assert text.strip()
        assert "Alex Keller" in text
        assert best["label"] in text


def test_reads_savings_potential_estimate_eur_key(analysis_and_optimizer):
    """Regression guard: the memo must read ``savings_potential_estimate_eur`` (the
    exact key mismatch that once broke it). Drop every other analysis key and confirm
    it still renders from just that field + preferences."""
    _, optimizer = analysis_and_optimizer
    minimal_analysis = {"savings_potential_estimate_eur": 123.45, "preferences": {}}
    memo = template_memos("Test User", minimal_analysis, optimizer)
    assert "123.45" in memo["memo_english"]


def test_no_change_scenario_reads_cleanly():
    """A recommended scenario with no add/cancel changes should render the
    'no contract changes' wording in both languages."""
    optimizer = {
        "best_recommendation_id": "A",
        "baseline_annual_cost": 600.0,
        "scenarios": [
            {
                "id": "A",
                "label": "Cost-Optimized Portfolio",
                "annual_cost": 600.0,
                "annual_savings": 0.0,
                "co2_savings_kg": 0.0,
                "changes": [],
                "explanation": "Your current setup is already optimal.",
                "portfolio": [],
            }
        ],
    }
    analysis = {"savings_potential_estimate_eur": 0.0, "preferences": {}}
    memo = template_memos("Test User", analysis, optimizer)
    assert "No contract changes required." in memo["memo_english"]
    assert "Keine Vertragsänderungen erforderlich." in memo["memo_german"]
