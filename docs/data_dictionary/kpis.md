# KPI Definitions

This document defines all Key Performance Indicators (KPIs) used in the StreamFlix platform, with mathematical formulas and implementation notes.

---

## 📊 USER ENGAGEMENT KPIs

### DAU (Daily Active Users)

**Definition**: Number of unique users who engaged with the platform on a given day.

**Formula**:
```
DAU(date) = COUNT(DISTINCT user_id)
WHERE date_id = date
AND event_type IN ('play', 'content_click', 'search')
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(DISTINCT user_id) AS dau
FROM fact_watch_events
WHERE event_type IN ('play', 'content_click', 'search')
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_dau(df: pd.DataFrame, date: str) -> int:
    return df[df['date_id'] == date]['user_id'].nunique()
```

**Notes**:
- Active user = user who performed at least one engagement action
- Engagement actions: play, content_click, search
- Does not count passive views (impressions)

---

### WAU (Weekly Active Users)

**Definition**: Number of unique users who engaged with the platform in a 7-day period.

**Formula**:
```
WAU(date) = COUNT(DISTINCT user_id)
WHERE date_id BETWEEN date - 6 days AND date
AND event_type IN ('play', 'content_click', 'search')
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(DISTINCT user_id) AS wau
FROM fact_watch_events
WHERE date_id BETWEEN date_id - INTERVAL '6 days' AND date_id
AND event_type IN ('play', 'content_click', 'search')
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_wau(df: pd.DataFrame, date: str) -> int:
    start_date = pd.to_datetime(date) - pd.Timedelta(days=6)
    mask = (df['date_id'] >= start_date) & (df['date_id'] <= date)
    return df[mask]['user_id'].nunique()
```

**Notes**:
- Rolling 7-day window
- Same engagement actions as DAU

---

### MAU (Monthly Active Users)

**Definition**: Number of unique users who engaged with the platform in a 30-day period.

**Formula**:
```
MAU(date) = COUNT(DISTINCT user_id)
WHERE date_id BETWEEN date - 29 days AND date
AND event_type IN ('play', 'content_click', 'search')
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(DISTINCT user_id) AS mau
FROM fact_watch_events
WHERE date_id BETWEEN date_id - INTERVAL '29 days' AND date_id
AND event_type IN ('play', 'content_click', 'search')
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_mau(df: pd.DataFrame, date: str) -> int:
    start_date = pd.to_datetime(date) - pd.Timedelta(days=29)
    mask = (df['date_id'] >= start_date) & (df['date_id'] <= date)
    return df[mask]['user_id'].nunique()
```

**Notes**:
- Rolling 30-day window
- Same engagement actions as DAU/WAU

---

## ⏱️ CONTENT CONSUMPTION KPIs

### Watch Time

**Definition**: Total time users spent watching content in a given period.

**Formula**:
```
Watch Time(period) = SUM(watch_seconds) / 3600
WHERE timestamp IN period
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    SUM(watch_seconds) / 3600.0 AS watch_time_hours
FROM fact_watch_events
WHERE event_type = 'play'
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_watch_time(df: pd.DataFrame, start_date: str, end_date: str) -> float:
    mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    return df[mask]['watch_seconds'].sum() / 3600.0
```

**Notes**:
- Measured in hours
- Only counts 'play' events
- Includes re-watches

---

### Average Session Duration

**Definition**: Average length of user sessions in a given period.

**Formula**:
```
Avg Session Duration(period) = AVG(duration_seconds) / 60
WHERE start_time IN period
```

**SQL Implementation**:
```sql
SELECT
    DATE(start_time) AS date,
    AVG(duration_seconds) / 60.0 AS avg_session_duration_minutes
FROM fact_sessions
WHERE duration_seconds IS NOT NULL
GROUP BY DATE(start_time);
```

**Python Implementation**:
```python
def calculate_avg_session_duration(df: pd.DataFrame, start_date: str, end_date: str) -> float:
    mask = (df['start_time'] >= start_date) & (df['start_time'] <= end_date)
    return df[mask]['duration_seconds'].mean() / 60.0
```

