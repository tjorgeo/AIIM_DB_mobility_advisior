"""
Shared SQLite helpers used by all agents.
All agents import from here — no agent touches sqlite3 directly.
"""

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "moveoptimizer.db"
SCHEMA_PATH = Path(__file__).parent / "schema.sql"


def init_db() -> None:
    """Create all tables if they don't exist yet. Safe to call on every startup."""
    with get_conn() as conn:
        conn.executescript(SCHEMA_PATH.read_text())


@contextmanager
def get_conn():
    """Context manager that yields a connection with foreign keys enabled."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def fetchone(sql: str, params: tuple = ()) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(sql, params).fetchone()
    return dict(row) if row else None


def fetchall(sql: str, params: tuple = ()) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(r) for r in rows]


def execute(sql: str, params: tuple = ()) -> int:
    """Run a single INSERT/UPDATE/DELETE. Returns rowcount."""
    with get_conn() as conn:
        cur = conn.execute(sql, params)
    return cur.rowcount


def executemany(sql: str, param_list: list[tuple]) -> int:
    with get_conn() as conn:
        cur = conn.executemany(sql, param_list)
    return cur.rowcount


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

def get_user(user_id: str) -> dict | None:
    return fetchone("SELECT * FROM users WHERE user_id = ?", (user_id,))


def get_user_by_username(username: str) -> dict | None:
    return fetchone("SELECT * FROM users WHERE username = ?", (username,))


def upsert_user(profile: dict) -> None:
    """Insert or replace a user row. Accepts a flat dict of column→value."""
    cols = list(profile.keys())
    placeholders = ", ".join("?" * len(cols))
    col_names = ", ".join(cols)
    sql = f"INSERT OR REPLACE INTO users ({col_names}) VALUES ({placeholders})"
    execute(sql, tuple(profile.values()))


# ---------------------------------------------------------------------------
# Trips
# ---------------------------------------------------------------------------

def get_trips(user_id: str, start_ts: str | None = None, end_ts: str | None = None) -> list[dict]:
    if start_ts and end_ts:
        return fetchall(
            "SELECT * FROM trips WHERE user_id = ? AND start_ts >= ? AND start_ts <= ? ORDER BY start_ts",
            (user_id, start_ts, end_ts),
        )
    return fetchall(
        "SELECT * FROM trips WHERE user_id = ? ORDER BY start_ts",
        (user_id,),
    )


def get_trip_legs(trip_id: str) -> list[dict]:
    return fetchall(
        "SELECT * FROM trip_legs WHERE trip_id = ? ORDER BY sequence_no",
        (trip_id,),
    )


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------

def get_subscription_products(filter_type: str = "all") -> list[dict]:
    if filter_type == "all":
        return fetchall("SELECT * FROM subscription_products WHERE is_active = 1")
    return fetchall(
        "SELECT * FROM subscription_products WHERE type = ? AND is_active = 1",
        (filter_type,),
    )


def get_user_subscriptions(user_id: str, status: str = "active") -> list[dict]:
    return fetchall(
        """SELECT us.*, sp.product_name, sp.type, sp.coverage_scope, sp.valid_modes
           FROM user_subscriptions us
           JOIN subscription_products sp ON us.product_id = sp.product_id
           WHERE us.user_id = ? AND us.status = ?""",
        (user_id, status),
    )


def add_user_subscription(sub: dict) -> None:
    cols = list(sub.keys())
    sql = f"INSERT INTO user_subscriptions ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    execute(sql, tuple(sub.values()))


def update_subscription_status(user_subscription_id: str, status: str) -> None:
    execute(
        "UPDATE user_subscriptions SET status = ?, updated_at = datetime('now') WHERE user_subscription_id = ?",
        (status, user_subscription_id),
    )


# ---------------------------------------------------------------------------
# Recommendations
# ---------------------------------------------------------------------------

def save_recommendation(rec: dict) -> None:
    cols = list(rec.keys())
    sql = f"INSERT INTO recommendations ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
    execute(sql, tuple(rec.values()))


def update_recommendation_status(recommendation_id: str, status: str, **extra_fields: Any) -> None:
    set_clauses = ["status = ?"]
    values: list[Any] = [status]
    for col, val in extra_fields.items():
        set_clauses.append(f"{col} = ?")
        values.append(val)
    values.append(recommendation_id)
    execute(
        f"UPDATE recommendations SET {', '.join(set_clauses)} WHERE recommendation_id = ?",
        tuple(values),
    )


def get_latest_recommendation(user_id: str) -> dict | None:
    return fetchone(
        "SELECT * FROM recommendations WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )


# ---------------------------------------------------------------------------
# JSON helpers — for columns that store JSON arrays
# ---------------------------------------------------------------------------

def parse_json_field(value: str | None) -> list:
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []
