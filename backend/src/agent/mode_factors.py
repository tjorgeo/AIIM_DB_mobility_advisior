"""Deterministic per-mode CO2 and travel-time reference factors.

Production counterpart of ``database/seed/gen_personas.py``'s ``CO2_FACTOR`` table.
``CO2_KG_PER_KM`` MUST stay numerically in sync with that table for every mode it
defines (checked by ``backend/tests/test_mode_factors.py``, which imports
``gen_personas.py`` directly — no runtime coupling between the two, just a drift
guard) — modes gen_personas.py doesn't cover (car, walking, ride_hailing, taxi) are
extended here with reasonable published-order-of-magnitude figures for use cases that
never appear in the seed data.

Used only to price a HYPOTHETICAL trip on a mode/category the user did not actually
take it on (``agent/engines/modal_shift.py``'s cross-category comparison). A real
per-leg ``estimated_co2_emissions``/``duration_minutes`` is always preferred when
available and is never overridden by this table.

v1 approximation: ``SPEED_KMH_AND_OVERHEAD_MIN`` is hand-authored — there is no
empirical speed/duration source anywhere in this dataset (durations in seed data are
hand-authored per persona scenario, not formula-derived). Revisit with real speed
telemetry or a routing API if/when one becomes available; until then this is a
reasonable urban/regional-Germany order-of-magnitude estimate, not a measured figure.

``PLAUSIBLE_TRIP_DISTANCE_KM`` exists because the linear cost/CO2/time model above
will happily "price" ANY distance on ANY mode — nothing stops it from quoting a cost
for a 3km ICE ride or a 300km bike-share trip, neither of which actually exists as a
real service. Which modes can physically serve which distances is a geography/network
fact, not a judgment call, so it's enforced as a deterministic hard filter in
modal_shift.py rather than left for the LLM feasibility check to (unreliably) catch —
that check only reasons about the customer's own stated circumstances, not network
coverage.
"""

# kg CO2 per km, by transport_mode. The 6 values shared with
# database/seed/gen_personas.py::CO2_FACTOR must match exactly.
CO2_KG_PER_KM = {
    "public_transport": 0.04,
    "regional_train": 0.035,
    "long_distance_train": 0.03,
    "bike_sharing": 0.005,
    "car_sharing": 0.15,
    "e_scooter": 0.02,
    # Not in gen_personas.py's CO2_FACTOR (never a subscribable category / never a
    # modal-shift target), extended here for completeness of the raw transport_mode
    # taxonomy (see database/init/01_create_table.sql's transport_mode CHECK).
    "walking": 0.0,
    "bicycle": 0.0,
    "car": 0.17,
    "ride_hailing": 0.18,
    "taxi": 0.18,
}

# mode -> (avg_speed_kmh, fixed_overhead_minutes). The overhead covers unlocking a
# shared vehicle, walking to a stop/station, or waiting for a ride — added once per
# trip, not per km.
SPEED_KMH_AND_OVERHEAD_MIN = {
    "public_transport": (18.0, 5.0),
    "regional_train": (55.0, 8.0),
    "long_distance_train": (120.0, 12.0),
    "bike_sharing": (14.0, 3.0),
    "car_sharing": (28.0, 5.0),
    "e_scooter": (16.0, 2.0),
    "walking": (4.5, 0.0),
    "bicycle": (15.0, 1.0),
    "car": (30.0, 2.0),
    "ride_hailing": (28.0, 6.0),
    "taxi": (28.0, 4.0),
}


# mode -> (min_km, max_km) plausible range for a SINGLE trip actually taken on that
# mode. None for max_km = no realistic upper bound. Deliberately conservative for
# long_distance_train (Fernverkehr/ICE-IC network doesn't serve short urban hops) and
# for the short-range shared-mobility modes (no bike-share/e-scooter network spans
# regional distances) — the two directions that produced visibly wrong modal-shift
# suggestions (e.g. "switch your 3km bike-share trips to long-distance rail").
PLAUSIBLE_TRIP_DISTANCE_KM = {
    "public_transport": (0.0, 80.0),
    "regional_train": (3.0, 250.0),
    "long_distance_train": (80.0, None),
    "bike_sharing": (0.0, 15.0),
    "car_sharing": (0.0, None),
    "e_scooter": (0.0, 8.0),
    "walking": (0.0, 5.0),
    "bicycle": (0.0, 20.0),
    "car": (0.0, None),
    "ride_hailing": (0.0, 60.0),
    "taxi": (0.0, 60.0),
}


def is_plausible_trip_distance(mode: str, distance_km: float) -> bool:
    """Whether ``mode`` is realistically usable for a SINGLE trip of ``distance_km``
    — see ``PLAUSIBLE_TRIP_DISTANCE_KM``'s module note. An unknown mode is never
    excluded on this basis (nothing to check it against)."""
    bounds = PLAUSIBLE_TRIP_DISTANCE_KM.get((mode or "").lower())
    if bounds is None:
        return True
    lo, hi = bounds
    if distance_km < lo:
        return False
    if hi is not None and distance_km > hi:
        return False
    return True


def estimate_co2_kg(mode: str, distance_km: float) -> float | None:
    """CO2 (kg) for a ``distance_km`` trip on ``mode``, or ``None`` for an unknown mode
    (never guessed at with a fallback factor — an unpriceable candidate should be
    surfaced as such, not silently assigned an arbitrary number)."""
    factor = CO2_KG_PER_KM.get((mode or "").lower())
    if factor is None:
        return None
    return round(factor * max(distance_km, 0.0), 4)


def estimate_time_minutes(mode: str, distance_km: float) -> float | None:
    """Minutes for a SINGLE trip of ``distance_km`` on ``mode`` (speed-implied time
    plus the mode's fixed overhead), or ``None`` for an unknown mode.

    ``distance_km`` must be one trip's distance — callers annualize by multiplying
    the per-trip result by the annual trip count; the fixed overhead must never be
    applied to an already-annualized total.
    """
    factors = SPEED_KMH_AND_OVERHEAD_MIN.get((mode or "").lower())
    if factors is None:
        return None
    speed_kmh, overhead_min = factors
    if speed_kmh <= 0:
        return None
    return round((max(distance_km, 0.0) / speed_kmh) * 60.0 + overhead_min, 2)
