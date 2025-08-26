#!/bin/bash
# Langfuse Version Update Script
# Safely updates Langfuse and related services to new versions

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
VERSIONS_FILE="$PROJECT_ROOT/versions.lock"
COMPOSE_DIR="$PROJECT_ROOT/compose"
BACKUP_DIR="${HOME}/LangfuseBackups"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-langfuse-prod}"

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

# Check for updates
check_updates() {
    log_info "Checking for Langfuse updates..."
    
    # Get current version
    source "$VERSIONS_FILE"
    local current_version="$LANGFUSE_VERSION"
    
    log_info "Current Langfuse version: v${current_version}"
    
    # Check latest release from GitHub
    local latest_release=$(curl -s https://api.github.com/repos/langfuse/langfuse/releases/latest | \
                          grep '"tag_name":' | \
                          sed -E 's/.*"v?([^"]+)".*/\1/')
    
    if [ -z "$latest_release" ]; then
        log_warn "Could not fetch latest release information"
        return 1
    fi
    
    log_info "Latest Langfuse version: v${latest_release}"
    
    if [ "$current_version" == "$latest_release" ]; then
        log_info "You are running the latest version!"
        return 0
    else
        log_warn "Update available: v${current_version} → v${latest_release}"
        return 2
    fi
}

# Update specific service version
update_service_version() {
    local service="$1"
    local new_version="$2"
    local variable_name="${3:-${service^^}_VERSION}"
    
    log_info "Updating $service to version $new_version..."
    
    # Backup current versions file
    cp "$VERSIONS_FILE" "${VERSIONS_FILE}.bak"
    
    # Update version in file
    sed -i.tmp "s/^${variable_name}=.*$/${variable_name}=${new_version}/" "$VERSIONS_FILE"
    rm "${VERSIONS_FILE}.tmp"
    
    # Add to version history
    local date=$(date +%Y-%m-%d)
    echo "# $date: Updated $service to $new_version" >> "$VERSIONS_FILE"
    
    log_info "$service version updated in versions.lock"
}

# Create pre-update backup
create_backup() {
    log_info "Creating pre-update backup..."
    
    # Trigger manual backup
    cd "$COMPOSE_DIR"
    
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.backup.yml \
        -p "$COMPOSE_PROJECT_NAME" \
        run --rm backup-manual
    
    if [ $? -eq 0 ]; then
        log_info "Backup completed successfully"
        
        # Get latest backup file
        local latest_backup=$(ls -t "$BACKUP_DIR"/langfuse-*.tar.gz | head -1)
        log_info "Backup saved as: $(basename "$latest_backup")"
    else
        log_error "Backup failed!"
        log_prompt "Continue without backup? (y/n):"
        read -r answer
        if [ "$answer" != "y" ]; then
            exit 1
        fi
    fi
}

# Pull new images
pull_images() {
    log_info "Pulling new images..."
    
    cd "$COMPOSE_DIR"
    
    # Load new versions
    source "$VERSIONS_FILE"
    
    # Export versions for docker compose
    export LANGFUSE_VERSION
    export LANGFUSE_WORKER_VERSION
    export POSTGRES_VERSION
    export CLICKHOUSE_VERSION
    export REDIS_VERSION
    export MINIO_VERSION
    export BACKUP_VERSION
    
    docker compose \
        -f docker-compose.yml \
        -f docker-compose.orbstack.yml \
        -p "$COMPOSE_PROJECT_NAME" \
        pull
    
    if [ $? -eq 0 ]; then
        log_info "Images pulled successfully"
    else
        log_error "Failed to pull images"
        exit 1
    fi
}

