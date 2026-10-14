-- =============================================================================
-- StreamFlix Analytics Views
-- Dashboard-ready KPI views derived from warehouse fact tables.
-- =============================================================================

CREATE OR REPLACE VIEW vw_daily_engagement AS
SELECT
    date_dim.date_id,
    COUNT(DISTINCT watch.user_id) FILTER (WHERE watch.event_type = 'play') AS daily_active_users,
    COUNT(*) FILTER (WHERE watch.event_type = 'play') AS play_events,
    COALESCE(SUM(watch.watch_seconds), 0) / 3600.0 AS watch_time_hours,
    COALESCE(AVG(session.duration_seconds), 0) / 60.0 AS avg_session_duration_minutes,
    COUNT(*) FILTER (WHERE watch.event_type = 'complete')::decimal
        / NULLIF(COUNT(*) FILTER (WHERE watch.event_type IN ('complete', 'stop')), 0) AS completion_rate,
    COUNT(*) FILTER (WHERE watch.event_type = 'stop')::decimal
        / NULLIF(COUNT(*) FILTER (WHERE watch.event_type IN ('complete', 'stop')), 0) AS abandonment_rate
FROM dim_date date_dim
LEFT JOIN fact_watch_events watch ON watch.date_id = date_dim.date_id
LEFT JOIN fact_sessions session ON session.start_time::date = date_dim.date_id
GROUP BY date_dim.date_id;

CREATE OR REPLACE VIEW vw_content_performance AS
SELECT
    content.content_id,
    content.title,
    content.content_type,
    genre.genre_name AS primary_genre,
    COUNT(DISTINCT watch.user_id) AS unique_viewers,
    COUNT(*) FILTER (WHERE watch.event_type = 'play') AS plays,
    COALESCE(SUM(watch.watch_seconds), 0) / 3600.0 AS watch_time_hours,
    COUNT(*) FILTER (WHERE watch.event_type = 'complete')::decimal
        / NULLIF(COUNT(*) FILTER (WHERE watch.event_type IN ('complete', 'stop')), 0) AS completion_rate,
    COUNT(*) FILTER (WHERE watch.event_type = 'stop')::decimal
        / NULLIF(COUNT(*) FILTER (WHERE watch.event_type IN ('complete', 'stop')), 0) AS abandonment_rate,
    COUNT(interaction.interaction_id) FILTER (WHERE interaction.interaction_type = 'like') AS likes,
    COUNT(interaction.interaction_id) FILTER (WHERE interaction.interaction_type = 'dislike') AS dislikes
FROM dim_content content
LEFT JOIN dim_genre genre ON genre.genre_id = content.primary_genre_id
LEFT JOIN fact_watch_events watch ON watch.content_id = content.content_id
LEFT JOIN fact_user_interactions interaction ON interaction.content_id = content.content_id
GROUP BY content.content_id, content.title, content.content_type, genre.genre_name;

CREATE OR REPLACE VIEW vw_device_usage AS
SELECT
    watch.date_id,
    device.device_type,
    COUNT(DISTINCT watch.user_id) AS active_users,
    COUNT(*) FILTER (WHERE watch.event_type = 'play') AS plays,
    COALESCE(SUM(watch.watch_seconds), 0) / 3600.0 AS watch_time_hours
FROM fact_watch_events watch
JOIN dim_device device ON device.device_id = watch.device_id
GROUP BY watch.date_id, device.device_type;

