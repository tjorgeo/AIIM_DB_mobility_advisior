-- Optional, falls gen_random_uuid() genutzt werden soll
CREATE TABLE IF NOT EXISTS user_profiles (
    user_id TEXT PRIMARY KEY,

    -- Persona / Generierung
    source_persona_id TEXT NOT NULL,
    profile_variant TEXT NOT NULL,
    generation_rationale TEXT,

    -- Account
    email TEXT,
    username TEXT,
    external_auth_id TEXT,

    -- Person Information
    first_name TEXT,
    last_name TEXT,
    display_name TEXT,
    date_of_birth DATE,
    age INTEGER CHECK (age >= 0),
    gender TEXT NOT NULL DEFAULT 'not_specified'
        CHECK (gender IN ('female', 'male', 'diverse', 'not_specified')),
    life_stage TEXT,
    home_city TEXT NOT NULL,
    home_postal_code TEXT NOT NULL,
    home_country_code CHAR(2) DEFAULT 'DE',
    city_type TEXT,

    -- Job Related
    job_industry TEXT,
    employment_status TEXT,
    income_range TEXT,
    working_pattern TEXT,
    commute_frequency TEXT,

    -- Mobility Profile
    has_car BOOLEAN,
    has_bike BOOLEAN,
    has_driving_license BOOLEAN,
    public_transport_affinity TEXT,
    preferred_modes TEXT[],
    avoided_modes TEXT[],
    typical_weekday_trip_level TEXT,
    typical_weekend_trip_level TEXT,

    -- Activity Profile
    leisure_intensity TEXT,
    preferred_activity_types TEXT[],
    evening_activity_frequency TEXT,
    weekend_activity_frequency TEXT,

    -- Ticketing Profile
    subscription_likelihood TEXT,
    current_ticket_product TEXT,
    likely_ticket_products TEXT[],
    price_sensitivity TEXT,
    purchase_channel_preference TEXT,
    employer_reimbursement_available BOOLEAN,

    -- User Statements
    travel_and_priorities TEXT,

    -- Metadata
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_user_profiles_city
ON user_profiles (home_city);

CREATE INDEX IF NOT EXISTS idx_user_profiles_source_persona
ON user_profiles (source_persona_id);

CREATE INDEX IF NOT EXISTS idx_user_profiles_email
ON user_profiles (email);

CREATE INDEX IF NOT EXISTS idx_user_profiles_preferred_modes
ON user_profiles USING GIN (preferred_modes);

CREATE INDEX IF NOT EXISTS idx_user_profiles_activity_types
ON user_profiles USING GIN (preferred_activity_types);