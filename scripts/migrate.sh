#!/bin/bash
# Langfuse Migration Script
# Safely migrates from existing Langfuse setup to new deployment repository

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
OLD_PROJECT_DIR="/Users/adeel/Documents/1_projects/langfuse"
COMPOSE_PROJECT_NAME="langfuse-prod"
BACKUP_DIR="${HOME}/LangfuseBackups"
MIGRATION_LOG="${PROJECT_ROOT}/migration-$(date +%Y%m%d-%H%M%S).log"

# Migration state tracking
MIGRATION_STEPS_COMPLETED=0
TOTAL_MIGRATION_STEPS=10

# Logging functions
log_info() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1"
    echo -e "${GREEN}[INFO]${NC} $1"
    echo "$msg" >> "$MIGRATION_LOG"
}

log_warn() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] WARN: $1"
    echo -e "${YELLOW}[WARN]${NC} $1"
    echo "$msg" >> "$MIGRATION_LOG"
}

log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1"
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$msg" >> "$MIGRATION_LOG"
}

log_step() {
    MIGRATION_STEPS_COMPLETED=$((MIGRATION_STEPS_COMPLETED + 1))
    echo -e "\n${BLUE}[Step $MIGRATION_STEPS_COMPLETED/$TOTAL_MIGRATION_STEPS]${NC} ${MAGENTA}$1${NC}"
    echo "==================================================" >> "$MIGRATION_LOG"
    echo "[Step $MIGRATION_STEPS_COMPLETED/$TOTAL_MIGRATION_STEPS] $1" >> "$MIGRATION_LOG"
}

log_prompt() {
    echo -e "${BLUE}[?]${NC} $1"
}

# Pre-flight checks
preflight_checks() {
    log_step "Running pre-flight checks"
    
    # Check if old project exists
    if [ ! -d "$OLD_PROJECT_DIR" ]; then
        log_error "Old Langfuse project not found at: $OLD_PROJECT_DIR"
        exit 1
    fi
    
    # Check if new deployment repo exists
    if [ ! -d "$PROJECT_ROOT" ]; then
        log_error "New deployment repository not found at: $PROJECT_ROOT"
        exit 1
    fi
    
    # Check Docker
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker is not running"
        exit 1
    fi
    
    # Check 1Password CLI
    if ! command -v op &> /dev/null; then
        log_warn "1Password CLI not installed. You'll need to set up secrets manually."
        log_info "Install with: brew install --cask 1password-cli"
    fi
    
    # Check if services are running
    if docker compose -p "$COMPOSE_PROJECT_NAME" ps --format json 2>/dev/null | jq -r '.[].State' | grep -q "running"; then
        log_info "Existing Langfuse services detected and running"
    else
        log_warn "No running Langfuse services detected"
    fi
    
    log_info "Pre-flight checks completed"
}

# Backup current setup
backup_current() {
    log_step "Creating backup of current setup"
    
    local backup_name="pre-migration-$(date +%Y%m%d-%H%M%S)"
    local backup_path="${BACKUP_DIR}/${backup_name}"
    
    mkdir -p "$backup_path"
    
    # Backup docker-compose files
    log_info "Backing up configuration files..."
    cp -r "$OLD_PROJECT_DIR"/{docker-compose*.yml,.env*} "$backup_path/" 2>/dev/null || true
    
    # Trigger data backup
    log_info "Creating data backup..."
    cd "$OLD_PROJECT_DIR"
    
    # Check if backup script exists
    if [ -f "$OLD_PROJECT_DIR/backup/scripts/langfuse-backup.sh" ]; then
        bash "$OLD_PROJECT_DIR/backup/scripts/langfuse-backup.sh"
    else
        log_warn "No backup script found, attempting manual backup..."
        
        # Manual backup using docker
        for volume in postgres clickhouse minio; do
            docker run --rm \
                -v "${COMPOSE_PROJECT_NAME}_langfuse_${volume}_data:/data:ro" \
                -v "$backup_path:/backup" \
                alpine tar czf "/backup/${volume}-data.tar.gz" -C / data
        done
    fi
    
    log_info "Backup created at: $backup_path"
}

