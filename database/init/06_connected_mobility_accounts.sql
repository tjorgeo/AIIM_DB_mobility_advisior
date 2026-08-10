-- Persist the simulated provider connections selected during onboarding and
-- managed later from the profile page. Additive and safe for existing data.
ALTER TABLE user_onboardings
    ADD COLUMN IF NOT EXISTS connected_mobility_accounts TEXT[] NOT NULL DEFAULT '{}';
