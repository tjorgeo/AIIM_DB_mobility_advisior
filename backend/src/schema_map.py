"""Domain helpers for the production schema (database/init/*.sql).

The deterministic agents compute over the production data model directly (full
transport-mode taxonomy, trips/legs, and the generic ``subscription_catalogs``).
This module holds the small amount of shared domain knowledge they need:

* ``group_mode`` — collapse the 11 production transport modes into the handful of
  display buckets the frontend's ``TravelModes`` component knows about. Grouping
  happens only at the *output* boundary; the agents keep full-fidelity modes
  internally.
* ``category_covers_mode`` — the coverage assumption that replaces the old
  hardcoded product logic: which transport modes a subscription category pays for.
* ``clean_row`` / ``jsonable`` — coerce psycopg2 scalars into JSON/arithmetic
  friendly types.
"""

from datetime import date, datetime
from decimal import Decimal

# Production ``transport_mode`` / ``main_transport_mode`` -> the display bucket the
# frontend's TravelModes MODE_META renders (train/bus/car/scooter known; bike/walk/
# other fall back to a generic icon + raw label).
_DISPLAY_MODE = {
    "walking": "walk",
    "bicycle": "bike",
    "bike_sharing": "bike",
    "public_transport": "bus",
    "regional_train": "train",
    "long_distance_train": "train",
    "car": "car",
    "car_sharing": "car",
    "ride_hailing": "car",
    "taxi": "car",
    "e_scooter": "scooter",
    "mixed": "other",
    "other": "other",
}


def group_mode(transport_mode) -> str:
    """Group a production transport mode into a frontend display bucket."""
    return _DISPLAY_MODE.get((transport_mode or "").lower(), "other")


# Which transport modes a subscription category pays for. This is the project's
# coverage assumption — the generic replacement for the old hardcoded product
# logic. Long-distance rail is intentionally not covered by a public-transport
# pass (it stays out-of-pocket).
_CATEGORY_COVERAGE = {
    "public_transport": {"public_transport", "regional_train"},
    "bike_sharing": {"bike_sharing"},
    "car_sharing": {"car_sharing"},
    "e_scooter": {"e_scooter"},
}


def category_covers_mode(subscription_category, transport_mode) -> bool:
    """True when a subscription of ``subscription_category`` pays for a leg taken
    with ``transport_mode``."""
    covered = _CATEGORY_COVERAGE.get((subscription_category or "").lower(), set())
    return (transport_mode or "").lower() in covered


def preferences_from_onboarding(row) -> dict:
    """Map onboarding 0-100 scores to the preference dict the agents consume."""
    def _as_int(value, default=50):
        try:
            return int(value)
        except (TypeError, ValueError):
            return default

    row = dict(row) if row else {}
    return {
        "cost_priority": _as_int(row.get("score_money")),
        "co2_priority": _as_int(row.get("score_emission")),
        "convenience_priority": _as_int(row.get("score_flexibility")),
        "class_preference": "2nd",
    }


def jsonable(value):
    """Coerce psycopg2 scalars (Decimal / date / datetime) into JSON- and
    arithmetic-friendly Python types."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def clean_row(row) -> dict:
    """Apply :func:`jsonable` to every value in a DB row mapping."""
    return {key: jsonable(val) for key, val in dict(row).items()}
