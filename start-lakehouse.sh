#!/bin/bash

# Lakehouse Lab Startup Script with Error Handling
# Compatible with current Docker Compose configuration

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
LAKEHOUSE_ROOT="${LAKEHOUSE_ROOT:-./lakehouse-data}"
STARTUP_MODE="${1:-normal}"  # normal, debug, minimal
MAX_RETRIES=2
RETRY_COUNT=0

echo -e "${BLUE}🏠 Lakehouse Lab Startup Script${NC}"
echo -e "${BLUE}================================${NC}"
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}❌ Docker not found. Please install Docker first.${NC}"
    exit 1
fi

if ! docker compose version &> /dev/null; then
    echo -e "${RED}❌ Docker Compose not found. Please install Docker Compose first.${NC}"
    exit 1
fi

# Function to check service health
check_service_health() {
    local service_name=$1
    local health_url=$2
    local max_attempts=${3:-20}
    
    echo -e "${YELLOW}⏳ Checking $service_name health...${NC}"
    
    for i in $(seq 1 $max_attempts); do
        if curl -sf "$health_url" >/dev/null 2>&1; then
            echo -e "${GREEN}✅ $service_name is healthy${NC}"
            return 0
        fi
        echo -e "   Attempt $i/$max_attempts - waiting 5s..."
        sleep 5
    done
    
    echo -e "${RED}❌ $service_name failed to become healthy${NC}"
    return 1
}

# Function to check if curl is available, install if needed
ensure_curl() {
    if ! command -v curl &> /dev/null; then
        echo -e "${YELLOW}⚠️  curl not found, trying to install...${NC}"
        # Try common package managers
        if command -v apt-get &> /dev/null; then
            sudo apt-get update && sudo apt-get install -y curl
        elif command -v yum &> /dev/null; then
            sudo yum install -y curl
        elif command -v brew &> /dev/null; then
            brew install curl
        else
            echo -e "${RED}❌ Cannot install curl automatically. Please install curl manually.${NC}"
            exit 1
        fi
    fi
}

