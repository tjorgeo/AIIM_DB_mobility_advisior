-- Allow account creation before optional mobility-profile data is available.
-- Existing seeded and registered users keep their real values; only the NOT NULL
-- requirement is relaxed for future minimal registrations.
ALTER TABLE users ALTER COLUMN date_of_birth DROP NOT NULL;
ALTER TABLE users ALTER COLUMN age DROP NOT NULL;
ALTER TABLE users ALTER COLUMN home_city DROP NOT NULL;
ALTER TABLE users ALTER COLUMN home_postal_code DROP NOT NULL;

ALTER TABLE user_onboardings
    ADD COLUMN IF NOT EXISTS onboarding_status TEXT NOT NULL DEFAULT 'completed';

ALTER TABLE user_onboardings
    ADD COLUMN IF NOT EXISTS onboarding_completed_at TIMESTAMPTZ;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'ck_user_onboardings_status'
    ) THEN
        ALTER TABLE user_onboardings
            ADD CONSTRAINT ck_user_onboardings_status
            CHECK (onboarding_status IN ('not_started', 'in_progress', 'completed'));
    END IF;
END $$;
