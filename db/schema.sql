-- DB MoveOptimizer — SQLite Schema
-- Single source of truth for all tables.
-- Array-type columns store valid JSON strings: ["a","b"]
-- Booleans are stored as 0/1 integers (SQLite has no native bool type).

PRAGMA foreign_keys = ON;

-- ---------------------------------------------------------------------------
-- users
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    user_id                         TEXT PRIMARY KEY,
    username                        TEXT UNIQUE NOT NULL,
    email                           TEXT UNIQUE,
    external_auth_id                TEXT,
    first_name                      TEXT,
    last_name                       TEXT,
    display_name                    TEXT,
    date_of_birth                   TEXT,       -- ISO 8601 date
    gender                          TEXT,
    life_stage                      TEXT,
    home_city                       TEXT,
    home_postal_code                TEXT,
    home_country_code               TEXT,
    city_type                       TEXT,       -- big_city / medium_city / small_city
    job_industry                    TEXT,
    employment_status               TEXT,
    income_range                    TEXT,
    working_pattern                 TEXT,       -- hybrid / on_site / remote
    commute_frequency               TEXT,
    has_car                         INTEGER,    -- 0/1
    has_bike                        INTEGER,
    has_driving_license             INTEGER,
    public_transport_affinity       TEXT,       -- low / medium / high
    preferred_modes                 TEXT,       -- JSON array
    avoided_modes                   TEXT,       -- JSON array
    preferred_activity_types        TEXT,       -- JSON array
    leisure_intensity               TEXT,
    evening_activity_frequency      TEXT,
    weekend_activity_frequency      TEXT,
    price_sensitivity               TEXT,       -- low / medium / high
    purchase_channel_preference     TEXT,
    employer_reimbursement_available INTEGER,   -- 0/1
    -- Collected by onboarding agent (0-10 scale)
    pref_cost_savings               INTEGER,
    pref_co2_savings                INTEGER,
    pref_flexibility                INTEGER,
    future_travel_plans             TEXT,
    onboarding_completed_at         TEXT,
    created_at                      TEXT DEFAULT (datetime('now')),
    updated_at                      TEXT DEFAULT (datetime('now'))
);

-- ---------------------------------------------------------------------------
-- trips
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trips (
    trip_id                 TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL REFERENCES users(user_id),
    start_ts                TEXT,
    end_ts                  TEXT,
    weekday                 TEXT,
    origin_city             TEXT,
    origin_place_type       TEXT,
    origin_label            TEXT,
    destination_city        TEXT,
    destination_place_type  TEXT,
    destination_label       TEXT,
    trip_purpose            TEXT,
    main_mode               TEXT,
    modes_used              TEXT,       -- JSON array
    distance_km             REAL,
    duration_min            INTEGER,
    estimated_cost_eur      REAL,
    co2_kg                  REAL,       -- calculated from mode + distance
    ticket_product_used     TEXT,
    is_commute              INTEGER,    -- 0/1
    is_recurring_pattern    INTEGER,
    planning_style          TEXT,
    data_source             TEXT DEFAULT 'synthetic',
    created_at              TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_trips_user_id ON trips(user_id);
CREATE INDEX IF NOT EXISTS idx_trips_start_ts ON trips(user_id, start_ts);

-- ---------------------------------------------------------------------------
-- trip_legs
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trip_legs (
    leg_id              TEXT PRIMARY KEY,
    trip_id             TEXT NOT NULL REFERENCES trips(trip_id),
    sequence_no         INTEGER,
    start_ts            TEXT,
    end_ts              TEXT,
    mode                TEXT,
    origin_label        TEXT,
    destination_label   TEXT,
    distance_km         REAL,
    duration_min        INTEGER,
    co2_kg              REAL,
    ticket_required     INTEGER,        -- 0/1
    ticket_product_used TEXT,
    leg_note            TEXT
);

CREATE INDEX IF NOT EXISTS idx_legs_trip_id ON trip_legs(trip_id);

-- ---------------------------------------------------------------------------
-- subscription_products  (catalogue — maintained by DB team)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS subscription_products (
    product_id                  TEXT PRIMARY KEY,
    product_name                TEXT NOT NULL,
    type                        TEXT,       -- card / subscription / pass
    monthly_cost_eur            REAL,
    annual_cost_eur             REAL,
    discount_pct                REAL,
    travel_class                INTEGER,    -- 1 or 2
    coverage_scope              TEXT,
    valid_modes                 TEXT,       -- JSON array of modes this covers
    min_commitment_months       INTEGER,
    cancellation_notice_months  INTEGER,
    auto_renews                 INTEGER,    -- 0/1
    combinable_with             TEXT,       -- JSON array of compatible product_ids
    is_active                   INTEGER DEFAULT 1,
    notes                       TEXT,
    -- Extended pricing fields (added in subscription catalogue expansion)
    pricing_model               TEXT,   -- flat_monthly / per_minute / per_km / per_km_and_time / time_pass / hybrid
    cost_per_minute_eur         REAL,
    cost_per_km_eur             REAL,
    unlock_fee_eur              REAL,
    free_minutes_per_ride       INTEGER,
    period_days                 INTEGER,    -- 1/3/7/30/90/365
    eligibility_min_age         INTEGER,
    eligibility_max_age         INTEGER,
    eligibility_notes           TEXT,
    city_availability           TEXT,
    markdown_ref                TEXT        -- relative path inside data/ for detailed AGB
);

-- ---------------------------------------------------------------------------
-- user_subscriptions  (which user holds which product right now)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS user_subscriptions (
    user_subscription_id        TEXT PRIMARY KEY,
    user_id                     TEXT NOT NULL REFERENCES users(user_id),
    product_id                  TEXT NOT NULL REFERENCES subscription_products(product_id),
    status                      TEXT DEFAULT 'active',  -- active / cancelled / pending_cancellation
    start_date                  TEXT,
    end_date                    TEXT,   -- NULL = open-ended
    monthly_cost_actual_eur     REAL,   -- actual price paid (may differ from catalogue)
    auto_renew                  INTEGER DEFAULT 1,
    cancellation_requested_at   TEXT,
    source                      TEXT DEFAULT 'manual',  -- manual / optimizer
    created_at                  TEXT DEFAULT (datetime('now')),
    updated_at                  TEXT DEFAULT (datetime('now'))
);

CREATE INDEX IF NOT EXISTS idx_user_subs_user_id ON user_subscriptions(user_id);

-- ---------------------------------------------------------------------------
-- recommendations  (optimizer output + approval state)
-- ---------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id       TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL REFERENCES users(user_id),
    analysis_period_start   TEXT,
    analysis_period_end     TEXT,
    analyst_output          TEXT,   -- JSON
    forecaster_output       TEXT,   -- JSON
    optimizer_scenarios     TEXT,   -- JSON array of scenario objects
    status                  TEXT DEFAULT 'analysing',
                                    -- analysing / ready / presented / approved / rejected / executed
    selected_scenario_id    TEXT,
    approved_at             TEXT,
    executed_at             TEXT,
    user_feedback           TEXT,
    created_at              TEXT DEFAULT (datetime('now'))
);
