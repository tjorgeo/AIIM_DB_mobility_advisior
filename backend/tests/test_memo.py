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


def test_cancel_action_never_names_a_to_plan_even_when_cheapest_alternative_exists():
    """A cancel verdict means no alternative subscription is worth it - full stop.
    cheapest_alternative may still be populated (the least-bad of the rejected
    alternatives, e.g. a BahnCard 50 that's pricier than just cancelling) but must
    never be reported as a recommended "to" plan, or the action reads as a switch
    that contradicts the actual cancel recommendation."""
    analysis = {
        "category_subscription_analysis": [
            {
                "category": "long_distance_rail",
                "annual_trips": 4.0,
                "no_subscription_annual_cost_eur": 184.72,
                "actual_annual_cost_eur": 201.44,
                "current_subscriptions": [
                    {"provider_plan_name": "BahnCard 25, 2. Klasse", "annual_cost_eur": 62.9, "annual_net_savings_eur": -16.72}
                ],
                "cheapest_alternative": {
                    "provider_plan_name": "BahnCard 50, 2. Klasse",
                    "estimated_annual_cost_eur": 336.36,
                    "pricing_basis": "50% discount card (estimated from plan name)",
                },
                "recommended_alternative": None,
                "non_comparable_alternatives": [],
                "recommendation": "cancel_current_go_pay_as_you_go",
            }
        ]
    }
    memo = template_memos("Test User", analysis)
    assert len(memo["actions_required"]) == 1
    action = memo["actions_required"][0]
    assert action["action"] == "cancel_current_go_pay_as_you_go"
    assert action["from"] == "BahnCard 25, 2. Klasse"
    assert action["to"] is None
    assert "BahnCard 50" not in memo["memo_english"]


def test_category_line_names_which_modes_it_covers():
    """applies_to_modes is now an entry-level field (one bucket, one scope) — the memo
    must name which specific modes a category's figures cover, so a long_distance_rail
    line never reads as if it were about the same trips as public_transport."""
    analysis = {
        "category_subscription_analysis": [
            {
                "category": "long_distance_rail",
                "annual_trips": 40.0,
                "no_subscription_annual_cost_eur": 900.0,
                "actual_annual_cost_eur": 588.0,
                "applies_to_modes": ["long_distance_train"],
                "current_subscriptions": [
                    {"provider_plan_name": "BahnCard 50, 2. Klasse", "annual_cost_eur": 244.0,
                     "annual_net_savings_eur": -100.0}
                ],
                "cheapest_alternative": {
                    "provider_plan_name": "BahnCard 25, 2. Klasse",
                    "estimated_annual_cost_eur": 400.0,
                    "pricing_basis": "25% discount card (estimated from plan name)",
                },
                "non_comparable_alternatives": [],
                "recommendation": "switch_to_alternative",
            }
        ]
    }
    memo = template_memos("Test User", analysis)
    assert "long-distance trains" in memo["memo_english"]
    assert "Long-distance rail" in memo["memo_english"]


def test_forecast_outlook_picks_matching_language_description():
    """Regression: the scenario description is bilingual (description_en/
    description_de, see forecasting.py) — the English memo must never quote the
    German text or vice versa."""
    analysis = {
        "category_subscription_analysis": [
            {
                "category": "public_transport", "annual_trips": 20.0,
                "no_subscription_annual_cost_eur": 300.0, "actual_annual_cost_eur": 300.0,
                "current_subscriptions": [], "cheapest_alternative": None,
                "non_comparable_alternatives": [], "recommendation": "no_subscription_needed",
            }
        ],
    }
    forecaster_out = {
        "scenarios": [
            {"label": "baseline", "description_en": "Baseline scenario.", "description_de": "Basisszenario.",
             "predicted_demand": []},
            {"label": "post_relocation",
             "description_en": "English-only relocation description.",
             "description_de": "Rein deutsche Umzugsbeschreibung.",
             "predicted_demand": [], "projected_category_analysis": []},
        ],
        "uncertainty_flags": {"life_event_detected": True, "life_event_type": "relocation"},
    }
    memo = template_memos("Test User", analysis, forecaster_out)
    assert "English-only relocation description." in memo["memo_english"]
    assert "Rein deutsche Umzugsbeschreibung." not in memo["memo_english"]
    assert "Rein deutsche Umzugsbeschreibung." in memo["memo_german"]
    assert "English-only relocation description." not in memo["memo_german"]


