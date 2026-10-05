-- =============================================================================
-- StreamFlix Data Warehouse - Fact Tables
-- This script creates all fact tables for the star schema
-- =============================================================================

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS fact_recommendation_feedback CASCADE;
DROP TABLE IF EXISTS fact_recommendations CASCADE;
DROP TABLE IF EXISTS fact_user_interactions CASCADE;
DROP TABLE IF EXISTS fact_sessions CASCADE;
DROP TABLE IF EXISTS fact_watch_events CASCADE;

-- =============================================================================
-- fact_watch_events
-- Individual watch events after ETL
-- =============================================================================
CREATE TABLE fact_watch_events (
    event_id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL,
    content_id INTEGER NOT NULL,
    date_id DATE NOT NULL,
    device_id INTEGER NOT NULL,
    location_id INTEGER,
    event_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    watch_seconds INTEGER,
    position_seconds INTEGER,
    completed BOOLEAN DEFAULT FALSE,
    is_from_recommendation BOOLEAN DEFAULT FALSE,
    recommendation_id UUID,
    
    FOREIGN KEY (user_id) REFERENCES dim_users(user_id),
    FOREIGN KEY (content_id) REFERENCES dim_content(content_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id),
    FOREIGN KEY (device_id) REFERENCES dim_device(device_id),
    FOREIGN KEY (location_id) REFERENCES dim_location(location_id)
);

-- Indexes
CREATE INDEX idx_fact_watch_user_date ON fact_watch_events(user_id, date_id);
CREATE INDEX idx_fact_watch_content ON fact_watch_events(content_id);
CREATE INDEX idx_fact_watch_recommendation ON fact_watch_events(recommendation_id);
CREATE INDEX idx_fact_watch_timestamp ON fact_watch_events(timestamp);
CREATE INDEX idx_fact_watch_device ON fact_watch_events(device_id);

-- Comments
COMMENT ON TABLE fact_watch_events IS 'Individual watch events after ETL';
COMMENT ON COLUMN fact_watch_events.event_id IS 'Unique event identifier';
COMMENT ON COLUMN fact_watch_events.user_id IS 'Foreign key to dim_users';
COMMENT ON COLUMN fact_watch_events.content_id IS 'Foreign key to dim_content';
COMMENT ON COLUMN fact_watch_events.date_id IS 'Foreign key to dim_date';
COMMENT ON COLUMN fact_watch_events.device_id IS 'Foreign key to dim_device';
COMMENT ON COLUMN fact_watch_events.location_id IS 'Foreign key to dim_location';
COMMENT ON COLUMN fact_watch_events.event_type IS 'Type of event';
COMMENT ON COLUMN fact_watch_events.timestamp IS 'When the event occurred';
COMMENT ON COLUMN fact_watch_events.watch_seconds IS 'Watch time in seconds';
COMMENT ON COLUMN fact_watch_events.position_seconds IS 'Playback position in seconds';
COMMENT ON COLUMN fact_watch_events.completed IS 'Whether content was completed';
COMMENT ON COLUMN fact_watch_events.is_from_recommendation IS 'Whether from recommendation';
COMMENT ON COLUMN fact_watch_events.recommendation_id IS 'Foreign key to fact_recommendations';

-- =============================================================================
-- fact_sessions
-- User session aggregations
-- =============================================================================
CREATE TABLE fact_sessions (
    session_id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL,
    start_time TIMESTAMP WITH TIME ZONE NOT NULL,
    end_time TIMESTAMP WITH TIME ZONE,
    duration_seconds INTEGER,
    device_id INTEGER NOT NULL,
    location_id INTEGER,
    events_count INTEGER DEFAULT 0,
    contents_watched INTEGER DEFAULT 0,
    total_watch_seconds INTEGER DEFAULT 0,
    
    FOREIGN KEY (user_id) REFERENCES dim_users(user_id),
    FOREIGN KEY (device_id) REFERENCES dim_device(device_id),
    FOREIGN KEY (location_id) REFERENCES dim_location(location_id)
);

-- Indexes
CREATE INDEX idx_fact_sessions_user ON fact_sessions(user_id);
CREATE INDEX idx_fact_sessions_date ON fact_sessions(start_time);
CREATE INDEX idx_fact_sessions_device ON fact_sessions(device_id);

-- Comments
COMMENT ON TABLE fact_sessions IS 'User session aggregations';
COMMENT ON COLUMN fact_sessions.session_id IS 'Unique session identifier';
COMMENT ON COLUMN fact_sessions.user_id IS 'Foreign key to dim_users';
COMMENT ON COLUMN fact_sessions.start_time IS 'Session start';
COMMENT ON COLUMN fact_sessions.end_time IS 'Session end';
COMMENT ON COLUMN fact_sessions.duration_seconds IS 'Session duration in seconds';
COMMENT ON COLUMN fact_sessions.device_id IS 'Foreign key to dim_device';
COMMENT ON COLUMN fact_sessions.location_id IS 'Foreign key to dim_location';
COMMENT ON COLUMN fact_sessions.events_count IS 'Number of events in session';
COMMENT ON COLUMN fact_sessions.contents_watched IS 'Number of unique contents watched';
COMMENT ON COLUMN fact_sessions.total_watch_seconds IS 'Total watch time in seconds';

