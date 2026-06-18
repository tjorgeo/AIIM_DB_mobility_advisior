CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE IF NOT EXISTS user_subscriptions (
    subscription_id TEXT PRIMARY KEY,

    user_id TEXT NOT NULL REFERENCES user_information(user_id) ON DELETE CASCADE,

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

    provider_name TEXT NOT NULL,
    provider_plan_name TEXT,

    subscription_type TEXT NOT NULL
        CHECK (
            subscription_type IN (
                'subscription',
                'membership',
                'pay_as_you_go_account',
                'trial',
                'employer_benefit',
                'student_benefit'
            )
        ),

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

    -- Validity
    valid_from DATE,
    valid_until DATE,

    -- Billing
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

    -- Usage / Relevance
    is_primary_mobility_option BOOLEAN NOT NULL DEFAULT FALSE,

    usage_frequency TEXT NOT NULL DEFAULT 'unknown'
        CHECK (
            usage_frequency IN (
                'daily',
                'several_times_per_week',
                'weekly',
                'several_times_per_month',
                'rarely',
                'unknown'
            )
        ),

    -- Generation Metadata
    created_from_persona TEXT,
    generation_rationale TEXT,

    -- Plausibility checks
    CHECK (
        valid_from IS NULL
        OR valid_until IS NULL
        OR valid_until >= valid_from
    )
);