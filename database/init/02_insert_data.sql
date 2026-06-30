-- ============================================================================
-- Load seed data from CSV files
-- ============================================================================

-- Important:
-- The CSV files are mounted into the Postgres container at /seed.
-- This script is executed automatically only when the database volume is created
-- for the first time.

COPY users
FROM '/seed/user_profiles_v2.csv'
WITH (
    FORMAT csv,
    HEADER true,
    DELIMITER ',',
    QUOTE '"',
    NULL ''
);

COPY user_onboardings
FROM '/seed/user_onboardings_v2.csv'
WITH (
    FORMAT csv,
    HEADER true,
    DELIMITER ',',
    QUOTE '"',
    NULL ''
);

-- subscription_catalogs

/*
COPY user_subscriptions
FROM '/seed/user_subscriptions_v2.csv'
WITH (
    FORMAT csv,
    HEADER true,
    DELIMITER ',',
    QUOTE '"',
    NULL ''
);
*/

COPY user_trips
FROM '/seed/user_trips_v3.csv'
WITH (
    FORMAT csv,
    HEADER true,
    DELIMITER ',',
    QUOTE '"',
    NULL ''
);

COPY trip_legs
FROM '/seed/trip_legs_v4.csv'
WITH (
    FORMAT csv,
    HEADER true,
    DELIMITER ',',
    QUOTE '"',
    NULL ''
);