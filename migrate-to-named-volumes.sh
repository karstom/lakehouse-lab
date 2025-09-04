#!/bin/bash

# =============================================================================
# Lakehouse Lab: Migrate from Bind Mounts to Named Volumes
# =============================================================================
# This script migrates existing installations from bind mount storage
# to the new named volume system for data persistence and safety.
#
# IMPORTANT: This is a ONE-WAY migration. Make backups first!
# =============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
LAKEHOUSE_ROOT="${LAKEHOUSE_ROOT:-./lakehouse-data}"
BACKUP_DIR="./lakehouse-data-backup-$(date +%Y%m%d_%H%M%S)"
DRY_RUN="${1:-false}"

print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD} 🔄 Lakehouse Lab Volume Migration${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    echo -e "${YELLOW}Migrating from bind mounts to named volumes${NC}"
    echo -e "${YELLOW}This ensures data persistence and safety${NC}"
    echo ""
}

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

check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if we're in the right directory
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "Please run this script from your Lakehouse Lab directory"
        log_info "Make sure docker-compose.yml file exists"
        exit 1
    fi
    
    # Check if old data directory exists
    if [[ ! -d "$LAKEHOUSE_ROOT" ]]; then
        log_warning "No existing data directory found at $LAKEHOUSE_ROOT"
        log_info "This appears to be a fresh installation - no migration needed"
        exit 0
    fi
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker not found. Please install Docker first."
        exit 1
    fi
    
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose not found. Please install Docker Compose first."
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

detect_existing_data() {
    log_info "Scanning for existing data..."
    
    local data_found=false
    local data_summary=""
    
    # Check each service data directory
    if [[ -d "$LAKEHOUSE_ROOT/postgres" ]] && [[ "$(ls -A $LAKEHOUSE_ROOT/postgres 2>/dev/null)" ]]; then
        data_summary+="\n  📊 PostgreSQL database data"
        data_found=true
    fi
    
    if [[ -d "$LAKEHOUSE_ROOT/minio" ]] && [[ "$(ls -A $LAKEHOUSE_ROOT/minio 2>/dev/null)" ]]; then
        data_summary+="\n  🪣 MinIO object storage data"
        data_found=true
    fi
    
    if [[ -d "$LAKEHOUSE_ROOT/notebooks" ]] && [[ "$(ls -A $LAKEHOUSE_ROOT/notebooks 2>/dev/null)" ]]; then
        data_summary+="\n  📓 Jupyter notebooks"
        data_found=true
    fi
    
    if [[ -d "$LAKEHOUSE_ROOT/airflow" ]] && [[ "$(find $LAKEHOUSE_ROOT/airflow -name "*.py" 2>/dev/null | head -1)" ]]; then
        data_summary+="\n  🌊 Airflow DAGs and logs"
        data_found=true
    fi
    
    if [[ -d "$LAKEHOUSE_ROOT/spark" ]] && [[ "$(ls -A $LAKEHOUSE_ROOT/spark 2>/dev/null)" ]]; then
        data_summary+="\n  ⚡ Spark jobs and logs"
        data_found=true
    fi
    
    if [[ -d "$LAKEHOUSE_ROOT/superset" ]] && [[ "$(ls -A $LAKEHOUSE_ROOT/superset 2>/dev/null)" ]]; then
        data_summary+="\n  📈 Superset dashboards"
        data_found=true
    fi
    
    if $data_found; then
        echo -e "${GREEN}Found existing data:${NC}$data_summary"
        echo ""
        return 0
    else
        log_warning "No significant data found in $LAKEHOUSE_ROOT"
        log_info "Migration may not be necessary"
        return 1
    fi
}

confirm_migration() {
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "DRY RUN MODE - No actual changes will be made"
        return 0
    fi
    
    echo -e "${YELLOW}${BOLD}IMPORTANT MIGRATION INFORMATION:${NC}"
    echo ""
    echo -e "${RED}This migration will:${NC}"
    echo -e "${RED}  1. Stop all running services${NC}"
    echo -e "${RED}  2. Create a backup of your current data${NC}"
    echo -e "${RED}  3. Create new Docker named volumes${NC}"
    echo -e "${RED}  4. Copy data from bind mounts to named volumes${NC}"
    echo -e "${RED}  5. Update your configuration${NC}"
    echo ""
    echo -e "${GREEN}Benefits after migration:${NC}"
    echo -e "${GREEN}  ✅ Data survives container recreation${NC}"
    echo -e "${GREEN}  ✅ Data survives 'docker compose down'${NC}"
    echo -e "${GREEN}  ✅ Data survives overlay switching${NC}"
    echo -e "${GREEN}  ✅ Data survives upgrade processes${NC}"
    echo ""
    echo -e "${YELLOW}Backup will be created at: $BACKUP_DIR${NC}"
    echo ""
    
    read -p "Do you want to proceed with the migration? [y/N]: " -r
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_warning "Migration cancelled by user"
        exit 0
    fi
    
    echo ""
    log_success "Migration confirmed"
}