# Extract secrets from current setup
extract_secrets() {
    log_step "Extracting secrets from current configuration"
    
    local env_file=""
    
    # Find the active .env file
    if [ -f "$OLD_PROJECT_DIR/.env.docker-prod-orbstack" ]; then
        env_file="$OLD_PROJECT_DIR/.env.docker-prod-orbstack"
    elif [ -f "$OLD_PROJECT_DIR/.env.docker-prod" ]; then
        env_file="$OLD_PROJECT_DIR/.env.docker-prod"
    elif [ -f "$OLD_PROJECT_DIR/.env" ]; then
        env_file="$OLD_PROJECT_DIR/.env"
    else
        log_error "No environment file found in old project"
        exit 1
    fi
    
    log_info "Using environment file: $env_file"
    
    # Create temporary secrets file
    local temp_secrets="${PROJECT_ROOT}/secrets/.migration-secrets"
    
    {
        echo "# Secrets extracted from migration - $(date)"
        echo "# IMPORTANT: Add these to 1Password and delete this file!"
        echo ""
        grep -E "PASSWORD|SECRET|KEY|AUTH" "$env_file" | grep -v "^#"
    } > "$temp_secrets"
    
    log_warn "Secrets extracted to: $temp_secrets"
    log_warn "ACTION REQUIRED: Add these secrets to 1Password vault 'Langfuse-Prod'"
}

# Stop old services
stop_old_services() {
    log_step "Stopping existing Langfuse services"
    
    cd "$OLD_PROJECT_DIR"
    
    # Stop services but keep volumes
    if docker compose -p "$COMPOSE_PROJECT_NAME" ps --format json 2>/dev/null | jq -r '.[].State' | grep -q "running"; then
        log_info "Stopping services..."
        docker compose -p "$COMPOSE_PROJECT_NAME" stop
        log_info "Services stopped (volumes preserved)"
    else
        log_info "No running services to stop"
    fi
}

# Setup 1Password vault
setup_1password() {
    log_step "Setting up 1Password vault"
    
    if ! command -v op &> /dev/null; then
        log_warn "1Password CLI not available, skipping..."
        return
    fi
    
    log_info "Please ensure you have created the 'Langfuse-Prod' vault in 1Password"
    log_info "Required items to create:"
    echo "  • PostgreSQL (with fields: connection-string, password)"
    echo "  • Security (with fields: nextauth-secret, salt, encryption-key)"
    echo "  • ClickHouse (with field: password)"
    echo "  • Redis (with field: password)"
    echo "  • MinIO (with fields: root-password, event-secret-key, media-secret-key, batch-secret-key)"
    echo "  • API (optional - with fields: public-key, secret-key)"
    echo ""
    
    log_prompt "Have you configured all secrets in 1Password? (y/n):"
    read -r answer
    
    if [ "$answer" != "y" ]; then
        log_warn "Please configure 1Password before proceeding with deployment"
        log_info "Refer to: ${PROJECT_ROOT}/secrets/.migration-secrets"
    fi
}

# Verify volume compatibility
verify_volumes() {
    log_step "Verifying Docker volumes"
    
    local volumes=(
        "${COMPOSE_PROJECT_NAME}_langfuse_postgres_data"
        "${COMPOSE_PROJECT_NAME}_langfuse_clickhouse_data"
        "${COMPOSE_PROJECT_NAME}_langfuse_clickhouse_logs"
        "${COMPOSE_PROJECT_NAME}_langfuse_minio_data"
    )
    
    for volume in "${volumes[@]}"; do
        if docker volume inspect "$volume" >/dev/null 2>&1; then
            log_info "✓ Volume exists: $volume"
            
            # Get volume size
            local mountpoint=$(docker volume inspect "$volume" | jq -r '.[0].Mountpoint')
            if [ -n "$mountpoint" ] && [ "$mountpoint" != "null" ]; then
                local size=$(du -sh "$mountpoint" 2>/dev/null | cut -f1)
                echo "    Size: ${size:-unknown}"
            fi
        else
            log_error "✗ Volume missing: $volume"
            log_warn "You may need to restore from backup"
        fi
    done
}

