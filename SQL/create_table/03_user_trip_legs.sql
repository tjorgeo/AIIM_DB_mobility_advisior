CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS trip_legs (
    leg_id TEXT PRIMARY KEY,

    trip_id TEXT NOT NULL REFERENCES user_trips(trip_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES user_information(user_id) ON DELETE CASCADE,

    leg_sequence_number INTEGER NOT NULL
        CHECK (leg_sequence_number >= 1),

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

    -- Transport
    transport_mode TEXT NOT NULL
        CHECK (
            transport_mode IN (
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
                'other'
            )
        ),

    ticket_type TEXT NOT NULL
        CHECK (
            ticket_type IN (
                'single_ticket',
                'subscription',
                'pay-as-you-go',
                'other',
                'none'
            )
        ),

    ticket_class TEXT NOT NULL DEFAULT 'none'
        CHECK (
            ticket_class IN (
                'second_class',
                'first_class',
                'none'
            )
        ),

    provider_name TEXT,
    service_line TEXT,
    vehicle_type TEXT,

    -- Estimates
    estimated_distance_km NUMERIC(10,3) NOT NULL
        CHECK (estimated_distance_km >= 0),

    estimated_cost_eur NUMERIC(10,2)
        CHECK (
            estimated_cost_eur IS NULL
            OR estimated_cost_eur >= 0
        ),

    estimated_co2_emissions NUMERIC(10,3)
        CHECK (
            estimated_co2_emissions IS NULL
            OR estimated_co2_emissions >= 0
        ),

    -- Leg role
    is_access_leg BOOLEAN NOT NULL DEFAULT FALSE,
    is_main_leg BOOLEAN NOT NULL DEFAULT FALSE,
    is_egress_leg BOOLEAN NOT NULL DEFAULT FALSE,
    is_transfer_leg BOOLEAN NOT NULL DEFAULT FALSE,

    wait_time_minutes INTEGER
        CHECK (
            wait_time_minutes IS NULL
            OR wait_time_minutes >= 0
        ),

    transfer_count_before_leg INTEGER NOT NULL DEFAULT 0
        CHECK (transfer_count_before_leg >= 0),

    -- Generation Metadata
    generation_rationale TEXT,

    -- Plausibility checks
    CHECK (ended_at >= started_at),

    CHECK (
        (
            is_access_leg::INTEGER +
            is_main_leg::INTEGER +
            is_egress_leg::INTEGER +
            is_transfer_leg::INTEGER
        ) >= 1
    )
);