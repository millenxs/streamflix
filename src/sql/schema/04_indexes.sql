-- =============================================================================
-- StreamFlix Additional Indexes and Constraints
-- This script creates additional indexes for query optimization
-- =============================================================================

-- Note: Basic indexes are already created in the table creation scripts
-- This script adds additional composite indexes for common query patterns

-- =============================================================================
-- Composite indexes for common query patterns
-- =============================================================================

-- For user activity analysis
CREATE INDEX idx_fact_watch_user_content_date ON fact_watch_events(user_id, content_id, date_id);

-- For content performance analysis
CREATE INDEX idx_fact_watch_content_date ON fact_watch_events(content_id, date_id);

-- For device analysis
CREATE INDEX idx_fact_watch_device_date ON fact_watch_events(device_id, date_id);

-- For location analysis
CREATE INDEX idx_fact_watch_location_date ON fact_watch_events(location_id, date_id);

-- For recommendation performance
CREATE INDEX idx_fact_recommendations_user_rank ON fact_recommendations(user_id, rank);

-- For feedback analysis
CREATE INDEX idx_fact_feedback_rec_type ON fact_recommendation_feedback(recommendation_id, feedback_type);

-- For session analysis
CREATE INDEX idx_fact_sessions_user_device ON fact_sessions(user_id, device_id);

-- =============================================================================
-- Partial indexes for filtered queries
-- =============================================================================

-- Only index completed events
CREATE INDEX idx_fact_watch_completed ON fact_watch_events(user_id, date_id) WHERE completed = TRUE;

-- Only index recommendation events
CREATE INDEX idx_fact_watch_from_rec ON fact_watch_events(user_id, date_id) WHERE is_from_recommendation = TRUE;

-- Only index active users
CREATE INDEX idx_dim_users_active ON dim_users(user_id) WHERE is_active = TRUE;

-- =============================================================================
-- Comments
-- =============================================================================
COMMENT ON SCHEMA public IS 'StreamFlix Database Schema';
