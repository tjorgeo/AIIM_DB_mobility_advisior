"""Session store — the analysis snapshot + chat transcript + chat-driven revisions.

A session is created on every fresh ``/api/analyze`` and holds everything needed to
serve the dashboard and ground the advisor **without re-running the deterministic
engines or the LLM**: the agent outputs, the display fields (user / preferences /
subscriptions) and the free-text onboarding. It shares its id with the
``recommendations`` row from the same run (one id, two tables), so the existing approve
flow keeps working while the session becomes the read-through source of truth (see
``orchestrator.Orchestrator._load_cached_session``).

``chat_messages`` and ``revisions`` back the conversational advisor (later phases);
their helpers already live here so those phases can wire straight in. All rows are
dict-like (``database`` uses ``RealDictCursor``) and queries use the ``?`` placeholder
the ``_CompatCursor`` rewrites to ``%s``.
"""

import json
import uuid

from database import get_connection


def _jsonable_snapshot(row) -> dict | None:
    """Parse a session DB row into ``{session_id, user_id, snapshot, created_at}`` with
    the snapshot JSON decoded, or ``None`` when the row is missing / unparseable."""
    if not row:
        return None
    row = dict(row)
    try:
        snapshot = json.loads(row["snapshot"]) if row.get("snapshot") else {}
    except (TypeError, json.JSONDecodeError):
        return None
    return {
        "session_id": row["session_id"],
        "user_id": row["user_id"],
        "snapshot": snapshot,
        "created_at": str(row.get("created_at")),
    }


def create_session(session_id: str, user_id: str, snapshot: dict) -> str:
    """Persist a new analysis session. ``session_id`` is shared with the
    ``recommendations`` row from the same run so both are addressable by one id."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO analysis_sessions (session_id, user_id, snapshot) VALUES (?, ?, ?)",
        (session_id, user_id, json.dumps(snapshot, default=str)),
    )
    conn.commit()
    conn.close()
    return session_id


def get_session(session_id: str) -> dict | None:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT session_id, user_id, snapshot, created_at FROM analysis_sessions WHERE session_id = ?",
        (session_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return _jsonable_snapshot(row)


def latest_session_for_user(user_id: str) -> dict | None:
    """The user's most recent session — the read-through cache source."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT session_id, user_id, snapshot, created_at FROM analysis_sessions "
        "WHERE user_id = ? ORDER BY created_at DESC LIMIT 1",
        (user_id,),
    )
    row = cursor.fetchone()
    conn.close()
    return _jsonable_snapshot(row)


# --- chat transcript (wired in Phase D) --------------------------------------


def append_message(session_id: str, role: str, content: str, trace_id: str | None = None) -> str:
    message_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO chat_messages (message_id, session_id, role, content, trace_id) "
        "VALUES (?, ?, ?, ?, ?)",
        (message_id, session_id, role, content, trace_id),
    )
    conn.commit()
    conn.close()
    return message_id


def get_messages(session_id: str) -> list[dict]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT role, content, trace_id, created_at FROM chat_messages "
        "WHERE session_id = ? ORDER BY created_at ASC",
        (session_id,),
    )
    rows = cursor.fetchall()
    conn.close()
    return [
        {"role": r["role"], "content": r["content"], "trace_id": r.get("trace_id"),
         "created_at": str(r.get("created_at"))}
        for r in (dict(row) for row in rows)
    ]


# --- chat-driven revisions (wired in Phase C) --------------------------------


def add_revision(session_id: str, revision: dict, status: str = "proposed") -> str:
    """Record a chat-driven re-optimisation (output of
    ``reoptimize.reoptimize_from_analysis``) against a session. ``status`` is
    ``'proposed'`` (a what-if) or ``'applied'`` (committed)."""
    revision_id = str(uuid.uuid4())
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO revisions (revision_id, session_id, status, constraints, category_analysis) "
        "VALUES (?, ?, ?, ?, ?)",
        (
            revision_id,
            session_id,
            status,
            json.dumps(revision.get("applied_constraints") or {}, default=str),
            json.dumps(revision.get("category_subscription_analysis") or [], default=str),
        ),
    )
    conn.commit()
    conn.close()
    return revision_id


def apply_revision(revision_id: str) -> bool:
    """Promote a proposed revision to ``applied``. Returns ``False`` when the id is
    unknown."""
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE revisions SET status = 'applied' WHERE revision_id = ?", (revision_id,))
    updated = cursor.rowcount
    conn.commit()
    conn.close()
    return updated > 0