CREATE OR REPLACE VIEW vw_recommendation_performance AS
SELECT
    feedback.timestamp::date AS date_id,
    recommendation.algorithm,
    COUNT(*) FILTER (WHERE feedback.feedback_type = 'impression') AS impressions,
    COUNT(*) FILTER (WHERE feedback.feedback_type = 'click') AS clicks,
    COUNT(*) FILTER (WHERE feedback.feedback_type = 'play') AS plays,
    COUNT(*) FILTER (WHERE feedback.feedback_type = 'complete') AS completes,
    COUNT(*) FILTER (WHERE feedback.feedback_type = 'click')::decimal
        / NULLIF(COUNT(*) FILTER (WHERE feedback.feedback_type = 'impression'), 0) AS recommendation_ctr,
    COUNT(*) FILTER (WHERE feedback.feedback_type = 'play')::decimal
        / NULLIF(COUNT(*) FILTER (WHERE feedback.feedback_type = 'click'), 0) AS recommendation_conversion_rate,
    COUNT(*) FILTER (WHERE feedback.feedback_type = 'complete')::decimal
        / NULLIF(COUNT(*) FILTER (WHERE feedback.feedback_type = 'play'), 0) AS recommendation_completion_rate
FROM fact_recommendation_feedback feedback
JOIN fact_recommendations recommendation ON recommendation.recommendation_id = feedback.recommendation_id
GROUP BY feedback.timestamp::date, recommendation.algorithm;

CREATE OR REPLACE VIEW vw_user_retention_churn AS
WITH user_activity AS (
    SELECT
        users.user_id,
        users.signup_date,
        MAX(watch.date_id) AS last_activity_date,
        COUNT(DISTINCT watch.date_id) AS active_days,
        COALESCE(SUM(watch.watch_seconds), 0) / 3600.0 AS lifetime_watch_hours
    FROM dim_users users
    LEFT JOIN fact_watch_events watch ON watch.user_id = users.user_id
    GROUP BY users.user_id, users.signup_date
)
SELECT
    user_id,
    signup_date,
    last_activity_date,
    active_days,
    lifetime_watch_hours,
    CASE
        WHEN last_activity_date IS NULL THEN TRUE
        WHEN last_activity_date < CURRENT_DATE - INTERVAL '30 days' THEN TRUE
        ELSE FALSE
    END AS is_churned_30d,
    CASE
        WHEN last_activity_date >= signup_date + INTERVAL '7 days' THEN TRUE
        ELSE FALSE
    END AS retained_7d,
    CASE
        WHEN last_activity_date >= signup_date + INTERVAL '30 days' THEN TRUE
        ELSE FALSE
    END AS retained_30d
FROM user_activity;

CREATE OR REPLACE VIEW vw_executive_kpis AS
SELECT
    daily.date_id,
    daily.daily_active_users,
    COUNT(DISTINCT rolling_7.user_id) AS weekly_active_users,
    COUNT(DISTINCT rolling_30.user_id) AS monthly_active_users,
    daily.watch_time_hours,
    daily.avg_session_duration_minutes,
    daily.completion_rate,
    daily.abandonment_rate,
    rec.recommendation_ctr,
    rec.recommendation_conversion_rate,
    rec.recommendation_completion_rate
FROM vw_daily_engagement daily
LEFT JOIN fact_watch_events rolling_7
    ON rolling_7.date_id BETWEEN daily.date_id - INTERVAL '6 days' AND daily.date_id
   AND rolling_7.event_type = 'play'
LEFT JOIN fact_watch_events rolling_30
    ON rolling_30.date_id BETWEEN daily.date_id - INTERVAL '29 days' AND daily.date_id
   AND rolling_30.event_type = 'play'
LEFT JOIN (
    SELECT
        date_id,
        SUM(clicks)::decimal / NULLIF(SUM(impressions), 0) AS recommendation_ctr,
        SUM(plays)::decimal / NULLIF(SUM(clicks), 0) AS recommendation_conversion_rate,
        SUM(completes)::decimal / NULLIF(SUM(plays), 0) AS recommendation_completion_rate
    FROM vw_recommendation_performance
    GROUP BY date_id
) rec ON rec.date_id = daily.date_id
GROUP BY
    daily.date_id,
    daily.daily_active_users,
    daily.watch_time_hours,
    daily.avg_session_duration_minutes,
    daily.completion_rate,
    daily.abandonment_rate,
    rec.recommendation_ctr,
    rec.recommendation_conversion_rate,
    rec.recommendation_completion_rate;
