CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_trips (
    trip_id TEXT PRIMARY KEY,

    user_id TEXT NOT NULL REFERENCES user_information(user_id) ON DELETE CASCADE,

    trip_sequence_number INTEGER NOT NULL
        CHECK (trip_sequence_number >= 1),

    -- Time
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER NOT NULL
        CHECK (duration_minutes >= 0),

    -- Origin
    origin_label TEXT NOT NULL,
    origin_city TEXT NOT NULL,
    origin_postal_code TEXT,
    origin_country_code CHAR(2) NOT NULL DEFAULT 'DE',

    -- Destination
    destination_label TEXT NOT NULL,
    destination_city TEXT NOT NULL,
    destination_postal_code TEXT,
    destination_country_code CHAR(2) NOT NULL DEFAULT 'DE',

    -- Trip Classification
    trip_purpose TEXT NOT NULL
        CHECK (
            trip_purpose IN (
                'commute',
                'education',
                'shopping',
                'leisure',
                'social',
                'errands',
                'healthcare',
                'sports',
                'childcare',
                'business',
                'home_return',
                'other'
            )
        ),

    main_transport_mode TEXT NOT NULL
        CHECK (
            main_transport_mode IN (
                'walking',
                'bicycle',
                'bike_sharing',
                'public_transport',
                'regional_train',
                'long_distance_train',
                'car',
                'car_sharing',
                'e_scooter',
                'ride_hailing',
                'taxi',
                'mixed',
                'other'
            )
        ),

    -- Estimates
    estimated_distance_km NUMERIC(10,3) NOT NULL
        CHECK (estimated_distance_km >= 0),

    -- Flags
    is_commute BOOLEAN NOT NULL DEFAULT FALSE,
    is_intermodal BOOLEAN NOT NULL DEFAULT FALSE,
    is_recurring_pattern BOOLEAN NOT NULL DEFAULT FALSE,

    -- Generation Metadata
    generation_rationale TEXT,

    -- Plausibility checks
    CHECK (ended_at >= started_at),

    UNIQUE (user_id, trip_sequence_number)
);