**Notes**:
- Measured in minutes
- Only includes completed sessions (end_time IS NOT NULL)
- Excludes sessions with duration_seconds = 0

---

### Completion Rate

**Definition**: Percentage of watch events where the user completed the content.

**Formula**:
```
Completion Rate(period) = COUNT(completed = TRUE) / COUNT(total) * 100
WHERE timestamp IN period
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(CASE WHEN completed = TRUE THEN 1 END) * 100.0 / COUNT(*) AS completion_rate
FROM fact_watch_events
WHERE event_type = 'play'
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_completion_rate(df: pd.DataFrame, start_date: str, end_date: str) -> float:
    mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    subset = df[mask]
    return (subset['completed'].sum() / len(subset)) * 100.0
```

**Notes**:
- Percentage (0-100)
- Content is considered completed if watch_seconds >= 90% of duration
- Only counts 'play' events

---

### Abandonment Rate

**Definition**: Percentage of watch events where the user abandoned the content before completion.

**Formula**:
```
Abandonment Rate(period) = COUNT(completed = FALSE) / COUNT(total) * 100
WHERE timestamp IN period
AND event_type = 'stop'
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(CASE WHEN completed = FALSE THEN 1 END) * 100.0 / COUNT(*) AS abandonment_rate
FROM fact_watch_events
WHERE event_type = 'stop'
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_abandonment_rate(df: pd.DataFrame, start_date: str, end_date: str) -> float:
    mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    mask &= (df['event_type'] == 'stop')
    subset = df[mask]
    return ((~subset['completed']).sum() / len(subset)) * 100.0
```

**Notes**:
- Percentage (0-100)
- Only counts 'stop' events (explicit abandonment)
- Complement of completion rate (ignoring pause/resume)

---

## 🎯 INTERACTION KPIs

### CTR (Click-Through Rate)

**Definition**: Percentage of content impressions that resulted in a click.

**Formula**:
```
CTR(period) = COUNT(content_click) / COUNT(content_impression) * 100
WHERE timestamp IN period
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(CASE WHEN event_type = 'content_click' THEN 1 END) * 100.0 /
    COUNT(CASE WHEN event_type = 'content_impression' THEN 1 END) AS ctr
FROM fact_watch_events
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_ctr(df: pd.DataFrame, start_date: str, end_date: str) -> float:
    mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    subset = df[mask]
    clicks = (subset['event_type'] == 'content_click').sum()
    impressions = (subset['event_type'] == 'content_impression').sum()
    return (clicks / impressions * 100.0) if impressions > 0 else 0.0
```

**Notes**:
- Percentage (0-100)
- Only counts content clicks, not recommendations
- CTR = 0 if no impressions

---

### Recommendation CTR

**Definition**: Percentage of recommendation impressions that resulted in a click.

**Formula**:
```
Rec CTR(period) = COUNT(recommendation_click) / COUNT(recommendation_impression) * 100
WHERE timestamp IN period
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(CASE WHEN feedback_type = 'click' THEN 1 END) * 100.0 /
    COUNT(CASE WHEN feedback_type = 'impression' THEN 1 END) AS recommendation_ctr
FROM fact_recommendation_feedback
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_recommendation_ctr(df: pd.DataFrame, start_date: str, end_date: str) -> float:
    mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    subset = df[mask]
    clicks = (subset['feedback_type'] == 'click').sum()
    impressions = (subset['feedback_type'] == 'impression').sum()
    return (clicks / impressions * 100.0) if impressions > 0 else 0.0
```

**Notes**:
- Percentage (0-100)
- Measures recommendation effectiveness
- Only from fact_recommendation_feedback

---

## 📈 RETENTION & CHURN KPIs

### Retention Rate

**Definition**: Percentage of users who return to the platform after their first session.

**Formula**:
```
Retention Rate(cohort, day_n) = COUNT(users active on day_n) / COUNT(cohort users) * 100
WHERE user IN cohort
AND day_n = signup_date + n days
```

