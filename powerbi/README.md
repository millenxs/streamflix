# Power BI Setup Guide

This guide explains how to connect Power BI to the StreamFlix PostgreSQL database and create the dashboards.

---

## 🔌 Prerequisites

### 1. PostgreSQL ODBC Driver

Power BI requires the PostgreSQL ODBC driver to connect to the database.

#### Windows
1. Download the PostgreSQL ODBC driver from: https://www.postgresql.org/ftp/odbc/versions/msi/
2. Install the driver (psqlODBC x64)
3. Verify installation in ODBC Data Source Administrator (odbcad32.exe)

#### WSL2 Connection
If PostgreSQL is running in WSL2 Docker:
1. Find WSL2 IP address: In WSL, run `hostname -I`
2. The IP will be something like `172.x.x.x`
3. Use this IP instead of `localhost` in Power BI connection
4. Ensure port 5432 is accessible from Windows

### 2. Database Credentials

Use the credentials from your `.env` file:
- **Server**: `localhost` (or WSL2 IP if using WSL2)
- **Port**: `5432`
- **Database**: `streamflix`
- **Username**: `streamflix`
- **Password**: `streamflix123` (or your configured password)

---

## 📊 Connecting Power BI to PostgreSQL

### Step 1: Open Power BI Desktop

Launch Power BI Desktop on your Windows machine.

### Step 2: Get Data

1. Click **Get Data** in the Home ribbon
2. Select **Database** → **PostgreSQL database**
3. Click **Connect**

### Step 3: Enter Connection Details

```
Server: localhost (or WSL2 IP, e.g., 172.x.x.x)
Database: streamflix
```

### Step 4: Authentication

1. Select **Database** authentication
2. Enter **Username**: `streamflix`
3. Enter **Password**: `streamflix123`
4. Click **Connect**

### Step 5: Select Tables/Views

Select the following tables and views for the initial dashboard:

**Dimension Tables**:
- dim_users
- dim_content
- dim_genre
- dim_device
- dim_location
- dim_date

**Fact Tables**:
- fact_watch_events
- fact_sessions
- fact_user_interactions
- fact_recommendations
- fact_recommendation_feedback

**Analytics Views** (after ETL):
- vw_kpis
- vw_content_analytics
- vw_user_behavior
- vw_retention
- vw_churn
- vw_recommendations

### Step 6: Load Data

Click **Load** to import the data into Power BI.

---

## 🔗 Setting Up Relationships

Power BI should auto-detect relationships based on foreign keys. Verify and adjust if needed:

### Relationships to Verify

1. **fact_watch_events → dim_users**
   - `fact_watch_events.user_id` → `dim_users.user_id`
   - Relationship: Many-to-One (*:1)
   - Cross filter direction: Single

2. **fact_watch_events → dim_content**
   - `fact_watch_events.content_id` → `dim_content.content_id`
   - Relationship: Many-to-One (*:1)
   - Cross filter direction: Single

3. **fact_watch_events → dim_date**
   - `fact_watch_events.date_id` → `dim_date.date_id`
   - Relationship: Many-to-One (*:1)
   - Cross filter direction: Single

4. **fact_watch_events → dim_device**
   - `fact_watch_events.device_id` → `dim_device.device_id`
   - Relationship: Many-to-One (*:1)
   - Cross filter direction: Single

5. **fact_watch_events → dim_location**
   - `fact_watch_events.location_id` → `dim_location.location_id`
   - Relationship: Many-to-One (*:1)
   - Cross filter direction: Single

6. **fact_sessions → dim_users**
   - `fact_sessions.user_id` → `dim_users.user_id`
   - Relationship: Many-to-One (*:1)
   - Cross filter direction: Single

7. **fact_recommendations → dim_users**
   - `fact_recommendations.user_id` → `dim_users.user_id`
   - Relationship: Many-to-One (*:1)
   - Cross filter direction: Single

8. **fact_recommendations → dim_content**
   - `fact_recommendations.content_id` → `dim_content.content_id`
   - Relationship: Many-to-One (*:1)
   - Cross filter direction: Single

---

## 📈 Creating Dashboards

### Page 1: Executive Overview

**Purpose**: High-level business metrics for executives.

**Visualizations**:

1. **MAU Trend**
   - Type: Line chart
   - X-axis: dim_date.date_id (Month)
   - Y-axis: MAU (measure)
   - Filter: Last 12 months

2. **Watch Time Trend**
   - Type: Line chart
   - X-axis: dim_date.date_id (Month)
   - Y-axis: Watch Time (hours)
   - Filter: Last 12 months

