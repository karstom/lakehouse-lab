#!/bin/bash

# =============================================================================
# Lakehouse Lab - Comprehensive Backup Script
# =============================================================================
# Creates backups of all persistent data from the Lakehouse Lab stack
# Can be run via CRON, Airflow, or manually
#
# Usage:
#   ./scripts/backup-lakehouse.sh [options]
#
# Options:
#   --output-dir PATH     Backup output directory (default: ./backups)
#   --retention-days N    Keep backups for N days (default: 30)
#   --compress            Compress backups with gzip
#   --verify              Verify backup integrity
#   --exclude SERVICE     Exclude specific service (postgres|minio|jupyter|airflow|spark|superset|all)
#   --dry-run            Show what would be backed up without doing it
#   --quiet              Reduce output verbosity
#   --parallel           Run backups in parallel where possible
#
# Examples:
#   ./scripts/backup-lakehouse.sh
#   ./scripts/backup-lakehouse.sh --output-dir /backup/lakehouse --retention-days 7 --compress
#   ./scripts/backup-lakehouse.sh --exclude minio --verify
#   ./scripts/backup-lakehouse.sh --dry-run
# =============================================================================

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default configuration
BACKUP_DIR="./backups"
RETENTION_DAYS=30
COMPRESS=false
VERIFY=false
DRY_RUN=false
QUIET=false
PARALLEL=false
EXCLUDE_SERVICES=()
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="lakehouse-backup-${TIMESTAMP}"

# Logging functions
log_info() {
    if [[ $QUIET != true ]]; then
        echo -e "${BLUE}ℹ️  $1${NC}"
    fi
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

log_debug() {
    if [[ $QUIET != true ]]; then
        echo -e "${CYAN}🔍 $1${NC}"
    fi
}

# Print header
print_header() {
    echo ""
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo -e "${BLUE}${BOLD} 💾 Lakehouse Lab Backup System${NC}"
    echo -e "${BLUE}${BOLD}============================================${NC}"
    echo ""
    echo -e "${YELLOW}Backup ID: ${BACKUP_NAME}${NC}"
    echo -e "${YELLOW}Target Directory: ${BACKUP_DIR}/${BACKUP_NAME}${NC}"
    echo -e "${YELLOW}Retention: ${RETENTION_DAYS} days${NC}"
    echo ""
}

# Parse command line arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --output-dir)
                BACKUP_DIR="$2"
                shift 2
                ;;
            --retention-days)
                RETENTION_DAYS="$2"
                shift 2
                ;;
            --compress)
                COMPRESS=true
                shift
                ;;
            --verify)
                VERIFY=true
                shift
                ;;
            --exclude)
                EXCLUDE_SERVICES+=("$2")
                shift 2
                ;;
            --dry-run)
                DRY_RUN=true
                shift
                ;;
            --quiet)
                QUIET=true
                shift
                ;;
            --parallel)
                PARALLEL=true
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

# Show help
show_help() {
    echo "Lakehouse Lab Backup Script"
    echo ""
    echo "Usage: $0 [options]"
    echo ""
    echo "Options:"
    echo "  --output-dir PATH       Backup output directory (default: ./backups)"
    echo "  --retention-days N      Keep backups for N days (default: 30)"
    echo "  --compress              Compress backups with gzip"
    echo "  --verify               Verify backup integrity"
    echo "  --exclude SERVICE      Exclude service (postgres|minio|jupyter|airflow|spark|superset)"
    echo "  --dry-run              Show what would be backed up"
    echo "  --quiet                Reduce output verbosity"
    echo "  --parallel             Run backups in parallel"
    echo "  --help                 Show this help"
    echo ""
    echo "Examples:"
    echo "  $0"
    echo "  $0 --output-dir /backup/lakehouse --compress"
    echo "  $0 --exclude minio --retention-days 7"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check if we're in the right directory
    if [[ ! -f "docker-compose.yml" ]]; then
        log_error "Please run this script from your Lakehouse Lab directory"
        log_info "Make sure docker-compose.yml file exists"
        exit 1
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
    
    # Check if services are running
    local running_services=$(docker compose ps --services --filter "status=running" | wc -l)
    if [[ $running_services -eq 0 ]]; then
        log_warning "No running services detected. Some backups may be incomplete."
    else
        log_debug "$running_services services are currently running"
    fi
    
    # Create backup directory
    if [[ $DRY_RUN != true ]]; then
        mkdir -p "$BACKUP_DIR/$BACKUP_NAME"
    fi
    
    log_success "Prerequisites check passed"
}

