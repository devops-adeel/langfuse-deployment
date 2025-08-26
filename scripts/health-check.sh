#!/bin/bash
# Langfuse Health Check Script
# Monitors the health status of all Langfuse services

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
COMPOSE_PROJECT_NAME="${COMPOSE_PROJECT_NAME:-langfuse-prod}"
VERBOSE="${VERBOSE:-false}"

# Service endpoints
WEB_URL="https://langfuse.local"
MINIO_URL="https://minio.local"
POSTGRES_HOST="postgres.langfuse.local"
CLICKHOUSE_URL="https://clickhouse.local"
REDIS_HOST="redis.langfuse.local"

# Health status tracking
OVERALL_HEALTH=0
HEALTH_REPORT=""

# Logging functions
log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_info() {
    echo -e "${CYAN}ℹ${NC} $1"
}

log_section() {
    echo -e "\n${BLUE}═══ $1 ═══${NC}"
}

# Check Docker daemon
check_docker() {
    log_section "Docker Status"
    
    if docker info >/dev/null 2>&1; then
        log_success "Docker daemon is running"
        
        # Check Docker Compose
        if docker compose version >/dev/null 2>&1; then
            local compose_version=$(docker compose version --short)
            log_success "Docker Compose version: $compose_version"
        else
            log_error "Docker Compose not available"
            OVERALL_HEALTH=1
        fi
    else
        log_error "Docker daemon is not running"
        OVERALL_HEALTH=1
        exit 1
    fi
}

# Check container status
check_container() {
    local service_name="$1"
    local container_name="${COMPOSE_PROJECT_NAME}-${service_name}-1"
    
    # Get container status
    local status=$(docker ps --filter "name=${container_name}" --format "{{.Status}}" 2>/dev/null | head -1)
    
    if [ -z "$status" ]; then
        log_error "$service_name: Container not found"
        OVERALL_HEALTH=1
        return 1
    elif echo "$status" | grep -q "Up"; then
        if echo "$status" | grep -q "healthy"; then
            log_success "$service_name: Running (healthy)"
        elif echo "$status" | grep -q "unhealthy"; then
            log_error "$service_name: Running (unhealthy)"
            OVERALL_HEALTH=1
        else
            log_warn "$service_name: Running (health check pending)"
        fi
        
        if [ "$VERBOSE" == "true" ]; then
            echo "  Status: $status"
        fi
    else
        log_error "$service_name: Not running"
        OVERALL_HEALTH=1
    fi
}

# Check all containers
check_containers() {
    log_section "Container Status"
    
    check_container "langfuse-web"
    check_container "langfuse-worker"
    check_container "postgres"
    check_container "clickhouse"
    check_container "redis"
    check_container "minio"
    check_container "backup"
}

# Check service endpoints
check_endpoints() {
    log_section "Service Endpoints"
    
    # Check Langfuse Web
    if curl -sSf -o /dev/null -w "%{http_code}" "$WEB_URL" 2>/dev/null | grep -q "200\|301\|302"; then
        log_success "Langfuse Web: Accessible at $WEB_URL"
    else
        log_error "Langfuse Web: Not accessible at $WEB_URL"
        OVERALL_HEALTH=1
    fi
    
    # Check MinIO
    if curl -sSf -o /dev/null -w "%{http_code}" "$MINIO_URL" 2>/dev/null | grep -q "200\|403"; then
        log_success "MinIO: Accessible at $MINIO_URL"
    else
        log_warn "MinIO: Not accessible at $MINIO_URL"
    fi
    
    # Check ClickHouse HTTP
    if curl -sSf -o /dev/null "$CLICKHOUSE_URL/ping" 2>/dev/null; then
        log_success "ClickHouse: Responding at $CLICKHOUSE_URL"
    else
        log_warn "ClickHouse: Not accessible at $CLICKHOUSE_URL"
    fi
}

