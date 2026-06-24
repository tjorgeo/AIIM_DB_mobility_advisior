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