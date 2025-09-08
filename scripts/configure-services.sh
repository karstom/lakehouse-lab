#!/bin/bash

# Lakehouse Lab - Service Configuration Wizard
# Allows users to selectively enable/disable components during installation

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

log_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

log_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

log_error() {
    echo -e "${RED}❌ $1${NC}"
}

# Service definitions with dependencies and descriptions
declare -A SERVICES
declare -A SERVICE_DESCRIPTIONS
declare -A SERVICE_DEPENDENCIES
declare -A SERVICE_PORTS
declare -A SERVICE_RESOURCES
declare -A SERVICE_CONFIG  # Store service configuration state

# Core services (cannot be disabled)
CORE_SERVICES=("postgres" "minio" "spark-master" "spark-worker" "lakehouse-init")

# Define services
SERVICES[airflow]="Apache Airflow (Workflow Orchestration)"
SERVICES[superset]="Apache Superset (Business Intelligence)"
SERVICES[jupyter]="JupyterLab (Data Science Notebooks)"
SERVICES[vizro]="Vizro (Interactive Dashboards)"
SERVICES[lancedb]="LanceDB (Vector Database)"
SERVICES[portainer]="Portainer (Docker Management)"
SERVICES[homepage]="Homepage (Service Dashboard)"

# Service descriptions
SERVICE_DESCRIPTIONS[airflow]="Workflow orchestration and scheduling platform for data pipelines"
SERVICE_DESCRIPTIONS[superset]="Modern data visualization and exploration platform"
SERVICE_DESCRIPTIONS[jupyter]="Interactive development environment for data science and analytics"
SERVICE_DESCRIPTIONS[vizro]="Low-code dashboard framework for interactive data visualization"
SERVICE_DESCRIPTIONS[lancedb]="High-performance vector database for AI/ML applications"
SERVICE_DESCRIPTIONS[portainer]="Web-based Docker container management interface"
SERVICE_DESCRIPTIONS[homepage]="Modern service dashboard with Docker integration and real-time monitoring"

# Service dependencies (services that depend on this service)
SERVICE_DEPENDENCIES[airflow]="lakehouse-init postgres"
SERVICE_DEPENDENCIES[superset]="lakehouse-init postgres"
SERVICE_DEPENDENCIES[jupyter]="lakehouse-init postgres minio"
SERVICE_DEPENDENCIES[vizro]="postgres minio lakehouse-init"
SERVICE_DEPENDENCIES[lancedb]="lakehouse-init"
SERVICE_DEPENDENCIES[portainer]=""
SERVICE_DEPENDENCIES[homepage]="lakehouse-init"

# Service ports
SERVICE_PORTS[airflow]="9020"
SERVICE_PORTS[superset]="9030"
SERVICE_PORTS[jupyter]="9040"
SERVICE_PORTS[vizro]="9050"
SERVICE_PORTS[lancedb]="9080"
SERVICE_PORTS[portainer]="9060"
SERVICE_PORTS[homepage]="9061"

# Resource requirements (RAM in GB)
SERVICE_RESOURCES[airflow]="4"
SERVICE_RESOURCES[superset]="4"
SERVICE_RESOURCES[jupyter]="8"
SERVICE_RESOURCES[vizro]="2"
SERVICE_RESOURCES[lancedb]="3"
SERVICE_RESOURCES[portainer]="0.5"
SERVICE_RESOURCES[homepage]="0.5"

# Configuration file
CONFIG_FILE=".lakehouse-services.conf"
COMPOSE_OVERRIDE_FILE="docker-compose.override.yml"

# Default configuration (all services enabled)
DEFAULT_CONFIG="airflow=true
superset=true
jupyter=true
vizro=true
lancedb=true
portainer=true
homepage=true"

