-- Additive migration for databases created before profile editing was introduced.
-- Fresh databases already receive this column from 01_create_table.sql.
ALTER TABLE user_subscriptions
    ADD COLUMN IF NOT EXISTS status_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW();
