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
FROM '/seed/user_profiles_v3.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO users
SELECT * FROM tmp_users
ON CONFLICT (user_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- user_onboardings
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_user_onboardings (LIKE user_onboardings);

COPY tmp_user_onboardings
FROM '/seed/user_onboardings_v3.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO user_onboardings
SELECT * FROM tmp_user_onboardings
ON CONFLICT (onboarding_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- subscription_catalogs (must load before user_subscriptions — FK dependency)
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_subscription_catalogs (LIKE subscription_catalogs);

COPY tmp_subscription_catalogs
FROM '/seed/subscription_catalogs_v1.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO subscription_catalogs
SELECT * FROM tmp_subscription_catalogs
ON CONFLICT (subscription_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- user_subscriptions
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_user_subscriptions (LIKE user_subscriptions);

COPY tmp_user_subscriptions
FROM '/seed/user_subscriptions_v4.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO user_subscriptions
SELECT * FROM tmp_user_subscriptions
ON CONFLICT (user_subscription_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- user_trips
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_user_trips (LIKE user_trips);

COPY tmp_user_trips
FROM '/seed/user_trips_v4.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO user_trips
SELECT * FROM tmp_user_trips
ON CONFLICT (trip_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- trip_legs
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_trip_legs (LIKE trip_legs);

COPY tmp_trip_legs
FROM '/seed/trip_legs_v7.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO trip_legs
SELECT * FROM tmp_trip_legs
ON CONFLICT (leg_id) DO NOTHING;

-- ----------------------------------------------------------------------------
-- user_calendars
-- ----------------------------------------------------------------------------
CREATE TEMP TABLE tmp_user_calendars (LIKE user_calendars);

COPY tmp_user_calendars
FROM '/seed/user_calendars_v1.csv'
WITH (FORMAT csv, HEADER true, DELIMITER ',', QUOTE '"', NULL '');

INSERT INTO user_calendars
SELECT * FROM tmp_user_calendars
ON CONFLICT (calendar_id) DO NOTHING;