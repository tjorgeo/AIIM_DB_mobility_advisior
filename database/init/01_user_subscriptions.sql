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