# Deploy new setup
deploy_new() {
    log_step "Deploying from new repository"
    
    cd "$PROJECT_ROOT"
    
    # Make scripts executable
    chmod +x scripts/*.sh
    chmod +x backup/*.sh
    
    log_info "Starting deployment..."
    
    # Check if secrets are configured
    if [ -f "$PROJECT_ROOT/secrets/.migration-secrets" ]; then
        log_warn "Using migration secrets file (temporary)"
        log_warn "Remember to migrate these to 1Password!"
        
        # Use migration secrets for now
        cp "$PROJECT_ROOT/secrets/.migration-secrets" "$PROJECT_ROOT/secrets/.env.secrets"
        
        # Deploy without 1Password
        cd "$PROJECT_ROOT/compose"
        docker compose \
            -f docker-compose.yml \
            -f docker-compose.orbstack.yml \
            -f docker-compose.backup.yml \
            -p "$COMPOSE_PROJECT_NAME" \
            --env-file "$PROJECT_ROOT/secrets/.env.secrets" \
            up -d
    else
        # Deploy with 1Password
        "$PROJECT_ROOT/scripts/deploy.sh"
    fi
    
    log_info "New deployment started"
}

# Verify new deployment
verify_deployment() {
    log_step "Verifying new deployment"
    
    sleep 10  # Wait for services to start
    
    "$PROJECT_ROOT/scripts/health-check.sh"
    
    log_info "Deployment verification complete"
}

# Cleanup old setup
cleanup_old() {
    log_step "Cleanup options for old setup"
    
    log_info "The migration is complete. The old setup at:"
    echo "  $OLD_PROJECT_DIR"
    echo ""
    log_info "Can be kept for reference or removed."
    log_info "Recommended actions:"
    echo "  1. Keep docker-compose files for reference"
    echo "  2. Remove .env files with secrets"
    echo "  3. Keep the repository for upstream tracking"
    echo ""
    
    log_prompt "Remove sensitive .env files from old setup? (y/n):"
    read -r answer
    
    if [ "$answer" == "y" ]; then
        rm -f "$OLD_PROJECT_DIR"/.env*
        log_info "Sensitive files removed"
    fi
}

# Create migration report
create_report() {
    log_step "Creating migration report"
    
    local report_file="${PROJECT_ROOT}/migration-report.md"
    
    {
        echo "# Langfuse Migration Report"
        echo "Date: $(date)"
        echo ""
        echo "## Migration Summary"
        echo "- **Source**: $OLD_PROJECT_DIR"
        echo "- **Target**: $PROJECT_ROOT"
        echo "- **Project Name**: $COMPOSE_PROJECT_NAME"
        echo "- **Migration Log**: $MIGRATION_LOG"
        echo ""
        echo "## Volumes Migrated"
        docker volume ls --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" --format "- {{.Name}}"
        echo ""
        echo "## Services Status"
        docker compose -p "$COMPOSE_PROJECT_NAME" ps
        echo ""
        echo "## Next Steps"
        echo "1. Configure 1Password secrets if not done"
        echo "2. Test all functionality"
        echo "3. Set up automated backups"
        echo "4. Remove temporary secrets file"
        echo ""
        echo "## Access Points"
        echo "- Langfuse Web: https://langfuse.local"
        echo "- MinIO Console: https://minio.local"
        echo ""
    } > "$report_file"
    
    log_info "Migration report saved to: $report_file"
}

# Main migration flow
main() {
    echo -e "${BLUE}╔═══════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║    Langfuse Deployment Migration Tool    ║${NC}"  
    echo -e "${BLUE}╚═══════════════════════════════════════════╝${NC}"
    echo ""
    log_info "Starting migration from old setup to new deployment repository"
    log_info "Migration log: $MIGRATION_LOG"
    echo ""
    
    # Confirm migration
    log_warn "This will migrate your existing Langfuse installation"
    log_warn "From: $OLD_PROJECT_DIR"
    log_warn "To:   $PROJECT_ROOT"
    echo ""
    log_prompt "Continue with migration? (yes/no):"
    read -r confirmation
    
    if [ "$confirmation" != "yes" ]; then
        log_info "Migration cancelled"
        exit 0
    fi
    
    # Run migration steps
    preflight_checks
    backup_current
    extract_secrets
    stop_old_services
    setup_1password
    verify_volumes
    deploy_new
    verify_deployment
    cleanup_old
    create_report
    
    echo ""
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo -e "${GREEN}  Migration completed successfully! ✓${NC}"
    echo -e "${GREEN}═══════════════════════════════════════════${NC}"
    echo ""
    log_info "Please review the migration report and test all functionality"
    log_warn "Remember to:"
    echo "  • Move secrets to 1Password"
    echo "  • Delete temporary secrets file"
    echo "  • Test backup/restore procedures"
    echo "  • Update any automation scripts"
}

# Run main function
main "$@"