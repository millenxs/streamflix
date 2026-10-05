# StreamFlix Data Flow

## 🌊 Complete Data Pipeline

This document describes the complete flow of data through the StreamFlix platform, from event generation to recommendation serving and feedback.

## 📊 Phase 1: Event Generation

### Step 1.1: User Profile Generation
```
Python Script: src/generation/user_generator.py
↓
Input: Configuration (NUM_USERS, behavioral profiles)
↓
Process: Generate synthetic users with:
  - User ID
  - Signup date
  - Country/region
  - Preferred device
  - Behavioral profile (casual, binger, explorer, etc.)
  - Genre preferences
↓
Output: CSV/JSON → data/processed/users/
```

### Step 1.2: Content Metadata Loading
```
Python Script: src/ingestion/load_movielens.py
↓
Input: MovieLens ml-latest-small public dataset
↓
Process: Load and normalize content:
  - Content ID
  - Clean title
  - Type (movie or deterministic synthetic series)
  - Release year
  - Estimated duration
  - Genres and primary genre
  - Rating count and average rating
  - IMDb/TMDB public identifiers when available
  - Portfolio-safe synthetic description
↓
Output:
  - data/processed/content/content_catalog.csv
  - data/processed/content/content_catalog.parquet
  - data/processed/content/content_genres.csv
  - data/processed/content/content_genres.parquet
  - PostgreSQL dim_content, dim_genre, dim_content_genre
```

### Step 1.3: Event Generation
```
Python Script: src/generation/event_generator.py
↓
Input: User profiles, Content metadata, Configuration
↓
Process: Generate events based on:
  - User behavioral profiles
  - Time of day patterns
  - Device preferences
  - Genre preferences
  - Realistic distributions (not random)
↓
Event Types:
  - user_login (user_id, timestamp, device, location)
  - home_view (user_id, session_id, timestamp)
  - content_impression (user_id, content_id, position)
  - content_click (user_id, content_id, session_id)
  - play (user_id, content_id, session_id, position, duration)
  - pause (user_id, content_id, session_id, position)
  - resume (user_id, content_id, session_id, position)
  - seek (user_id, content_id, session_id, from, to)
  - stop (user_id, content_id, session_id, position, duration)
  - complete (user_id, content_id, session_id, duration)
  - search (user_id, query, timestamp)
  - like (user_id, content_id, timestamp)
  - dislike (user_id, content_id, timestamp)
  - recommendation_impression (user_id, content_id, rec_id)
  - recommendation_click (user_id, content_id, rec_id)
  - session_end (user_id, session_id, duration)
↓
Output: Python objects → Kafka Producer
```

## 🚀 Phase 2: Streaming Ingestion

### Step 2.1: Kafka Producer
```
Python Script: src/streaming/kafka_producer.py
↓
Input: Event objects from generator
↓
Process:
  - Serialize events (JSON/Avro)
  - Batch events for efficiency
  - Send to appropriate topic
  - Handle connection errors
  - Log success/failure
↓
Topics:
  - streamflix.events (general events)
  - streamflix.playback (play, pause, resume, seek, stop, complete)
  - streamflix.interactions (like, dislike, search)
  - streamflix.recommendations (recommendation_impression, recommendation_click)
↓
Output: Kafka topics
```

### Step 2.2: Kafka Topics
```
Kafka Cluster (Docker)
↓
Topics:
  - streamflix.events (partitions: 3, replication: 1)
  - streamflix.playback (partitions: 3, replication: 1)
  - streamflix.interactions (partitions: 2, replication: 1)
  - streamflix.recommendations (partitions: 2, replication: 1)
  - streamflix.events.dlq (partitions: 1, replication: 1)
↓
Characteristics:
  - Retention: 7 days
  - Compression: gzip
  - Offset retention: 7 days
↓
Output: Available for consumers
```

