CREATE TABLE IF NOT EXISTS user_calenders (
    user_calender_id TEXT PRIMARY KEY,
    user_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,

    tbd TEXT

);