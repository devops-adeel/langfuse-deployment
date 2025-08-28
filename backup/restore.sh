#!/bin/bash
# Langfuse Restore Script
# Restores Langfuse data from backup archives created by offen/docker-volume-backup

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${BACKUP_DIR:-${HOME}/LangfuseBackups}"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-langfuse-prod}"
TEMP_RESTORE_DIR="/tmp/langfuse-restore-$$"

# Logging functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_prompt() {
    echo -e "${BLUE}[?]${NC} $1"
}

# Cleanup function
cleanup() {
    if [ -d "$TEMP_RESTORE_DIR" ]; then
        log_info "Cleaning up temporary files..."
        rm -rf "$TEMP_RESTORE_DIR"
    fi
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# List available backups
list_backups() {
    log_info "Available backups in $BACKUP_DIR:"
    echo "======================================"

    if [ ! -d "$BACKUP_DIR" ]; then
        log_error "Backup directory does not exist: $BACKUP_DIR"
        exit 1
    fi

    local backups=($(find "$BACKUP_DIR" -name "langfuse-*.tar.gz" -type f | sort -r))

    if [ ${#backups[@]} -eq 0 ]; then
        log_error "No backups found in $BACKUP_DIR"
        exit 1
    fi

    for i in "${!backups[@]}"; do
        local backup_file=$(basename "${backups[$i]}")
        local backup_size=$(du -h "${backups[$i]}" | cut -f1)
        local backup_date=$(stat -f "%Sm" -t "%Y-%m-%d %H:%M:%S" "${backups[$i]}" 2>/dev/null || \
                          stat -c "%y" "${backups[$i]}" 2>/dev/null | cut -d' ' -f1-2)

        printf "%2d) %-40s %8s  %s\n" $((i+1)) "$backup_file" "$backup_size" "$backup_date"
    done

    echo "======================================"

    # Check for latest symlink
    if [ -L "$BACKUP_DIR/langfuse-latest.tar.gz" ]; then
        local latest=$(readlink "$BACKUP_DIR/langfuse-latest.tar.gz")
        log_info "Latest backup symlink points to: $(basename "$latest")"
    fi
}

# Select backup to restore
select_backup() {
    local backups=($(find "$BACKUP_DIR" -name "langfuse-*.tar.gz" -type f | sort -r))

    log_prompt "Enter backup number to restore (1-${#backups[@]}), or 'latest' for most recent:"
    read -r selection

    if [ "$selection" == "latest" ]; then
        if [ -L "$BACKUP_DIR/langfuse-latest.tar.gz" ]; then
            RESTORE_FILE="$BACKUP_DIR/langfuse-latest.tar.gz"
        else
            RESTORE_FILE="${backups[0]}"
        fi
    elif [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le ${#backups[@]} ]; then
        RESTORE_FILE="${backups[$((selection-1))]}"
    else
        log_error "Invalid selection"
        exit 1
    fi

    log_info "Selected: $(basename "$RESTORE_FILE")"
}

# Confirm restore operation
confirm_restore() {
    log_warn "WARNING: This will restore the following:"
    echo "  - PostgreSQL database"
    echo "  - ClickHouse analytics data"
    echo "  - MinIO object storage"
    echo "  - All data will be REPLACED with backup contents"
    echo ""
    log_prompt "Type 'yes' to confirm restore operation:"
    read -r confirmation

    if [ "$confirmation" != "yes" ]; then
        log_info "Restore cancelled."
        exit 0
    fi
}

# Stop services
stop_services() {
    log_info "Stopping Langfuse services..."

    cd "$PROJECT_ROOT/compose"

    # Stop all services except backup service
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.orbstack.yml \
        -p "$COMPOSE_PROJECT_NAME" \
        stop langfuse-web langfuse-worker postgres clickhouse minio redis

    log_info "Services stopped."
}

# Extract backup archive
extract_backup() {
    log_info "Extracting backup archive..."

    mkdir -p "$TEMP_RESTORE_DIR"

    if ! tar -xzf "$RESTORE_FILE" -C "$TEMP_RESTORE_DIR"; then
        log_error "Failed to extract backup archive"
        exit 1
    fi

    log_info "Backup extracted to temporary directory."
}

# Restore volume data
restore_volume() {
    local volume_name="$1"
    local backup_path="$2"

    log_info "Restoring volume: $volume_name"

    # Create temporary container to restore data
    docker run --rm \
        -v "${COMPOSE_PROJECT_NAME}_${volume_name}:/restore" \
        -v "${backup_path}:/backup:ro" \
        alpine sh -c "rm -rf /restore/* && cp -a /backup/. /restore/"

    if [ $? -eq 0 ]; then
        log_info "Volume $volume_name restored successfully."
    else
        log_error "Failed to restore volume $volume_name"
        return 1
    fi
}

# Restore all volumes
restore_all_volumes() {
    log_info "Starting volume restoration..."

    # Check what's in the backup
    if [ -d "$TEMP_RESTORE_DIR/backup" ]; then
        BACKUP_BASE="$TEMP_RESTORE_DIR/backup"
    else
        BACKUP_BASE="$TEMP_RESTORE_DIR"
    fi

    # Restore PostgreSQL
    if [ -d "$BACKUP_BASE/postgres" ]; then
        restore_volume "langfuse_postgres_data" "$BACKUP_BASE/postgres"
    else
        log_warn "PostgreSQL backup not found in archive"
    fi

    # Restore ClickHouse data
    if [ -d "$BACKUP_BASE/clickhouse" ]; then
        restore_volume "langfuse_clickhouse_data" "$BACKUP_BASE/clickhouse"
    else
        log_warn "ClickHouse data backup not found in archive"
    fi

    # Restore ClickHouse logs
    if [ -d "$BACKUP_BASE/clickhouse-logs" ]; then
        restore_volume "langfuse_clickhouse_logs" "$BACKUP_BASE/clickhouse-logs"
    else
        log_warn "ClickHouse logs backup not found in archive"
    fi

    # Restore MinIO
    if [ -d "$BACKUP_BASE/minio" ]; then
        restore_volume "langfuse_minio_data" "$BACKUP_BASE/minio"
    else
        log_warn "MinIO backup not found in archive"
    fi
}

# Start services
start_services() {
    log_info "Starting Langfuse services..."

    cd "$PROJECT_ROOT"

    # Use the deploy script to start services properly with secrets
    if [ -x "$PROJECT_ROOT/scripts/deploy.sh" ]; then
        "$PROJECT_ROOT/scripts/deploy.sh"
    else
        log_error "Deploy script not found. Please start services manually."
        exit 1
    fi
}

# Verify restoration
verify_restoration() {
    log_info "Verifying restoration..."

    # Wait a bit for services to start
    sleep 10

    # Check if services are running
    if docker compose -p "$COMPOSE_PROJECT_NAME" ps --format json | jq -r '.[].State' | grep -q "running"; then
        log_info "Services are running."
    else
        log_warn "Some services may not be running. Check with: docker compose ps"
    fi

    log_info "Restoration complete!"
    echo ""
    log_info "Please verify your data at: https://langfuse.local"
    log_info "Check logs with: make logs"
}

# Main execution
main() {
    log_info "Langfuse Restore Utility"
    echo "======================================"

    # Check if running with specific backup file
    if [ $# -eq 1 ] && [ -f "$1" ]; then
        RESTORE_FILE="$1"
        log_info "Using specified backup: $(basename "$RESTORE_FILE")"
    else
        list_backups
        select_backup
    fi

    confirm_restore
    stop_services
    extract_backup
    restore_all_volumes
    start_services
    verify_restoration

    log_info "Restore operation completed successfully!"
}

# Run main function
main "$@"