### Step 2.3: Kafka Consumer
```
Python Script: src/streaming/kafka_consumer.py
↓
Input: Kafka topics
↓
Process:
  - Subscribe to topics (consumer group)
  - Poll for messages
  - Deserialize events
  - Validate events (schema, required fields)
  - Send to raw storage or DLQ
  - Commit offsets on success
  - Handle errors (retry, DLQ)
↓
Validation:
  - event_id exists and is UUID
  - user_id exists
  - timestamp is valid
  - event_type is known
  - content_id exists (if applicable)
↓
Output: Valid events → PostgreSQL, Invalid events → DLQ
```

### Step 2.4: Dead Letter Queue Handler
```
Python Script: src/streaming/dlq_handler.py
↓
Input: Failed events from DLQ topic
↓
Process:
  - Consume from DLQ
  - Log error details
  - Attempt to fix (if possible)
  - Store in error table for manual review
  - Alert (logging)
↓
Output: Error logs, Manual review queue
```

## 💾 Phase 3: Raw Storage

### Step 3.1: Raw Events Storage
```
Python Script: src/database/raw_layer.py
↓
Input: Valid events from Kafka consumer
↓
Process:
  - Insert into raw_events
  - Add Kafka metadata (offset, partition, topic)
  - Add processing timestamp
  - Handle duplicates (upsert)
↓
Table: raw_events
  - event_id (UUID, PK)
  - event_type (VARCHAR)
  - user_id (INTEGER)
  - session_id (UUID)
  - content_id (INTEGER)
  - timestamp (TIMESTAMP)
  - device_type (VARCHAR)
  - country (VARCHAR)
  - region (VARCHAR)
  - metadata (JSONB)
  - processed_at (TIMESTAMP)
  - kafka_offset (BIGINT)
  - kafka_partition (INTEGER)
  - kafka_topic (VARCHAR)
↓
Output: Immutable event log
```

### Step 3.2: Raw Playback Events Storage
```
Python Script: src/database/raw_layer.py
↓
Input: Playback events from Kafka consumer
↓
Process:
  - Insert into raw_playback_events
  - Enrich with timing data
↓
Table: raw_playback_events
  - event_id (UUID, PK)
  - user_id (INTEGER)
  - session_id (UUID)
  - content_id (INTEGER)
  - event_type (VARCHAR)
  - timestamp (TIMESTAMP)
  - position_seconds (INTEGER)
  - watch_seconds (INTEGER)
  - duration_seconds (INTEGER)
  - device_type (VARCHAR)
↓
Output: Immutable playback event log
```

## 🔄 Phase 4: ETL/ELT Pipeline

### Step 4.1: Event ETL
```
Python Script: src/etl/event_etl.py
↓
Input: raw_events, raw_playback_events
↓
Process:
  1. Extract: Read from raw layer (batch)
  2. Validate:
     - Check for duplicates
     - Validate user_id exists in dim_users
     - Validate content_id exists in dim_content
     - Check timestamps are valid
     - Check durations are non-negative
  3. Clean:
     - Handle null values
     - Standardize device types
     - Normalize country codes
     - Fill missing regions
  4. Transform:
     - Calculate date_id from timestamp
     - Derive device_id from device_type
     - Derive location_id from country/region
     - Mark completed events (watch_seconds >= duration_seconds * 0.9)
     - Mark from_recommendation events
  5. Load: Upsert to fact_watch_events
↓
Data Quality Checks:
  - Duplicate event_ids → Reject
  - Events without user_id → Reject
  - Events with non-existent content_id → Reject
  - Negative watch_seconds → Reject
  - Invalid timestamps → Reject
↓
Output: fact_watch_events (clean, validated)
```

### Step 4.2: Session ETL
```
Python Script: src/etl/session_etl.py
↓
Input: raw_events (filtered by session_id)
↓
Process:
  1. Group events by session_id
  2. Calculate session metrics:
     - start_time: First event timestamp
     - end_time: Last event timestamp
     - duration_seconds: end_time - start_time
     - events_count: Number of events
     - contents_watched: Unique content_ids
     - total_watch_seconds: Sum of watch_seconds
  3. Derive device_id, location_id
  4. Upsert to fact_sessions
↓
Output: fact_sessions
```

