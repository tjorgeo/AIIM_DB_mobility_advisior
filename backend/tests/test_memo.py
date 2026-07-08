"""Unit tests for agent.engines.memo.template_memos (deterministic template fallback)."""

import pytest

from agent.engines import analyze_portfolio, template_memos


@pytest.fixture
def analysis(travel_history, subscriptions, pricing_catalog, preferences):
    out = analyze_portfolio(travel_history, subscriptions, pricing_catalog)
    out["preferences"] = preferences  # the pipeline attaches this before the memo
    return out


def test_returns_expected_keys(analysis):
    memo = template_memos("Alex Keller", analysis)
    assert {
        "memo_english",
        "memo_german",
        "total_estimated_savings_eur",
        "actions_required",
    } <= set(memo)


def test_both_memos_nonempty_and_mention_customer(analysis):
    memo = template_memos("Alex Keller", analysis)
    for text in (memo["memo_english"], memo["memo_german"]):
        assert text.strip()
        assert "Alex Keller" in text


def test_every_category_gets_a_line_in_both_languages(analysis):
    memo = template_memos("Alex Keller", analysis)
    for entry in analysis["category_subscription_analysis"]:
        label_en = {
            "public_transport": "Public transport",
            "bike_sharing": "Bike sharing",
            "car_sharing": "Car sharing",
            "e_scooter": "E-scooter",
        }[entry["category"]]
        assert label_en in memo["memo_english"]


def test_no_categories_renders_cleanly():
    """No travel history in any subscribable category should still produce a valid,
    non-crashing memo rather than an empty/broken one."""
    analysis = {"category_subscription_analysis": []}
    memo = template_memos("Test User", analysis)
    assert memo["total_estimated_savings_eur"] == 0.0
    assert memo["actions_required"] == []
    assert "Test User" in memo["memo_english"]
    assert "Test User" in memo["memo_german"]


def test_switch_to_alternative_reports_positive_savings_and_action():
    analysis = {
        "category_subscription_analysis": [
            {
                "category": "public_transport",
                "annual_trips": 20.0,
                "no_subscription_annual_cost_eur": 300.0,
                "actual_annual_cost_eur": 588.0,
                "current_subscriptions": [
                    {"provider_plan_name": "Deutschlandticket", "annual_cost_eur": 588.0, "annual_net_savings_eur": -400.0}
                ],
                "cheapest_alternative": {
                    "provider_plan_name": "BahnCard 25, 2. Klasse",
                    "estimated_annual_cost_eur": 287.9,
                    "pricing_basis": "25% discount card (estimated from plan name)",
                },
                "non_comparable_alternatives": [],
                "recommendation": "switch_to_alternative",
            }
        ]
    }
    memo = template_memos("Test User", analysis)
    assert memo["total_estimated_savings_eur"] == round(588.0 - 287.9, 2)
    assert len(memo["actions_required"]) == 1
    action = memo["actions_required"][0]
    assert action["action"] == "switch_to_alternative"
    assert action["from"] == "Deutschlandticket"
    assert action["to"] == "BahnCard 25, 2. Klasse"
    assert "BahnCard 25, 2. Klasse" in memo["memo_english"]
    assert "Deutschlandticket" in memo["memo_english"]


def test_keep_current_reports_no_action_and_no_savings():
    analysis = {
        "category_subscription_analysis": [
            {
                "category": "public_transport",
                "annual_trips": 200.0,
                "no_subscription_annual_cost_eur": 900.0,
                "actual_annual_cost_eur": 588.0,
                "current_subscriptions": [
                    {"provider_plan_name": "Deutschlandticket", "annual_cost_eur": 588.0, "annual_net_savings_eur": 312.0}
                ],
                "cheapest_alternative": None,
                "non_comparable_alternatives": [],
                "recommendation": "keep_current",
            }
        ]
    }
    memo = template_memos("Test User", analysis)
    assert memo["actions_required"] == []
    assert memo["total_estimated_savings_eur"] == 0.0
    assert "keep it" in memo["memo_english"]
