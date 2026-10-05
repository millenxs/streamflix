# StreamFlix Architecture Overview

## 📐 System Architecture

StreamFlix is designed as a modular, scalable data platform that simulates a real-world streaming analytics and recommendation system.

## 🏛️ Architectural Principles

1. **Separation of Concerns**: Each layer has a distinct responsibility (generation, streaming, storage, transformation, analytics, ML, serving)
2. **Idempotency**: All operations can be safely retried without side effects
3. **Observability**: Structured logging and metrics throughout the pipeline
4. **Scalability**: Architecture can scale from 10k to 1M+ events
5. **Modularity**: Components can be developed, tested, and deployed independently

## 🔄 Data Flow Architecture

### 1. Event Generation Layer
**Purpose**: Simulate realistic user behavior at scale

**Components**:
- User Simulator: Creates synthetic user profiles with behavioral patterns
- Event Generator: Produces events based on user profiles and distributions
- Session Generator: Creates realistic session timelines

**Event Types**:
- user_login
- home_view
- content_impression
- content_click
- play
- pause
- resume
- seek
- stop
- complete
- search
- like
- dislike
- recommendation_impression
- recommendation_click
- session_end

**Output**: Python event objects → Kafka Producer

### 2. Streaming Layer
**Purpose**: Real-time event ingestion and distribution

**Technology**: Apache Kafka (via Docker)

**Topics**:
- `streamflix.events`: General user events
- `streamflix.playback`: Playback-specific events
- `streamflix.interactions`: User interactions (likes, dislikes)
- `streamflix.recommendations`: Recommendation events
- `streamflix.events.dlq`: Dead Letter Queue for failed events

**Key Concepts**:
- **Producers**: Python services that publish events to topics
- **Consumers**: Python services that subscribe and process events
- **Partitions**: Parallel processing units within topics
- **Offsets**: Position markers for consumer progress
- **Consumer Groups**: Groups of consumers that share load

**Error Handling**:
- Events that fail validation are sent to DLQ
- Offsets are committed only after successful processing
- At-least-once delivery semantics

### 3. Raw Storage Layer
**Purpose**: Immutable storage of ingested events

**Technology**: PostgreSQL

**Tables**:
- `raw_events`: All behavioral events with metadata
- `raw_playback_events`: Playback-specific events with timing data

**Characteristics**:
- Append-only (no updates/deletes)
- Enriched with Kafka metadata (offset, partition, topic)
- Timestamped for temporal queries
- Indexed for efficient querying

### 4. ETL/ELT Layer
**Purpose**: Transform raw events into analytics-ready data

**Process**:
1. **Extract**: Read from raw layer
2. **Validate**: Check data quality (nulls, duplicates, invalid values)
3. **Clean**: Handle missing values, standardize formats
4. **Transform**: Apply business rules, calculate derived fields
5. **Load**: Upsert to data warehouse

**Data Quality Checks**:
- Duplicate event IDs
- Events without user_id
- Non-existent content_id
- Negative durations
- Invalid timestamps
- Impossible watch_time
- Inconsistent sessions

**Idempotency**:
- Natural keys (event_id, user_id, content_id)
- Upsert operations (INSERT ... ON CONFLICT)
- Idempotent batch processing

### 5. Data Warehouse Layer
**Purpose**: Optimized storage for analytics and ML

**Model**: Star Schema

**Fact Tables** (Transactional data):
- `fact_watch_events`: User watch events
- `fact_sessions`: User sessions
- `fact_user_interactions`: Likes, dislikes, shares
- `fact_recommendations`: Generated recommendations
- `fact_recommendation_feedback`: Recommendation interactions

**Dimension Tables** (Descriptive data):
- `dim_users`: User profiles, clusters, churn probability
- `dim_content`: Movies, series, genres
- `dim_genre`: Genre definitions
- `dim_device`: Device types
- `dim_location`: Geographic data
- `dim_date`: Date dimension for time-based analysis

**Optimizations**:
- Foreign key constraints
- Strategic indexes
- Materialized views for heavy queries
- Partitioning by date (if needed)

### 6. Analytics Layer
**Purpose**: Business intelligence and insights

**Components**:
- SQL Views: Pre-computed aggregations for BI
- KPI Calculator: Python-based metric calculations
- Cohort Analyzer: Retention and churn analysis
- Content Analytics: Content performance metrics

**KPIs**:
- DAU/WAU/MAU (Daily/Weekly/Monthly Active Users)
- Watch Time
- Average Session Duration
- Completion Rate
- Abandonment Rate
- CTR (Click-Through Rate)
- Recommendation CTR
- Retention Rate
- Churn Rate
- Engagement Rate

**Output**: Power BI dashboards, CSV exports, API endpoints

### 7. Machine Learning Layer
**Purpose**: Predictive modeling and personalization

**Components**:

