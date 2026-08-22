-- Indexes on the per-user lookups the analyze path runs.
--
-- 01_create_table.sql declares user_id as a FOREIGN KEY on these tables, which
-- Postgres does NOT index automatically (unlike the referenced primary key). Every
-- read in agent/context.py::load_context therefore fell back to a sequential scan of
-- the whole table. Invisible at seed scale (a few thousand trip_legs rows); a real
-- cost as soon as the leg history grows.
--
-- Each index is ordered to serve the exact query in load_context, so the query is
-- answered by an index scan alone rather than an index lookup plus a sort:
--   * trip_legs        -- WHERE user_id = ? ORDER BY started_at ASC
--   * user_calendars   -- WHERE user_id = ? AND component_type = 'VEVENT'
--   * recommendations  -- analysis_service reads the newest row per user
--
-- Reminder: database/init/*.sql only runs on a FRESH volume. On an existing local
-- database this file will not be picked up by a plain restart — either recreate the
-- volume (docker compose down -v && docker compose up --build, which deletes all
-- local data) or apply it by hand:
--   docker compose exec -T db psql -U postgres -d app_db < database/init/08_indexes.sql
-- Every statement is IF NOT EXISTS, so applying it by hand is safe and repeatable.

CREATE INDEX IF NOT EXISTS idx_trip_legs_user_started
    ON trip_legs (user_id, started_at);

CREATE INDEX IF NOT EXISTS idx_user_subscriptions_user
    ON user_subscriptions (user_id);

CREATE INDEX IF NOT EXISTS idx_user_onboardings_user
    ON user_onboardings (user_id);

CREATE INDEX IF NOT EXISTS idx_user_calendars_user_component
    ON user_calendars (user_id, component_type);

CREATE INDEX IF NOT EXISTS idx_user_trips_user
    ON user_trips (user_id);

CREATE INDEX IF NOT EXISTS idx_recommendations_user_created
    ON recommendations (user_id, created_at DESC);
