#!/bin/bash

# =============================================================================
# Lakehouse Lab - Backup Restore Script
# =============================================================================
# Restores backups created by backup-lakehouse.sh
#
# Usage:
#   ./scripts/restore-lakehouse.sh BACKUP_ID [options]
#
# Options:
#   --backup-dir PATH     Backup directory (default: ./backups)
#   --service SERVICE     Restore only specific service (postgres|minio|jupyter|airflow|spark|superset)
#   --dry-run            Show what would be restored
#   --force              Skip confirmation prompts
#   --stop-services      Stop services before restore
#
# Examples:
#   ./scripts/restore-lakehouse.sh lakehouse-backup-20240304_143052
#   ./scripts/restore-lakehouse.sh lakehouse-backup-20240304_143052 --service postgres
#   ./scripts/restore-lakehouse.sh lakehouse-backup-20240304_143052 --dry-run
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

# Default configuration
BACKUP_DIR="./backups"
BACKUP_ID=""
RESTORE_SERVICE=""
DRY_RUN=false
FORCE=false
STOP_SERVICES=false

# Logging functions
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

# Parse arguments
parse_args() {
    if [[ $# -eq 0 ]]; then
        echo "Error: Backup ID is required"
        show_help
        exit 1
    fi
    
    BACKUP_ID="$1"
    shift
    
    while [[ $# -gt 0 ]]; do
        case $1 in
            --backup-dir)
                BACKUP_DIR="$2"
                shift 2
                ;;
            --service)
                RESTORE_SERVICE="$2"
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --force)
                FORCE=true
                shift
                ;;
            --stop-services)
                STOP_SERVICES=true
                shift
                ;;
            --help|-h)
                show_help
                exit 0
                ;;
            *)
                echo "Unknown option: $1"
                show_help
                exit 1
                ;;
        esac
    done
}

show_help() {
    echo "Lakehouse Lab Restore Script"
    echo ""
    echo "Usage: $0 BACKUP_ID [options]"
    echo ""
    echo "Options:"
    echo "  --backup-dir PATH     Backup directory (default: ./backups)"
    echo "  --service SERVICE     Restore specific service only"
    echo "  --dry-run            Show what would be restored"
    echo "  --force              Skip confirmation prompts"
    echo "  --stop-services      Stop services before restore"
    echo "  --help               Show this help"
    echo ""
    echo "Available services: postgres, minio, jupyter, airflow, spark, superset"
}

# Check prerequisites and backup
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    local backup_path="$BACKUP_DIR/$BACKUP_ID"
    
    if [[ ! -d "$backup_path" ]]; then
        log_error "Backup not found: $backup_path"
        log_info "Available backups:"
        find "$BACKUP_DIR" -maxdepth 1 -type d -name "lakehouse-backup-*" 2>/dev/null | sort | while read -r backup; do
            echo "  $(basename "$backup")"
        done || echo "  No backups found"
        exit 1
    fi
    
    if [[ ! -f "$backup_path/backup-metadata.json" ]]; then
        log_warning "Backup metadata not found - this may be an old or incomplete backup"
    fi
    
    # Check if we're in the right directory
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "Please run this script from your Lakehouse Lab directory"
        exit 1
    fi
    
    log_success "Prerequisites check passed"
}

# Get project name
get_project_name() {
    basename "$(pwd)" | tr '[:upper:]' '[:lower:]'
}

# Confirm restore operation
confirm_restore() {
    if [[ $FORCE == true ]] || [[ $DRY_RUN == true ]]; then
        return 0
    fi
    
    echo ""
    log_warning "⚠️  RESTORE OPERATION WARNING ⚠️"
    echo ""
    echo -e "${RED}This will overwrite existing data!${NC}"
    echo -e "Backup: ${CYAN}$BACKUP_ID${NC}"
    if [[ -n "$RESTORE_SERVICE" ]]; then
        echo -e "Service: ${YELLOW}$RESTORE_SERVICE only${NC}"
    else
        echo -e "Services: ${YELLOW}All services${NC}"
    fi
    echo ""
    echo -e "${RED}Current data will be replaced with backup data.${NC}"
    echo -e "${RED}This operation cannot be undone.${NC}"
    echo ""
    read -p "Type 'RESTORE' to confirm: " -r
    if [[ $REPLY != "RESTORE" ]]; then
        log_info "Restore operation cancelled"
        exit 0
    fi
    echo ""
}

# Stop services if requested
stop_services_if_requested() {
    if [[ $STOP_SERVICES == true ]] && [[ $DRY_RUN != true ]]; then
        log_info "Stopping services before restore..."
        docker compose stop || log_warning "Some services may not have stopped cleanly"
        sleep 5
        log_success "Services stopped"
    fi
}

