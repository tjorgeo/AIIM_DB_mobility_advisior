-- Adds the memo_trace_id column that the post-merge orchestrator writes to.
-- Safe to run repeatedly and on both old and new volumes (IF NOT EXISTS).
-- The column was introduced in the branch that was merged in; existing Postgres
-- data volumes created before the merge never ran the updated init script, so
-- the live table is missing it.
ALTER TABLE recommendations
    ADD COLUMN IF NOT EXISTS memo_trace_id TEXT;