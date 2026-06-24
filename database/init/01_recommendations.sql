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