### Step 4.3: User ETL
```
Python Script: src/etl/user_etl.py
↓
Input: User profiles + Event aggregations
↓
Process:
  1. Calculate user metrics:
     - days_since_last_session
     - sessions_last_30d
     - watch_hours_last_30d
     - completion_rate
     - abandonment_rate
     - genres_watched
     - recommendation_ctr
  2. Update dim_users with metrics
  3. Add cluster_id (from ML model)
  4. Add churn_probability (from ML model)
↓
Output: dim_users (enriched)
```

### Step 4.4: Data Quality Pipeline
```
Python Script: src/etl/data_quality.py
↓
Input: All tables
↓
Process:
  1. Run quality checks:
     - Referential integrity (FKs valid)
     - No orphan records
     - Consistent timestamps
     - No negative durations
     - Valid event types
  2. Calculate quality metrics:
     - Data completeness (%)
     - Data accuracy (%)
     - Data consistency (%)
  3. Log quality metrics
  4. Alert if thresholds breached
↓
Output: Quality metrics, Alerts
```

## 🏢 Phase 5: Data Warehouse

### Step 5.1: Dimension Tables Population
```
Python Script: src/database/dw_layer.py
↓
Input: Processed data
↓
Process:
  - dim_users: User profiles + calculated metrics
  - dim_content: Content metadata
  - dim_genre: Genre definitions
  - dim_device: Device types
  - dim_location: Country/region combinations
  - dim_date: Date dimension (pre-populated)
↓
Output: Dimension tables (slowly changing)
```

### Step 5.2: Fact Tables Population
```
Python Script: src/database/dw_layer.py
↓
Input: Processed events
↓
Process:
  - fact_watch_events: All watch events
  - fact_sessions: Session aggregations
  - fact_user_interactions: Likes, dislikes, shares
  - fact_recommendations: Generated recommendations
  - fact_recommendation_feedback: Recommendation interactions
↓
Output: Fact tables (append-only)
```

### Step 5.3: Indexes and Constraints
```
SQL Script: src/sql/schema/04_indexes.sql
↓
Process:
  - Create foreign key constraints
  - Create indexes on foreign keys
  - Create indexes on frequently queried columns
  - Create indexes on timestamp columns
  - Create composite indexes for common joins
↓
Output: Optimized database
```

## 📈 Phase 6: Analytics

### Step 6.1: SQL Views Creation
```
SQL Scripts: src/sql/views/
↓
Process:
  - vw_kpis: Pre-calculated KPIs
  - vw_content_analytics: Content performance
  - vw_user_behavior: User activity patterns
  - vw_retention: Retention curves
  - vw_churn: Churn analysis
  - vw_recommendations: Recommendation performance
↓
Output: Reusable analytics views
```

### Step 6.2: KPI Calculation
```
Python Script: src/analytics/kpi_calculator.py
↓
Input: Data warehouse
↓
Process:
  - DAU: COUNT(DISTINCT user_id) WHERE date = CURRENT_DATE
  - WAU: COUNT(DISTINCT user_id) WHERE date BETWEEN CURRENT_DATE - 7 AND CURRENT_DATE
  - MAU: COUNT(DISTINCT user_id) WHERE date BETWEEN CURRENT_DATE - 30 AND CURRENT_DATE
  - Watch Time: SUM(watch_seconds) / 3600
  - Average Session Duration: AVG(duration_seconds)
  - Completion Rate: COUNT(completed) / COUNT(total)
  - Abandonment Rate: COUNT(abandoned) / COUNT(total)
  - CTR: COUNT(clicks) / COUNT(impressions)
  - Recommendation CTR: COUNT(rec_clicks) / COUNT(rec_impressions)
  - Retention Rate: Cohort analysis
  - Churn Rate: Users inactive for 30 days / total users
  - Engagement Rate: Active users / total users
↓
Output: KPI values (stored or served via API)
```