# Perform rolling update
rolling_update() {
    log_info "Performing rolling update..."
    
    cd "$PROJECT_ROOT"
    
    # Stop services gracefully
    log_info "Stopping services..."
    docker compose \
        -f compose/docker-compose.yml \
        -f compose/docker-compose.orbstack.yml \
        -p "$COMPOSE_PROJECT_NAME" \
        stop langfuse-web langfuse-worker
    
    # Update and start services
    log_info "Starting updated services..."
    "$PROJECT_ROOT/scripts/deploy.sh"
    
    if [ $? -eq 0 ]; then
        log_info "Services updated successfully"
    else
        log_error "Update failed! Rolling back..."
        rollback_update
        exit 1
    fi
}

# Rollback update
rollback_update() {
    log_warn "Rolling back to previous version..."
    
    # Restore versions file
    if [ -f "${VERSIONS_FILE}.bak" ]; then
        mv "${VERSIONS_FILE}.bak" "$VERSIONS_FILE"
        log_info "Versions file restored"
    fi
    
    # Redeploy with old versions
    "$PROJECT_ROOT/scripts/deploy.sh"
    
    log_info "Rollback completed"
}

# Interactive update menu
interactive_update() {
    log_info "Interactive Update Menu"
    echo "======================="
    echo "1) Update Langfuse (core + worker)"
    echo "2) Update PostgreSQL"
    echo "3) Update ClickHouse"
    echo "4) Update Redis"
    echo "5) Update MinIO"
    echo "6) Update Backup service"
    echo "7) Update all services"
    echo "0) Exit"
    echo ""
    
    log_prompt "Select option (0-7):"
    read -r option
    
    case $option in
        1)
            log_prompt "Enter new Langfuse version (e.g., 3.98.0):"
            read -r version
            update_service_version "LANGFUSE" "$version"
            update_service_version "LANGFUSE_WORKER" "$version"
            ;;
        2)
            log_prompt "Enter new PostgreSQL version (e.g., 15.8-alpine):"
            read -r version
            update_service_version "POSTGRES" "$version"
            ;;
        3)
            log_prompt "Enter new ClickHouse version (e.g., 24.3.4.102-alpine):"
            read -r version
            update_service_version "CLICKHOUSE" "$version"
            ;;
        4)
            log_prompt "Enter new Redis version (e.g., 7.2.6-alpine):"
            read -r version
            update_service_version "REDIS" "$version"
            ;;
        5)
            log_prompt "Enter new MinIO version (e.g., RELEASE.2024-08-26T...):"
            read -r version
            update_service_version "MINIO" "$version"
            ;;
        6)
            log_prompt "Enter new Backup service version (e.g., v2.44.0):"
            read -r version
            update_service_version "BACKUP" "$version"
            ;;
        7)
            log_warn "This will update all services to their latest versions"
            log_prompt "Continue? (y/n):"
            read -r answer
            if [ "$answer" == "y" ]; then
                # TODO: Implement auto-detection of latest versions
                log_error "Auto-update not yet implemented. Please update services individually."
            fi
            ;;
        0)
            log_info "Exiting..."
            exit 0
            ;;
        *)
            log_error "Invalid option"
            exit 1
            ;;
    esac
    
    log_prompt "Apply updates now? (y/n):"
    read -r answer
    if [ "$answer" == "y" ]; then
        create_backup
        pull_images
        rolling_update
    fi
}

# Main execution
main() {
    local mode="${1:-check}"
    
    log_info "Langfuse Update Manager"
    echo "======================="
    
    case "$mode" in
        check)
            check_updates
            ;;
        
        interactive)
            interactive_update
            ;;
        
        apply)
            if [ $# -lt 3 ]; then
                log_error "Usage: $0 apply <service> <version>"
                exit 1
            fi
            update_service_version "$2" "$3"
            create_backup
            pull_images
            rolling_update
            ;;
        
        rollback)
            rollback_update
            ;;
        
        *)
            echo "Usage: $0 [check|interactive|apply|rollback]"
            echo "  check       - Check for updates (default)"
            echo "  interactive - Interactive update menu"
            echo "  apply       - Apply specific update"
            echo "  rollback    - Rollback to previous version"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"