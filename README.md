# StreamFlix — End-to-End Big Data, Analytics & Recommendation Platform

![Python](https://img.shields.io/badge/Python-3.11--3.12-blue)
![SQL](https://img.shields.io/badge/SQL-PostgreSQL-336791)
![Kafka](https://img.shields.io/badge/Kafka-Apka-231F20)
![PowerBI](https://img.shields.io/badge/PowerBI-F2C811)
![MachineLearning](https://img.shields.io/badge/MachineLearning-Scikit--learn-F7931E)
![FastAPI](https://img.shields.io/badge/FastAPI-009688)
![Docker](https://img.shields.io/badge/Docker-2496ED)

---

## 📖 Overview

StreamFlix is a comprehensive data platform that simulates how a streaming company collects millions of behavioral events, processes them in real-time, stores and transforms data, performs business analytics, creates BI dashboards, and uses Machine Learning for user segmentation and content recommendation.

This project demonstrates a complete end-to-end data architecture, suitable for portfolio presentation for roles in:
- Data Analyst
- BI Analyst
- Data Engineer
- Analytics Engineer
- Junior Data Scientist
- Machine Learning Engineer

---

## 🎯 Business Problem

A fictional streaming company wants to leverage data to:
- Understand how users interact with the platform
- Identify high-engagement content
- Detect content abandonment patterns
- Analyze behavior by device, time, and region
- Identify churn-related patterns
- Segment users by behavior (Taste Communities)
- Recommend movies and series
- Personalize user experience
- Measure recommendation quality
- Provide strategic insights for content teams
- Deliver KPIs to managers via Power BI

---

## 🏗️ Architecture

```
User Simulator → Event Generator → Kafka Producer → Kafka Topics
                                                          ↓
                                    Kafka Consumers → PostgreSQL (Raw Layer)
                                                          ↓
                                    ETL Pipeline → Data Warehouse (Star Schema)
                                                          ↓
                                              ┌─────────┴─────────┐
                                              ↓                   ↓
                                      Power BI Dashboards   Machine Learning
                                              ↓                   ↓
                                    Business Insights   Recommendation Engine
                                              ↓                   ↓
                                              └─────────┬─────────┘
                                                        ↓
                                              FastAPI (Recommendation Service)
                                                        ↓
                                              Feedback Events → Kafka
```

### Tech Stack

| Layer | Technology |
|-------|------------|
| Language | Python 3.11–3.12 |
| Data Processing | Pandas, NumPy, PyArrow |
| Database | PostgreSQL 16 |
| Streaming | Apache Kafka-compatible broker via Confluent Platform 7.5.0 |
| Machine Learning | Scikit-learn |
| API | FastAPI, Pydantic, Uvicorn |
| BI | Power BI (Tableau-compatible) |
| Infrastructure | Docker, Docker Compose |
| Testing | Pytest |
| Package Management | pip + pyproject.toml |

---

## 📊 Data Flow

1. **Event Generation**: Python simulates thousands/millions of user interactions (login, play, pause, complete, search, recommendation clicks)
2. **Streaming Ingestion**: Events are sent to Kafka topics and consumed by Python consumers
3. **Raw Storage**: Events are stored in PostgreSQL raw layer
4. **ETL/ELT**: Python pipeline validates, cleans, and transforms data into dimensional model
5. **Data Warehouse**: Star schema with fact tables (watch events, sessions, interactions, recommendations) and dimensions (users, content, genre, device, location, date)
6. **Analytics**: SQL views serve Power BI dashboards for business KPIs
7. **Machine Learning**:
   - Taste Clustering (K-Means) for user segmentation
   - Churn Prediction (Logistic Regression, Random Forest)
   - Recommendation Engine (Popularity, Content-Based, Collaborative, Hybrid)
8. **API**: FastAPI serves recommendations and analytics
9. **Feedback Loop**: User interactions with recommendations return to Kafka for continuous improvement

---

## 🗄️ Data Model

### Raw Layer
- `raw_events`: All behavioral events
- `raw_playback_events`: Playback-specific events

### Data Warehouse (Star Schema)

**Fact Tables:**
- `fact_watch_events`: User watch events
- `fact_sessions`: User sessions
- `fact_user_interactions`: Likes, dislikes, shares
- `fact_recommendations`: Generated recommendations
- `fact_recommendation_feedback`: Recommendation interactions

**Dimension Tables:**
- `dim_users`: User profiles and clusters
- `dim_content`: Movies and series metadata
- `dim_genre`: Content genres
- `dim_device`: Device types
- `dim_location`: Geographic data
- `dim_date`: Date dimension for time-based analysis

---

## 📈 Key Features

### Business Intelligence (Power BI)
- **Executive Overview**: MAU, Watch Time, Retention, Churn, Completion Rate, Recommendation CTR
- **Content Analytics**: Most watched titles, genres, completion, abandonment
- **User Behavior**: Peak hours, devices, sessions, frequency
- **Retention & Churn**: Cohort analysis, retention curves, churn patterns
- **Recommendation Performance**: Impressions, clicks, CTR, conversion
- **Taste Clusters**: Cluster size, genres, behavior, watch time

### Machine Learning
- **Taste Clustering**: User segmentation based on behavior (K-Means + PCA)
- **Churn Prediction**: Identify users at risk of churning
- **Recommendation Engine**:
  - Baseline: Popularity-based
  - Content-Based: Similarity of content features
  - Collaborative Filtering: Matrix factorization
  - Hybrid: Combination of approaches
- **A/B Testing**: Compare recommendation algorithms statistically

### Data Engineering
- Real-time event streaming with Apache Kafka
- ETL pipeline with data quality checks
- Idempotent batch processing
- Structured logging and observability
- Error handling with Dead Letter Queue

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11 or 3.12
- Docker & Docker Compose
- WSL2 (recommended for Windows)
- PostgreSQL client (psql)
- Power BI Desktop (for dashboards)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/millenxs/streamflix.git
cd streamflix
```

2. **Create a virtual environment and install Python dependencies**
```bash
python -m venv .venv

# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# Linux/Mac/WSL
source .venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements-dev.txt
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Start infrastructure (WSL2 recommended)**
```bash
docker compose up -d
```

Or use helper scripts:
```bash
# Windows PowerShell
.\scripts\docker_helpers.ps1 start

# Linux/Mac/WSL
./scripts/docker_helpers.sh start
```

Create Kafka topics after Kafka is healthy:
```bash
# Windows PowerShell
.\scripts\docker_helpers.ps1 topics

# Linux/Mac/WSL
./scripts/docker_helpers.sh topics
```

5. **Initialize database**
```bash
python scripts/init_db.py
```

6. **Load and enrich content data**
```bash
python src/ingestion/load_movielens.py
```

This command downloads MovieLens, builds an enriched StreamFlix catalog, creates deterministic synthetic series records, writes processed artifacts under `data/processed/content/`, and loads `dim_content`, `dim_genre`, and `dim_content_genre` in PostgreSQL.

7. **Generate users and simulate events**
```bash
python -m src.generation.users
python -m src.generation.events --days 7 --users 100
```

8. **Publish simulated events to Kafka**
```bash
# Preview generated events and topic routing without Kafka writes
python -m src.streaming.producer --days 1 --users 10 --limit 20 --dry-run

# Publish to Kafka topics
python -m src.streaming.producer --days 1 --users 10 --limit 1000 --events-per-second 100
```

9. **Persist Kafka events into the raw PostgreSQL layer**
```bash
# Consume only the canonical all-events topic to avoid duplicate raw ingestion
python -m src.streaming.consumer --limit 1000 --idle-timeout 10
```

10. **Run raw-to-warehouse ETL/ELT**
```bash
python -m src.etl.pipeline
```

This command upserts device/location dimensions and populates `fact_recommendations`, `fact_watch_events`, `fact_sessions`, `fact_user_interactions`, and `fact_recommendation_feedback` idempotently from the raw layer.

11. **Run data quality checks and create analytics views**
```bash
python -m src.analytics.quality
python -m src.analytics.views
python -m src.analytics.eda
```

The quality command verifies core raw and warehouse consistency rules. The views command creates dashboard-ready KPI views such as `vw_executive_kpis`, `vw_content_performance`, and `vw_recommendation_performance`. The EDA command exports view data to CSV for dashboard validation.

12. **Build ML features and train models**
```bash
python -m src.features.user_features
python -m src.ml.clustering.train
python -m src.ml.churn.train
python -m src.ml.recommendation.generate
```

13. **Serve recommendations and collect feedback**
```bash
uvicorn src.api.main:app --reload
```

Current executable setup covers infrastructure, database initialization, MovieLens content loading, user/event generation, Kafka event publishing, raw Kafka event persistence, raw-to-warehouse ETL/ELT, data quality checks, SQL analytics views, EDA exports, feature engineering, ML training, recommendation evaluation utilities, API serving, feedback capture, A/B testing, and thumbnail personalization.

### Running Tests
```bash
pytest
```

---

## 📚 Documentation

- [Architecture Overview](docs/architecture/overview.md)
- [Data Flow](docs/architecture/data_flow.md)
- [Data Dictionary](docs/data_dictionary/tables.md)
- [Technology Choices](docs/decisions/technology_choices.md)
- [Power BI Setup](powerbi/README.md)
- [Performance Optimization](docs/decisions/performance_optimization.md)
- [Final Demonstration](docs/final_demo.md)

---

## 🎓 Learning Outcomes

This project demonstrates:

### For Data Analyst / BI Analyst
- Translating business questions into SQL queries
- Creating interactive Power BI dashboards
- Defining KPIs with mathematical formulas
- Structured exploratory analysis
- Dimensional modeling (Star Schema)
- Data storytelling through visualizations

### For Data Engineer
- End-to-end data pipeline
- Apache Kafka for event streaming
- ETL/ELT with validation and data quality
- PostgreSQL as Data Warehouse
- Docker orchestration
- Error handling and idempotency
- Structured logging and observability

### For Analytics Engineer
- SQL transformations
- Reusable BI views
- Data modeling best practices
- Collaboration between engineering and analytics
- Data documentation

### For Junior Data Scientist
- Feature engineering for real problems
- Clustering (K-Means) with interpretation
- Churn analysis with feature engineering
- Baseline vs advanced models
- Model evaluation with proper metrics
- EDA before modeling

### For Machine Learning Engineer
- Recommendation system with multiple approaches
- Recommender evaluation (Precision@K, Recall@K, NDCG@K)
- Serving models via API (FastAPI)
- Feedback loop (recommendations → interactions → retraining)
- Model persistence
- Data leakage prevention
- Model and endpoint testing

---

## 📊 Business Impact & Insights

This platform enables:
- **Data-driven content decisions**: Identify high-performing genres and titles
- **User retention optimization**: Understand churn patterns and intervene
- **Personalization at scale**: Recommend content based on taste communities
- **Real-time monitoring**: Track KPIs and system health
- **Experimentation**: A/B test recommendation algorithms
- **Scalable architecture**: Configurable from 10k to 1M+ events

---

## ⚠️ Disclaimer

**This project is an independent educational simulation inspired by large-scale streaming data architectures. It is not affiliated with Netflix, Disney+, or any streaming service.**

All user data is synthetic and anonymized. No personal information is used or stored.

---

## 🔧 Configuration

Event generation can be configured via environment variables:
- `NUM_USERS`: Number of synthetic users (default: 10000)
- `NUM_CONTENT`: Number of content items (default: 5000)
- `EVENTS_PER_SECOND`: Event generation rate (default: 100)
- `SIMULATION_DURATION`: Simulation duration in seconds (default: 3600)

---

## 📝 Development Status

- [x] Architecture and repository structure
- [x] Docker + PostgreSQL + Kafka setup
- [x] Content dataset integration (MovieLens loader)
- [x] Database schema implementation (raw + dimensional base)
- [x] User and event generators
- [x] Kafka producer
- [x] Kafka consumer
- [x] Raw event layer
- [x] ETL/ELT pipeline
- [x] Data warehouse population
- [x] Data quality checks
- [x] SQL analytics views
- [x] Exploratory data analysis
- [x] KPI calculation
- [x] Power BI dashboards
- [x] Feature engineering
- [x] Taste clustering
- [x] Churn prediction model
- [x] Recommendation baseline
- [x] Content-based recommendation
- [x] Collaborative filtering
- [x] Hybrid recommendation
- [x] Recommendation evaluation
- [x] FastAPI implementation
- [x] Recommendation feedback loop
- [x] Thumbnail personalization
- [x] A/B testing
- [x] End-to-end tests
- [x] Performance optimization
- [x] Documentation
- [x] Final demonstration

---

## 🤝 Contributing

This is a portfolio project. Suggestions and improvements are welcome!

---

## 📄 License

MIT License

---

## 👤 Author

Millenxs

**Senior Data Engineer | Data Scientist | Machine Learning Engineer**

---

**Built with ❤️ for data engineering and machine learning portfolio**