# Function to start services with dependency checking
start_with_dependencies() {
    echo -e "${BLUE}🚀 Starting Lakehouse Lab ($STARTUP_MODE mode, attempt $((RETRY_COUNT + 1))/$((MAX_RETRIES + 1)))...${NC}"
    
    # Ensure curl is available for health checks
    ensure_curl
    
    # Ensure data directory exists
    mkdir -p "$LAKEHOUSE_ROOT"
    
    case "$STARTUP_MODE" in
        "minimal")
            echo -e "${YELLOW}📦 Starting minimal services (storage + basic query)...${NC}"
            docker compose up -d postgres minio
            check_service_health "MinIO" "http://localhost:9000/minio/health/live"
            
            # Start lakehouse-init to set up buckets and sample data
            echo -e "${BLUE}🔧 Running initialization...${NC}"
            docker compose up lakehouse-init
            
            # Start Homer for service links
            docker compose up -d homer
            ;;
            
        "debug")
            echo -e "${YELLOW}🔍 Starting in debug mode (services one by one)...${NC}"
            
            # Layer 1: Storage
            echo -e "${BLUE}Layer 1: Storage services${NC}"
            docker compose up -d postgres minio
            check_service_health "MinIO" "http://localhost:9000/minio/health/live"
            
            # Layer 2: Processing
            echo -e "${BLUE}Layer 2: Compute engines${NC}"
            docker compose up -d spark-master spark-worker
            check_service_health "Spark Master" "http://localhost:8080" 15
            
            # Layer 3: Initialization
            echo -e "${BLUE}Layer 3: Data initialization${NC}"
            docker compose up lakehouse-init
            
            # Layer 4: Applications
            echo -e "${BLUE}Layer 4: User applications${NC}"
            docker compose up -d jupyter airflow-init
            sleep 30  # Give airflow-init time to complete
            docker compose up -d airflow-scheduler airflow-webserver
            
            # Layer 5: BI and monitoring
            echo -e "${BLUE}Layer 5: BI and monitoring${NC}"
            docker compose up -d superset portainer
            
            # Optional services
            echo -e "${BLUE}Layer 6: Optional services${NC}"
            docker compose --profile optional up -d homer || echo -e "${YELLOW}⚠️  Homer is optional and may not start${NC}"
            ;;
            
        "normal"|*)
            echo -e "${YELLOW}📦 Starting all services...${NC}"
            
            # Try normal startup first
            if docker compose up -d; then
                echo -e "${GREEN}✅ All services started successfully${NC}"
                
                # Check key services
                sleep 10
                check_service_health "MinIO" "http://localhost:9000/minio/health/live" 10
                check_service_health "Spark Master" "http://localhost:8080" 15
                
            else
                echo -e "${RED}❌ Normal startup failed${NC}"
                
                # Check retry limits to prevent infinite loops
                if [ $RETRY_COUNT -lt $MAX_RETRIES ]; then
                    RETRY_COUNT=$((RETRY_COUNT + 1))
                    echo -e "${YELLOW}⏳ Retrying with debug mode (attempt $((RETRY_COUNT + 1))/$((MAX_RETRIES + 1)))...${NC}"
                    sleep 5
                    
                    # Switch to debug mode for retry
                    STARTUP_MODE="debug"
                    start_with_dependencies
                    return
                else
                    echo -e "${RED}❌ Maximum retries ($MAX_RETRIES) exceeded. Startup failed.${NC}"
                    echo -e "${YELLOW}💡 Try running: ./start-lakehouse.sh debug${NC}"
                    echo -e "${YELLOW}💡 Or check logs: ./start-lakehouse.sh logs${NC}"
                    exit 1
                fi
            fi
            ;;
    esac
    
    # Final status check
    echo -e "${BLUE}📊 Final status check...${NC}"
    docker compose ps
    
    echo ""
    echo -e "${GREEN}🎉 Lakehouse Lab is ready!${NC}"
    echo ""
    echo -e "${BLUE}Access points:${NC}"
    echo -e "  🐳 Portainer:         ${GREEN}http://localhost:9060${NC} (container management)"
    echo -e "  📈 Superset BI:       ${GREEN}http://localhost:9030${NC} (admin/admin)"
    echo -e "  📋 Airflow:           ${GREEN}http://localhost:9020${NC} (admin/admin)"
    echo -e "  📓 JupyterLab:        ${GREEN}http://localhost:9040${NC} (token: lakehouse)"
    echo -e "  ☁️  MinIO Console:     ${GREEN}http://localhost:9001${NC} (minio/minio123)"
    echo -e "  ⚡ Spark Master:      ${GREEN}http://localhost:8080${NC}"
    echo -e "  🏠 Service Links:     ${GREEN}http://localhost:9061${NC} (optional Homer)"
    echo ""
    echo -e "${YELLOW}💡 Tip: Use Portainer (localhost:9060) for container management and monitoring${NC}"
    echo -e "${YELLOW}📖 Check QUICKSTART.md for step-by-step usage instructions${NC}"
    echo ""
}

# Function to show logs for problematic services
show_logs() {
    echo -e "${BLUE}📋 Recent logs for key services:${NC}"
    echo ""
    
    for service in lakehouse-init airflow-init airflow-scheduler airflow-webserver superset jupyter spark-master; do
        echo -e "${YELLOW}=== $service ===${NC}"
        docker compose logs --tail=20 "$service" 2>/dev/null || echo "Service not running or no logs available"
        echo ""
    done
}