**SQL Implementation**:
```sql
WITH cohort_users AS (
    SELECT user_id, signup_date
    FROM dim_users
    WHERE signup_date = '2024-01-01'
),
retention AS (
    SELECT
        cu.user_id,
        cu.signup_date,
        COUNT(DISTINCT CASE WHEN fwe.date_id = cu.signup_date + INTERVAL '7 days' THEN 1 END) AS retained_7d,
        COUNT(DISTINCT CASE WHEN fwe.date_id = cu.signup_date + INTERVAL '30 days' THEN 1 END) AS retained_30d
    FROM cohort_users cu
    LEFT JOIN fact_watch_events fwe ON cu.user_id = fwe.user_id
    GROUP BY cu.user_id, cu.signup_date
)
SELECT
    AVG(retained_7d) * 100.0 AS retention_7d_rate,
    AVG(retained_30d) * 100.0 AS retention_30d_rate
FROM retention;
```

**Python Implementation**:
```python
def calculate_retention_rate(df: pd.DataFrame, cohort_date: str, day_n: int) -> float:
    cohort_users = df[df['signup_date'] == cohort_date]['user_id'].unique()
    target_date = pd.to_datetime(cohort_date) + pd.Timedelta(days=day_n)
    active_users = df[
        (df['user_id'].isin(cohort_users)) &
        (df['date_id'] == target_date)
    ]['user_id'].nunique()
    return (active_users / len(cohort_users)) * 100.0 if len(cohort_users) > 0 else 0.0
```

**Notes**:
- Percentage (0-100)
- Cohort-based analysis
- Typically measured at 7, 30, 90 days

---

### Churn Rate

**Definition**: Percentage of users who have not engaged with the platform in the last 30 days.

**Formula**:
```
Churn Rate(date) = COUNT(users inactive for 30 days) / COUNT(total users) * 100
WHERE last_activity_date < date - 30 days
```

**SQL Implementation**:
```sql
SELECT
    COUNT(CASE WHEN last_activity_date < CURRENT_DATE - INTERVAL '30 days' THEN 1 END) * 100.0 / COUNT(*) AS churn_rate
FROM (
    SELECT
        user_id,
        MAX(date_id) AS last_activity_date
    FROM fact_watch_events
    GROUP BY user_id
) user_activity;
```

**Python Implementation**:
```python
def calculate_churn_rate(df: pd.DataFrame, date: str) -> float:
    last_activity = df.groupby('user_id')['date_id'].max().reset_index()
    cutoff_date = pd.to_datetime(date) - pd.Timedelta(days=30)
    churned = (last_activity['date_id'] < cutoff_date).sum()
    total = len(last_activity)
    return (churned / total) * 100.0 if total > 0 else 0.0
```

**Notes**:
- Percentage (0-100)
- User is considered churned if inactive for 30 days
- Can be calculated by cohort or overall

---

### Engagement Rate

**Definition**: Percentage of total users who are active in a given period.

**Formula**:
```
Engagement Rate(period) = COUNT(active users) / COUNT(total users) * 100
WHERE last_activity_date IN period
```

**SQL Implementation**:
```sql
SELECT
    COUNT(CASE WHEN last_activity_date >= CURRENT_DATE - INTERVAL '30 days' THEN 1 END) * 100.0 / COUNT(*) AS engagement_rate
FROM (
    SELECT
        user_id,
        MAX(date_id) AS last_activity_date
    FROM fact_watch_events
    GROUP BY user_id
) user_activity;
```

**Python Implementation**:
```python
def calculate_engagement_rate(df: pd.DataFrame, date: str, days: int = 30) -> float:
    last_activity = df.groupby('user_id')['date_id'].max().reset_index()
    cutoff_date = pd.to_datetime(date) - pd.Timedelta(days=days)
    active = (last_activity['date_id'] >= cutoff_date).sum()
    total = len(last_activity)
    return (active / total) * 100.0 if total > 0 else 0.0
```

**Notes**:
- Percentage (0-100)
- Complement of churn rate (for same period)
- Typically measured as 30-day engagement rate

---

## 🎯 RECOMMENDATION KPIs

### Recommendation Conversion Rate

**Definition**: Percentage of recommendation clicks that resulted in a play event.