# Function to load existing configuration
load_config() {
    # Initialize all services to true by default
    for service in "${!SERVICES[@]}"; do
        SERVICE_CONFIG["$service"]="true"
    done
    
    if [[ -f "$CONFIG_FILE" ]]; then
        log_info "Loading existing configuration from $CONFIG_FILE"
        # Parse config file manually to handle service names with hyphens
        while IFS='=' read -r service value; do
            # Skip empty lines and comments
            [[ -z "$service" || "$service" =~ ^[[:space:]]*# ]] && continue
            
            # Store in associative array
            SERVICE_CONFIG["$service"]="$value"
        done < <(grep -E '^[a-zA-Z0-9_-]+=' "$CONFIG_FILE" || true)
    else
        log_info "No existing configuration found, using defaults"
    fi
}

# Function to save configuration
save_config() {
    log_info "Saving configuration to $CONFIG_FILE"
    cat > "$CONFIG_FILE" << EOF
# Lakehouse Lab Service Configuration
# Generated on: $(date)
# Edit this file to customize which services are enabled

EOF
    
    for service in "${!SERVICES[@]}"; do
        local value="${SERVICE_CONFIG[$service]:-true}"
        echo "${service}=${value}" >> "$CONFIG_FILE"
    done
    
    log_success "Configuration saved to $CONFIG_FILE"
}

# Function to show current configuration
show_config() {
    echo -e "${BLUE}🔧 Current Service Configuration${NC}"
    echo -e "${BLUE}=================================${NC}"
    echo ""
    
    local total_ram=0
    local enabled_count=0
    
    for service in "${!SERVICES[@]}"; do
        local enabled="${SERVICE_CONFIG[$service]:-true}"
        local status_icon="❌"
        local status_text="DISABLED"
        
        if [[ "$enabled" == "true" ]]; then
            status_icon="✅"
            status_text="ENABLED"
            total_ram=$(echo "$total_ram + ${SERVICE_RESOURCES[$service]}" | bc -l)
            enabled_count=$((enabled_count + 1))
        fi
        
        printf "%-12s %s %-8s (Port: %s, RAM: %sGB)\n" \
            "$service:" "$status_icon" "$status_text" \
            "${SERVICE_PORTS[$service]}" "${SERVICE_RESOURCES[$service]}"
        printf "             %s\n" "${SERVICE_DESCRIPTIONS[$service]}"
        echo ""
    done
    
    echo -e "${YELLOW}📊 Summary:${NC}"
    echo -e "  Enabled services: $enabled_count/${#SERVICES[@]}"
    printf "  Total RAM usage: %.1fGB\n" "$total_ram"
    echo -e "  Core services (always enabled): ${#CORE_SERVICES[@]}"
    echo ""
}

# Function to configure services interactively
configure_interactive() {
    echo -e "${BLUE}🛠️  Interactive Service Configuration${NC}"
    echo -e "${BLUE}====================================${NC}"
    echo ""
    echo -e "${YELLOW}Configure which services you want to enable in your Lakehouse Lab.${NC}"
    echo -e "${YELLOW}Core services (PostgreSQL, MinIO, Spark) are always enabled.${NC}"
    echo ""
    
    for service in "${!SERVICES[@]}"; do
        local var_name="${service}"
        local current_value="${!var_name:-true}"
        local default_text="Y/n"
        
        if [[ "$current_value" == "false" ]]; then
            default_text="y/N"
        fi
        
        echo -e "${GREEN}${SERVICES[$service]}${NC}"
        echo -e "  ${SERVICE_DESCRIPTIONS[$service]}"
        echo -e "  Port: ${SERVICE_PORTS[$service]}, RAM: ${SERVICE_RESOURCES[$service]}GB"
        
        while true; do
            echo -n "  Enable this service? [$default_text]: "
            read -r response
            
            case "$response" in
                [Yy]*)
                    declare -g "$var_name=true"
                    break
                    ;;
                [Nn]*)
                    declare -g "$var_name=false"
                    break
                    ;;
                "")
                    # Use current/default value
                    break
                    ;;
                *)
                    echo -e "  ${RED}Please answer y or n${NC}"
                    ;;
            esac
        done
        echo ""
    done
    
    # Show final configuration
    echo -e "${BLUE}📋 Final Configuration:${NC}"
    show_config
    
    echo -n "Save this configuration? [Y/n]: "
    read -r save_response
    if [[ ! "$save_response" =~ ^[Nn]$ ]]; then
        save_config
        generate_compose_override
        log_success "Configuration saved and applied!"
    fi
}