# Check if service is excluded
is_service_excluded() {
    local service="$1"
    for excluded in "${EXCLUDE_SERVICES[@]}"; do
        if [[ "$excluded" == "$service" ]] || [[ "$excluded" == "all" ]]; then
            return 0
        fi
    done
    return 1
}

# Get project name for volume naming
get_project_name() {
    basename "$(pwd)" | tr '[:upper:]' '[:lower:]'
}

# Backup PostgreSQL databases
backup_postgresql() {
    if is_service_excluded "postgres"; then
        log_info "Skipping PostgreSQL backup (excluded)"
        return 0
    fi
    
    log_info "🗄️  Backing up PostgreSQL databases..."
    
    local backup_file="$BACKUP_DIR/$BACKUP_NAME/postgresql_backup.sql"
    
    if [[ $DRY_RUN == true ]]; then
        log_debug "[DRY RUN] Would backup PostgreSQL to: $backup_file"
        return 0
    fi
    
    # Check if PostgreSQL is running
    if ! docker compose ps postgres | grep -q "running\|Up"; then
        log_warning "PostgreSQL container is not running, backing up volume data instead"
        backup_volume_data "postgres_data" "postgresql"
        return 0
    fi
    
    # Get database credentials from environment
    local postgres_auth=""
    if [[ -f ".env" ]]; then
        postgres_auth=$(grep "^POSTGRES_PASSWORD=" .env | cut -d'=' -f2- | tr -d '"' || echo "")
    fi
    
    if [[ -z "$postgres_auth" ]]; then
        log_error "Could not find POSTGRES_PASSWORD in .env file"
        return 1
    fi
    
    # Create database dump
    if docker compose exec -T postgres pg_dumpall -U postgres > "$backup_file" 2>/dev/null; then
        local backup_size=$(du -h "$backup_file" | cut -f1)
        log_success "PostgreSQL backup completed ($backup_size)"
        
        if [[ $COMPRESS == true ]]; then
            gzip "$backup_file"
            log_success "PostgreSQL backup compressed"
        fi
        
        if [[ $VERIFY == true ]]; then
            verify_postgresql_backup "$backup_file"
        fi
    else
        log_error "PostgreSQL backup failed"
        return 1
    fi
}

