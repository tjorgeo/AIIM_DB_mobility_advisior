"""Adapters between the production schema (database/init/*.sql) and the
deterministic agents.

The agents reason over a simplified mobility vocabulary (modes like ``train`` /
``car`` and service slugs like ``deutschlandticket`` / ``bahncard_25_2nd``). The
production schema stores a richer set of transport modes and a free-form
subscription catalog, so these helpers translate one onto the other in a single
place shared by the pipeline, onboarding, chat and tool layers.
"""

import re
from datetime import date, datetime
from decimal import Decimal

# Production ``transport_mode`` / ``main_transport_mode`` -> simplified mode the
# analyst, forecaster and optimizer reason about.
_SIMPLE_MODE = {
    "walking": "walk",
    "bicycle": "bike",
    "bike_sharing": "bike",
    "public_transport": "train",
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


def simplify_mode(transport_mode) -> str:
    """Collapse a production transport mode into the agents' coarse vocabulary."""
    return _SIMPLE_MODE.get((transport_mode or "").lower(), "other")


def normalize_service(provider_plan_name, subscription_category=None, travel_class=None) -> str:
    """Map a ``subscription_catalogs`` plan to the service slug the optimizer and
    analyst reason about (e.g. ``deutschlandticket``, ``bahncard_50_2nd``,
    ``miles_sharing``). Falls back to a slugified plan name for unknown products."""
    name = (provider_plan_name or "").lower()
    cls = "1st" if str(travel_class) == "1" else "2nd"
    if "deutschlandticket" in name or "deutschland" in name or "49-euro" in name:
        return "deutschlandticket"
    if "bahncard 100" in name or "bc100" in name:
        return f"bahncard_100_{cls}"
    if "bahncard 50" in name or "bc50" in name:
        return f"bahncard_50_{cls}"
    if "bahncard 25" in name or "bc25" in name:
        return f"bahncard_25_{cls}"
    if (subscription_category or "") == "car_sharing" or "miles" in name or "sharing" in name:
        return "miles_sharing"
    slug = re.sub(r"[^a-z0-9]+", "_", name).strip("_")
    return slug or "unknown"


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