3. **Retention Rate (7d, 30d)**
   - Type: Multi-row card
   - Values: Retention 7d, Retention 30d

4. **Churn Rate Trend**
   - Type: Line chart
   - X-axis: dim_date.date_id (Month)
   - Y-axis: Churn Rate (%)
   - Filter: Last 12 months

5. **Completion Rate**
   - Type: Gauge chart
   - Value: Completion Rate (%)
   - Target: 70%

6. **Recommendation CTR**
   - Type: Line chart
   - X-axis: dim_date.date_id (Month)
   - Y-axis: Recommendation CTR (%)
   - Filter: Last 12 months

**DAX Measures**:
See `powerbi/dax/kpi_measures.dax`

---

### Page 2: Content Analytics

**Purpose**: Analyze content performance.

**Visualizations**:

1. **Top 10 Titles by Watch Time**
   - Type: Bar chart
   - X-axis: dim_content.title
   - Y-axis: Watch Time (hours)
   - Filter: Top 10 by Watch Time

2. **Genre Distribution**
   - Type: Donut chart
   - Values: Watch Time by genre
   - Category: dim_genre.genre_name

3. **Completion Rate by Genre**
   - Type: Clustered bar chart
   - X-axis: dim_genre.genre_name
   - Y-axis: Completion Rate (%)

4. **Abandonment Rate by Genre**
   - Type: Clustered bar chart
   - X-axis: dim_genre.genre_name
   - Y-axis: Abandonment Rate (%)

5. **Content Type Distribution**
   - Type: Pie chart
   - Values: Count by content_type (movie/series)

6. **Watch Time Heatmap (Genre vs Month)**
   - Type: Matrix
   - Rows: dim_genre.genre_name
   - Columns: dim_date.month
   - Values: Watch Time

---

### Page 3: User Behavior

**Purpose**: Understand user activity patterns.

**Visualizations**:

1. **DAU/WAU/MAU Trend**
   - Type: Line chart (3 lines)
   - X-axis: dim_date.date_id
   - Y-axis: Active users
   - Legend: DAU, WAU, MAU

2. **Peak Hours Heatmap**
   - Type: Matrix
   - Rows: Hour of day (extracted from timestamp)
   - Columns: Day of week
   - Values: Event count

3. **Device Distribution**
   - Type: Donut chart
   - Values: Event count
   - Category: dim_device.device_type

4. **Session Duration Distribution**
   - Type: Histogram
   - X-axis: fact_sessions.duration_seconds (in minutes)
   - Y-axis: Count

5. **Geographic Distribution**
   - Type: Map
   - Location: dim_location.country
   - Size: Event count

6. **User Frequency**
   - Type: Column chart
   - X-axis: Sessions per user (buckets)
   - Y-axis: User count

---

### Page 4: Retention & Churn

**Purpose**: Analyze user retention and churn patterns.

**Visualizations**:

1. **Cohort Retention Table**
   - Type: Matrix
   - Rows: Cohort (signup month)
   - Columns: Day (0, 7, 30, 90)
   - Values: Retention rate (%)

2. **Churn Rate Trend**
   - Type: Line chart
   - X-axis: dim_date.date_id (Month)
   - Y-axis: Churn Rate (%)

3. **Churn Rate by Taste Cluster**
   - Type: Clustered bar chart
   - X-axis: Taste Cluster
   - Y-axis: Churn Rate (%)

4. **Churn Predictors**
   - Type: Ribbon chart
   - X-axis: Churn probability buckets
   - Y-axis: User count
   - Legend: High/Medium/Low risk

5. **Days Since Last Session Distribution**
   - Type: Histogram
   - X-axis: Days since last session
   - Y-axis: User count

6. **Churn by Watch Time**
   - Type: Scatter plot
   - X-axis: Watch hours last 30d
   - Y-axis: Churn probability
   - Size: User count

---

### Page 5: Recommendation Performance

**Purpose**: Analyze recommendation effectiveness.

**Visualizations**:

1. **Recommendation CTR Trend**
   - Type: Line chart
   - X-axis: dim_date.date_id (Month)
   - Y-axis: Recommendation CTR (%)

2. **CTR by Algorithm**
   - Type: Clustered bar chart
   - X-axis: Algorithm (popularity, content_based, collaborative, hybrid)
   - Y-axis: CTR (%)

3. **Conversion Rate Trend**
   - Type: Line chart
   - X-axis: dim_date.date_id (Month)
   - Y-axis: Conversion Rate (%)

4. **Completion Rate by Algorithm**
   - Type: Clustered bar chart
   - X-axis: Algorithm
   - Y-axis: Completion Rate (%)

