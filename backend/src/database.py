import os
import threading
import time

import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2.pool import ThreadedConnectionPool

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

    The rewrite is a blunt ``str.replace`` and would silently corrupt a query that
    mixes ``?`` placeholders with a literal ``?`` (e.g. a JSONB ``?`` operator) or a
    ``%`` (e.g. ``LIKE '%x%'`` — which psycopg2 would then read as a format marker).
    No query in this codebase does either. To keep that assumption from failing
    silently, refuse the ambiguous case loudly instead of rewriting it wrong.
    """

    def execute(self, query, vars=None):
        if "?" in query:
            if "%" in query:
                raise ValueError(
                    "Query mixes '?' placeholders with a literal '%'; the ?->%s "
                    "compat rewrite would corrupt it. Use native '%s' placeholders."
                )
            query = query.replace("?", "%s")
        return super().execute(query, vars)


# Pool bounds. Kept small — the pilot is single-instance and low-concurrency; the point
# of pooling is to stop every request opening (and TCP/auth-handshaking) a brand new
# Postgres connection, not to serve heavy load.
_POOL_MIN = int(os.getenv("DB_POOL_MIN", "1"))
_POOL_MAX = int(os.getenv("DB_POOL_MAX", "10"))

_pool: ThreadedConnectionPool | None = None
_pool_lock = threading.Lock()


class _PooledConnection:
    """Thin proxy so existing call sites keep using ``conn.close()`` unchanged — but
    ``close()`` returns the connection to the pool instead of tearing it down. Everything
    else (``cursor()``, ``commit()``, …) delegates to the real psycopg2 connection."""

    def __init__(self, pool: ThreadedConnectionPool, conn):
        self._pool = pool
        self._conn = conn

    def __getattr__(self, name):
        return getattr(self._conn, name)

    def close(self):
        # Reset any open transaction so the next borrower starts clean (no-op after an
        # explicit commit). If the connection is broken, drop it from the pool instead.
        try:
            if self._conn.closed:
                self._pool.putconn(self._conn, close=True)
                return
            self._conn.rollback()
            self._pool.putconn(self._conn)
        except psycopg2.Error:
            self._pool.putconn(self._conn, close=True)

    def __enter__(self):
        return self._conn.__enter__()

    def __exit__(self, *exc):
        return self._conn.__exit__(*exc)


def _get_pool(retries: int, delay: float) -> ThreadedConnectionPool:
    """Lazily build the shared connection pool. Retries briefly so the backend can start
    before Postgres is fully accepting connections (compose `depends_on` does not wait for
    readiness)."""
    global _pool
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is not None:
            return _pool
        last_err = None
        for _ in range(retries):
            try:
                _pool = ThreadedConnectionPool(
                    _POOL_MIN, _POOL_MAX, DATABASE_URL, cursor_factory=_CompatCursor
                )
                return _pool
            except psycopg2.OperationalError as err:
                last_err = err
                time.sleep(delay)
        raise last_err


def get_connection(retries: int = 30, delay: float = 1.0):
    """Lease a Postgres connection from the shared pool. Same signature and
    ``conn.close()`` contract as before, so no call site changes — but connections are
    reused rather than opened per call."""
    pool = _get_pool(retries, delay)
    conn = pool.getconn()
    # Guard against a pooled connection the server has since closed (idle timeout etc.):
    # discard it and lease a fresh one.
    if conn.closed:
        pool.putconn(conn, close=True)
        conn = pool.getconn()
    return _PooledConnection(pool, conn)


def ping_db():
    """Open and close a connection to confirm the database is reachable.

    The schema itself is provisioned by Postgres from database/init/*.sql, so the
    backend only needs to verify connectivity on startup."""
    conn = get_connection()
    conn.close()


if __name__ == "__main__":
    ping_db()
    print("Database reachable at:", DATABASE_URL)