# Check database connections
check_databases() {
    log_section "Database Connectivity"
    
    # Check PostgreSQL
    if docker exec "${COMPOSE_PROJECT_NAME}-postgres-1" pg_isready -U postgres >/dev/null 2>&1; then
        log_success "PostgreSQL: Accepting connections"
        
        # Check database size
        if [ "$VERBOSE" == "true" ]; then
            local db_size=$(docker exec "${COMPOSE_PROJECT_NAME}-postgres-1" \
                psql -U postgres -t -c "SELECT pg_size_pretty(pg_database_size('postgres'));" 2>/dev/null | xargs)
            echo "  Database size: $db_size"
        fi
    else
        log_error "PostgreSQL: Not accepting connections"
        OVERALL_HEALTH=1
    fi
    
    # Check ClickHouse
    if docker exec "${COMPOSE_PROJECT_NAME}-clickhouse-1" \
        clickhouse-client --query "SELECT 1" >/dev/null 2>&1; then
        log_success "ClickHouse: Query execution successful"
        
        # Check table count
        if [ "$VERBOSE" == "true" ]; then
            local table_count=$(docker exec "${COMPOSE_PROJECT_NAME}-clickhouse-1" \
                clickhouse-client --query "SELECT count() FROM system.tables WHERE database != 'system'" 2>/dev/null)
            echo "  User tables: $table_count"
        fi
    else
        log_error "ClickHouse: Query execution failed"
        OVERALL_HEALTH=1
    fi
    
    # Check Redis
    if docker exec "${COMPOSE_PROJECT_NAME}-redis-1" redis-cli ping >/dev/null 2>&1; then
        log_success "Redis: Responding to ping"
        
        # Check memory usage
        if [ "$VERBOSE" == "true" ]; then
            local mem_used=$(docker exec "${COMPOSE_PROJECT_NAME}-redis-1" \
                redis-cli INFO memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
            echo "  Memory used: $mem_used"
        fi
    else
        log_error "Redis: Not responding"
        OVERALL_HEALTH=1
    fi
}

# Check disk usage
check_disk_usage() {
    log_section "Disk Usage"
    
    # Check Docker volumes
    local volumes=("langfuse_postgres_data" "langfuse_clickhouse_data" "langfuse_minio_data")
    
    for volume in "${volumes[@]}"; do
        local volume_name="${COMPOSE_PROJECT_NAME}_${volume}"
        local size=$(docker volume inspect "$volume_name" 2>/dev/null | \
            jq -r '.[0].Mountpoint' | \
            xargs du -sh 2>/dev/null | \
            cut -f1)
        
        if [ -n "$size" ]; then
            echo "  $volume: $size"
        fi
    done
    
    # Check backup directory
    if [ -d "${HOME}/LangfuseBackups" ]; then
        local backup_size=$(du -sh "${HOME}/LangfuseBackups" 2>/dev/null | cut -f1)
        echo "  Backups: $backup_size"
    fi
    
    # Check available disk space
    local available=$(df -h "${HOME}" | tail -1 | awk '{print $4}')
    echo "  Available space: $available"
}

# Check resource usage
check_resources() {
    log_section "Resource Usage"
    
    # Get container stats
    local stats=$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" \
        $(docker ps --filter "label=com.docker.compose.project=$COMPOSE_PROJECT_NAME" -q) 2>/dev/null)
    
    if [ -n "$stats" ]; then
        echo "$stats" | column -t -s $'\t'
    else
        log_warn "Could not retrieve resource statistics"
    fi
}

# Check backup status
check_backup() {
    log_section "Backup Status"
    
    local backup_container="${COMPOSE_PROJECT_NAME}-backup-1"
    
    # Check if backup container is running
    if docker ps --filter "name=${backup_container}" --format "{{.Names}}" | grep -q "$backup_container"; then
        log_success "Backup service: Running"
        
        # Check last backup
        if [ -d "${HOME}/LangfuseBackups" ]; then
            local latest_backup=$(ls -t "${HOME}/LangfuseBackups"/langfuse-*.tar.gz 2>/dev/null | head -1)
            
            if [ -n "$latest_backup" ]; then
                local backup_age=$(( ($(date +%s) - $(stat -f %m "$latest_backup" 2>/dev/null || stat -c %Y "$latest_backup")) / 3600 ))
                local backup_size=$(du -h "$latest_backup" | cut -f1)
                
                if [ $backup_age -lt 25 ]; then
                    log_success "Last backup: $(basename "$latest_backup") ($backup_size, ${backup_age}h ago)"
                else
                    log_warn "Last backup: $(basename "$latest_backup") ($backup_size, ${backup_age}h ago)"
                fi
            else
                log_warn "No backups found"
            fi
        fi
        
        # Check next scheduled backup
        local next_backup=$(docker exec "$backup_container" sh -c 'echo "Next backup: $(date -d @$(cat /var/spool/cron/crontabs/root | head -1 | cut -d" " -f1-5 | xargs -I {} date -d "{}" +%s) "+%Y-%m-%d %H:%M:%S")"' 2>/dev/null || echo "Unable to determine")
        echo "  $next_backup"
    else
        log_warn "Backup service: Not running"
    fi
}

# Check for errors in logs
check_logs() {
    log_section "Recent Errors (last 5 minutes)"
    
    local services=("langfuse-web" "langfuse-worker" "postgres" "clickhouse" "redis" "minio")
    local errors_found=false
    
    for service in "${services[@]}"; do
        local container="${COMPOSE_PROJECT_NAME}-${service}-1"
        local errors=$(docker logs --since 5m "$container" 2>&1 | grep -iE "error|fatal|panic|exception" | head -3)
        
        if [ -n "$errors" ]; then
            log_warn "$service has errors:"
            echo "$errors" | sed 's/^/    /'
            errors_found=true
        fi
    done
    
    if [ "$errors_found" == "false" ]; then
        log_success "No recent errors found"
    fi
}

# Generate health summary
generate_summary() {
    log_section "Health Summary"
    
    if [ $OVERALL_HEALTH -eq 0 ]; then
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${GREEN}  All systems operational ✓${NC}"
        echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    else
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
        echo -e "${RED}  Issues detected - review above ✗${NC}"
        echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    fi
    
    echo ""
    log_info "Quick Actions:"
    echo "  • View logs:     make logs"
    echo "  • Restart:       make restart"
    echo "  • Stop services: make stop"
    echo "  • Manual backup: make backup"
}

# Main execution
main() {
    echo -e "${BLUE}╔══════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Langfuse Health Check Report     ║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════╝${NC}"
    
    check_docker
    check_containers
    check_endpoints
    check_databases
    check_disk_usage
    
    if [ "$VERBOSE" == "true" ]; then
        check_resources
        check_logs
    fi
    
    check_backup
    generate_summary
    
    exit $OVERALL_HEALTH
}

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -v|--verbose)
            VERBOSE=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [-v|--verbose]"
            echo "  -v, --verbose  Show detailed information"
            echo "  -h, --help     Show this help message"
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Run main function
main