# Restore PostgreSQL
restore_postgresql() {
    local backup_path="$BACKUP_DIR/$BACKUP_ID"
    local sql_file="$backup_path/postgresql_backup.sql"
    local compressed_file="$sql_file.gz"
    
    log_info "🗄️  Restoring PostgreSQL databases..."
    
    # Check which backup file exists
    if [[ -f "$compressed_file" ]]; then
        sql_file="$compressed_file"
    elif [[ ! -f "$sql_file" ]]; then
        log_warning "No PostgreSQL backup found, trying volume restore..."
        restore_volume_data "postgres_data" "$backup_path/postgresql"
        return $?
    fi
    
    if [[ $DRY_RUN == true ]]; then
        log_info "[DRY RUN] Would restore PostgreSQL from: $sql_file"
        return 0
    fi
    
    # Ensure PostgreSQL is running
    docker compose up -d postgres
    sleep 10
    
    # Restore database
    if [[ "$sql_file" == *.gz ]]; then
        if gunzip -c "$sql_file" | docker compose exec -T postgres psql -U postgres; then
            log_success "PostgreSQL restore completed"
        else
            log_error "PostgreSQL restore failed"
            return 1
        fi
    else
        if docker compose exec -T postgres psql -U postgres < "$sql_file"; then
            log_success "PostgreSQL restore completed"
        else
            log_error "PostgreSQL restore failed"
            return 1
        fi
    fi
}

