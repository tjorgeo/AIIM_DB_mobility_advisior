-- CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_profiles (
    user_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Login / Identifikation
    email TEXT,
    username TEXT,
    external_auth_id TEXT,

    -- Persönliche Profildaten
    first_name TEXT,
    last_name TEXT,
    display_name TEXT,
    date_of_birth DATE,
    gender TEXT NOT NULL DEFAULT 'not_specified'
        CHECK (gender IN ('female', 'male', 'diverse', 'not_specified')),

    -- Lokalisierung
    -- language_code VARCHAR(10) NOT NULL DEFAULT 'de',
    -- timezone TEXT NOT NULL DEFAULT 'Europe/Berlin',

    -- Wohnort / Startpunkt
    home_city TEXT NOT NULL,
    home_postal_code TEXT NOT NULL,
    home_country_code CHAR(2) DEFAULT 'DE',
    -- home_latitude NUMERIC(9,6),
    -- home_longitude NUMERIC(9,6),

    -- work related
    work_name TEXT NOT NULL,
    work_pattern TEXT NOT NULL DEFAULT 'onsite'
        CHECK (work_pattern IN (
            'onsite',
            'hybrid',
            'remote'
        )),

    -- Arbeitsort / häufiger Zielpunkt
    -- work_city TEXT,
    -- work_postal_code TEXT,
    -- work_country_code CHAR(2) DEFAULT 'DE',
    -- work_latitude NUMERIC(9,6),
    -- work_longitude NUMERIC(9,6),

    -- Mobilitätsprofil
    mobility_profile TEXT NOT NULL DEFAULT 'standard'
        CHECK (mobility_profile IN (
            'standard',
            'commuter',
            'student',
            'tourist',
            'senior',
            'reduced_mobility'
        )),

    owns_car BOOLEAN NOT NULL DEFAULT FALSE,
    owns_bike BOOLEAN NOT NULL DEFAULT FALSE,
    has_driving_license BOOLEAN NOT NULL DEFAULT FALSE,
    -- has_public_transport_pass BOOLEAN NOT NULL DEFAULT FALSE,

    -- Präferenzen für spätere Routen-/Aktivitätsplanung
    preferred_transport_modes TEXT[] NOT NULL DEFAULT ARRAY['public_transport']::TEXT[],
    avoided_transport_modes TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    accessibility_needs TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],

    max_walking_distance_m INTEGER NOT NULL DEFAULT 1000
        CHECK (max_walking_distance_m >= 0),

    /*
    walking_speed_m_per_s NUMERIC(4,2) NOT NULL DEFAULT 1.40
        CHECK (walking_speed_m_per_s > 0),
    */

    budget_preference TEXT NOT NULL DEFAULT 'medium'
        CHECK (budget_preference IN ('low', 'medium', 'high')),

    prefers_low_emission BOOLEAN NOT NULL DEFAULT TRUE,
    prefers_fewer_transfers BOOLEAN NOT NULL DEFAULT FALSE,
    prefers_short_travel_time BOOLEAN NOT NULL DEFAULT TRUE,

    -- Flexible Zusatzdaten, falls du später nicht sofort neue Spalten bauen willst
    preferences JSONB NOT NULL DEFAULT '{}'::JSONB,

    -- Zustimmung / Benachrichtigungen
    notification_email_opt_in BOOLEAN NOT NULL DEFAULT FALSE,
    -- marketing_opt_in BOOLEAN NOT NULL DEFAULT FALSE,

    -- Technische Felder
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    deleted_at TIMESTAMPTZ

    -- Validierung Koordinaten Wohnort
    /*
    CONSTRAINT chk_home_coordinates
        CHECK (
            (home_latitude IS NULL AND home_longitude IS NULL)
            OR (
                home_latitude BETWEEN -90 AND 90
                AND home_longitude BETWEEN -180 AND 180
            )
        ),
    */

    -- Validierung Koordinaten Arbeitsort
    /*
    CONSTRAINT chk_work_coordinates
        CHECK (
            (work_latitude IS NULL AND work_longitude IS NULL)
            OR (
                work_latitude BETWEEN -90 AND 90
                AND work_longitude BETWEEN -180 AND 180
            )
        )
    */
);

-- Case-insensitive eindeutige E-Mail
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_profiles_email_lower
ON user_profiles (LOWER(email))
WHERE email IS NOT NULL;

-- Case-insensitive eindeutiger Username
CREATE UNIQUE INDEX IF NOT EXISTS idx_user_profiles_username_lower
ON user_profiles (LOWER(username))
WHERE username IS NOT NULL;

-- Nützliche Such-Indizes
CREATE INDEX IF NOT EXISTS idx_user_profiles_home_city
ON user_profiles (home_city);

CREATE INDEX IF NOT EXISTS idx_user_profiles_mobility_profile
ON user_profiles (mobility_profile);

CREATE INDEX IF NOT EXISTS idx_user_profiles_is_active
ON user_profiles (is_active);

CREATE INDEX IF NOT EXISTS idx_user_profiles_preferences
ON user_profiles USING GIN (preferences);