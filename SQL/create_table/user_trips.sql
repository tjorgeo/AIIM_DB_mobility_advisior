-- CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE TABLE IF NOT EXISTS user_trips (
    trip_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES user_profiles(user_id) ON DELETE CASCADE,

    -- Zeit
    trip_date DATE NOT NULL,
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL,

    -- Start
    origin_type TEXT NOT NULL
        CHECK (origin_type IN (
            'home',
            'work',
            'education',
            'shopping',
            'leisure',
            'errand',
            'healthcare',
            'station',
            'other'
        )),

    -- origin_label TEXT,
    origin_city TEXT,
    -- origin_latitude NUMERIC(9,6),
    -- origin_longitude NUMERIC(9,6),

    -- Ziel
    destination_type TEXT NOT NULL
        CHECK (destination_type IN (
            'home',
            'work',
            'education',
            'shopping',
            'leisure',
            'errand',
            'healthcare',
            'station',
            'other'
        )),

    -- destination_label TEXT,
    destination_city TEXT,
    -- destination_latitude NUMERIC(9,6),
    -- destination_longitude NUMERIC(9,6),

    -- Trip-Information
    trip_purpose TEXT NOT NULL
        CHECK (trip_purpose IN (
            'commute',
            'education',
            'shopping',
            'leisure',
            'errand',
            'healthcare',
            'return_home',
            'other'
        )),

    transport_mode TEXT NOT NULL
        CHECK (transport_mode IN (
            'walking',
            'bike',
            'car',
            'public_transport',
            'bus',
            'tram',
            'subway',
            'train',
            'taxi',
            'shared_mobility',
            'mixed',
            'other'
        )),

    distance_m INTEGER CHECK (distance_m IS NULL OR distance_m >= 0),
    duration_min INTEGER CHECK (duration_min IS NULL OR duration_min >= 0),
    transfer_count INTEGER NOT NULL DEFAULT 0 CHECK (transfer_count >= 0),

    -- Kosten / Emissionen optional geschätzt
    estimated_cost_eur NUMERIC(8,2) CHECK (
        estimated_cost_eur IS NULL OR estimated_cost_eur >= 0
    ),

    estimated_co2_g INTEGER CHECK (
        estimated_co2_g IS NULL OR estimated_co2_g >= 0
    ),

    -- Generierungs-Metadaten
    data_source TEXT NOT NULL DEFAULT 'synthetic_openai'
        CHECK (data_source IN (
            'synthetic_openai',
            'synthetic_rule_based',
            'manual',
            'imported'
        )),

    generation_batch_id UUID,
    generation_model TEXT,
    generation_prompt_version TEXT,

    -- Flexible Zusatzdaten
    metadata JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Technische Felder
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Plausibilität
    CONSTRAINT chk_trip_time_order
        CHECK (ended_at > started_at),

    CONSTRAINT chk_origin_coordinates
        CHECK (
            (origin_latitude IS NULL AND origin_longitude IS NULL)
            OR (
                origin_latitude BETWEEN -90 AND 90
                AND origin_longitude BETWEEN -180 AND 180
            )
        ),

    CONSTRAINT chk_destination_coordinates
        CHECK (
            (destination_latitude IS NULL AND destination_longitude IS NULL)
            OR (
                destination_latitude BETWEEN -90 AND 90
                AND destination_longitude BETWEEN -180 AND 180
            )
        )
);

CREATE INDEX IF NOT EXISTS idx_mobility_trips_user_id
ON mobility_trips (user_id);

CREATE INDEX IF NOT EXISTS idx_mobility_trips_trip_date
ON mobility_trips (trip_date);

CREATE INDEX IF NOT EXISTS idx_mobility_trips_user_date
ON mobility_trips (user_id, trip_date);

CREATE INDEX IF NOT EXISTS idx_mobility_trips_transport_mode
ON mobility_trips (transport_mode);

CREATE INDEX IF NOT EXISTS idx_mobility_trips_trip_purpose
ON mobility_trips (trip_purpose);

CREATE INDEX IF NOT EXISTS idx_mobility_trips_metadata
ON mobility_trips USING GIN (metadata);