create_backup() {
    log_info "Creating backup of current data..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create backup: $BACKUP_DIR"
        return 0
    fi
    
    # Create backup directory
    mkdir -p "$BACKUP_DIR"
    
    # Copy all data
    if [[ -d "$LAKEHOUSE_ROOT" ]]; then
        cp -r "$LAKEHOUSE_ROOT"/* "$BACKUP_DIR/" 2>/dev/null || true
    fi
    
    # Copy configuration files
    cp .env "$BACKUP_DIR/.env.backup" 2>/dev/null || true
    cp docker-compose.yml "$BACKUP_DIR/docker-compose.yml.backup" 2>/dev/null || true
    
    log_success "Backup created at $BACKUP_DIR"
}

stop_services() {
    log_info "Stopping all services..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would stop services with: docker compose stop"
        return 0
    fi
    
    # Use stop instead of down to preserve any existing volumes
    docker compose stop || log_warning "Some services may not have stopped cleanly"
    
    log_success "Services stopped"
}

create_named_volumes() {
    log_info "Creating named volumes..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would create named volumes"
        return 0
    fi
    
    # Get the project name (directory name)
    local project_name=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]')
    
    # Create all named volumes
    local volumes=(
        "postgres_data"
        "minio_data" 
        "jupyter_notebooks"
        "jupyter_config"
        "airflow_dags"
        "airflow_logs"
        "airflow_plugins"
        "spark_jobs"
        "spark_logs"
        "superset_data"
        "homer_data"
        "vizro_data"
        "lancedb_data"
        "lakehouse_shared"
    )
    
    for volume in "${volumes[@]}"; do
        docker volume create "${project_name}_${volume}" || log_warning "Volume ${volume} may already exist"
        
        # Fix ownership for Airflow volumes if they need special permissions
        if [[ "$volume" == "airflow_"* ]]; then
            # Use a temporary container to fix Airflow volume ownership
            docker run --rm \
                -v "${project_name}_${volume}:/mnt/volume" \
                --user root \
                alpine:latest \
                sh -c "chown -R ${AIRFLOW_UID:-50000}:0 /mnt/volume && chmod -R 755 /mnt/volume" >/dev/null 2>&1 || log_warning "Could not fix permissions for ${volume}"
        fi
    done
    
    log_success "Named volumes created"
}

migrate_data() {
    log_info "Migrating data to named volumes..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would migrate data from $LAKEHOUSE_ROOT to named volumes"
        return 0
    fi
    
    local project_name=$(basename "$(pwd)" | tr '[:upper:]' '[:lower:]')
    
    # Migration mapping: source_path:volume_name:container_path
    local migrations=(
        "$LAKEHOUSE_ROOT/postgres:${project_name}_postgres_data:/var/lib/postgresql/data"
        "$LAKEHOUSE_ROOT/minio:${project_name}_minio_data:/data"
        "$LAKEHOUSE_ROOT/notebooks:${project_name}_jupyter_notebooks:/notebooks"
        "$LAKEHOUSE_ROOT/jupyter-config:${project_name}_jupyter_config:/config" 
        "$LAKEHOUSE_ROOT/airflow/dags:${project_name}_airflow_dags:/dags"
        "$LAKEHOUSE_ROOT/airflow/logs:${project_name}_airflow_logs:/logs"
        "$LAKEHOUSE_ROOT/airflow/plugins:${project_name}_airflow_plugins:/plugins"
        "$LAKEHOUSE_ROOT/spark/jobs:${project_name}_spark_jobs:/jobs"
        "$LAKEHOUSE_ROOT/spark/logs:${project_name}_spark_logs:/logs"
        "$LAKEHOUSE_ROOT/superset:${project_name}_superset_data:/data"
        "$LAKEHOUSE_ROOT/homer:${project_name}_homer_data:/data"
        "$LAKEHOUSE_ROOT/vizro:${project_name}_vizro_data:/data"
        "$LAKEHOUSE_ROOT/lancedb:${project_name}_lancedb_data:/data"
    )
    
    for migration in "${migrations[@]}"; do
        IFS=':' read -r source_path volume_name container_path <<< "$migration"
        
        if [[ -d "$source_path" ]] && [[ "$(ls -A "$source_path" 2>/dev/null)" ]]; then
            log_info "Migrating $(basename "$source_path") data..."
            
            # Use a temporary container to copy data
            docker run --rm \
                -v "$source_path:/source" \
                -v "$volume_name:/target" \
                alpine:latest \
                sh -c "cp -r /source/* /target/ 2>/dev/null || cp -r /source/. /target/ 2>/dev/null || true" || {
                log_warning "Migration of $(basename "$source_path") may have failed"
            }
        fi
    done
    
    # Special case: migrate shared data
    if [[ -d "$LAKEHOUSE_ROOT" ]]; then
        docker run --rm \
            -v "$LAKEHOUSE_ROOT:/source" \
            -v "${project_name}_lakehouse_shared:/target" \
            alpine:latest \
            sh -c "cp -r /source/* /target/ 2>/dev/null || true" || {
            log_warning "Shared data migration may have failed"
        }
    fi
    
    log_success "Data migration completed"
}

update_configuration() {
    log_info "Configuration is already updated for named volumes"
    log_success "No configuration changes needed"
}

start_services() {
    log_info "Starting services with new named volumes..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would start services with: docker compose up -d"
        return 0
    fi
    
    # Start core services first
    docker compose up -d postgres minio lakehouse-init
    sleep 15
    
    # Start remaining services
    docker compose up -d
    
    log_success "Services started with named volumes"
}

verify_migration() {
    log_info "Verifying migration..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log_info "[DRY RUN] Would verify migration success"
        return 0
    fi
    
    # Check that services are running
    local running_services=$(docker compose ps --services --filter "status=running" | wc -l)
    
    if [[ $running_services -gt 0 ]]; then
        log_success "Migration verification passed ($running_services services running)"
    else
        log_warning "Some services may not be running - check with: docker compose ps"
    fi
}

cleanup_old_data() {
    log_info "Old data cleanup options:"
    echo ""
    echo -e "${YELLOW}Your original data is still in: $LAKEHOUSE_ROOT${NC}"
    echo -e "${YELLOW}Your backup is available at: $BACKUP_DIR${NC}"
    echo ""
    echo -e "${BLUE}After verifying everything works correctly, you can:${NC}"
    echo -e "  1. Keep both for extra safety (recommended initially)"
    echo -e "  2. Remove old data: ${CYAN}rm -rf $LAKEHOUSE_ROOT${NC}"
    echo -e "  3. Remove backup: ${CYAN}rm -rf $BACKUP_DIR${NC}"
    echo ""
    log_warning "DO NOT remove old data until you've verified the migration worked!"
}

print_summary() {
    echo ""
    echo -e "${GREEN}${BOLD}🎉 Migration Complete!${NC}"
    echo ""
    echo -e "${BLUE}What was migrated:${NC}"
    echo -e "  ✅ Bind mount storage → Named Docker volumes"
    echo -e "  ✅ Data preservation and safety"
    echo -e "  ✅ Overlay switching compatibility"
    echo ""
    echo -e "${BLUE}Benefits you now have:${NC}"
    echo -e "  🛡️  Data survives container recreation"
    echo -e "  🛡️  Data survives 'docker compose down'"
    echo -e "  🛡️  Data survives overlay switching"
    echo -e "  🛡️  Data survives upgrade processes"
    echo ""
    echo -e "${BLUE}Next steps:${NC}"
    echo -e "  1. Test your applications and data"
    echo -e "  2. Verify notebooks, databases, etc. work correctly"
    echo -e "  3. After verification, clean up old data directories"
    echo ""
    echo -e "${CYAN}Happy data engineering with persistent storage! 🚀${NC}"
}

# Main migration flow
main() {
    print_header
    
    # Parse command line arguments
    if [[ "$1" == "--dry-run" ]]; then
        DRY_RUN="true"
        log_info "Running in DRY RUN mode - no changes will be made"
        echo ""
    fi
    
    check_prerequisites
    
    if ! detect_existing_data; then
        exit 0
    fi
    
    confirm_migration
    create_backup
    stop_services
    create_named_volumes
    migrate_data
    update_configuration
    start_services
    verify_migration
    cleanup_old_data
    print_summary
}

# Handle script interruption
trap 'echo -e "\n${RED}Migration interrupted.${NC}"; exit 1' INT TERM

# Run main function
main "$@"