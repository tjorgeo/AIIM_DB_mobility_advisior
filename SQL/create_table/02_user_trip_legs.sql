CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_trip_legs (
    leg_id TEXT PRIMARY KEY,

    -- Bezug zum übergeordneten Trip
    trip_id TEXT NOT NULL
        REFERENCES user_trips(trip_id)
        ON DELETE CASCADE,

    user_id TEXT NOT NULL
        REFERENCES user_profiles(user_id)
        ON DELETE CASCADE,

    -- Reihenfolge innerhalb des Trips
    leg_sequence INTEGER NOT NULL CHECK (leg_sequence >= 1),

    -- Verkehrsmittel / Modus
    mode TEXT NOT NULL,
    mode_detail TEXT,
    operator_name TEXT,
    line_name TEXT,
    line_id TEXT,
    route_id TEXT,
    direction TEXT,

    -- Zeitliche Informationen
    start_ts TIMESTAMPTZ NOT NULL,
    end_ts TIMESTAMPTZ NOT NULL,
    duration_minutes INTEGER CHECK (duration_minutes >= 0),

    -- Startpunkt des Legs
    origin_name TEXT,
    origin_type TEXT,
    origin_station_id TEXT,
    origin_city TEXT,
    origin_postal_code TEXT,
    origin_country_code CHAR(2) DEFAULT 'DE',
    origin_latitude NUMERIC(9,6),
    origin_longitude NUMERIC(9,6),

    -- Zielpunkt des Legs
    destination_name TEXT,
    destination_type TEXT,
    destination_station_id TEXT,
    destination_city TEXT,
    destination_postal_code TEXT,
    destination_country_code CHAR(2) DEFAULT 'DE',
    destination_latitude NUMERIC(9,6),
    destination_longitude NUMERIC(9,6),

    -- Distanz / Bewegung
    distance_km NUMERIC(8,3) CHECK (distance_km >= 0),
    estimated_speed_kmh NUMERIC(6,2) CHECK (estimated_speed_kmh >= 0),

    -- Umstieg / Zugang / Abgang
    is_access_leg BOOLEAN DEFAULT FALSE,
    is_egress_leg BOOLEAN DEFAULT FALSE,
    is_transfer_leg BOOLEAN DEFAULT FALSE,
    transfer_wait_minutes INTEGER CHECK (transfer_wait_minutes >= 0),

    -- Ticketing / Kosten auf Leg-Ebene, optional
    ticket_product_used TEXT,
    fare_zone TEXT,
    estimated_cost_eur NUMERIC(8,2) CHECK (estimated_cost_eur >= 0),

    -- Qualität / Kontext
    delay_minutes INTEGER DEFAULT 0,
    crowding_level TEXT,
    comfort_level TEXT,
    weather_condition TEXT,

    -- Freitext / Generierungsdaten
    leg_description TEXT,
    generation_rationale TEXT,
    raw_leg_json JSONB,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Constraints
    CONSTRAINT chk_trip_legs_time_order
        CHECK (end_ts >= start_ts),

    CONSTRAINT uq_trip_legs_trip_sequence
        UNIQUE (trip_id, leg_sequence)
);