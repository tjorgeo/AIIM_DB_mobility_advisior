-- ============================================================================
-- Load seed data from CSV files
-- ============================================================================

-- Important:
-- The CSV files are mounted into the Postgres container at /seed.
-- This script is executed automatically only when the database volume is created
-- for the first time.
--
-- Pattern: COPY into a temp table, then INSERT ... ON CONFLICT DO NOTHING
-- so the script is safe to re-run without duplicating rows or failing on
-- existing primary keys.

-- ----------------------------------------------------------------------------
-- users
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_users (LIKE users);

COPY tmp_users (user_id, email, username, external_auth_id, first_name, last_name, date_of_birth, age, gender, life_stage, home_city, home_postal_code, home_country_code)
FROM '/seed/user_profiles_v4.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO users
SELECT * FROM tmp_users
ON CONFLICT (user_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- user_onboardings
-- ----------------------------------------------------------------------------
-- INCLUDING DEFAULTS so columns added by the later migrations (e.g.
-- `connected_mobility_accounts`, 06) keep their defaults when this script is
-- re-run by hand against an already-migrated database.
CREATE TEMP TABLE tmp_user_onboardings (LIKE user_onboardings INCLUDING DEFAULTS);
ALTER TABLE tmp_user_onboardings ALTER COLUMN onboarding_status SET DEFAULT 'completed';
ALTER TABLE tmp_user_onboardings ALTER COLUMN bike_access TYPE TEXT;

COPY tmp_user_onboardings (
    onboarding_id, user_id, employment_status, occupation, work_city,
    work_postal_code, work_country_code, work_arrangement, remote_work_share,
    household_size, household_type, income_band, mobility_budget_monthly_eur,
    has_driving_license, car_access, bike_access, preferred_transport_modes,
    avoided_transport_modes, mobility_constraints, score_emission, score_money,
    score_flexibility, typical_weekday_pattern, typical_weekend_pattern,
    travel_statement, activity_statement
)
FROM '/seed/user_onboardings_v4.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

ALTER TABLE tmp_user_onboardings
    ALTER COLUMN bike_access TYPE TEXT[]
    USING CASE
        WHEN bike_access IS NULL OR bike_access = '' THEN '{}'::TEXT[]
        ELSE string_to_array(bike_access, ',')
    END;

INSERT INTO user_onboardings
SELECT * FROM tmp_user_onboardings
ON CONFLICT (onboarding_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- subscription_catalogs (must load before user_subscriptions — FK dependency)
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_subscription_catalogs (LIKE subscription_catalogs);

COPY tmp_subscription_catalogs
FROM '/seed/subscription_catalogs_v2.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO subscription_catalogs
SELECT * FROM tmp_subscription_catalogs
ON CONFLICT (subscription_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- user_subscriptions
-- ----------------------------------------------------------------------------
-- INCLUDING DEFAULTS so the NOT NULL `status_changed_at` (absent from the CSV)
-- gets its NOW() default in the temp table instead of failing the load.
CREATE TEMP TABLE tmp_user_subscriptions (LIKE user_subscriptions INCLUDING DEFAULTS);

-- Explicit column list: the table carries `status_changed_at` (position 7, see
-- 01_create_table.sql) which the CSV does not, so a bare positional COPY would
-- feed `is_primary_mobility_option` into it and abort the whole script.
COPY tmp_user_subscriptions (
    user_subscription_id, user_id, subscription_id, valid_from, valid_until,
    subscription_status, is_primary_mobility_option, estimated_usage_frequency
)
FROM '/seed/user_subscriptions_v5.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO user_subscriptions (
    user_subscription_id, user_id, subscription_id, valid_from, valid_until,
    subscription_status, is_primary_mobility_option, estimated_usage_frequency
)
SELECT user_subscription_id, user_id, subscription_id, valid_from, valid_until,
       subscription_status, is_primary_mobility_option, estimated_usage_frequency
FROM tmp_user_subscriptions
ON CONFLICT (user_subscription_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- user_trips
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_user_trips (LIKE user_trips);

COPY tmp_user_trips
FROM '/seed/user_trips_v5.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO user_trips
SELECT * FROM tmp_user_trips
ON CONFLICT (trip_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- trip_legs
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_trip_legs (LIKE trip_legs);

COPY tmp_trip_legs
FROM '/seed/trip_legs_v8.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO trip_legs
SELECT * FROM tmp_trip_legs
ON CONFLICT (leg_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- user_calendars
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_user_calendars (LIKE user_calendars);

COPY tmp_user_calendars
FROM '/seed/user_calendars_v2.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO user_calendars
SELECT * FROM tmp_user_calendars
ON CONFLICT (calendar_id) DO NOTHING;