#### Feature Engineering
- User features: Activity patterns, preferences, churn risk
- Content features: Genre distribution, popularity, metadata
- Session features: Duration, device, time patterns

#### Taste Clustering
- Algorithm: K-Means + PCA
- Features: Genre distribution, watch time, completion rate, device usage
- Output: User segment labels (e.g., "Night Thriller Bingers")

#### Churn Prediction
- Algorithms: Logistic Regression, Random Forest
- Features: Recency, frequency, engagement, recommendations CTR
- Output: Churn probability per user

#### Recommendation Engine
- **Baseline**: Popularity-based (most watched overall/segment)
- **Content-Based**: Similarity of content features (genres, metadata)
- **Collaborative Filtering**: Matrix factorization (user-item interactions)
- **Hybrid**: Weighted combination of approaches
- **Evaluation**: Precision@K, Recall@K, MAP@K, NDCG@K

**Model Persistence**:
- Models saved with Joblib
- Metadata in JSON (version, parameters, metrics)
- Versioned by timestamp

### 8. API Layer
**Purpose**: Serve recommendations and analytics

**Technology**: FastAPI

**Endpoints**:
- `GET /health`: Health check
- `GET /users/{user_id}/profile`: User profile and cluster
- `GET /users/{user_id}/cluster`: User taste cluster
- `GET /users/{user_id}/recommendations`: Personalized recommendations
- `GET /content/{content_id}/analytics`: Content performance
- `GET /analytics/kpis`: Business KPIs
- `POST /events`: Ingest events via API
- `POST /recommendations/{id}/feedback`: Recommendation feedback

**Features**:
- Automatic OpenAPI documentation
- Pydantic validation
- Type hints
- Error handling
- Request logging

### 9. Feedback Loop
**Purpose**: Continuous improvement of recommendations

**Flow**:
1. Recommendation generated → Stored in `fact_recommendations`
2. User sees recommendation → Event: `recommendation_impression`
3. User clicks recommendation → Event: `recommendation_click`
4. User watches content → Event: `play_from_recommendation`
5. Feedback stored in `fact_recommendation_feedback`
6. Metrics calculated (CTR, conversion, completion)
7. Models retrained with new data
8. Improved recommendations served

## 🔧 Technology Choices

### Python 3.12+
- Rich ecosystem for data science
- Type hints for code quality
- Performance improvements

### PostgreSQL 16
- ACID compliance
- Advanced SQL features (window functions, CTEs)
- JSONB support for flexible metadata
- Mature and reliable

### Apache Kafka 3.7
- Industry standard for streaming
- Scalable and fault-tolerant
- Supports complex event patterns
- Good Windows support via WSL2

### Scikit-learn
- Comprehensive ML library
- Well-documented
- Industry-standard algorithms
- Good for portfolio projects

### FastAPI
- Modern, fast Python web framework
- Automatic API documentation
- Type validation with Pydantic
- Async support

### Docker
- Reproducible environments
- Easy local development
- Production-like setup
- Simplifies dependencies

### Power BI
- Industry-standard BI tool
- Rich visualizations
- DAX for complex calculations
- Widely used in industry

## 📊 Scalability Considerations

### Current Scope (Local Development)
- 10k-100k users
- 100k-1M events
- Single machine
- PostgreSQL without partitioning
- Kafka with single broker

### Production Considerations (Future)
- Horizontal scaling: Multiple Kafka brokers, consumer groups
- Database: Read replicas, connection pooling, partitioning
- Caching: Redis for frequently accessed data
- Orchestration: Airflow for scheduled ETL
- Monitoring: Prometheus + Grafana
- Message Queue: Additional consumers for specialized processing

## 🔒 Security and Privacy

### Data Anonymization
- No PII (Personally Identifiable Information)
- Synthetic user IDs
- Aggregated location data (country/region only)
- No names, emails, or contact information

### Data Minimization
- Only collect necessary event data
- No behavioral profiling beyond business needs
- Retention policies for raw events

### GDPR/LGPD Considerations
- Right to deletion (not applicable with synthetic data)
- Data portability (export functionality)
- Consent tracking (simulated)

### Recommendation Ethics
- Avoid filter bubbles
- Diversity in recommendations
- Transparency (explainable recommendations)
- Fairness across segments

## 📝 Implementation Order

1. Infrastructure (Docker, PostgreSQL, Kafka)
2. Data ingestion (content datasets)
3. Database schema (raw + DW)
4. Event generation (users, events, sessions)
5. Streaming (producer, consumer)
6. ETL pipeline
7. Analytics (SQL views, KPIs)
8. BI (Power BI dashboards)
9. Feature engineering
10. ML models (clustering, churn, recommendations)
11. API (FastAPI)
12. Feedback loop
13. Testing
14. Documentation

---

*This architecture is designed for educational purposes and portfolio demonstration. It is inspired by real-world streaming platforms but uses synthetic data.*
