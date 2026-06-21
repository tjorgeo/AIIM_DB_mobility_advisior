import os
import time

import psycopg2
from psycopg2.extras import RealDictCursor

# Phase 2: the app now persists to the docker Postgres `db` service instead of a
# local SQLite file. The schema below is tjorge's original demo schema, translated
# 1:1 to Postgres (TEXT / REAL / INTEGER are all valid PG types). Canonicalising
# onto database/init + the real product catalogue is deferred to Phase 3.
DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/app_db"
)


class _CompatCursor(RealDictCursor):
    """Cursor that (a) returns dict-like rows so existing ``dict(row)`` / ``row["x"]``
    access keeps working, and (b) accepts the legacy SQLite ``?`` placeholder by
    rewriting it to psycopg2's ``%s``.

    Safe for this codebase: the only ``?`` characters live inside SQL query
    strings here (verified), and query text contains no literal ``%``.
    """

    def execute(self, query, vars=None):
        if "?" in query:
            query = query.replace("?", "%s")
        return super().execute(query, vars)


def get_connection(retries: int = 30, delay: float = 1.0):
    """Open a Postgres connection. Retries briefly so the backend can start
    before Postgres is fully accepting connections (compose `depends_on` does
    not wait for readiness)."""
    last_err = None
    for _ in range(retries):
        try:
            return psycopg2.connect(DATABASE_URL, cursor_factory=_CompatCursor)
        except psycopg2.OperationalError as err:
            last_err = err
            time.sleep(delay)
    raise last_err


SCHEMA_SQL = """
-- 1. Users
CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    db_customer_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    preferences TEXT NOT NULL,      -- JSON string (cost_priority, co2_priority, ...)
    consent_status TEXT NOT NULL    -- JSON string (email_opted_in, calendar_shared, ...)
);

-- 2. Travel History
CREATE TABLE IF NOT EXISTS travel_history (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    trip_date TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    mode TEXT NOT NULL,
    distance_km REAL NOT NULL,
    cost_eur REAL NOT NULL,
    co2_kg REAL NOT NULL,
    created_at TEXT NOT NULL
);

-- 3. Current Subscriptions
CREATE TABLE IF NOT EXISTS subscriptions (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    service TEXT NOT NULL,
    status TEXT NOT NULL,
    monthly_cost_eur REAL NOT NULL,
    renewal_date TEXT
);

-- 4. Recommendations & Approvals
CREATE TABLE IF NOT EXISTS recommendations (
    id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    scenarios TEXT NOT NULL,        -- JSON string of ranked portfolios
    status TEXT NOT NULL,           -- analyzing / ready / approved / rejected
    approval_timestamp TEXT
);

-- 5. Audit Log
CREATE TABLE IF NOT EXISTS audit_log (
    id TEXT PRIMARY KEY,
    user_id TEXT,
    action TEXT NOT NULL,
    details TEXT NOT NULL,          -- JSON string
    timestamp TEXT NOT NULL
);

-- 6. Internal Pricing Catalog (for Optimizer)
CREATE TABLE IF NOT EXISTS pricing_catalog (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    monthly_cost REAL NOT NULL,
    discount_percent REAL NOT NULL,
    unlimited_trips INTEGER NOT NULL,
    coverage TEXT NOT NULL
);
"""


def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(SCHEMA_SQL)
    conn.commit()
    conn.close()


if __name__ == "__main__":
    init_db()
    print("Database initialized successfully at:", DATABASE_URL)
