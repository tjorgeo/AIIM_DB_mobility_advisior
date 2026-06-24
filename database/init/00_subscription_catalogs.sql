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