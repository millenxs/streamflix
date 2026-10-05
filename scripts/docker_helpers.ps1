# StreamFlix Docker Helper Scripts (PowerShell)
# These scripts help manage the Docker infrastructure

function Write-Status {
    param([string]$Message)
    Write-Host "[INFO] $Message" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Message)
    Write-Host "[WARN] $Message" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Message)
    Write-Host "[ERROR] $Message" -ForegroundColor Red
}

# Start all services
function Start-Services {
    Write-Status "Starting StreamFlix services..."
    docker compose up -d
    Write-Status "Waiting for services to be healthy..."
    Start-Sleep -Seconds 10
    docker compose ps
    Write-Status "Services started successfully!"
    Write-Status "Kafka UI: http://localhost:8080"
    Write-Status "PostgreSQL: localhost:5432"
    Write-Status "Kafka from host apps: localhost:29092"
    Write-Status "Kafka inside Docker network: kafka:9092"
}

# Stop all services
function Stop-Services {
    Write-Status "Stopping StreamFlix services..."
    docker compose down
    Write-Status "Services stopped!"
}

# Restart all services
function Restart-Services {
    Write-Status "Restarting StreamFlix services..."
    docker compose restart
    Write-Status "Services restarted!"
}

# Show service status
function Show-Status {
    Write-Status "StreamFlix service status:"
    docker compose ps
}

# Show logs
function Show-Logs {
    param([string]$Service = "")
    if ($Service -eq "") {
        docker compose logs
    } else {
        docker compose logs -f $Service
    }
}

# Create Kafka topics
function Create-Topics {
    Write-Status "Creating Kafka topics..."
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.events --partitions 3 --replication-factor 1 2>$null; if ($LASTEXITCODE -ne 0) { Write-Warning "Topic streamflix.events already exists" }
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.playback --partitions 3 --replication-factor 1 2>$null; if ($LASTEXITCODE -ne 0) { Write-Warning "Topic streamflix.playback already exists" }
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.interactions --partitions 2 --replication-factor 1 2>$null; if ($LASTEXITCODE -ne 0) { Write-Warning "Topic streamflix.interactions already exists" }
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.recommendations --partitions 2 --replication-factor 1 2>$null; if ($LASTEXITCODE -ne 0) { Write-Warning "Topic streamflix.recommendations already exists" }
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --create --topic streamflix.events.dlq --partitions 1 --replication-factor 1 2>$null; if ($LASTEXITCODE -ne 0) { Write-Warning "Topic streamflix.events.dlq already exists" }
    Write-Status "Kafka topics created!"
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --list
}

# List Kafka topics
function List-Topics {
    Write-Status "Kafka topics:"
    docker exec streamflix-kafka kafka-topics --bootstrap-server localhost:9092 --list
}

# Connect to PostgreSQL
function Connect-Postgres {
    Write-Status "Connecting to PostgreSQL..."
    docker exec -it streamflix-postgres psql -U streamflix -d streamflix
}

# Show help
function Show-Help {
    Write-Host "StreamFlix Docker Helper Scripts"
    Write-Host ""
    Write-Host "Usage: .\docker_helpers.ps1 [command]"
    Write-Host ""
    Write-Host "Commands:"
    Write-Host "  start       - Start all services"
    Write-Host "  stop        - Stop all services"
    Write-Host "  restart     - Restart all services"
    Write-Host "  status      - Show service status"
    Write-Host "  logs [service] - Show logs (optional: specify service)"
    Write-Host "  topics      - Create Kafka topics"
    Write-Host "  list-topics - List Kafka topics"
    Write-Host "  postgres    - Connect to PostgreSQL"
    Write-Host "  help        - Show this help message"
}

# Main script logic
$command = $args[0]

switch ($command) {
    "start" {
        Start-Services
    }
    "stop" {
        Stop-Services
    }
    "restart" {
        Restart-Services
    }
    "status" {
        Show-Status
    }
    "logs" {
        $service = $args[1]
        Show-Logs -Service $service
    }
    "topics" {
        Create-Topics
    }
    "list-topics" {
        List-Topics
    }
    "postgres" {
        Connect-Postgres
    }
    "help" {
        Show-Help
    }
    default {
        Write-Error "Unknown command: $command"
        Show-Help
        exit 1
    }
}