# Restore MinIO
restore_minio() {
    local backup_path="$BACKUP_DIR/$BACKUP_ID"
    local minio_backup="$backup_path/minio"
    local minio_archive="$backup_path/minio.tar.gz"
    
    log_info "🪣 Restoring MinIO object storage..."
    
    # Check backup format
    if [[ -f "$minio_archive" ]]; then
        if [[ $DRY_RUN != true ]]; then
            log_info "Extracting MinIO backup archive..."
            tar -xzf "$minio_archive" -C "$backup_path/"
        fi
        minio_backup="$backup_path/minio"
    fi
    
    if [[ ! -d "$minio_backup" ]]; then
        log_warning "No MinIO backup found, trying volume restore..."
        restore_volume_data "minio_data" "$backup_path/minio"
        return $?
    fi
    
    if [[ $DRY_RUN == true ]]; then
        log_info "[DRY RUN] Would restore MinIO from: $minio_backup"
        return 0
    fi
    
    # Ensure MinIO is running
    docker compose up -d minio
    sleep 15
    
    # Get MinIO credentials
    local minio_user=""
    local minio_auth=""
    if [[ -f ".env" ]]; then
        minio_user=$(grep "^MINIO_ROOT_USER=" .env | cut -d'=' -f2- | tr -d '"' || echo "admin")
        local minio_env_var="MINIO_ROOT_PASSWORD="
        minio_auth=$(grep "^${minio_env_var}" .env | cut -d'=' -f2- | tr -d '"' || echo "")
    fi
    
    # Restore MinIO data
    docker run --rm \
        --network "$(get_project_name)_lakehouse" \
        -v "$minio_backup:/restore" \
        minio/mc:latest \
        bash -c "
            # Configure mc client
            mc alias set lakehouse http://minio:9000 '$minio_user' '$minio_auth' || exit 1
            
            # Restore buckets
            for bucket_dir in /restore/*/; do
                if [[ -d \"\$bucket_dir\" ]]; then
                    bucket=\$(basename \"\$bucket_dir\")
                    echo \"Restoring bucket: \$bucket\"
                    
                    # Create bucket if it doesn't exist
                    mc mb lakehouse/\$bucket 2>/dev/null || true
                    
                    # Restore bucket contents
                    mc cp --recursive \"\$bucket_dir\" lakehouse/\$bucket/ || echo \"Failed to restore bucket: \$bucket\"
                fi
            done
            
            echo 'MinIO data restore completed'
        " || {
        log_warning "MinIO restore may have failed, trying volume restore..."
        restore_volume_data "minio_data" "$backup_path/minio"
        return $?
    }
    
    log_success "MinIO restore completed"
}

# Restore generic volume data
restore_volume_data() {
    local volume_name="$1"
    local backup_source="$2"
    local project_name=$(get_project_name)
    local full_volume_name="${project_name}_${volume_name}"
    
    if [[ ! -d "$backup_source" ]]; then
        log_warning "Backup source not found: $backup_source"
        return 1
    fi
    
    if [[ $DRY_RUN == true ]]; then
        log_info "[DRY RUN] Would restore volume $full_volume_name from: $backup_source"
        return 0
    fi
    
    log_info "Restoring volume: $volume_name"
    
    # Restore volume data using rsync
    docker run --rm \
        -v "$full_volume_name:/target" \
        -v "$backup_source:/source" \
        alpine:latest \
        sh -c "
            # Install rsync for reliable restore
            apk add --no-cache rsync >/dev/null 2>&1 || {
                # Fallback to cp
                rm -rf /target/* /target/.[^.]* 2>/dev/null || true
                cp -r /source/. /target/ 2>/dev/null || cp -r /source/* /target/ 2>/dev/null || true
                exit 0
            }
            
            # Clear target and restore with rsync
            rm -rf /target/* /target/.[^.]* 2>/dev/null || true
            rsync -av /source/ /target/ || {
                # Fallback to cp
                cp -r /source/. /target/ 2>/dev/null || cp -r /source/* /target/ 2>/dev/null || true
            }
        " || {
        log_error "Failed to restore volume: $volume_name"
        return 1
    }
    
    log_success "Volume $volume_name restored"
}

# Restore specific service
restore_service() {
    local service="$1"
    
    case "$service" in
        postgres|postgresql)
            restore_postgresql
            ;;
        minio)
            restore_minio
            ;;
        jupyter)
            restore_volume_data "jupyter_notebooks" "$BACKUP_DIR/$BACKUP_ID/jupyter/notebooks"
            restore_volume_data "jupyter_config" "$BACKUP_DIR/$BACKUP_ID/jupyter/config"
            ;;
        airflow)
            restore_volume_data "airflow_dags" "$BACKUP_DIR/$BACKUP_ID/airflow/dags"
            restore_volume_data "airflow_logs" "$BACKUP_DIR/$BACKUP_ID/airflow/logs"
            restore_volume_data "airflow_plugins" "$BACKUP_DIR/$BACKUP_ID/airflow/plugins"
            ;;
        spark)
            restore_volume_data "spark_jobs" "$BACKUP_DIR/$BACKUP_ID/spark/jobs"
            restore_volume_data "spark_logs" "$BACKUP_DIR/$BACKUP_ID/spark/logs"
            ;;
        superset)
            restore_volume_data "superset_data" "$BACKUP_DIR/$BACKUP_ID/superset"
            ;;
        *)
            log_error "Unknown service: $service"
            log_info "Available services: postgres, minio, jupyter, airflow, spark, superset"
            exit 1
            ;;
    esac
}

# Restore all services
restore_all_services() {
    log_info "🔄 Restoring all services..."
    
    restore_postgresql
    restore_minio
    
    # Restore other volume-based services
    restore_volume_data "jupyter_notebooks" "$BACKUP_DIR/$BACKUP_ID/jupyter/notebooks"
    restore_volume_data "jupyter_config" "$BACKUP_DIR/$BACKUP_ID/jupyter/config"
    restore_volume_data "airflow_dags" "$BACKUP_DIR/$BACKUP_ID/airflow/dags"
    restore_volume_data "airflow_logs" "$BACKUP_DIR/$BACKUP_ID/airflow/logs"
    restore_volume_data "airflow_plugins" "$BACKUP_DIR/$BACKUP_ID/airflow/plugins"
    restore_volume_data "spark_jobs" "$BACKUP_DIR/$BACKUP_ID/spark/jobs"
    restore_volume_data "spark_logs" "$BACKUP_DIR/$BACKUP_ID/spark/logs"
    restore_volume_data "superset_data" "$BACKUP_DIR/$BACKUP_ID/superset"
    restore_volume_data "homer_data" "$BACKUP_DIR/$BACKUP_ID/homer"
    restore_volume_data "vizro_data" "$BACKUP_DIR/$BACKUP_ID/vizro"
    restore_volume_data "lancedb_data" "$BACKUP_DIR/$BACKUP_ID/lancedb"
    restore_volume_data "portainer_data" "$BACKUP_DIR/$BACKUP_ID/portainer"
    restore_volume_data "lakehouse_shared" "$BACKUP_DIR/$BACKUP_ID/shared"
    
    log_success "All services restored"
}

# Restart services after restore
restart_services() {
    if [[ $DRY_RUN == true ]]; then
        log_info "[DRY RUN] Would restart services"
        return 0
    fi
    
    log_info "🔄 Restarting services to apply restored data..."
    
    # Start core services first
    docker compose up -d postgres minio lakehouse-init
    sleep 15
    
    # Start remaining services
    docker compose up -d
    
    log_success "Services restarted"
}

# Show restore summary
show_restore_summary() {
    echo ""
    log_success "🎉 Restore completed!"
    echo -e "  • Backup: ${CYAN}$BACKUP_ID${NC}"
    if [[ -n "$RESTORE_SERVICE" ]]; then
        echo -e "  • Service: ${YELLOW}$RESTORE_SERVICE${NC}"
    else
        echo -e "  • Services: ${YELLOW}All services${NC}"
    fi
    echo -e "  • Completed: ${GREEN}$(date -Iseconds)${NC}"
    echo ""
    log_info "💡 Check service status with: docker compose ps"
    log_info "💡 View service logs with: docker compose logs [service]"
}

# Main restore function
main() {
    parse_args "$@"
    
    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD} 🔄 Lakehouse Lab Restore System${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    
    check_prerequisites
    confirm_restore
    stop_services_if_requested
    
    local start_time=$(date -Iseconds)
    
    if [[ -n "$RESTORE_SERVICE" ]]; then
        restore_service "$RESTORE_SERVICE"
    else
        restore_all_services
    fi
    
    restart_services
    show_restore_summary
    
    echo -e "${BLUE}Started: ${start_time}${NC}"
    echo -e "${BLUE}Finished: $(date -Iseconds)${NC}"
}

# Handle script interruption
trap 'echo -e "\n${RED}Restore interrupted.${NC}"; exit 1' INT TERM

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi