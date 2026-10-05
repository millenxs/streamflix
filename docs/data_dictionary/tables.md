# Data Dictionary - Tables

This document describes all tables in the StreamFlix database.

---

## 📦 RAW LAYER

### raw_events

**Purpose**: Immutable storage of all behavioral events from Kafka.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| event_id | UUID | Unique identifier for the event | PRIMARY KEY |
| event_type | VARCHAR(50) | Type of event (play, pause, click, etc.) | NOT NULL |
| user_id | INTEGER | Foreign key to dim_users | NOT NULL |
| session_id | UUID | Unique session identifier | NOT NULL |
| content_id | INTEGER | Foreign key to dim_content | NULL |
| timestamp | TIMESTAMP WITH TIME ZONE | When the event occurred | NOT NULL |
| device_type | VARCHAR(50) | Device that generated the event | NULL |
| country | VARCHAR(3) | ISO 3166-1 alpha-3 country code | NULL |
| region | VARCHAR(100) | Region within country | NULL |
| metadata | JSONB | Additional event-specific data | NULL |
| processed_at | TIMESTAMP WITH TIME ZONE | When the event was processed | NULL |
| kafka_offset | BIGINT | Kafka offset for the event | NULL |
| kafka_partition | INTEGER | Kafka partition | NULL |
| kafka_topic | VARCHAR(100) | Kafka topic name | NULL |
| created_at | TIMESTAMP WITH TIME ZONE | Row creation timestamp | DEFAULT NOW() |

**Indexes**:
- idx_raw_events_user_id (user_id)
- idx_raw_events_timestamp (timestamp)
- idx_raw_events_event_type (event_type)

**Notes**:
- Events are append-only, never updated
- Kafka metadata for debugging and replay
- metadata field contains event-specific attributes

---

### raw_playback_events

**Purpose**: Immutable storage of playback-specific events with timing data.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| event_id | UUID | Unique identifier for the event | PRIMARY KEY |
| user_id | INTEGER | Foreign key to dim_users | NOT NULL |
| session_id | UUID | Unique session identifier | NOT NULL |
| content_id | INTEGER | Foreign key to dim_content | NOT NULL |
| event_type | VARCHAR(50) | Type of playback event (play, pause, resume, seek, stop, complete) | NOT NULL |
| timestamp | TIMESTAMP WITH TIME ZONE | When the event occurred | NOT NULL |
| position_seconds | INTEGER | Current playback position in seconds | NULL |
| watch_seconds | INTEGER | Total watch time in seconds | NULL |
| duration_seconds | INTEGER | Total content duration in seconds | NULL |
| device_type | VARCHAR(50) | Device that generated the event | NULL |
| created_at | TIMESTAMP WITH TIME ZONE | Row creation timestamp | DEFAULT NOW() |

**Indexes**:
- idx_raw_playback_user_content (user_id, content_id)
- idx_raw_playback_timestamp (timestamp)

**Notes**:
- Separate from raw_events due to different schema
- Timing data for engagement analysis
- position_seconds is current position, watch_seconds is cumulative

---

## 🏢 DATA WAREHOUSE - DIMENSIONS

### dim_users

**Purpose**: User profiles and calculated metrics.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| user_id | INTEGER | Unique user identifier | PRIMARY KEY |
| signup_date | DATE | When the user signed up | NOT NULL |
| country | VARCHAR(3) | ISO 3166-1 alpha-3 country code | NULL |
| region | VARCHAR(100) | Region within country | NULL |
| preferred_device | VARCHAR(50) | Most used device type | NULL |
| is_active | BOOLEAN | Whether user is active | DEFAULT TRUE |
| taste_cluster_id | INTEGER | Foreign key to taste cluster | NULL |
| churn_probability | DECIMAL(5,4) | Predicted churn probability (0-1) | NULL |
| created_at | TIMESTAMP WITH TIME ZONE | Row creation timestamp | DEFAULT NOW() |
| updated_at | TIMESTAMP WITH TIME ZONE | Row update timestamp | DEFAULT NOW() |

**Notes**:
- churn_probability from ML model
- taste_cluster_id from clustering model
- is_active updated by ETL based on recent activity

---

### dim_content

**Purpose**: Content metadata (movies and series).

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| content_id | INTEGER | Unique content identifier | PRIMARY KEY |
| title | VARCHAR(500) | Content title | NOT NULL |
| content_type | VARCHAR(20) | Type: 'movie' or 'series' | NOT NULL |
| release_year | INTEGER | Year of release | NULL |
| duration_minutes | INTEGER | Duration in minutes | NULL |
| primary_genre_id | INTEGER | Foreign key to dim_genre | NULL |
| tmdb_id | INTEGER | TMDB identifier | NULL |
| imdb_id | VARCHAR(20) | IMDB identifier | NULL |
| description | TEXT | Content description | NULL |
| is_active | BOOLEAN | Whether content is available | DEFAULT TRUE |
| created_at | TIMESTAMP WITH TIME ZONE | Row creation timestamp | DEFAULT NOW() |
| updated_at | TIMESTAMP WITH TIME ZONE | Row update timestamp | DEFAULT NOW() |

