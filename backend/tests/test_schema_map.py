"""Unit tests for agent.schema_map — the domain vocabulary helpers."""

from datetime import date
from decimal import Decimal

from agent.schema_map import (
    category_covers_mode,
    preferences_from_onboarding,
    jsonable,
    clean_row,
)


def test_category_covers_mode():
    # public-transport pass covers local transit + regional rail, NOT long-distance rail
    assert category_covers_mode("public_transport", "regional_train") is True
    assert category_covers_mode("public_transport", "public_transport") is True
    assert category_covers_mode("public_transport", "long_distance_train") is False
    # category only covers its own mode family
    assert category_covers_mode("car_sharing", "car_sharing") is True
    assert category_covers_mode("car_sharing", "e_scooter") is False
    # unknown / None never covers
    assert category_covers_mode(None, "public_transport") is False
    assert category_covers_mode("public_transport", None) is False


def test_preferences_from_onboarding_maps_scores():
    row = {"score_money": 90, "score_emission": 30, "score_flexibility": 70}
    prefs = preferences_from_onboarding(row)
    assert prefs["cost_priority"] == 90
    assert prefs["co2_priority"] == 30
    assert prefs["convenience_priority"] == 70


def test_preferences_from_onboarding_defaults_on_missing_or_none():
    assert preferences_from_onboarding(None)["cost_priority"] == 50
    assert preferences_from_onboarding({})["co2_priority"] == 50
    # non-numeric values fall back to the default rather than raising
    assert preferences_from_onboarding({"score_money": "abc"})["cost_priority"] == 50


def test_jsonable_coerces_scalars():
    assert jsonable(Decimal("12.50")) == 12.5
    assert isinstance(jsonable(Decimal("1")), float)
    assert jsonable(date(2026, 7, 2)) == "2026-07-02"
    assert jsonable("plain") == "plain"


def test_clean_row_applies_jsonable_to_every_value():
    row = {"cost": Decimal("9.99"), "day": date(2026, 1, 1), "name": "x"}
    cleaned = clean_row(row)
    assert cleaned == {"cost": 9.99, "day": "2026-01-01", "name": "x"}
