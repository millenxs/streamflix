-- =============================================================================
-- StreamFlix Populate Date Dimension
-- This script populates the dim_date table with dates
-- =============================================================================

-- Populate dim_date with dates from 2020-01-01 to 2030-12-31
INSERT INTO dim_date (date_id, day, month, year, quarter, day_of_week, is_weekend)
SELECT
    generate_series AS date_id,
    EXTRACT(DAY FROM generate_series)::INTEGER AS day,
    EXTRACT(MONTH FROM generate_series)::INTEGER AS month,
    EXTRACT(YEAR FROM generate_series)::INTEGER AS year,
    EXTRACT(QUARTER FROM generate_series)::INTEGER AS quarter,
    EXTRACT(DOW FROM generate_series)::INTEGER AS day_of_week,
    (EXTRACT(DOW FROM generate_series) IN (0, 6))::BOOLEAN AS is_weekend
FROM generate_series('2020-01-01'::DATE, '2030-12-31'::DATE, '1 day'::INTERVAL);

-- Create index for faster date range queries
CREATE INDEX idx_dim_date_range ON dim_date(date_id);

-- Verify the population
SELECT COUNT(*) AS total_dates FROM dim_date;
SELECT MIN(date_id) AS min_date, MAX(date_id) AS max_date FROM dim_date;