**Notes**:
- primary_genre_id is the main genre, additional genres in bridge table
- duration_minutes is an estimated runtime for movies and an estimated average episode duration for synthetic series
- rating_count and avg_rating are kept in processed catalog files for feature engineering; they are not persisted in dim_content yet
- is_active can be set to FALSE for removed content

---

### dim_genre

**Purpose**: Genre definitions.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| genre_id | INTEGER | Unique genre identifier | PRIMARY KEY |
| genre_name | VARCHAR(100) | Genre name | NOT NULL, UNIQUE |
| created_at | TIMESTAMP WITH TIME ZONE | Row creation timestamp | DEFAULT NOW() |

**Notes**:
- Standard genres: Action, Comedy, Drama, Horror, Thriller, etc.
- One-to-many relationship with content via bridge table

---

### dim_content_genre

**Purpose**: Many-to-many relationship between content and genres.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| content_id | INTEGER | Foreign key to dim_content | NOT NULL, FK |
| genre_id | INTEGER | Foreign key to dim_genre | NOT NULL, FK |

**Primary Key**: (content_id, genre_id)

**Notes**:
- Bridge table for content-genre relationships
- Content can belong to multiple genres

---

### dim_device

**Purpose**: Device type definitions.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| device_id | SERIAL | Unique device identifier | PRIMARY KEY |
| device_type | VARCHAR(50) | Device type | NOT NULL, UNIQUE |
| created_at | TIMESTAMP WITH TIME ZONE | Row creation timestamp | DEFAULT NOW() |

**Notes**:
- Standard device types: smart_tv, mobile, web, tablet, console
- device_type is used in events to join to this table

---

### dim_location

**Purpose**: Geographic location definitions.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| location_id | SERIAL | Unique location identifier | PRIMARY KEY |
| country | VARCHAR(3) | ISO 3166-1 alpha-3 country code | NOT NULL |
| region | VARCHAR(100) | Region within country | NOT NULL |

**Primary Key**: (country, region)

**Notes**:
- Composite key on country and region
- Coarse granularity for privacy (no city-level)

---

### dim_date

**Purpose**: Date dimension for time-based analysis.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| date_id | DATE | Date | PRIMARY KEY |
| day | INTEGER | Day of month (1-31) | NOT NULL |
| month | INTEGER | Month (1-12) | NOT NULL |
| year | INTEGER | Year | NOT NULL |
| quarter | INTEGER | Quarter (1-4) | NOT NULL |
| day_of_week | INTEGER | Day of week (0-6, Sunday=0) | NOT NULL |
| is_weekend | BOOLEAN | Whether date is weekend | NOT NULL |
| is_holiday | BOOLEAN | Whether date is holiday | DEFAULT FALSE |

**Notes**:
- Pre-populated with dates from project start to future
- Enables efficient time-based filtering and aggregation
- is_holiday can be populated based on country

---

## 🏢 DATA WAREHOUSE - FACTS

### fact_watch_events

**Purpose**: Individual watch events after ETL.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| event_id | UUID | Unique event identifier | PRIMARY KEY |
| user_id | INTEGER | Foreign key to dim_users | NOT NULL, FK |
| content_id | INTEGER | Foreign key to dim_content | NOT NULL, FK |
| date_id | DATE | Foreign key to dim_date | NOT NULL, FK |
| device_id | INTEGER | Foreign key to dim_device | NOT NULL, FK |
| location_id | INTEGER | Foreign key to dim_location | NULL, FK |
| event_type | VARCHAR(50) | Type of event | NOT NULL |
| timestamp | TIMESTAMP WITH TIME ZONE | When the event occurred | NOT NULL |
| watch_seconds | INTEGER | Watch time in seconds | NULL |
| position_seconds | INTEGER | Playback position in seconds | NULL |
| completed | BOOLEAN | Whether content was completed | DEFAULT FALSE |
| is_from_recommendation | BOOLEAN | Whether from recommendation | DEFAULT FALSE |
| recommendation_id | UUID | Foreign key to fact_recommendations | NULL |

**Indexes**:
- idx_fact_watch_user_date (user_id, date_id)
- idx_fact_watch_content (content_id)
- idx_fact_watch_recommendation (recommendation_id)

**Notes**:
- completed = TRUE if watch_seconds >= 90% of duration
- is_from_recommendation tracks recommendation effectiveness

---

### fact_sessions