5. **CTR by Taste Cluster**
   - Type: Clustered bar chart
   - X-axis: Taste Cluster
   - Y-axis: CTR (%)

6. **Recommendation Funnel**
   - Type: Funnel chart
   - Stages: Impressions → Clicks → Plays → Completes

---

### Page 6: Taste Clusters

**Purpose**: Analyze user segments.

**Visualizations**:

1. **Cluster Size Distribution**
   - Type: Pie chart
   - Values: User count
   - Category: Taste Cluster

2. **Watch Time by Cluster**
   - Type: Clustered bar chart
   - X-axis: Taste Cluster
   - Y-axis: Watch Time (hours)

3. **Completion Rate by Cluster**
   - Type: Clustered bar chart
   - X-axis: Taste Cluster
   - Y-axis: Completion Rate (%)

4. **Churn Rate by Cluster**
   - Type: Clustered bar chart
   - X-axis: Taste Cluster
   - Y-axis: Churn Rate (%)

5. **Genre Preferences by Cluster**
   - Type: Stacked bar chart
   - X-axis: Taste Cluster
   - Y-axis: Watch Time
   - Legend: Genre

6. **Device Usage by Cluster**
   - Type: 100% Stacked column chart
   - X-axis: Taste Cluster
   - Y-axis: Percentage
   - Legend: Device type

---

## 📝 DAX Measures

### Basic KPI Measures

Create a calculated table or measures in Power BI using the DAX formulas in `powerbi/dax/kpi_measures.dax`.

Key measures include:
- DAU, WAU, MAU
- Watch Time
- Average Session Duration
- Completion Rate
- Abandonment Rate
- CTR
- Recommendation CTR
- Retention Rate
- Churn Rate
- Engagement Rate

### Example DAX Measure

```dax
// MAU (Monthly Active Users)
MAU = 
CALCULATE(
    DISTINCTCOUNT(fact_watch_events[user_id]),
    DATESINPERIOD(
        dim_date[date_id],
        MAX(dim_date[date_id]),
        -30,
        DAY
    ),
    fact_watch_events[event_type] IN {"play", "content_click", "search"}
)

// Completion Rate
Completion Rate = 
DIVIDE(
    COUNTROWS(FILTER(fact_watch_events, fact_watch_events[completed] = TRUE)),
    COUNTROWS(fact_watch_events),
    0
) * 100
```

---

## 🔄 Refreshing Data

### Manual Refresh

1. Click **Refresh** in the Home ribbon
2. Power BI will reconnect to PostgreSQL and fetch latest data

### Scheduled Refresh (Power BI Service)

If publishing to Power BI Service:
1. Publish the report to Power BI Service
2. Go to Dataset settings
3. Configure scheduled refresh (e.g., daily)
4. Ensure gateway is configured if using on-premises PostgreSQL

---

## 🐛 Troubleshooting

### Connection Issues

**Problem**: Cannot connect to PostgreSQL

**Solutions**:
1. Verify PostgreSQL is running: `docker ps`
2. Check if using WSL2 IP instead of localhost
3. Verify ODBC driver is installed
4. Check firewall settings
5. Test connection with psql: `psql -h localhost -U streamflix -d streamflix`

### WSL2 IP Changes

**Problem**: WSL2 IP changes after restart

**Solution**:
1. Create a PowerShell script to update WSL2 IP in hosts file
2. Or use Docker's host access feature
3. Or configure Docker to use a fixed IP

### Performance Issues

**Problem**: Power BI is slow to load data

**Solutions**:
1. Use SQL views instead of raw tables
2. Add indexes in PostgreSQL
3. Reduce data volume (filter by date range)
4. Use incremental refresh
5. Use DirectQuery instead of Import mode

### Relationship Issues

**Problem**: Relationships not detected correctly

**Solutions**:
1. Manually create relationships in Manage Relationships
2. Ensure data types match (INTEGER to INTEGER)
3. Check for duplicate values in dimension tables

---

## 📚 Tableau Compatibility

The SQL views are designed to be compatible with Tableau as well:

1. In Tableau, select **Connect to Server** → **PostgreSQL**
2. Enter the same connection details
3. Select the same tables/views
4. Tableau will auto-detect relationships
5. Create visualizations using Tableau's drag-and-drop interface

The data model is generic enough to work with any BI tool that supports PostgreSQL.

---

## 📸 Screenshots

After creating dashboards, add screenshots to `powerbi/screenshots/` for documentation.

Naming convention:
- `executive_overview.png`
- `content_analytics.png`
- `user_behavior.png`
- `retention_churn.png`
- `recommendation_performance.png`
- `taste_clusters.png`

---

*Document updated: 2025-01-05*