### Step 6.3: Power BI Connection
```
Power BI Desktop
↓
Process:
  1. Connect to PostgreSQL (localhost:5432)
  2. Select views (vw_kpis, vw_content_analytics, etc.)
  3. Create relationships
  4. Build measures (DAX)
  5. Create visualizations
  6. Publish dashboards
↓
Output: Interactive dashboards
```

## 🤖 Phase 7: Machine Learning

### Step 7.1: Feature Engineering
```
Python Script: src/features/user_features.py
↓
Input: Data warehouse
↓
Process:
  - User features:
    - Recency: days_since_last_session
    - Frequency: sessions_last_30d
    - Monetary: watch_hours_last_30d
    - Engagement: completion_rate, abandonment_rate
    - Preferences: genre_distribution
    - Behavior: peak_hour, preferred_device
  - Content features:
    - Popularity: total_watch_time
    - Engagement: avg_completion_rate
    - Genre distribution
    - Metadata embeddings
  - Session features:
    - Duration
    - Device
    - Time of day
    - Content diversity
↓
Output: Feature matrices
```

### Step 7.2: Taste Clustering
```
Python Script: src/ml/clustering/taste_clustering.py
↓
Input: User features
↓
Process:
  1. Standardize features (StandardScaler)
  2. Reduce dimensionality (PCA)
  3. Determine optimal clusters (Elbow, Silhouette)
  4. Fit K-Means (k=8)
  5. Assign cluster labels to users
  6. Interpret clusters (analyze centroids)
  7. Name clusters (e.g., "Night Thriller Bingers")
↓
Output:
  - Cluster labels for dim_users
  - Model saved to models/clustering/
  - Cluster interpretation document
```

### Step 7.3: Churn Prediction
```
Python Script: src/ml/churn/churn_predictor.py
↓
Input: User features + churn labels
↓
Process:
  1. Define churn: inactive for 30 days
  2. Split data (temporal: train on past, test on future)
  3. Train Logistic Regression (baseline)
  4. Train Random Forest (improved)
  5. Evaluate:
     - Precision, Recall, F1
     - ROC-AUC, PR-AUC
     - Confusion matrix
  6. Select best model
  7. Predict churn probability for all users
↓
Output:
  - Churn probabilities in dim_users
  - Model saved to models/churn/
  - Evaluation metrics
```

### Step 7.4: Recommendation Engine
```
Python Scripts: src/ml/recommendation/
↓
Input: User features, Content features, Interactions
↓
Process:

A. Popularity-Based (Baseline):
   - Calculate global popularity
   - Calculate segment popularity (by cluster)
   - Return top N popular items

B. Content-Based:
   - Create content feature vectors
   - Calculate similarity (cosine)
   - For user: find similar to watched content
   - Return top N similar items

C. Collaborative Filtering:
   - Create user-item matrix
   - Apply matrix factorization (SVD/NMF)
   - Predict ratings for unwatched items
   - Return top N predicted items

D. Hybrid:
   - Combine scores from all approaches
   - Weight by cluster preference
   - Add diversity
   - Return top N recommendations

E. Evaluation:
   - Split train/test (temporal)
   - Calculate:
     - Precision@K
     - Recall@K
     - MAP@K
     - NDCG@K
   - Compare approaches
↓
Output:
  - Recommendations in fact_recommendations
  - Models saved to models/recommendation/
  - Evaluation metrics
```

## 🌐 Phase 8: API Serving

### Step 8.1: FastAPI Application
```
Python Script: src/api/main.py
↓
Process:
  - Initialize FastAPI app
  - Configure database connection
  - Load ML models
  - Register routers
  - Add middleware (logging, CORS)
  - Start Uvicorn server
↓
Output: Running API server (http://localhost:8000)
```

