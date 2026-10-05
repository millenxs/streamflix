-- =============================================================================
-- StreamFlix Simulation Layer
-- Hidden ground truth used only by the synthetic data generators.
-- Analytics and ML must never read this table as a feature source; it exists so
-- the event generator can simulate behavior and so clustering can be validated.
-- =============================================================================

DROP TABLE IF EXISTS sim_user_profiles CASCADE;

-- =============================================================================
-- sim_user_profiles
-- Latent behavioral profile of each synthetic user
-- =============================================================================
CREATE TABLE sim_user_profiles (
    user_id INTEGER PRIMARY KEY,
    persona VARCHAR(50) NOT NULL,
    genre_affinity JSONB NOT NULL,
    sessions_per_week DECIMAL(5,2) NOT NULL CHECK (sessions_per_week > 0),
    peak_hour SMALLINT NOT NULL CHECK (peak_hour BETWEEN 0 AND 23),
    weekend_bias DECIMAL(4,3) NOT NULL CHECK (weekend_bias BETWEEN 0 AND 1),
    series_preference DECIMAL(4,3) NOT NULL CHECK (series_preference BETWEEN 0 AND 1),
    completion_propensity DECIMAL(4,3) NOT NULL CHECK (completion_propensity BETWEEN 0 AND 1),
    discovery_rate DECIMAL(4,3) NOT NULL CHECK (discovery_rate BETWEEN 0 AND 1),
    churn_risk DECIMAL(4,3) NOT NULL CHECK (churn_risk BETWEEN 0 AND 1),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    FOREIGN KEY (user_id) REFERENCES dim_users(user_id) ON DELETE CASCADE
);

CREATE INDEX idx_sim_user_profiles_persona ON sim_user_profiles(persona);

-- Comments
COMMENT ON TABLE sim_user_profiles IS 'Simulation-only ground truth; never use as an analytics or ML feature';
COMMENT ON COLUMN sim_user_profiles.persona IS 'Hidden behavioral persona assigned at generation time';
COMMENT ON COLUMN sim_user_profiles.genre_affinity IS 'Probability of choosing each genre (values sum to 1)';
COMMENT ON COLUMN sim_user_profiles.sessions_per_week IS 'Expected number of sessions per week';
COMMENT ON COLUMN sim_user_profiles.peak_hour IS 'Local hour (0-23) around which sessions concentrate';
COMMENT ON COLUMN sim_user_profiles.weekend_bias IS 'Probability that a session happens on a weekend';
COMMENT ON COLUMN sim_user_profiles.series_preference IS 'Probability of choosing a series over a movie';
COMMENT ON COLUMN sim_user_profiles.completion_propensity IS 'Probability of finishing a started title';
COMMENT ON COLUMN sim_user_profiles.discovery_rate IS 'Probability of searching or browsing instead of playing directly';
COMMENT ON COLUMN sim_user_profiles.churn_risk IS 'Probability of becoming inactive during the simulation';
