-- Session model for the pipeline re-engineering (To-Be Phase B).
--
-- A session is created on every fresh /api/analyze and holds the complete analysis
-- snapshot (numbers + preferences + onboarding + agent outputs) as JSON, so the
-- dashboard and (later) the advisor agent can be served without re-running the
-- deterministic engines or the LLM. A session shares its id with the `recommendations`
-- row from the same run (one id, two tables), so the existing approve flow keeps
-- working while the session becomes the read-through source of truth.
--
-- chat_messages and revisions back the conversational advisor (later phases); the
-- tables are created now so those phases can wire straight in.
--
-- Idempotent (IF NOT EXISTS) and safe on both fresh and existing volumes. Init scripts
-- only auto-run on a fresh Postgres volume, so on an existing volume apply this once:
--   docker exec aiim_postgres psql -U postgres -d app_db -f /docker-entrypoint-initdb.d/04_analysis_sessions.sql

CREATE TABLE IF NOT EXISTS analysis_sessions (
    session_id  TEXT PRIMARY KEY,
    user_id     TEXT NOT NULL,
    snapshot    TEXT NOT NULL,                       -- JSON: full analysis snapshot
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_sessions_user_created
    ON analysis_sessions (user_id, created_at DESC);

CREATE TABLE IF NOT EXISTS chat_messages (
    message_id  TEXT PRIMARY KEY,
    session_id  TEXT NOT NULL REFERENCES analysis_sessions (session_id) ON DELETE CASCADE,
    role        TEXT NOT NULL,                       -- 'user' | 'assistant'
    content     TEXT NOT NULL,
    trace_id    TEXT,                                -- Langfuse trace of the turn (nullable)
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_chat_messages_session_created
    ON chat_messages (session_id, created_at);

CREATE TABLE IF NOT EXISTS revisions (
    revision_id        TEXT PRIMARY KEY,
    session_id         TEXT NOT NULL REFERENCES analysis_sessions (session_id) ON DELETE CASCADE,
    status             TEXT NOT NULL DEFAULT 'proposed',   -- 'proposed' | 'applied'
    constraints        TEXT,                               -- JSON: keep/drop/prefer/exclude
    category_analysis  TEXT,                               -- JSON: revised per-category analysis
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_revisions_session_created
    ON revisions (session_id, created_at DESC);