**Formula**:
```
Rec Conversion Rate(period) = COUNT(play_from_recommendation) / COUNT(recommendation_click) * 100
WHERE timestamp IN period
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(CASE WHEN feedback_type = 'play' THEN 1 END) * 100.0 /
    COUNT(CASE WHEN feedback_type = 'click' THEN 1 END) AS recommendation_conversion_rate
FROM fact_recommendation_feedback
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_recommendation_conversion_rate(df: pd.DataFrame, start_date: str, end_date: str) -> float:
    mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    subset = df[mask]
    plays = (subset['feedback_type'] == 'play').sum()
    clicks = (subset['feedback_type'] == 'click').sum()
    return (plays / clicks * 100.0) if clicks > 0 else 0.0
```

**Notes**:
- Percentage (0-100)
- Measures how many clicked recommendations actually resulted in watching
- Higher than CTR typically

---

### Recommendation Completion Rate

**Definition**: Percentage of recommendation plays that were completed.

**Formula**:
```
Rec Completion Rate(period) = COUNT(complete_from_recommendation) / COUNT(play_from_recommendation) * 100
WHERE timestamp IN period
```

**SQL Implementation**:
```sql
SELECT
    date_id,
    COUNT(CASE WHEN feedback_type = 'complete' THEN 1 END) * 100.0 /
    COUNT(CASE WHEN feedback_type = 'play' THEN 1 END) AS recommendation_completion_rate
FROM fact_recommendation_feedback
GROUP BY date_id;
```

**Python Implementation**:
```python
def calculate_recommendation_completion_rate(df: pd.DataFrame, start_date: str, end_date: str) -> float:
    mask = (df['timestamp'] >= start_date) & (df['timestamp'] <= end_date)
    subset = df[mask]
    completes = (subset['feedback_type'] == 'complete').sum()
    plays = (subset['feedback_type'] == 'play').sum()
    return (completes / plays * 100.0) if plays > 0 else 0.0
```

**Notes**:
- Percentage (0-100)
- Measures quality of recommendations
- High completion rate = good recommendations

---

## 📊 KPI CONSISTENCY

### Implementation Consistency

All KPIs must use the same definitions across:
- SQL queries (PostgreSQL)
- Python calculations (Pandas)
- Power BI measures (DAX)
- API responses (FastAPI)

### Testing Strategy

1. **Unit tests**: Test each KPI calculation function
2. **Integration tests**: Compare SQL vs Python results
3. **Consistency tests**: Ensure Power BI matches backend
4. **Regression tests**: Detect changes in KPI logic

### Example Consistency Test

```python
def test_kpi_consistency():
    # Calculate DAU via Python
    dau_python = calculate_dau(df, '2024-01-01')
    
    # Calculate DAU via SQL
    dau_sql = execute_sql("SELECT COUNT(DISTINCT user_id) FROM fact_watch_events WHERE date_id = '2024-01-01'")
    
    # Assert consistency
    assert dau_python == dau_sql, f"DAU mismatch: Python={dau_python}, SQL={dau_sql}"
```

---

## 🎯 KPI DASHBOARD STRUCTURE

### Executive Overview
- MAU (trend)
- Watch Time (trend)
- Retention Rate (7d, 30d)
- Churn Rate (trend)
- Completion Rate (trend)
- Recommendation CTR (trend)

### Content Analytics
- Watch Time by content
- Completion Rate by content
- Abandonment Rate by content
- Top 10 titles by watch time
- Genre distribution

### User Behavior
- DAU/WAU/MAU trend
- Peak hours heatmap
- Device distribution
- Session duration distribution
- Geographic distribution

### Retention & Churn
- Cohort retention table
- Churn rate by segment
- Churn rate by taste cluster
- Churn predictors

### Recommendation Performance
- Recommendation CTR (trend)
- Conversion rate (trend)
- Completion rate (trend)
- CTR by algorithm
- CTR by taste cluster

### Taste Clusters
- Cluster size distribution
- Watch time by cluster
- Completion rate by cluster
- Churn rate by cluster
- Genre preferences by cluster

---

*Document updated: 2025-01-05*
