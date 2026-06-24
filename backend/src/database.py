import os
import time

import psycopg2
from psycopg2.extras import RealDictCursor

# The app persists to the docker Postgres `db` service. The production schema
# lives in database/init/*.sql and is auto-loaded by Postgres on first init
# (mounted to /docker-entrypoint-initdb.d in docker-compose.yml), so the backend
# no longer owns / creates the schema itself.
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


def ping_db():
    """Open and close a connection to confirm the database is reachable.

    The schema itself is provisioned by Postgres from database/init/*.sql, so the
    backend only needs to verify connectivity on startup."""
    conn = get_connection()
    conn.close()


if __name__ == "__main__":
    ping_db()
    print("Database reachable at:", DATABASE_URL)
