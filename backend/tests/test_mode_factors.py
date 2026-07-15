"""Tests for agent.mode_factors — deterministic CO2/time reference tables.

The drift-guard test reads database/seed/gen_personas.py's CO2_FACTOR by parsing its
source (ast.literal_eval on the assignment) rather than importing the module: that
script runs seed-data generation and CSV writes unconditionally at module scope (no
``if __name__ == "__main__":`` guard), so importing it would have real side effects.
"""

import ast
from pathlib import Path

import pytest

from agent.mode_factors import CO2_KG_PER_KM, estimate_co2_kg, estimate_time_minutes

_GEN_PERSONAS_PATH = Path(__file__).resolve().parents[2] / "database" / "seed" / "gen_personas.py"


def _seed_co2_factor() -> dict:
    tree = ast.parse(_GEN_PERSONAS_PATH.read_text(encoding="utf-8"))
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "CO2_FACTOR" for target in node.targets
        ):
            return ast.literal_eval(node.value)
    raise AssertionError("CO2_FACTOR assignment not found in gen_personas.py")


def test_co2_factors_match_seed_generator():
    """mode_factors.CO2_KG_PER_KM must stay numerically in sync with the seed data
    generator's CO2_FACTOR for every mode the generator defines — a silent drift here
    would make production CO2 estimates diverge from the demo dataset's own model."""
    seed_factor = _seed_co2_factor()
    assert seed_factor, "sanity: seed CO2_FACTOR should be non-empty"
    for mode, value in seed_factor.items():
        assert CO2_KG_PER_KM[mode] == value, f"mode_factors.CO2_KG_PER_KM[{mode!r}] drifted from gen_personas.py"


def test_estimate_co2_kg_linear_in_distance():
    assert estimate_co2_kg("car_sharing", 100.0) == pytest.approx(15.0)
    assert estimate_co2_kg("car_sharing", 0.0) == 0.0
    assert estimate_co2_kg("bike_sharing", 40.0) == pytest.approx(0.2)


def test_estimate_co2_kg_unknown_mode_returns_none():
    assert estimate_co2_kg("teleportation", 10.0) is None


def test_estimate_time_minutes_includes_speed_and_overhead():
    # public_transport: 18 km/h, 5 min overhead -> 9km at 18km/h = 30 min + 5 = 35 min
    assert estimate_time_minutes("public_transport", 9.0) == pytest.approx(35.0)


def test_estimate_time_minutes_zero_distance_is_just_overhead():
    assert estimate_time_minutes("bike_sharing", 0.0) == pytest.approx(3.0)


def test_estimate_time_minutes_unknown_mode_returns_none():
    assert estimate_time_minutes("teleportation", 10.0) is None


def test_negative_distance_clamped_to_zero():
    """Defensive: a caller should never pass a negative distance, but this must not
    produce a negative CO2/time figure if it happens."""
    assert estimate_co2_kg("car_sharing", -5.0) == 0.0
    assert estimate_time_minutes("car_sharing", -5.0) == pytest.approx(5.0)  # just the overhead
