CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_trips (
    trip_id TEXT PRIMARY KEY,

    -- Bezug zum User
    user_id TEXT NOT NULL
        REFERENCES user_profiles(user_id)
        ON DELETE CASCADE,

    -- Generierung / Herkunft
    source_persona_id TEXT,
    profile_variant TEXT,
    trip_sequence INTEGER CHECK (trip_sequence >= 1),
    generation_batch_id TEXT,
    generation_rationale TEXT,

    -- Zeitliche Informationen
    -- trip_date DATE NOT NULL,
    trip_date DATE,
    start_ts TIMESTAMPTZ NOT NULL,
    end_ts TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER CHECK (duration_minutes >= 0),

    -- Trip-Kontext
    trip_purpose TEXT,
    trip_category TEXT,
    is_commute BOOLEAN DEFAULT FALSE,
    is_weekend BOOLEAN,
    is_round_trip BOOLEAN DEFAULT FALSE,

    -- Startpunkt
    origin_name TEXT,
    origin_type TEXT,
    origin_city TEXT,
    origin_postal_code TEXT,
    origin_country_code CHAR(2) DEFAULT 'DE',
    origin_latitude NUMERIC(9,6),
    origin_longitude NUMERIC(9,6),

    -- Zielpunkt
    destination_name TEXT,
    destination_type TEXT,
    destination_city TEXT,
    destination_postal_code TEXT,
    destination_country_code CHAR(2) DEFAULT 'DE',
    destination_latitude NUMERIC(9,6),
    destination_longitude NUMERIC(9,6),

    -- Mobilität
    main_mode TEXT,
    modes TEXT[],
    mode_chain TEXT,
    number_of_transfers INTEGER CHECK (number_of_transfers >= 0),
    distance_km NUMERIC(8,3) CHECK (distance_km >= 0),
    walking_distance_km NUMERIC(8,3) CHECK (walking_distance_km >= 0),
    cycling_distance_km NUMERIC(8,3) CHECK (cycling_distance_km >= 0),
    public_transport_distance_km NUMERIC(8,3) CHECK (public_transport_distance_km >= 0),

    -- Ticketing / Kosten
    ticket_product_used TEXT,
    fare_type TEXT,
    estimated_cost_eur NUMERIC(8,2) CHECK (estimated_cost_eur >= 0),
    reimbursed_by_employer BOOLEAN DEFAULT FALSE,

    -- Qualität / Verhalten
    planning_channel TEXT,
    booking_channel TEXT,
    delay_minutes INTEGER DEFAULT 0,
    comfort_level TEXT,
    crowding_level TEXT,
    weather_condition TEXT,

    -- Freitext aus der Generierung
    trip_description TEXT,
    user_reasoning TEXT,

    -- Flexible Zusatzdaten, falls der Generator später mehr Felder liefert
    raw_trip_json JSONB,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Plausibilitätscheck
    CONSTRAINT chk_user_trips_time_order
        CHECK (end_ts >= start_ts)
);

CREATE INDEX IF NOT EXISTS idx_user_trips_user_id
ON user_trips (user_id);

CREATE INDEX IF NOT EXISTS idx_user_trips_trip_date
ON user_trips (trip_date);

CREATE INDEX IF NOT EXISTS idx_user_trips_user_date
ON user_trips (user_id, trip_date);

CREATE INDEX IF NOT EXISTS idx_user_trips_start_ts
ON user_trips (start_ts);

CREATE INDEX IF NOT EXISTS idx_user_trips_main_mode
ON user_trips (main_mode);

CREATE INDEX IF NOT EXISTS idx_user_trips_trip_purpose
ON user_trips (trip_purpose);

CREATE INDEX IF NOT EXISTS idx_user_trips_modes
ON user_trips USING GIN (modes);

CREATE INDEX IF NOT EXISTS idx_user_trips_raw_json
ON user_trips USING GIN (raw_trip_json);