# Function to generate Docker Compose override file
generate_compose_override() {
    log_info "Generating Docker Compose override file..."
    
    cat > "$COMPOSE_OVERRIDE_FILE" << 'EOF'
# Lakehouse Lab - Service Override Configuration
# This file is auto-generated by scripts/configure-services.sh
# DO NOT EDIT MANUALLY - use the configuration script instead

services:
EOF
    
    # Check each service and add to override if disabled
    for service in "${!SERVICES[@]}"; do
        local enabled="${SERVICE_CONFIG[$service]:-true}"
        
        if [[ "$enabled" == "false" ]]; then
            # Disable the service by setting replicas to 0
            cat >> "$COMPOSE_OVERRIDE_FILE" << EOF
  ${service}:
    deploy:
      replicas: 0
    profiles:
      - disabled
EOF
            
            # Handle multi-service components (like Airflow)
            if [[ "$service" == "airflow" ]]; then
                for airflow_service in "airflow-scheduler" "airflow-webserver" "airflow-init"; do
                    cat >> "$COMPOSE_OVERRIDE_FILE" << EOF
  ${airflow_service}:
    deploy:
      replicas: 0
    profiles:
      - disabled
EOF
                done
            fi
        fi
    done
    
    log_success "Generated $COMPOSE_OVERRIDE_FILE"
}

# Function to show system recommendations
show_recommendations() {
    local total_ram=0
    local enabled_services=()
    
    # Calculate total resource requirements
    for service in "${!SERVICES[@]}"; do
        local var_name="${service}"
        local enabled="${!var_name:-true}"
        
        if [[ "$enabled" == "true" ]]; then
            total_ram=$(echo "$total_ram + ${SERVICE_RESOURCES[$service]}" | bc -l)
            enabled_services+=("$service")
        fi
    done
    
    # Add core services RAM (estimated)
    local core_ram=6  # PostgreSQL (2GB) + MinIO (2GB) + Spark (2GB)
    total_ram=$(echo "$total_ram + $core_ram" | bc -l)
    
    echo -e "${BLUE}💡 System Recommendations${NC}"
    echo -e "${BLUE}=========================${NC}"
    echo ""
    
    printf "Estimated RAM usage: %.1fGB (including core services)\n" "$total_ram"
    echo ""
    
    if (( $(echo "$total_ram > 32" | bc -l) )); then
        echo -e "${RED}⚠️  HIGH RESOURCE USAGE WARNING${NC}"
        echo -e "   This configuration requires substantial system resources"
        echo -e "   Recommended: 64GB+ RAM, 16+ CPU cores"
        echo -e "   Consider using the 'fat server' configuration"
    elif (( $(echo "$total_ram > 16" | bc -l) )); then
        echo -e "${YELLOW}⚠️  MODERATE RESOURCE USAGE${NC}"
        echo -e "   This configuration works well on development machines"
        echo -e "   Recommended: 32GB+ RAM, 8+ CPU cores"
    else
        echo -e "${GREEN}✅ LIGHT RESOURCE USAGE${NC}"
        echo -e "   This configuration works on most modern laptops"
        echo -e "   Minimum: 16GB RAM, 4+ CPU cores"
    fi
    
    echo ""
    echo -e "${YELLOW}Service-specific recommendations:${NC}"
    
    for service in "${enabled_services[@]}"; do
        case "$service" in
            "jupyter"|"airflow"|"superset")
                echo -e "  • ${service}: Consider SSD storage for better performance"
                ;;
            "lancedb")
                echo -e "  • ${service}: Benefits from fast storage for vector operations"
                ;;
            "vizro")
                echo -e "  • ${service}: Lightweight, minimal resource impact"
                ;;
        esac
    done
    echo ""
}

# Function to create preset configurations
create_preset() {
    local preset=$1
    
    case "$preset" in
        "minimal")
            log_info "Creating minimal configuration (core + Jupyter only)"
            cat > "$CONFIG_FILE" << EOF
# Minimal Lakehouse Lab Configuration
airflow=false
superset=false
jupyter=true
vizro=false
lancedb=false
portainer=true
homer=false
EOF
            ;;
        "analytics")
            log_info "Creating analytics configuration (Jupyter + Superset + Vizro)"
            cat > "$CONFIG_FILE" << EOF
