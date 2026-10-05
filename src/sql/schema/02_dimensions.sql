-- =============================================================================
-- StreamFlix Data Warehouse - Dimension Tables
-- This script creates all dimension tables for the star schema
-- =============================================================================

-- Drop tables if they exist (for clean setup)
DROP TABLE IF EXISTS dim_content_genre CASCADE;
DROP TABLE IF EXISTS dim_genre CASCADE;
DROP TABLE IF EXISTS dim_location CASCADE;
DROP TABLE IF EXISTS dim_device CASCADE;
DROP TABLE IF EXISTS dim_date CASCADE;
DROP TABLE IF EXISTS dim_content CASCADE;
DROP TABLE IF EXISTS dim_users CASCADE;

-- =============================================================================
-- dim_users
-- User profiles and calculated metrics
-- =============================================================================
CREATE TABLE dim_users (
    user_id INTEGER PRIMARY KEY,
    signup_date DATE NOT NULL,
    country VARCHAR(3),
    region VARCHAR(100),
    preferred_device VARCHAR(50),
    is_active BOOLEAN DEFAULT TRUE,
    taste_cluster_id INTEGER,
    churn_probability DECIMAL(5,4),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_dim_users_country ON dim_users(country);
CREATE INDEX idx_dim_users_taste_cluster ON dim_users(taste_cluster_id);
CREATE INDEX idx_dim_users_is_active ON dim_users(is_active);

-- Comments
COMMENT ON TABLE dim_users IS 'User profiles and calculated metrics';
COMMENT ON COLUMN dim_users.user_id IS 'Unique user identifier';
COMMENT ON COLUMN dim_users.signup_date IS 'When the user signed up';
COMMENT ON COLUMN dim_users.country IS 'ISO 3166-1 alpha-3 country code';
COMMENT ON COLUMN dim_users.region IS 'Region within country';
COMMENT ON COLUMN dim_users.preferred_device IS 'Most used device type';
COMMENT ON COLUMN dim_users.is_active IS 'Whether user is active';
COMMENT ON COLUMN dim_users.taste_cluster_id IS 'Foreign key to taste cluster';
COMMENT ON COLUMN dim_users.churn_probability IS 'Predicted churn probability (0-1)';

-- =============================================================================
-- dim_content
-- Content metadata (movies and series)
-- =============================================================================
CREATE TABLE dim_content (
    content_id INTEGER PRIMARY KEY,
    title VARCHAR(500) NOT NULL,
    content_type VARCHAR(20) NOT NULL CHECK (content_type IN ('movie', 'series')),
    release_year INTEGER,
    duration_minutes INTEGER,
    primary_genre_id INTEGER,
    tmdb_id INTEGER,
    imdb_id VARCHAR(20),
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_dim_content_type ON dim_content(content_type);
CREATE INDEX idx_dim_content_genre ON dim_content(primary_genre_id);
CREATE INDEX idx_dim_content_year ON dim_content(release_year);
CREATE INDEX idx_dim_content_is_active ON dim_content(is_active);

-- Comments
COMMENT ON TABLE dim_content IS 'Content metadata (movies and series)';
COMMENT ON COLUMN dim_content.content_id IS 'Unique content identifier';
COMMENT ON COLUMN dim_content.title IS 'Content title';
COMMENT ON COLUMN dim_content.content_type IS 'Type: movie or series';
COMMENT ON COLUMN dim_content.release_year IS 'Year of release';
COMMENT ON COLUMN dim_content.duration_minutes IS 'Duration in minutes';
COMMENT ON COLUMN dim_content.primary_genre_id IS 'Foreign key to dim_genre';
COMMENT ON COLUMN dim_content.tmdb_id IS 'TMDB identifier';
COMMENT ON COLUMN dim_content.imdb_id IS 'IMDB identifier';
COMMENT ON COLUMN dim_content.description IS 'Content description';
COMMENT ON COLUMN dim_content.is_active IS 'Whether content is available';

-- =============================================================================
-- dim_genre
-- Genre definitions
-- =============================================================================
CREATE TABLE dim_genre (
    genre_id SERIAL PRIMARY KEY,
    genre_name VARCHAR(100) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comments
COMMENT ON TABLE dim_genre IS 'Genre definitions';
COMMENT ON COLUMN dim_genre.genre_id IS 'Unique genre identifier';
COMMENT ON COLUMN dim_genre.genre_name IS 'Genre name';

-- =============================================================================
-- dim_content_genre
-- Many-to-many relationship between content and genres
-- =============================================================================
CREATE TABLE dim_content_genre (
    content_id INTEGER NOT NULL,
    genre_id INTEGER NOT NULL,
    PRIMARY KEY (content_id, genre_id),
    FOREIGN KEY (content_id) REFERENCES dim_content(content_id) ON DELETE CASCADE,
    FOREIGN KEY (genre_id) REFERENCES dim_genre(genre_id) ON DELETE CASCADE
);

-- Indexes
CREATE INDEX idx_dim_content_genre_genre ON dim_content_genre(genre_id);

-- Comments
COMMENT ON TABLE dim_content_genre IS 'Many-to-many relationship between content and genres';

-- =============================================================================
-- dim_device
-- Device type definitions
-- =============================================================================
CREATE TABLE dim_device (
    device_id SERIAL PRIMARY KEY,
    device_type VARCHAR(50) NOT NULL UNIQUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Comments
COMMENT ON TABLE dim_device IS 'Device type definitions';
COMMENT ON COLUMN dim_device.device_id IS 'Unique device identifier';
COMMENT ON COLUMN dim_device.device_type IS 'Device type';

-- =============================================================================
-- dim_location
-- Geographic location definitions
-- =============================================================================
CREATE TABLE dim_location (
    location_id SERIAL PRIMARY KEY,
    country VARCHAR(3) NOT NULL,
    region VARCHAR(100) NOT NULL,
    UNIQUE (country, region)
);

-- Indexes
CREATE INDEX idx_dim_location_country ON dim_location(country);

-- Comments
COMMENT ON TABLE dim_location IS 'Geographic location definitions';
COMMENT ON COLUMN dim_location.location_id IS 'Unique location identifier';
COMMENT ON COLUMN dim_location.country IS 'ISO 3166-1 alpha-3 country code';
COMMENT ON COLUMN dim_location.region IS 'Region within country';

-- =============================================================================
-- dim_date
-- Date dimension for time-based analysis
-- =============================================================================
CREATE TABLE dim_date (
    date_id DATE PRIMARY KEY,
    day INTEGER NOT NULL,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    quarter INTEGER NOT NULL,
    day_of_week INTEGER NOT NULL,
    is_weekend BOOLEAN NOT NULL,
    is_holiday BOOLEAN DEFAULT FALSE
);

-- Indexes
CREATE INDEX idx_dim_date_year ON dim_date(year);
CREATE INDEX idx_dim_date_month ON dim_date(month);
CREATE INDEX idx_dim_date_quarter ON dim_date(quarter);

-- Comments
COMMENT ON TABLE dim_date IS 'Date dimension for time-based analysis';
COMMENT ON COLUMN dim_date.date_id IS 'Date';
COMMENT ON COLUMN dim_date.day IS 'Day of month (1-31)';
COMMENT ON COLUMN dim_date.month IS 'Month (1-12)';
COMMENT ON COLUMN dim_date.year IS 'Year';
COMMENT ON COLUMN dim_date.quarter IS 'Quarter (1-4)';
COMMENT ON COLUMN dim_date.day_of_week IS 'Day of week (0-6, Sunday=0)';
COMMENT ON COLUMN dim_date.is_weekend IS 'Whether date is weekend';
COMMENT ON COLUMN dim_date.is_holiday IS 'Whether date is holiday';
