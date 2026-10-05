-- =============================================================================
-- StreamFlix Raw Layer Schema
-- This script creates the raw event storage layer
-- =============================================================================

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS raw_playback_events CASCADE;
DROP TABLE IF EXISTS raw_events CASCADE;

-- =============================================================================
-- raw_events
-- Immutable storage of all behavioral events from Kafka
-- =============================================================================
CREATE TABLE raw_events (
    event_id UUID PRIMARY KEY,
    event_type VARCHAR(50) NOT NULL,
    user_id INTEGER NOT NULL,
    session_id UUID NOT NULL,
    content_id INTEGER,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    device_type VARCHAR(50),
    country VARCHAR(3),
    region VARCHAR(100),
    metadata JSONB,
    processed_at TIMESTAMP WITH TIME ZONE,
    kafka_offset BIGINT,
    kafka_partition INTEGER,
    kafka_topic VARCHAR(100),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_raw_events_user_id ON raw_events(user_id);
CREATE INDEX idx_raw_events_timestamp ON raw_events(timestamp);
CREATE INDEX idx_raw_events_event_type ON raw_events(event_type);
CREATE INDEX idx_raw_events_session_id ON raw_events(session_id);
CREATE INDEX idx_raw_events_content_id ON raw_events(content_id);

-- Comment
COMMENT ON TABLE raw_events IS 'Immutable storage of all behavioral events from Kafka';
COMMENT ON COLUMN raw_events.event_id IS 'Unique identifier for the event';
COMMENT ON COLUMN raw_events.event_type IS 'Type of event (play, pause, click, etc.)';
COMMENT ON COLUMN raw_events.user_id IS 'Foreign key to dim_users';
COMMENT ON COLUMN raw_events.session_id IS 'Unique session identifier';
COMMENT ON COLUMN raw_events.content_id IS 'Foreign key to dim_content';
COMMENT ON COLUMN raw_events.timestamp IS 'When the event occurred';
COMMENT ON COLUMN raw_events.device_type IS 'Device that generated the event';
COMMENT ON COLUMN raw_events.country IS 'ISO 3166-1 alpha-3 country code';
COMMENT ON COLUMN raw_events.region IS 'Region within country';
COMMENT ON COLUMN raw_events.metadata IS 'Additional event-specific data';
COMMENT ON COLUMN raw_events.processed_at IS 'When the event was processed';
COMMENT ON COLUMN raw_events.kafka_offset IS 'Kafka offset for the event';
COMMENT ON COLUMN raw_events.kafka_partition IS 'Kafka partition';
COMMENT ON COLUMN raw_events.kafka_topic IS 'Kafka topic name';

-- =============================================================================
-- raw_playback_events
-- Immutable storage of playback-specific events with timing data
-- =============================================================================
CREATE TABLE raw_playback_events (
    event_id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL,
    session_id UUID NOT NULL,
    content_id INTEGER NOT NULL,
    event_type VARCHAR(50) NOT NULL,
    timestamp TIMESTAMP WITH TIME ZONE NOT NULL,
    position_seconds INTEGER,
    watch_seconds INTEGER,
    duration_seconds INTEGER,
    device_type VARCHAR(50),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for performance
CREATE INDEX idx_raw_playback_user_content ON raw_playback_events(user_id, content_id);
CREATE INDEX idx_raw_playback_timestamp ON raw_playback_events(timestamp);
CREATE INDEX idx_raw_playback_session_id ON raw_playback_events(session_id);

-- Comment
COMMENT ON TABLE raw_playback_events IS 'Immutable storage of playback-specific events with timing data';
COMMENT ON COLUMN raw_playback_events.event_id IS 'Unique identifier for the event';
COMMENT ON COLUMN raw_playback_events.user_id IS 'Foreign key to dim_users';
COMMENT ON COLUMN raw_playback_events.session_id IS 'Unique session identifier';
COMMENT ON COLUMN raw_playback_events.content_id IS 'Foreign key to dim_content';
COMMENT ON COLUMN raw_playback_events.event_type IS 'Type of playback event (play, pause, resume, seek, stop, complete)';
COMMENT ON COLUMN raw_playback_events.timestamp IS 'When the event occurred';
COMMENT ON COLUMN raw_playback_events.position_seconds IS 'Current playback position in seconds';
COMMENT ON COLUMN raw_playback_events.watch_seconds IS 'Total watch time in seconds';
COMMENT ON COLUMN raw_playback_events.duration_seconds IS 'Total content duration in seconds';
COMMENT ON COLUMN raw_playback_events.device_type IS 'Device that generated the event';