# Analytics-focused Lakehouse Lab Configuration
airflow=false
superset=true
jupyter=true
vizro=true
lancedb=false
portainer=true
homepage=true
EOF
            ;;
        "ml")
            log_info "Creating ML configuration (Jupyter + LanceDB + Airflow)"
            cat > "$CONFIG_FILE" << EOF
# ML/AI-focused Lakehouse Lab Configuration
airflow=true
superset=false
jupyter=true
vizro=false
lancedb=true
portainer=true
homepage=true
EOF
            ;;
        "full")
            log_info "Creating full configuration (all services enabled)"
            echo "$DEFAULT_CONFIG" > "$CONFIG_FILE"
            ;;
        *)
            log_error "Unknown preset: $preset"
            log_info "Available presets: minimal, analytics, ml, full"
            exit 1
            ;;
    esac
    
    # Load and apply the preset
    load_config
    generate_compose_override
    log_success "Applied '$preset' preset configuration"
}

# Function to validate configuration
validate_config() {
    log_info "Validating service configuration..."
    
    local errors=0
    
    # Check for dependency conflicts
    for service in "${!SERVICES[@]}"; do
        local var_name="${service}"
        local enabled="${!var_name:-true}"
        
        if [[ "$enabled" == "true" ]]; then
            # Check if dependencies are available
            local deps="${SERVICE_DEPENDENCIES[$service]}"
            for dep in $deps; do
                if [[ " ${CORE_SERVICES[*]} " =~ " ${dep} " ]]; then
                    continue  # Core services are always enabled
                fi
                
                local dep_var="${dep}"
                local dep_enabled="${!dep_var:-true}"
                
                if [[ "$dep_enabled" == "false" ]]; then
                    log_error "$service requires $dep, but $dep is disabled"
                    errors=$((errors + 1))
                fi
            done
        fi
    done
    
    if [[ $errors -gt 0 ]]; then
        log_error "Configuration validation failed with $errors errors"
        return 1
    else
        log_success "Configuration validation passed"
        return 0
    fi
}

# Main script logic
main() {
    echo -e "${BLUE}🔧 Lakehouse Lab Service Configurator${NC}"
    echo -e "${BLUE}=====================================${NC}"
    echo ""
    
    # Load existing configuration
    load_config
    
    case "${1:-interactive}" in
        "interactive"|"config")
            configure_interactive
            ;;
        "show"|"status")
            show_config
            ;;
        "preset")
            if [[ -n "${2:-}" ]]; then
                create_preset "$2"
            else
                log_error "Please specify a preset: minimal, analytics, ml, full"
                exit 1
            fi
            ;;
        "validate")
            validate_config
            ;;
        "recommendations"|"recommend")
            show_recommendations
            ;;
        "reset")
            log_warning "Resetting to default configuration..."
            echo "$DEFAULT_CONFIG" > "$CONFIG_FILE"
            load_config
            generate_compose_override
            log_success "Reset to default configuration"
            ;;
        "help"|"-h"|"--help")
            echo -e "${YELLOW}Usage:${NC}"
            echo -e "  $0 [command] [options]"
            echo ""
            echo -e "${YELLOW}Commands:${NC}"
            echo -e "  interactive    Configure services interactively (default)"
            echo -e "  show           Show current configuration"
            echo -e "  preset <name>  Apply a preset configuration"
            echo -e "  validate       Validate current configuration"
            echo -e "  recommend      Show system recommendations"
            echo -e "  reset          Reset to default configuration"
            echo -e "  help           Show this help"
            echo ""
            echo -e "${YELLOW}Presets:${NC}"
            echo -e "  minimal        Core services + Jupyter only"
            echo -e "  analytics      Jupyter + Superset + Vizro"
            echo -e "  ml             Jupyter + LanceDB + Airflow"
            echo -e "  full           All services enabled"
            echo -e ""
            echo ""
            ;;
        *)
            log_error "Unknown command: $1"
            log_info "Use '$0 help' for usage information"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"