-- =============================================================================
-- fact_user_interactions
-- User interactions (likes, dislikes, shares)
-- =============================================================================
CREATE TABLE fact_user_interactions (
    interaction_id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL,
    content_id INTEGER NOT NULL,
    date_id DATE NOT NULL,
    interaction_type VARCHAR(50) NOT NULL CHECK (interaction_type IN ('like', 'dislike', 'add_to_list', 'share')),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES dim_users(user_id),
    FOREIGN KEY (content_id) REFERENCES dim_content(content_id),
    FOREIGN KEY (date_id) REFERENCES dim_date(date_id)
);

-- Indexes
CREATE INDEX idx_fact_interactions_user ON fact_user_interactions(user_id);
CREATE INDEX idx_fact_interactions_content ON fact_user_interactions(content_id);
CREATE INDEX idx_fact_interactions_type ON fact_user_interactions(interaction_type);
CREATE INDEX idx_fact_interactions_date ON fact_user_interactions(date_id);

-- Comments
COMMENT ON TABLE fact_user_interactions IS 'User interactions (likes, dislikes, shares)';
COMMENT ON COLUMN fact_user_interactions.interaction_id IS 'Unique interaction identifier';
COMMENT ON COLUMN fact_user_interactions.user_id IS 'Foreign key to dim_users';
COMMENT ON COLUMN fact_user_interactions.content_id IS 'Foreign key to dim_content';
COMMENT ON COLUMN fact_user_interactions.date_id IS 'Foreign key to dim_date';
COMMENT ON COLUMN fact_user_interactions.interaction_type IS 'Type: like, dislike, add_to_list, share';
COMMENT ON COLUMN fact_user_interactions.timestamp IS 'When interaction occurred';

-- =============================================================================
-- fact_recommendations
-- Generated recommendations
-- =============================================================================
CREATE TABLE fact_recommendations (
    recommendation_id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL,
    content_id INTEGER NOT NULL,
    model_version VARCHAR(50) NOT NULL,
    algorithm VARCHAR(50) NOT NULL CHECK (algorithm IN ('popularity', 'content_based', 'collaborative', 'hybrid')),
    score DECIMAL(10,6) NOT NULL,
    rank INTEGER NOT NULL,
    generated_at TIMESTAMP WITH TIME ZONE NOT NULL,
    
    FOREIGN KEY (user_id) REFERENCES dim_users(user_id),
    FOREIGN KEY (content_id) REFERENCES dim_content(content_id)
);

-- Indexes
CREATE INDEX idx_fact_recommendations_user ON fact_recommendations(user_id);
CREATE INDEX idx_fact_recommendations_content ON fact_recommendations(content_id);
CREATE INDEX idx_fact_recommendations_algorithm ON fact_recommendations(algorithm);
CREATE INDEX idx_fact_recommendations_generated_at ON fact_recommendations(generated_at);

-- Comments
COMMENT ON TABLE fact_recommendations IS 'Generated recommendations';
COMMENT ON COLUMN fact_recommendations.recommendation_id IS 'Unique recommendation identifier';
COMMENT ON COLUMN fact_recommendations.user_id IS 'Foreign key to dim_users';
COMMENT ON COLUMN fact_recommendations.content_id IS 'Foreign key to dim_content';
COMMENT ON COLUMN fact_recommendations.model_version IS 'Model version that generated this';
COMMENT ON COLUMN fact_recommendations.algorithm IS 'Algorithm: popularity, content_based, collaborative, hybrid';
COMMENT ON COLUMN fact_recommendations.score IS 'Recommendation score (0-1)';
COMMENT ON COLUMN fact_recommendations.rank IS 'Rank in recommendation list';
COMMENT ON COLUMN fact_recommendations.generated_at IS 'When recommendation was generated';

-- =============================================================================
-- fact_recommendation_feedback
-- User interactions with recommendations
-- =============================================================================
CREATE TABLE fact_recommendation_feedback (
    feedback_id UUID PRIMARY KEY,
    recommendation_id UUID NOT NULL,
    user_id INTEGER NOT NULL,
    content_id INTEGER NOT NULL,
    feedback_type VARCHAR(50) NOT NULL CHECK (feedback_type IN ('impression', 'click', 'play', 'complete')),
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    
    FOREIGN KEY (recommendation_id) REFERENCES fact_recommendations(recommendation_id),
    FOREIGN KEY (user_id) REFERENCES dim_users(user_id),
    FOREIGN KEY (content_id) REFERENCES dim_content(content_id)
);

-- Indexes
CREATE INDEX idx_fact_feedback_rec ON fact_recommendation_feedback(recommendation_id);
CREATE INDEX idx_fact_feedback_user ON fact_recommendation_feedback(user_id);
CREATE INDEX idx_fact_feedback_type ON fact_recommendation_feedback(feedback_type);
CREATE INDEX idx_fact_feedback_timestamp ON fact_recommendation_feedback(timestamp);

-- Comments
COMMENT ON TABLE fact_recommendation_feedback IS 'User interactions with recommendations';
COMMENT ON COLUMN fact_recommendation_feedback.feedback_id IS 'Unique feedback identifier';
COMMENT ON COLUMN fact_recommendation_feedback.recommendation_id IS 'Foreign key to fact_recommendations';
COMMENT ON COLUMN fact_recommendation_feedback.user_id IS 'Foreign key to dim_users';
COMMENT ON COLUMN fact_recommendation_feedback.content_id IS 'Foreign key to dim_content';
COMMENT ON COLUMN fact_recommendation_feedback.feedback_type IS 'Type: impression, click, play, complete';
COMMENT ON COLUMN fact_recommendation_feedback.timestamp IS 'When feedback occurred';