# Function to check system resources
check_resources() {
    echo -e "${BLUE}💻 System Resource Check${NC}"
    echo -e "${BLUE}========================${NC}"
    echo ""
    
    # Check available memory
    if command -v free &> /dev/null; then
        echo -e "${YELLOW}Memory Usage:${NC}"
        free -h
        echo ""
    fi
    
    # Check disk space
    if command -v df &> /dev/null; then
        echo -e "${YELLOW}Disk Usage:${NC}"
        df -h . 2>/dev/null || echo "Cannot check disk usage"
        echo ""
    fi
    
    # Check Docker system
    echo -e "${YELLOW}Docker System Info:${NC}"
    docker system df 2>/dev/null || echo "Cannot get Docker system info"
    echo ""
    
    # Recommend configuration
    echo -e "${YELLOW}💡 Configuration Recommendations:${NC}"
    echo -e "  • Standard setup: 16GB RAM, 4+ CPU cores"
    echo -e "  • Fat server setup: 64GB+ RAM, 16+ CPU cores"
    echo -e "  • Copy .env.fat-server to .env for high-performance systems"
    echo ""
}

# Function to clean up and reset
reset_environment() {
    echo -e "${RED}🧹 Resetting Lakehouse Lab environment...${NC}"
    echo -e "${RED}This will destroy ALL data and containers!${NC}"
    echo ""
    
    read -p "Are you absolutely sure? Type 'yes' to continue: " -r
    echo
    if [[ $REPLY == "yes" ]]; then
        echo -e "${YELLOW}Stopping all services...${NC}"
        docker compose down -v
        
        echo -e "${YELLOW}Removing data directory...${NC}"
        rm -rf "$LAKEHOUSE_ROOT"
        
        echo -e "${YELLOW}Pruning Docker system...${NC}"
        docker system prune -f
        
        echo -e "${GREEN}✅ Environment reset complete${NC}"
        echo -e "${BLUE}💡 Run './start-lakehouse.sh' to start fresh${NC}"
    else
        echo -e "${YELLOW}Reset cancelled${NC}"
    fi
}

# Function to show status
show_status() {
    echo -e "${BLUE}📊 Lakehouse Lab Status${NC}"
    echo -e "${BLUE}=======================${NC}"
    echo ""
    
    echo -e "${YELLOW}Container Status:${NC}"
    docker compose ps
    echo ""
    
    echo -e "${YELLOW}Service Health:${NC}"
    services=(
        "MinIO:http://localhost:9000/minio/health/live"
        "Spark:http://localhost:8080"
        "Airflow:http://localhost:9020/health"
        "Superset:http://localhost:9030/health"
        "Portainer:http://localhost:9060"
    )
    
    for service_info in "${services[@]}"; do
        IFS=':' read -r name url <<< "$service_info"
        if curl -sf "$url" >/dev/null 2>&1; then
            echo -e "  ✅ $name is healthy"
        else
            echo -e "  ❌ $name is not responding"
        fi
    done
    echo ""
}

# Main script logic
case "$STARTUP_MODE" in
    "logs")
        show_logs
        ;;
    "reset")
        reset_environment
        ;;
    "stop")
        echo -e "${YELLOW}🛑 Stopping Lakehouse Lab...${NC}"
        docker compose down
        echo -e "${GREEN}✅ All services stopped${NC}"
        ;;
    "status")
        show_status
        ;;
    "resources")
        check_resources
        ;;
    "help"|"-h"|"--help")
        echo -e "${BLUE}Lakehouse Lab Startup Script${NC}"
        echo ""
        echo -e "${YELLOW}Usage:${NC}"
        echo -e "  ./start-lakehouse.sh [mode]"
        echo ""
        echo -e "${YELLOW}Modes:${NC}"
        echo -e "  normal     Start all services (default)"
        echo -e "  debug      Start services layer by layer"
        echo -e "  minimal    Start only core services"
        echo -e "  stop       Stop all services"
        echo -e "  status     Show service status"
        echo -e "  logs       Show recent logs"
        echo -e "  resources  Check system resources"
        echo -e "  reset      Reset entire environment (DESTRUCTIVE)"
        echo -e "  help       Show this help"
        echo ""
        ;;
    *)
        start_with_dependencies
        ;;
esac