def test_modal_shift_section_states_the_users_priority_scores():
    analysis = {
        "category_subscription_analysis": [],
        "preferences": {"cost_priority": 60, "co2_priority": 45, "convenience_priority": 80},
        "modal_shift_suggestions": [
            {
                "from_category": "e_scooter",
                "stay_annual_cost_eur": 422.54,
                "stay_annual_co2_kg": 4.51,
                "stay_annual_time_minutes": 980.7,
                "suggested_shift": {
                    "to_category": "bike_sharing",
                    "annual_cost_eur": 171.69,
                    "annual_co2_kg": 1.13,
                    "annual_time_minutes": 1066.6,
                    "feasibility": {"feasible": True, "confidence": "high", "reasoning": "..."},
                },
                "excluded_candidates": [],
            }
        ],
    }
    memo = template_memos("Test User", analysis)
    assert "60/100" in memo["memo_english"]
    assert "45/100" in memo["memo_english"]
    assert "80/100" in memo["memo_english"]
    assert "Kosten **60/100**" in memo["memo_german"]


def test_modal_shift_section_appears_when_a_shift_is_suggested():
    analysis = {
        "category_subscription_analysis": [],
        "modal_shift_suggestions": [
            {
                "from_category": "e_scooter",
                "stay_annual_cost_eur": 422.54,
                "stay_annual_co2_kg": 4.51,
                "stay_annual_time_minutes": 980.7,
                "suggested_shift": {
                    "to_category": "bike_sharing",
                    "annual_cost_eur": 171.69,
                    "annual_co2_kg": 1.13,
                    "annual_time_minutes": 1066.6,
                    "feasibility": {"feasible": True, "confidence": "high", "reasoning": "..."},
                },
                "excluded_candidates": [],
            }
        ],
    }
    memo = template_memos("Test User", analysis)
    assert "Bigger changes worth considering" in memo["memo_english"]
    assert "E-scooter" in memo["memo_english"] and "Bike sharing" in memo["memo_english"]
    assert "save an estimated €250.85/year" in memo["memo_english"]
    assert "Größere Veränderungen" in memo["memo_german"]
    # Low-confidence caveat must NOT appear for a high-confidence suggestion.
    assert "tentative" not in memo["memo_english"]


def test_modal_shift_section_omitted_when_nothing_beats_staying():
    analysis = {
        "category_subscription_analysis": [],
        "modal_shift_suggestions": [
            {"from_category": "car_sharing", "stay_annual_cost_eur": 500.0,
             "stay_annual_co2_kg": 50.0, "stay_annual_time_minutes": 300.0,
             "suggested_shift": None, "excluded_candidates": []},
        ],
    }
    memo = template_memos("Test User", analysis)
    assert "Bigger changes worth considering" not in memo["memo_english"]
    assert "Größere Veränderungen" not in memo["memo_german"]


def test_modal_shift_low_confidence_gets_caveat_and_no_raw_english_leaks_into_german():
    analysis = {
        "category_subscription_analysis": [],
        "modal_shift_suggestions": [
            {
                "from_category": "car_sharing",
                "stay_annual_cost_eur": 500.0, "stay_annual_co2_kg": 100.0, "stay_annual_time_minutes": 300.0,
                "suggested_shift": {
                    "to_category": "bike_sharing", "annual_cost_eur": 450.0,
                    "annual_co2_kg": 90.0, "annual_time_minutes": 300.0,
                    "feasibility": {
                        "feasible": True, "confidence": "low",
                        "reasoning": "LLM not available; free-text onboarding constraints were not checked.",
                    },
                },
                "excluded_candidates": [],
            }
        ],
    }
    memo = template_memos("Test User", analysis)
    assert "tentative idea" in memo["memo_english"]
    assert "vorläufige Idee" in memo["memo_german"]
    # The raw English reasoning string must never leak untranslated into the German memo.
    assert "not available" not in memo["memo_german"]


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
