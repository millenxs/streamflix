#!/bin/bash
# StreamFlix Docker Helper Scripts
# These scripts help manage the Docker infrastructure

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Start all services
start_services() {
    print_status "Starting StreamFlix services..."
    docker compose up -d
    print_status "Waiting for services to be healthy..."
    sleep 10
    docker compose ps
    print_status "Services started successfully!"
    print_status "Kafka UI: http://localhost:8080"
    print_status "PostgreSQL: localhost:5432"
    print_status "Kafka from host apps: localhost:29092"
    print_status "Kafka inside Docker network: kafka:9092"
}

# Stop all services
stop_services() {
    print_status "Stopping StreamFlix services..."
    docker compose down
    print_status "Services stopped!"
}

# Restart all services
restart_services() {
    print_status "Restarting StreamFlix services..."
    docker compose restart
    print_status "Services restarted!"
}

# Show service status
show_status() {
    print_status "StreamFlix service status:"
    docker compose ps
}

# Show logs
show_logs() {
    local service=$1
    if [ -z "$service" ]; then
        docker compose logs
    else
        docker compose logs -f "$service"
    fi
}

# Create Kafka topics
create_topics() {
    print_status "Creating Kafka topics..."
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.events --partitions 3 --replication-factor 1 2>/dev/null || print_warning "Topic streamflix.events already exists"
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.playback --partitions 3 --replication-factor 1 2>/dev/null || print_warning "Topic streamflix.playback already exists"
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.interactions --partitions 2 --replication-factor 1 2>/dev/null || print_warning "Topic streamflix.interactions already exists"
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.recommendations --partitions 2 --replication-factor 1 2>/dev/null || print_warning "Topic streamflix.recommendations already exists"
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.events.dlq --partitions 1 --replication-factor 1 2>/dev/null || print_warning "Topic streamflix.events.dlq already exists"
    print_status "Kafka topics created!"
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --list
}

# List Kafka topics
list_topics() {
    print_status "Kafka topics:"
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --list
}

# Connect to PostgreSQL
connect_postgres() {
    print_status "Connecting to PostgreSQL..."
    docker exec -it streamflix-postgres psql -U streamflix -d streamflix
}

# Show help
show_help() {
    echo "StreamFlix Docker Helper Scripts"
    echo ""
    echo "Usage: ./docker_helpers.sh [command]"
    echo ""
    echo "Commands:"
    echo "  start       - Start all services"
    echo "  stop        - Stop all services"
    echo "  restart     - Restart all services"
    echo "  status      - Show service status"
    echo "  logs [service] - Show logs (optional: specify service)"
    echo "  topics      - Create Kafka topics"
    echo "  list-topics - List Kafka topics"
    echo "  postgres    - Connect to PostgreSQL"
    echo "  help        - Show this help message"
}

# Main script logic
case "$1" in
    start)
        start_services
        ;;
    stop)
        stop_services
        ;;
    restart)
        restart_services
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs "$2"
        ;;
    topics)
        create_topics
        ;;
    list-topics)
        list_topics
        ;;
    postgres)
        connect_postgres
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        print_error "Unknown command: $1"
        show_help
        exit 1
        ;;
esac
