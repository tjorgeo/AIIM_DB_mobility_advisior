"""
One-time migration: CSV files → SQLite database.

Fixes applied during migration:
  - PostgreSQL array literals {"a","b"} → proper JSON arrays ["a","b"]
  - String booleans "true"/"false" / "True"/"False" → 0/1 integers
  - Generation metadata columns stripped from users and trips
  - CO2 estimated per trip leg (mode × distance × emission factor)
  - subscription_products enriched with valid_modes / combinable_with

Run from the repo root:
    uv run python db/migrate_csv_to_sqlite.py
"""

import json
import re
import sys
import uuid
from pathlib import Path

import pandas as pd

# Make db_utils importable regardless of working directory
sys.path.insert(0, str(Path(__file__).parent.parent))

from db.db_utils import DB_PATH, executemany, init_db
from db.seed_subscription_products import seed_products

DATA_DIR = Path(__file__).parent.parent / "data"

# ---------------------------------------------------------------------------
# CO2 emission factors (kg per km) by transport mode
# Source: rough EEA averages, good enough for prototype
# ---------------------------------------------------------------------------
CO2_KG_PER_KM: dict[str, float] = {
    "walking": 0.0,
    "bike": 0.0,
    "shared_bike": 0.0,
    "regional_train": 0.006,
    "long_distance_train": 0.004,
    "subway": 0.005,
    "tram": 0.005,
    "bus": 0.089,
    "car": 0.171,
    "car_sharing": 0.150,
    "ride_hailing": 0.171,
    "shared_scooter": 0.067,
}

