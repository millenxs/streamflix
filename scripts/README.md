# Docker Helper Scripts

This directory contains helper scripts to manage the StreamFlix Docker infrastructure.

## 🚀 Quick Start

### Windows (PowerShell)

```powershell
# Start all services
.\docker_helpers.ps1 start

# Stop all services
.\docker_helpers.ps1 stop

# Restart all services
.\docker_helpers.ps1 restart

# Show service status
.\docker_helpers.ps1 status

# Show logs
.\docker_helpers.ps1 logs
.\docker_helpers.ps1 logs postgres

# Create Kafka topics
.\docker_helpers.ps1 topics

# List Kafka topics
.\docker_helpers.ps1 list-topics

# Connect to PostgreSQL
.\docker_helpers.ps1 postgres
```

### Linux/Mac/WSL (Bash)

```bash
# Make script executable
chmod +x docker_helpers.sh

# Start all services
./docker_helpers.sh start

# Stop all services
./docker_helpers.sh stop

# Restart all services
./docker_helpers.sh restart

# Show service status
./docker_helpers.sh status

# Show logs
./docker_helpers.sh logs
./docker_helpers.sh logs postgres

# Create Kafka topics
./docker_helpers.sh topics

# List Kafka topics
./docker_helpers.sh list-topics

# Connect to PostgreSQL
./docker_helpers.sh postgres
```

## 📋 Available Services

| Service | Port | Description |
|---------|------|-------------|
| PostgreSQL | 5432 | Database server |
| Kafka | 9092, 29092 | Message broker (`29092` for host apps, `9092` inside Docker) |
| Zookeeper | 2181 | Kafka coordination |
| Kafka UI | 8080 | Web UI for Kafka |

## 🔗 Access Points

- **Kafka UI**: http://localhost:8080
- **PostgreSQL**: localhost:5432
  - User: streamflix
  - Password: streamflix123
  - Database: streamflix
- **Kafka**: localhost:29092 from host Python apps; kafka:9092 from Docker services

## 📊 Kafka Topics

The following topics are created by default:
- `streamflix.events` (3 partitions)
- `streamflix.playback` (3 partitions)
- `streamflix.interactions` (2 partitions)
- `streamflix.recommendations` (2 partitions)
- `streamflix.events.dlq` (1 partition)

## 🔧 Manual Docker Commands

If you prefer to use Docker directly:

```bash
# Start services
docker compose up -d

# Stop services
docker compose down

# View logs
docker compose logs -f

# View service status
docker compose ps

# Connect to PostgreSQL
docker exec -it streamflix-postgres psql -U streamflix -d streamflix

# Create Kafka topic
docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic <topic-name> --partitions 3 --replication-factor 1

# List Kafka topics
docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --list
```

## 🐛 Troubleshooting

### Services not starting

Check Docker is running:
```bash
docker ps
```

Check service logs:
```bash
docker compose logs
```

### PostgreSQL connection issues

Verify PostgreSQL is healthy:
```bash
docker compose ps
```

Test connection:
```bash
docker exec streamflix-postgres psql -U streamflix -d streamflix -c "SELECT version();"
```

### Kafka connection issues

Verify Kafka is healthy:
```bash
docker compose ps
```

Test Kafka:
```bash
docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --list
```

### Port conflicts

If ports are already in use, change them in `.env`:
```env
POSTGRES_PORT=5433
KAFKA_PORT=9093
KAFKA_UI_PORT=8081
```

Then restart services:
```bash
docker compose down
docker compose up -d
```

## 🧪 Event generation and Kafka publishing

Run these commands from the repository root after PostgreSQL and Kafka are healthy, topics exist, and the content catalog/users have been loaded:

```powershell
# Generate synthetic users
python -m src.generation.users

# Preview event generation without Kafka writes
python -m src.streaming.producer --days 1 --users 10 --limit 20 --dry-run

# Publish events to Kafka from the host machine
python -m src.streaming.producer --days 1 --users 10 --limit 1000 --events-per-second 100

# Persist canonical events into PostgreSQL raw tables
python -m src.streaming.consumer --limit 1000 --idle-timeout 10

# Populate warehouse fact tables from the raw layer
python -m src.etl.pipeline

# Validate raw/warehouse consistency
python -m src.analytics.quality

# Create dashboard-ready analytics views and EDA exports
python -m src.analytics.views
python -m src.analytics.eda

# Build features and train ML models
python -m src.features.user_features
python -m src.ml.clustering.train
python -m src.ml.churn.train
python -m src.ml.recommendation.generate

# Serve recommendations and feedback API
uvicorn src.api.main:app --reload
```

The producer writes every event to `streamflix.events` and duplicates domain-specific events to `streamflix.playback`, `streamflix.interactions`, or `streamflix.recommendations`.
The consumer reads `streamflix.events` by default, inserts idempotently into `raw_events`, and materializes playback events into `raw_playback_events`.
The ETL pipeline upserts device/location dimensions and idempotently populates recommendation, watch, session, interaction, and recommendation-feedback facts.
The quality checks validate key raw/warehouse consistency rules, analytics views expose dashboard-ready KPI datasets, and ML/API commands cover recommendation serving, feedback, A/B assignment, and thumbnail personalization.

## 📝 Notes

- Services are configured in `docker-compose.yml`
- Environment variables are in `.env`
- Data is persisted in Docker volumes
- PostgreSQL data is in `postgres_data` volume
