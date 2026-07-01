CREATE TABLE IF NOT EXISTS subscription_catalogs (
    subscription_id TEXT PRIMARY KEY,
    
    provider_id TEXT NOT NULL,
    provider_plan_id TEXT NOT NULL,

    provider_name TEXT NOT NULL,
    provider_plan_name TEXT NOT NULL,

    -- Subscription Information
    subscription_category TEXT NOT NULL
        CHECK (
            subscription_category IN (
                'public_transport',
                'bike_sharing',
                'car_sharing',
                'e_scooter'
            )
        ),

    subscription_type TEXT NOT NULL
        CHECK (
            subscription_type IN (
                'subscription',
                'membership',
                'pay_as_you_go_account',
                'trial',
                'employer_benefit',
                'student_benefit',
                'other'
            )
        ),

    subscription_type_other TEXT,
    travel_class INTEGER,    

    -- Billing
    pricing_model TEXT,   -- flat_monthly / per_minute / per_km / per_km_and_time / time_pass / hybrid
    billing_cycle TEXT
        CHECK (
            billing_cycle IS NULL
            OR billing_cycle IN (
                'monthly',
                'yearly',
                'pay_as_you_go',
                'one_time',
                'none'
            )
        ),

    monthly_cost_eur NUMERIC(10,2)
        CHECK (
            monthly_cost_eur IS NULL
            OR monthly_cost_eur >= 0
        ),
    annual_cost_eur NUMERIC(10,2)
        CHECK (
            annual_cost_eur IS NULL
            OR annual_cost_eur >= 0
        ),

    markdown_ref TEXT 
);

CREATE TABLE IF NOT EXISTS users (
    user_id TEXT PRIMARY KEY,

    -- Account
    email TEXT,
    username TEXT,
    external_auth_id TEXT,

    -- Person Information
    first_name TEXT NOT NULL,
    last_name TEXT NOT NULL,
    date_of_birth DATE NOT NULL,
    age INTEGER NOT NULL CHECK (age >= 0),
    gender TEXT NOT NULL DEFAULT 'not_specified'
        CHECK (gender IN ('female', 'male', 'diverse', 'not_specified')),
    life_stage TEXT,

    -- Home Location
    home_city TEXT NOT NULL,
    home_postal_code TEXT NOT NULL,
    home_country_code CHAR(2) NOT NULL DEFAULT 'DE'
);

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

    -- transportation_modes: 'walking', 'bicycle', 'public_transport', 'regional_train', 'long_distance_train', 'car', 'e_scooter', 'ride_hailing', 'taxi', 'mixed', 'other'

    score_emission INTEGER,
    score_money INTEGER,
    score_flexibility INTEGER,

    typical_weekday_pattern TEXT,
    typical_weekend_pattern TEXT,

    -- Statements
    travel_statement TEXT NOT NULL,
    activity_statement TEXT NOT NULL
   
);

CREATE TABLE IF NOT EXISTS user_calenders (
    user_calender_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    tbd TEXT

);

CREATE TABLE IF NOT EXISTS user_subscriptions (
    user_subscription_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    subscription_id TEXT REFERENCES subscription_catalogs(subscription_id) ON DELETE CASCADE,

    -- Validity
    valid_from DATE,
    valid_until DATE,

    subscription_status TEXT NOT NULL
        CHECK (
            subscription_status IN (
                'active',
                'inactive',
                'paused',
                'cancelled',
                'expired'
            )
        ),

    -- Usage / Relevance
    is_primary_mobility_option BOOLEAN NOT NULL DEFAULT FALSE,

    estimated_usage_frequency TEXT NOT NULL DEFAULT 'unknown'
        CHECK (
            estimated_usage_frequency IN (
                'daily',
                'several_times_per_week',
                'weekly',
                'several_times_per_month',
                'rarely',
                'unknown'
            )
        )
);

CREATE TABLE IF NOT EXISTS user_trips (
    trip_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

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
    trip_purpose_other TEXT,

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
    main_transport_mode_other TEXT,

    -- Estimates
    estimated_distance_km NUMERIC(10,3) NOT NULL
        CHECK (estimated_distance_km >= 0),

    -- Flags
    is_commute BOOLEAN NOT NULL DEFAULT FALSE,
    is_intermodal BOOLEAN NOT NULL DEFAULT FALSE,
    is_recurring_pattern BOOLEAN NOT NULL DEFAULT FALSE

);

CREATE TABLE IF NOT EXISTS trip_legs (
    leg_id TEXT PRIMARY KEY,
    trip_id TEXT NOT NULL REFERENCES user_trips(trip_id) ON DELETE CASCADE,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    user_subscription_id TEXT REFERENCES user_subscriptions(user_subscription_id) ON DELETE CASCADE,

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

    ticket_type TEXT NOT NULL,
    ticket_class INTEGER,
    ticket_purchased_at TIMESTAMPTZ,

    -- Estimates
    estimated_distance_km NUMERIC(10,3) NOT NULL
        CHECK (estimated_distance_km >= 0),

    estimated_cost_eur NUMERIC(10,2)
        CHECK (
            estimated_cost_eur IS NULL
            OR estimated_cost_eur >= 0
        ),

    -- Pay-as-you-go reference price for this leg, regardless of any subscription held.
    -- Used by the analyst to measure how much a subscription actually saved.
    -- For unsubscribed legs this equals estimated_cost_eur.
    reference_cost_eur NUMERIC(10,2)
        CHECK (
            reference_cost_eur IS NULL
            OR reference_cost_eur >= 0
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

    wait_time_minutes FLOAT
        CHECK (
            wait_time_minutes IS NULL
            OR wait_time_minutes >= 0
        ),

    transfer_count_before_leg INTEGER NOT NULL DEFAULT 0
        CHECK (transfer_count_before_leg >= 0)
);

CREATE TABLE IF NOT EXISTS recommendations (
    recommendation_id       TEXT PRIMARY KEY,
    user_id                 TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    analysis_period_start   TEXT,
    analysis_period_end     TEXT,
    analyst_output          TEXT,   -- JSON
    forecaster_output       TEXT,   -- JSON
    optimizer_scenarios     TEXT,   -- JSON array of scenario objects
    analysis_status                  TEXT DEFAULT 'analysing',
                                    -- analysing / ready / presented / approved / rejected / executed
    selected_scenario_id    TEXT,
    approved_at             TEXT,
    executed_at             TEXT,
    user_feedback           TEXT,
    created_at              TEXT
);