# ---------------------------------------------------------------------------
# Subscription product enrichments not in the original CSV
# ---------------------------------------------------------------------------
PRODUCT_ENRICHMENTS: dict[str, dict] = {
    "DT-49":   {"valid_modes": ["bus","tram","subway","regional_train","shared_bike"],
                 "cancellation_notice_months": 1, "auto_renews": 1,
                 "combinable_with": ["BC25-2","BC25-1","BC50-2","BC50-1","BC100-2","BC100-1"]},
    "BC25-2":  {"valid_modes": ["regional_train","long_distance_train"],
                 "cancellation_notice_months": 3, "auto_renews": 1,
                 "combinable_with": ["DT-49"]},
    "BC25-1":  {"valid_modes": ["regional_train","long_distance_train"],
                 "cancellation_notice_months": 3, "auto_renews": 1,
                 "combinable_with": ["DT-49"]},
    "BC50-2":  {"valid_modes": ["regional_train","long_distance_train"],
                 "cancellation_notice_months": 3, "auto_renews": 1,
                 "combinable_with": ["DT-49"]},
    "BC50-1":  {"valid_modes": ["regional_train","long_distance_train"],
                 "cancellation_notice_months": 3, "auto_renews": 1,
                 "combinable_with": ["DT-49"]},
    "BC100-2": {"valid_modes": ["regional_train","long_distance_train"],
                 "cancellation_notice_months": 3, "auto_renews": 1,
                 "combinable_with": []},
    "BC100-1": {"valid_modes": ["regional_train","long_distance_train"],
                 "cancellation_notice_months": 3, "auto_renews": 1,
                 "combinable_with": []},
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def pg_array_to_json(value: str | float) -> str:
    """Convert PostgreSQL array literal {"a","b"} to JSON ["a","b"]."""
    if not isinstance(value, str) or not value.strip().startswith("{"):
        return "[]"
    # Strip outer braces, split on commas, strip quotes
    inner = value.strip().lstrip("{").rstrip("}")
    items = [item.strip().strip('"') for item in inner.split(",") if item.strip()]
    return json.dumps(items)


def to_bool_int(value) -> int:
    """Convert any truthy string or bool to 0/1."""
    if isinstance(value, (int, float)):
        return int(bool(value))
    if isinstance(value, str):
        return 1 if value.strip().lower() in ("true", "1", "yes") else 0
    return 0


def estimate_co2(mode: str, distance_km: float) -> float:
    factor = CO2_KG_PER_KM.get(str(mode).lower(), 0.05)  # default: low-emission transit
    return round(factor * float(distance_km or 0), 4)


# ---------------------------------------------------------------------------
# Migrate users
# ---------------------------------------------------------------------------

USERS_KEEP = [
    "user_id", "username", "email", "external_auth_id",
    "first_name", "last_name", "display_name", "date_of_birth",
    "gender", "life_stage",
    "home_city", "home_postal_code", "home_country_code", "city_type",
    "job_industry", "employment_status", "income_range",
    "working_pattern", "commute_frequency",
    "has_car", "has_bike", "has_driving_license",
    "public_transport_affinity", "preferred_modes", "avoided_modes",
    "preferred_activity_types", "leisure_intensity",
    "evening_activity_frequency", "weekend_activity_frequency",
    "price_sensitivity", "purchase_channel_preference",
    "employer_reimbursement_available",
]

USERS_BOOL = ["has_car", "has_bike", "has_driving_license", "employer_reimbursement_available"]
USERS_JSON = ["preferred_modes", "avoided_modes", "preferred_activity_types"]


def migrate_users(df: pd.DataFrame) -> list[tuple]:
    rows = []
    for _, r in df.iterrows():
        row = {col: r.get(col) for col in USERS_KEEP}
        for col in USERS_BOOL:
            row[col] = to_bool_int(row[col])
        for col in USERS_JSON:
            row[col] = pg_array_to_json(row[col])
        rows.append(tuple(row.values()))
    return rows


# ---------------------------------------------------------------------------
# Migrate trips
# ---------------------------------------------------------------------------

TRIPS_KEEP = [
    "trip_id", "user_id", "start_ts", "end_ts", "weekday",
    "origin_city", "origin_place_type", "origin_label",
    "destination_city", "destination_place_type", "destination_label",
    "trip_purpose", "main_mode", "modes_used",
    "distance_km", "duration_min", "estimated_cost_eur",
    "ticket_product_used", "is_commute", "is_recurring_pattern",
    "planning_style",
]

TRIPS_BOOL = ["is_commute", "is_recurring_pattern"]
TRIPS_JSON = ["modes_used"]


def migrate_trips(df: pd.DataFrame) -> list[tuple]:
    rows = []
    for _, r in df.iterrows():
        row = {col: r.get(col) for col in TRIPS_KEEP}
        for col in TRIPS_BOOL:
            row[col] = to_bool_int(row[col])
        for col in TRIPS_JSON:
            row[col] = pg_array_to_json(row[col])
        # Add computed CO2
        row["co2_kg"] = estimate_co2(row["main_mode"], row["distance_km"])
        row["data_source"] = "synthetic"
        rows.append(tuple(row.values()))
    return rows


# ---------------------------------------------------------------------------
# Migrate trip legs
# ---------------------------------------------------------------------------

LEGS_KEEP = [
    "leg_id", "trip_id", "sequence_no", "start_ts", "end_ts",
    "mode", "origin_label", "destination_label",
    "distance_km", "duration_min",
    "ticket_required", "ticket_product_used", "leg_note",
]

LEGS_BOOL = ["ticket_required"]


def migrate_legs(df: pd.DataFrame) -> list[tuple]:
    rows = []
    for _, r in df.iterrows():
        row = {col: r.get(col) for col in LEGS_KEEP}
        for col in LEGS_BOOL:
            row[col] = to_bool_int(row[col])
        row["co2_kg"] = estimate_co2(row["mode"], row["distance_km"])
        rows.append(tuple(row.values()))
    return rows


# ---------------------------------------------------------------------------
# Migrate subscription products
# ---------------------------------------------------------------------------

def migrate_subscription_products(df: pd.DataFrame) -> list[tuple]:
    rows = []
    for _, r in df.iterrows():
        pid = str(r["product_id"])
        enrichment = PRODUCT_ENRICHMENTS.get(pid, {})
        rows.append((
            pid,
            r.get("product_name"),
            r.get("type"),
            r.get("monthly_cost_eur"),
            r.get("annual_cost_eur"),
            r.get("discount_pct"),
            r.get("travel_class"),
            r.get("coverage_scope"),
            json.dumps(enrichment.get("valid_modes", [])),
            r.get("min_commitment_months"),
            enrichment.get("cancellation_notice_months"),
            enrichment.get("auto_renews", 1),
            json.dumps(enrichment.get("combinable_with", [])),
            1,  # is_active
            r.get("notes"),
        ))
    return rows


# ---------------------------------------------------------------------------
# Seed synthetic user_subscriptions from profile data
# ---------------------------------------------------------------------------

def seed_user_subscriptions(profiles_df: pd.DataFrame) -> list[tuple]:
    """
    The original CSVs have no user_subscriptions table.
    Seed one row per user based on current_ticket_product in their profile,
    mapping the free-text value to a product_id in subscription_products.
    """
    product_map = {
        "monthly_pass":   "DT-49",
        "subscription":   "DT-49",
        "job_ticket":     "DT-49",
    }
    rows = []
    for _, r in profiles_df.iterrows():
        product_key = str(r.get("current_ticket_product", "")).strip()
        product_id = product_map.get(product_key)
        if not product_id:
            continue  # 'none' or unknown → no active subscription to seed
        rows.append((
            str(uuid.uuid4()),
            r["user_id"],
            product_id,
            "active",
            "2026-01-01",   # synthetic start
            None,
            None,           # actual monthly cost unknown from synthetic data
            1,
            None,
            "synthetic",
        ))
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("Initialising database schema...")
    init_db()

    # ── Users ────────────────────────────────────────────────────────────────
    print("Migrating users...")
    profiles_df = pd.read_csv(DATA_DIR / "user_profiles.csv")
    user_rows = migrate_users(profiles_df)
    cols = USERS_KEEP + USERS_JSON  # JSON cols already replaced in-place
    user_col_names = ", ".join(USERS_KEEP)
    user_placeholders = ", ".join("?" * len(USERS_KEEP))
    executemany(
        f"INSERT OR REPLACE INTO users ({user_col_names}) VALUES ({user_placeholders})",
        user_rows,
    )
    print(f"  {len(user_rows)} users inserted.")

    # ── Subscription products ─────────────────────────────────────────────────
    print("Seeding subscription products from catalogue...")
    seed_products()

    # ── User subscriptions ────────────────────────────────────────────────────
    print("Seeding user_subscriptions from profile data...")
    us_rows = seed_user_subscriptions(profiles_df)
    executemany(
        """INSERT OR IGNORE INTO user_subscriptions
           (user_subscription_id, user_id, product_id, status, start_date,
            end_date, monthly_cost_actual_eur, auto_renew,
            cancellation_requested_at, source)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        us_rows,
    )
    print(f"  {len(us_rows)} user subscriptions seeded.")

    # ── Trips ────────────────────────────────────────────────────────────────
    print("Migrating trips (this may take a moment)...")
    trips_df = pd.read_csv(DATA_DIR / "user_trips.csv")
    trip_rows = migrate_trips(trips_df)
    trip_col_names = ", ".join(TRIPS_KEEP + ["co2_kg", "data_source"])
    trip_placeholders = ", ".join("?" * (len(TRIPS_KEEP) + 2))
    executemany(
        f"INSERT OR REPLACE INTO trips ({trip_col_names}) VALUES ({trip_placeholders})",
        trip_rows,
    )
    print(f"  {len(trip_rows)} trips inserted.")

    # ── Trip legs ─────────────────────────────────────────────────────────────
    print("Migrating trip legs...")
    legs_df = pd.read_csv(DATA_DIR / "trip_legs.csv")
    leg_rows = migrate_legs(legs_df)
    leg_col_names = ", ".join(LEGS_KEEP + ["co2_kg"])
    leg_placeholders = ", ".join("?" * (len(LEGS_KEEP) + 1))
    executemany(
        f"INSERT OR REPLACE INTO trip_legs ({leg_col_names}) VALUES ({leg_placeholders})",
        leg_rows,
    )
    print(f"  {len(leg_rows)} trip legs inserted.")

    print(f"\nDone. Database written to: {DB_PATH}")


if __name__ == "__main__":
    main()
