CREATE TABLE IF NOT EXISTS user_onboardings (
    onboarding_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

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

    -- Mobility Preferences
    preferred_transport_modes TEXT[] NOT NULL DEFAULT '{}',
    avoided_transport_modes TEXT[] NOT NULL DEFAULT '{}',
    mobility_constraints TEXT[] NOT NULL DEFAULT '{}',

    score_emission INTEGER,
    score_money INTEGER,
    score_flexibility INTEGER,

    typical_weekday_pattern TEXT,
    typical_weekend_pattern TEXT,

    -- Statements
    travel_statement TEXT NOT NULL,
    activity_statement TEXT NOT NULL
   
);