**Purpose**: User session aggregations.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| session_id | UUID | Unique session identifier | PRIMARY KEY |
| user_id | INTEGER | Foreign key to dim_users | NOT NULL, FK |
| start_time | TIMESTAMP WITH TIME ZONE | Session start | NOT NULL |
| end_time | TIMESTAMP WITH TIME ZONE | Session end | NULL |
| duration_seconds | INTEGER | Session duration in seconds | NULL |
| device_id | INTEGER | Foreign key to dim_device | NOT NULL, FK |
| location_id | INTEGER | Foreign key to dim_location | NULL, FK |
| events_count | INTEGER | Number of events in session | DEFAULT 0 |
| contents_watched | INTEGER | Number of unique contents watched | DEFAULT 0 |
| total_watch_seconds | INTEGER | Total watch time in seconds | DEFAULT 0 |

**Indexes**:
- idx_fact_sessions_user (user_id)
- idx_fact_sessions_date (start_time)

**Notes**:
- Sessions are groups of events within a time window
- ETL calculates aggregations from raw events

---

### fact_user_interactions

**Purpose**: User interactions (likes, dislikes, shares).

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| interaction_id | UUID | Unique interaction identifier | PRIMARY KEY |
| user_id | INTEGER | Foreign key to dim_users | NOT NULL, FK |
| content_id | INTEGER | Foreign key to dim_content | NOT NULL, FK |
| date_id | DATE | Foreign key to dim_date | NOT NULL, FK |
| interaction_type | VARCHAR(50) | Type: like, dislike, add_to_list, share | NOT NULL |
| timestamp | TIMESTAMP WITH TIME ZONE | When interaction occurred | NOT NULL |

**Indexes**:
- idx_fact_interactions_user (user_id)
- idx_fact_interactions_content (content_id)

**Notes**:
- Captures explicit user feedback
- Used for content-based recommendations

---

### fact_recommendations

**Purpose**: Generated recommendations.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| recommendation_id | UUID | Unique recommendation identifier | PRIMARY KEY |
| user_id | INTEGER | Foreign key to dim_users | NOT NULL, FK |
| content_id | INTEGER | Foreign key to dim_content | NOT NULL, FK |
| model_version | VARCHAR(50) | Model version that generated this | NOT NULL |
| algorithm | VARCHAR(50) | Algorithm: popularity, content_based, collaborative, hybrid | NOT NULL |
| score | DECIMAL(10,6) | Recommendation score (0-1) | NOT NULL |
| rank | INTEGER | Rank in recommendation list | NOT NULL |
| generated_at | TIMESTAMP WITH TIME ZONE | When recommendation was generated | NOT NULL |

**Indexes**:
- idx_fact_recommendations_user (user_id)
- idx_fact_recommendations_content (content_id)

**Notes**:
- One row per recommendation per user
- Used for A/B testing different algorithms
- score is normalized to 0-1 range

---

### fact_recommendation_feedback

**Purpose**: User interactions with recommendations.

**Schema**:

| Column | Type | Description | Constraints |
|--------|------|-------------|--------------|
| feedback_id | UUID | Unique feedback identifier | PRIMARY KEY |
| recommendation_id | UUID | Foreign key to fact_recommendations | NOT NULL, FK |
| user_id | INTEGER | Foreign key to dim_users | NOT NULL, FK |
| content_id | INTEGER | Foreign key to dim_content | NOT NULL, FK |
| feedback_type | VARCHAR(50) | Type: impression, click, play, complete | NOT NULL |
| timestamp | TIMESTAMP WITH TIME ZONE | When feedback occurred | NOT NULL |

**Indexes**:
- idx_fact_feedback_rec (recommendation_id)
- idx_fact_feedback_user (user_id)

**Notes**:
- Tracks recommendation effectiveness
- Used to calculate CTR, conversion rate
- Enables feedback loop for model improvement

---

## 📊 RELATIONSHIPS

### Entity Relationship Diagram (Simplified)

```
dim_users (user_id)
    ↓
fact_watch_events (user_id) → dim_content (content_id) → dim_content_genre → dim_genre
                                 ↓
                             dim_date (date_id)
                                 ↓
                             dim_device (device_id)
                                 ↓
                             dim_location (location_id)

dim_users (user_id)
    ↓
fact_sessions (user_id) → dim_device (device_id)
                         → dim_location (location_id)

dim_users (user_id)
    ↓
fact_user_interactions (user_id) → dim_content (content_id)
                                    → dim_date (date_id)

dim_users (user_id)
    ↓
fact_recommendations (user_id) → dim_content (content_id)
                                 ↓
                             fact_recommendation_feedback (recommendation_id)
                                 ↓
                             dim_users (user_id)
```

---

*Document updated: 2025-01-05*
