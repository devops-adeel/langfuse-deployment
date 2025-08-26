#!/bin/bash
# Langfuse Deployment Script with 1Password Integration
# This script safely deploys Langfuse using secrets from 1Password

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_DIR="$PROJECT_ROOT/compose"
SECRETS_DIR="$PROJECT_ROOT/secrets"
TEMP_ENV="/tmp/.langfuse-env-$$"
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

# Cleanup function
cleanup() {
    if [ -f "$TEMP_ENV" ]; then
        log_info "Cleaning up temporary files..."
        shred -u "$TEMP_ENV" 2>/dev/null || rm -f "$TEMP_ENV"
    fi
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check for 1Password CLI
    if ! command -v op &> /dev/null; then
        log_error "1Password CLI (op) is not installed."
        log_info "Install with: brew install --cask 1password-cli"
        exit 1
    fi
    
    # Check for Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed."
        exit 1
    fi
    
    # Check for Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available."
        exit 1
    fi
    
    log_info "All prerequisites met."
}

# Check 1Password authentication
check_1password_auth() {
    log_info "Checking 1Password authentication..."
    
    if ! op account list &> /dev/null; then
        log_warn "Not signed in to 1Password."
        log_info "Please sign in to 1Password:"
        op signin
        
        if [ $? -ne 0 ]; then
            log_error "Failed to sign in to 1Password."
            exit 1
        fi
    else
        log_info "Already signed in to 1Password."
    fi
}

# Inject secrets from 1Password
inject_secrets() {
    log_info "Injecting secrets from 1Password..."
    
    # Try core template first, fall back to full template
    if [ -f "$SECRETS_DIR/.env.1password.core" ]; then
        TEMPLATE_FILE="$SECRETS_DIR/.env.1password.core"
    elif [ -f "$SECRETS_DIR/.env.1password.template" ]; then
        TEMPLATE_FILE="$SECRETS_DIR/.env.1password.template"
    else
        log_error "No 1Password template found in $SECRETS_DIR"
        exit 1
    fi
    
    log_info "Using template: $(basename $TEMPLATE_FILE)"
    
    # Inject secrets into temporary file
    if ! op inject -i "$TEMPLATE_FILE" -o "$TEMP_ENV" 2>/dev/null; then
        log_error "Failed to inject secrets from 1Password."
        log_info "Please ensure the 'Langfuse-Prod' vault exists with all required items."
        exit 1
    fi
    
    # Verify critical secrets were injected
    if grep -q "op://" "$TEMP_ENV"; then
        log_error "Some secrets were not resolved. Check your 1Password vault."
        grep "op://" "$TEMP_ENV" | head -5
        exit 1
    fi
    
    log_info "Secrets successfully injected."
}

# Deploy services
deploy_services() {
    local compose_files="-f docker-compose.yml"
    local deploy_mode="${1:-full}"
    
    cd "$COMPOSE_DIR"
    
    # Add backup service for full deployment
    if [ "$deploy_mode" == "full" ]; then
        log_info "Including backup service..."
        compose_files="$compose_files -f docker-compose.backup.yml"
    fi
    
    log_info "Pulling latest images..."
    COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" \
        docker compose $compose_files \
        --env-file "$TEMP_ENV" \
        pull --quiet
    
    log_info "Starting services..."
    COMPOSE_PROJECT_NAME="$COMPOSE_PROJECT_NAME" \
        docker compose $compose_files \
        --env-file "$TEMP_ENV" \
        up -d
    
    if [ $? -eq 0 ]; then
        log_info "Deployment successful!"
    else
        log_error "Deployment failed!"
        exit 1
    fi
}

# Wait for services to be healthy
wait_for_health() {
    log_info "Waiting for services to be healthy..."
    
    local max_wait=60
    local wait_time=0
    
    while [ $wait_time -lt $max_wait ]; do
        if docker compose ps --format json | jq -r '.[].Health' | grep -q "unhealthy"; then
            echo -n "."
            sleep 2
            wait_time=$((wait_time + 2))
        else
            echo
            log_info "All services are healthy!"
            return 0
        fi
    done
    
    echo
    log_warn "Some services may not be fully healthy. Check with: make health"
    return 1
}

# Show deployment info
show_info() {
    log_info "Deployment Information:"
    echo "======================================"
    echo "Project Name: $COMPOSE_PROJECT_NAME"
    echo "Langfuse Web: https://langfuse.local"
    echo "MinIO Console: https://minio.local"
    echo "======================================"
    echo ""
    log_info "View logs with: make logs"
    log_info "Check health with: make health"
    log_info "Stop services with: make stop"
}

# Main execution
main() {
    local deploy_mode="${1:-full}"
    
    log_info "Starting Langfuse deployment..."
    
    check_prerequisites
    check_1password_auth
    inject_secrets
    deploy_services "$deploy_mode"
    wait_for_health
    show_info
    
    log_info "Deployment complete!"
}

# Run main function
main "$@"