### Step 8.2: Recommendation Endpoint
```
Endpoint: GET /users/{user_id}/recommendations
↓
Process:
  1. Validate user_id
  2. Load user profile (dim_users)
  3. Get user cluster
  4. Load recommendation model
  5. Generate recommendations:
     - Filter out watched content
     - Apply cluster-specific weights
     - Add diversity
     - Rank by score
  6. Format response
  7. Log request
↓
Response:
{
  "user_id": 1842,
  "taste_cluster": "Night Thriller Bingers",
  "recommendations": [
    {
      "content_id": 918,
      "title": "Example Movie",
      "score": 0.94,
      "algorithm": "hybrid"
    }
  ]
}
↓
Output: JSON response
```

## 🔄 Phase 9: Feedback Loop

### Step 9.1: Recommendation Impressions
```
User Action: View recommendation
↓
Event: recommendation_impression
↓
Fields: user_id, content_id, recommendation_id, timestamp
↓
Flow: Event → Kafka → Consumer → fact_recommendation_feedback
↓
Metric: Count impressions per recommendation
```

### Step 9.2: Recommendation Clicks
```
User Action: Click recommendation
↓
Event: recommendation_click
↓
Fields: user_id, content_id, recommendation_id, timestamp
↓
Flow: Event → Kafka → Consumer → fact_recommendation_feedback
↓
Metric: CTR = clicks / impressions
```

### Step 9.3: Recommendation Play and Complete
```
User Action: Watch from recommendation
↓
Events: play_from_recommendation, complete_from_recommendation
↓
Flow: Events → Kafka → Consumer → fact_recommendation_feedback
↓
Metrics:
  - Conversion Rate = plays / clicks
  - Completion Rate = completes / plays
```

### Step 9.4: Model Retraining
```
Process (Offline, Batch):
  1. Accumulate feedback data
  2. Update feature matrices
  3. Retrain models (weekly/monthly)
  4. Evaluate new models
  5. A/B test if significant improvement
  6. Deploy new model version
  7. Update API to use new model
↓
Output: Improved recommendations
```

## 📊 Phase 10: A/B Testing

### Step 10.1: Experiment Configuration
```
Python Script: src/experiments/ab_test_config.py
↓
Process:
  - Define experiment (e.g., Algorithm A vs Algorithm B)
  - Assign users to control/treatment groups
  - Configure traffic split (50/50)
  - Define metrics (CTR, watch time, completion)
  - Set duration (e.g., 2 weeks)
↓
Output: Experiment configuration
```

### Step 10.2: Data Collection
```
Process:
  - Serve Algorithm A to control group
  - Serve Algorithm B to treatment group
  - Collect metrics for both groups
  - Store in fact_recommendations_feedback with group_id
↓
Output: Experimental data
```

### Step 10.3: Statistical Analysis
```
Python Script: src/experiments/ab_test_analyzer.py
↓
Input: Experimental data
↓
Process:
  1. Calculate metrics per group
  2. Perform statistical test (t-test, chi-square)
  3. Calculate p-value
  4. Calculate confidence interval
  5. Calculate effect size (Cohen's d)
  6. Determine statistical significance
  7. Determine business significance
↓
Output:
  - Statistical significance (yes/no)
  - Business impact
  - Recommendation (adopt/continue testing)
```

## 🎯 Complete Flow Summary

```
User Simulator
    ↓
Event Generator
    ↓
Kafka Producer
    ↓
Kafka Topics
    ↓
Kafka Consumer
    ↓
PostgreSQL (Raw Layer)
    ↓
ETL Pipeline
    ↓
PostgreSQL (Data Warehouse)
    ↓
┌───────────────┴───────────────┐
↓                               ↓
Power BI                  Machine Learning
(Dashboards)              (Clustering, Churn, Recs)
    ↓                               ↓
Business Insights              API (FastAPI)
    ↓                               ↓
Strategic Decisions          Recommendations
                                        ↓
                              User Interactions
                                        ↓
                              Feedback Events
                                        ↓
                                    Kafka
                                        ↓
                              (Loop continues)
```

---

*This data flow ensures a complete, working end-to-end system where each component serves a clear purpose and integrates seamlessly with the others.*