# Backup MinIO object storage
backup_minio() {
    if is_service_excluded "minio"; then
        log_info "Skipping MinIO backup (excluded)"
        return 0
    fi
    
    log_info "🪣 Backing up MinIO object storage..."
    
    local backup_dir="$BACKUP_DIR/$BACKUP_NAME/minio"
    
    if [[ $DRY_RUN == true ]]; then
        log_debug "[DRY RUN] Would backup MinIO to: $backup_dir"
        return 0
    fi
    
    mkdir -p "$backup_dir"
    
    # Check if MinIO is running
    if ! docker compose ps minio | grep -q "running\|Up"; then
        log_warning "MinIO container is not running, backing up volume data instead"
        backup_volume_data "minio_data" "minio"
        return 0
    fi
    
    # Get MinIO credentials
    local minio_user=""
    local minio_auth=""
    if [[ -f ".env" ]]; then
        minio_user=$(grep "^MINIO_ROOT_USER=" .env | cut -d'=' -f2- | tr -d '"'"'" || echo "admin")
        minio_auth=$(grep "^MINIO_ROOT_PASSWORD=" .env | cut -d'=' -f2- | tr -d '"' || echo "")
    fi
    
    if [[ -z "$minio_auth" ]]; then
        log_error "Could not find MINIO_ROOT_PASSWORD in .env file"
        return 1
    fi
    
    # Use mc (MinIO Client) to backup buckets
    docker run --rm \
        --network "$(get_project_name)_lakehouse" \
        -v "$backup_dir:/backup" \
        minio/mc:latest \
        bash -c "
            # Configure mc client
            mc alias set lakehouse http://minio:9000 '$minio_user' '$minio_auth' || exit 1
            
            # List and backup all buckets
            buckets=\$(mc ls lakehouse | awk '{print \$5}' | grep -v '^$' || true)
            
            if [[ -z \"\$buckets\" ]]; then
                echo 'No buckets found to backup'
                exit 0
            fi
            
            for bucket in \$buckets; do
                echo \"Backing up bucket: \$bucket\"
                mc cp --recursive lakehouse/\$bucket /backup/\$bucket/ || echo \"Failed to backup bucket: \$bucket\"
            done
            
            # Backup server configuration and policies
            mc admin config export lakehouse > /backup/minio-config.json 2>/dev/null || echo 'Could not export MinIO config'
            mc admin user list lakehouse > /backup/minio-users.txt 2>/dev/null || echo 'Could not export MinIO users'
            mc admin policy list lakehouse > /backup/minio-policies.txt 2>/dev/null || echo 'Could not export MinIO policies'
        " || {
        log_warning "MinIO backup may have failed, trying volume backup instead"
        backup_volume_data "minio_data" "minio"
        return 0
    }
    
    local backup_size=$(du -sh "$backup_dir" | cut -f1)
    log_success "MinIO backup completed ($backup_size)"
    
    if [[ $COMPRESS == true ]]; then
        tar -czf "$BACKUP_DIR/$BACKUP_NAME/minio.tar.gz" -C "$BACKUP_DIR/$BACKUP_NAME" minio
        rm -rf "$backup_dir"
        log_success "MinIO backup compressed"
    fi
}

# Backup Jupyter notebooks and configuration
backup_jupyter() {
    if is_service_excluded "jupyter"; then
        log_info "Skipping Jupyter backup (excluded)"
        return 0
    fi
    
    log_info "📓 Backing up Jupyter notebooks and configuration..."
    
    # Backup notebooks volume
    backup_volume_data "jupyter_notebooks" "jupyter/notebooks"
    
    # Backup jupyter configuration
    backup_volume_data "jupyter_config" "jupyter/config"
    
    log_success "Jupyter backup completed"
}

# Backup Airflow DAGs, logs, and plugins
backup_airflow() {
    if is_service_excluded "airflow"; then
        log_info "Skipping Airflow backup (excluded)"
        return 0
    fi
    
    log_info "🌊 Backing up Airflow DAGs, logs, and plugins..."
    
    # Backup DAGs
    backup_volume_data "airflow_dags" "airflow/dags"
    
    # Backup logs (but limit to recent logs to save space)
    backup_volume_data "airflow_logs" "airflow/logs"
    
    # Backup plugins
    backup_volume_data "airflow_plugins" "airflow/plugins"
    
    log_success "Airflow backup completed"
}

# Backup Spark jobs and logs
backup_spark() {
    if is_service_excluded "spark"; then
        log_info "Skipping Spark backup (excluded)"
        return 0
    fi
    
    log_info "⚡ Backing up Spark jobs and logs..."
    
    # Backup Spark jobs
    backup_volume_data "spark_jobs" "spark/jobs"
    
    # Backup Spark logs (recent only)
    backup_volume_data "spark_logs" "spark/logs"
    
    log_success "Spark backup completed"
}

# Backup Superset dashboards and configuration
backup_superset() {
    if is_service_excluded "superset"; then
        log_info "Skipping Superset backup (excluded)"
        return 0
    fi
    
    log_info "📈 Backing up Superset dashboards and configuration..."
    
    backup_volume_data "superset_data" "superset"
    
    log_success "Superset backup completed"
}

# Backup other services (Vizro, LanceDB, etc.)
backup_other_services() {
    log_info "🔧 Backing up other service data..."
    
    
    # Vizro dashboards
    backup_volume_data "vizro_data" "vizro"
    
    # LanceDB vector data
    backup_volume_data "lancedb_data" "lancedb"
    
    # Portainer configuration
    backup_volume_data "portainer_data" "portainer"
    
    # Shared lakehouse data
    backup_volume_data "lakehouse_shared" "shared"
    
    log_success "Other services backup completed"
}

# Generic volume data backup function
backup_volume_data() {
    local volume_name="$1"
    local backup_subdir="$2"
    local project_name=$(get_project_name)
    local full_volume_name="${project_name}_${volume_name}"
    local backup_path="$BACKUP_DIR/$BACKUP_NAME/$backup_subdir"
    
    if [[ $DRY_RUN == true ]]; then
        log_debug "[DRY RUN] Would backup volume $full_volume_name to: $backup_path"
        return 0
    fi
    
    mkdir -p "$backup_path"
    
    # Check if volume exists
    if ! docker volume inspect "$full_volume_name" >/dev/null 2>&1; then
        log_debug "Volume $full_volume_name not found, skipping"
        return 0
    fi
    
    # Backup volume data using rsync
    docker run --rm \
        -v "$full_volume_name:/source" \
        -v "$backup_path:/backup" \
        alpine:latest \
        sh -c "
            # Install rsync for reliable backup
            apk add --no-cache rsync >/dev/null 2>&1 || {
                # Fallback to cp if rsync unavailable
                cp -r /source/. /backup/ 2>/dev/null || cp -r /source/* /backup/ 2>/dev/null || true
                exit 0
            }
            
            # Use rsync for backup
            rsync -av /source/ /backup/ 2>/dev/null || {
                # Fallback to cp
                cp -r /source/. /backup/ 2>/dev/null || cp -r /source/* /backup/ 2>/dev/null || true
            }
        " || {
        log_warning "Backup of volume $volume_name may have failed"
        return 1
    }
    
    local backup_size=$(du -sh "$backup_path" 2>/dev/null | cut -f1 || echo "unknown")
    log_debug "Volume $volume_name backed up ($backup_size)"
}

# Verify PostgreSQL backup
verify_postgresql_backup() {
    local backup_file="$1"
    
    if [[ $COMPRESS == true ]]; then
        backup_file="${backup_file}.gz"
    fi
    
    log_debug "Verifying PostgreSQL backup..."
    
    if [[ $COMPRESS == true ]]; then
        # Check if compressed file is valid
        if gzip -t "$backup_file" 2>/dev/null; then
            log_success "PostgreSQL backup verification passed"
        else
            log_error "PostgreSQL backup verification failed"
            return 1
        fi
    else
        # Check if SQL file contains expected content
        if grep -q "PostgreSQL database dump" "$backup_file" 2>/dev/null; then
            log_success "PostgreSQL backup verification passed"
        else
            log_warning "PostgreSQL backup verification inconclusive"
        fi
    fi
}

# Create backup metadata
create_backup_metadata() {
    if [[ $DRY_RUN == true ]]; then
        log_debug "[DRY RUN] Would create backup metadata"
        return 0
    fi
    
    local metadata_file="$BACKUP_DIR/$BACKUP_NAME/backup-metadata.json"
    
    cat > "$metadata_file" << EOF
{
    "backup_id": "$BACKUP_NAME",
    "timestamp": "$TIMESTAMP",
    "date": "$(date -Iseconds)",
    "lakehouse_version": "$(git describe --tags 2>/dev/null || git rev-parse --short HEAD 2>/dev/null || echo 'unknown')",
    "docker_compose_version": "$(docker compose version --short 2>/dev/null || echo 'unknown')",
    "backup_options": {
        "compress": $COMPRESS,
        "verify": $VERIFY,
        "parallel": $PARALLEL,
        "excluded_services": $(printf '%s\n' "${EXCLUDE_SERVICES[@]}" | jq -R . | jq -s . 2>/dev/null || echo '[]')
    },
    "services_status": $(docker compose ps --format json 2>/dev/null | jq -s . 2>/dev/null || echo '[]'),
    "volume_list": $(docker volume ls --filter "name=$(get_project_name)_" --format "{{.Name}}" | jq -R . | jq -s . 2>/dev/null || echo '[]')
}
EOF
    
    log_success "Backup metadata created"
}

# Clean old backups based on retention policy
cleanup_old_backups() {
    if [[ $DRY_RUN == true ]]; then
        log_debug "[DRY RUN] Would clean up backups older than $RETENTION_DAYS days"
        return 0
    fi
    
    log_info "🧹 Cleaning up backups older than $RETENTION_DAYS days..."
    
    local deleted_count=0
    
    # Find and remove old backup directories
    find "$BACKUP_DIR" -maxdepth 1 -type d -name "lakehouse-backup-*" -mtime +$RETENTION_DAYS 2>/dev/null | while read -r old_backup; do
        if [[ -n "$old_backup" ]]; then
            log_debug "Removing old backup: $(basename "$old_backup")"
            rm -rf "$old_backup"
            deleted_count=$((deleted_count + 1))
        fi
    done
    
    if [[ $deleted_count -gt 0 ]]; then
        log_success "Cleaned up $deleted_count old backups"
    else
        log_debug "No old backups to clean up"
    fi
}

# Generate backup summary
generate_backup_summary() {
    local backup_path="$BACKUP_DIR/$BACKUP_NAME"
    
    if [[ $DRY_RUN == true ]]; then
        log_info "📊 Backup Summary (DRY RUN)"
        echo -e "  • Would create backup at: ${CYAN}$backup_path${NC}"
        echo -e "  • Retention policy: ${YELLOW}$RETENTION_DAYS days${NC}"
        echo -e "  • Compression: ${YELLOW}$([ $COMPRESS == true ] && echo "enabled" || echo "disabled")${NC}"
        echo -e "  • Verification: ${YELLOW}$([ $VERIFY == true ] && echo "enabled" || echo "disabled")${NC}"
        if [[ ${#EXCLUDE_SERVICES[@]} -gt 0 ]]; then
            echo -e "  • Excluded services: ${YELLOW}$(IFS=,; echo "${EXCLUDE_SERVICES[*]}")${NC}"
        fi
        return 0
    fi
    
    local total_size=$(du -sh "$backup_path" 2>/dev/null | cut -f1 || echo "unknown")
    local file_count=$(find "$backup_path" -type f | wc -l)
    local end_time=$(date -Iseconds)
    
    log_info "📊 Backup Summary"
    echo -e "  • Backup ID: ${CYAN}$BACKUP_NAME${NC}"
    echo -e "  • Location: ${CYAN}$backup_path${NC}"
    echo -e "  • Total size: ${YELLOW}$total_size${NC}"
    echo -e "  • Files backed up: ${YELLOW}$file_count${NC}"
    echo -e "  • Completed: ${GREEN}$end_time${NC}"
    echo -e "  • Retention: ${YELLOW}$RETENTION_DAYS days${NC}"
    
    if [[ ${#EXCLUDE_SERVICES[@]} -gt 0 ]]; then
        echo -e "  • Excluded: ${YELLOW}$(IFS=,; echo "${EXCLUDE_SERVICES[*]}")${NC}"
    fi
    
    echo ""
    log_success "Backup completed successfully!"
    echo -e "${BLUE}💡 To restore this backup, use: ${CYAN}./scripts/restore-lakehouse.sh $BACKUP_NAME${NC}"
}

# Run parallel backup jobs
run_parallel_backups() {
    log_info "🔄 Running backup jobs in parallel..."
    
    # Define backup jobs
    local -a backup_jobs=(
        "backup_postgresql"
        "backup_jupyter" 
        "backup_airflow"
        "backup_spark"
        "backup_superset"
        "backup_other_services"
    )
    
    # MinIO needs to run separately due to network requirements
    backup_minio
    
    # Run other backups in parallel
    for job in "${backup_jobs[@]}"; do
        $job &
    done
    
    # Wait for all background jobs
    wait
    
    log_success "Parallel backup jobs completed"
}

# Run sequential backup jobs
run_sequential_backups() {
    log_info "🔄 Running backup jobs sequentially..."
    
    backup_postgresql
    backup_minio
    backup_jupyter
    backup_airflow
    backup_spark
    backup_superset
    backup_other_services
    
    log_success "Sequential backup jobs completed"
}

# Main backup function
main() {
    parse_args "$@"
    print_header
    check_prerequisites
    
    local start_time=$(date -Iseconds)
    
    # Run backups
    if [[ $PARALLEL == true ]]; then
        run_parallel_backups
    else
        run_sequential_backups
    fi
    
    # Post-backup tasks
    create_backup_metadata
    cleanup_old_backups
    generate_backup_summary
    
    # Final message
    echo ""
    log_success "🎉 Lakehouse Lab backup completed!"
    echo -e "${BLUE}Started: ${start_time}${NC}"
    echo -e "${BLUE}Finished: $(date -Iseconds)${NC}"
}

# Handle script interruption
trap 'echo -e "\n${RED}Backup interrupted.${NC}"; exit 1' INT TERM

# Run main function
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi