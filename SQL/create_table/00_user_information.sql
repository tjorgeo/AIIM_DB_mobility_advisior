CREATE TABLE IF NOT EXISTS user_information (
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
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    display_name TEXT NOT NULL,
    date_of_birth DATE NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 0),
    gender TEXT NOT NULL DEFAULT 'not_specified'
        CHECK (gender IN ('female', 'male', 'diverse', 'not_specified')),
    life_stage TEXT,

    -- Home Location
    home_city TEXT NOT NULL,
    home_postal_code TEXT NOT NULL,
    home_country_code CHAR(2) NOT NULL DEFAULT 'DE',
    city_type TEXT,

    -- Work / Employment
    employment_status TEXT,
    occupation TEXT,
    work_city TEXT,
    work_postal_code TEXT,
    work_country_code CHAR(2),
    work_arrangement TEXT,
    remote_work_share NUMERIC(4,3)
        CHECK (remote_work_share IS NULL OR remote_work_share BETWEEN 0 AND 1),

    -- Household / Finance
    household_size INTEGER
        CHECK (household_size IS NULL OR household_size >= 1),
    household_type TEXT,
    income_band TEXT,
    mobility_budget_monthly_eur NUMERIC(10,2)
        CHECK (
            mobility_budget_monthly_eur IS NULL
            OR mobility_budget_monthly_eur >= 0
        ),

    -- Mobility Access
    has_driving_license BOOLEAN,

    car_access TEXT
        CHECK (
            car_access IS NULL
            OR car_access IN ('none', 'occasional', 'shared', 'own')
        ),

    bike_access TEXT
        CHECK (
            bike_access IS NULL
            OR bike_access IN ('none', 'occasional', 'own', 'shared')
        ),

    public_transport_subscription TEXT
        CHECK (
            public_transport_subscription IS NULL
            OR public_transport_subscription IN (
                'none',
                'monthly_pass',
                'deutschlandticket',
                'job_ticket',
                'student_ticket',
                'other'
            )
        ),

    -- Mobility Preferences
    preferred_transport_modes TEXT[] NOT NULL DEFAULT '{}',
    avoided_transport_modes TEXT[] NOT NULL DEFAULT '{}',
    mobility_constraints TEXT[] NOT NULL DEFAULT '{}',

    typical_weekday_pattern TEXT,
    typical_weekend_pattern TEXT,

    -- Statements
    travel_statement TEXT NOT NULL,
    activity_statement TEXT NOT NULL
);