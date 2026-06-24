-- Single dummy user that fits the production schema (database/init).
-- Testing-only fixture so the backend has at least one fully-formed user to read.
-- Runs last (99_) so every referenced table already exists.

-- 1. Catalog entry referenced by the user's subscription
INSERT INTO subscription_catalogs (
    subscription_id, provider_id, provider_plan_id,
    provider_name, provider_plan_name,
    subscription_category, subscription_type,
    pricing_model, billing_cycle,
    monthly_cost_eur, annual_cost_eur
) VALUES (
    'cat-deutschlandticket', 'db', 'dticket',
    'Deutsche Bahn', 'Deutschlandticket',
    'public_transport', 'subscription',
    'flat_monthly', 'monthly',
    49.00, 588.00
);

-- 2. The dummy user
INSERT INTO users (
    user_id, email, username, external_auth_id,
    first_name, last_name, date_of_birth, age, gender, life_stage,
    home_city, home_postal_code, home_country_code
) VALUES (
    'dummy-user-001', 'test.user@example.com', 'testuser', NULL,
    'Test', 'User', '1990-01-01', 36, 'male', 'single',
    'Berlin', '10115', 'DE'
);

-- 3. Onboarding profile (preferences / employment / mobility access)
INSERT INTO user_onboardings (
    onboarding_id, user_id,
    employment_status, occupation, work_city, work_postal_code, work_country_code,
    work_arrangement, remote_work_share,
    household_size, household_type, income_band, mobility_budget_monthly_eur,
    has_driving_license, car_access, bike_access,
    preferred_transport_modes, avoided_transport_modes, mobility_constraints,
    score_emission, score_money, score_flexibility,
    typical_weekday_pattern, typical_weekend_pattern,
    travel_statement, activity_statement
) VALUES (
    'onb-001', 'dummy-user-001',
    'employed_full_time', 'software engineer', 'Berlin', '10117', 'DE',
    'hybrid', 0.400,
    1, 'single', 'medium', 150.00,
    TRUE, 'none', 'own',
    ARRAY['public_transport', 'bicycle'], ARRAY['car', 'taxi'], ARRAY['environmental_concerns'],
    80, 60, 70,
    'Commutes to the office by U-Bahn three days a week; works remotely otherwise.',
    'Cycles locally and meets friends at cafes after work.',
    'Uses public transport regularly and combines it with biking for the last kilometre.',
    'Often combines workdays with after-work activities; occasional weekend regional-train trips.'
);

-- 4. Active subscription held by the user
INSERT INTO user_subscriptions (
    user_subscription_id, user_id, subscription_id,
    valid_from, valid_until, subscription_status,
    is_primary_mobility_option, estimated_usage_frequency
) VALUES (
    'usub-001', 'dummy-user-001', 'cat-deutschlandticket',
    '2026-01-01', NULL, 'active',
    TRUE, 'daily'
);

-- 5. A recurring commute trip
INSERT INTO user_trips (
    trip_id, user_id,
    started_at, ended_at, duration_minutes,
    origin_label, origin_city, origin_postal_code, origin_country_code,
    destination_label, destination_city, destination_postal_code, destination_country_code,
    trip_purpose, main_transport_mode, estimated_distance_km,
    is_commute, is_intermodal, is_recurring_pattern
) VALUES (
    'trip-001', 'dummy-user-001',
    '2026-06-01 08:00:00+02', '2026-06-01 08:30:00+02', 30,
    'Home', 'Berlin', '10115', 'DE',
    'Office', 'Berlin', '10117', 'DE',
    'commute', 'public_transport', 8.500,
    TRUE, FALSE, TRUE
);

-- 6. The single leg of that trip
INSERT INTO trip_legs (
    leg_id, trip_id, user_id, user_subscription_id,
    leg_sequence_number,
    started_at, ended_at, duration_minutes,
    origin_label, origin_city, origin_postal_code, origin_country_code,
    destination_label, destination_city, destination_postal_code, destination_country_code,
    transport_mode, ticket_type, ticket_class,
    estimated_distance_km, estimated_cost_eur, estimated_co2_emissions,
    is_access_leg, is_main_leg, is_egress_leg, is_transfer_leg,
    wait_time_minutes, transfer_count_before_leg
) VALUES (
    'leg-001', 'trip-001', 'dummy-user-001', 'usub-001',
    1,
    '2026-06-01 08:00:00+02', '2026-06-01 08:30:00+02', 30,
    'Home', 'Berlin', '10115', 'DE',
    'Office', 'Berlin', '10117', 'DE',
    'public_transport', 'subscription', 2,
    8.500, 0.00, 0.500,
    FALSE, TRUE, FALSE, FALSE,
    3, 0
);
