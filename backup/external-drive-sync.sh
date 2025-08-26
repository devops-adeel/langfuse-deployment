#!/bin/bash
# External Drive Backup Sync Script
# Syncs Langfuse backups to external drive (e.g., SanDisk) when available

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PRIMARY_BACKUP_DIR="${HOME}/LangfuseBackups"
EXTERNAL_DRIVE_NAME="${EXTERNAL_DRIVE_NAME:-SanDisk}"
EXTERNAL_BACKUP_DIR="/Volumes/${EXTERNAL_DRIVE_NAME}/LangfuseBackups"
LOCK_FILE="${PRIMARY_BACKUP_DIR}/.sync-lock"
LOG_FILE="${PRIMARY_BACKUP_DIR}/sync-$(date +%Y%m%d).log"

# Logging functions
log_info() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] INFO: $1"
    echo -e "${GREEN}[INFO]${NC} $1"
    echo "$msg" >> "$LOG_FILE"
}

log_warn() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] WARN: $1"
    echo -e "${YELLOW}[WARN]${NC} $1"
    echo "$msg" >> "$LOG_FILE"
}

log_error() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $1"
    echo -e "${RED}[ERROR]${NC} $1"
    echo "$msg" >> "$LOG_FILE"
}

# Check if external drive is mounted
check_external_drive() {
    if [ -d "/Volumes/${EXTERNAL_DRIVE_NAME}" ]; then
        # Check if drive is writable
        if [ -w "/Volumes/${EXTERNAL_DRIVE_NAME}" ]; then
            return 0
        else
            log_error "External drive is mounted but not writable"
            
            # Attempt to fix read-only issue (macOS specific)
            if [[ "$OSTYPE" == "darwin"* ]]; then
                log_info "Attempting to fix read-only issue..."
                
                # Try to remount as read-write
                local device=$(mount | grep "/Volumes/${EXTERNAL_DRIVE_NAME}" | awk '{print $1}')
                if [ -n "$device" ]; then
                    log_info "Device: $device"
                    
                    # Unmount and remount
                    if diskutil unmount "/Volumes/${EXTERNAL_DRIVE_NAME}" 2>/dev/null; then
                        sleep 2
                        if diskutil mount readWrite "$device" 2>/dev/null; then
                            log_info "Successfully remounted drive as read-write"
                            return 0
                        fi
                    fi
                fi
                
                log_error "Could not remount drive as read-write"
                log_info "Try: sudo mount -uw /Volumes/${EXTERNAL_DRIVE_NAME}"
            fi
            return 1
        fi
    else
        return 1
    fi
}

# Create lock file
create_lock() {
    if [ -f "$LOCK_FILE" ]; then
        local lock_pid=$(cat "$LOCK_FILE")
        
        # Check if process is still running
        if ps -p "$lock_pid" > /dev/null 2>&1; then
            log_warn "Another sync process is running (PID: $lock_pid)"
            exit 1
        else
            log_info "Removing stale lock file"
            rm -f "$LOCK_FILE"
        fi
    fi
    
    echo $$ > "$LOCK_FILE"
}

# Remove lock file
remove_lock() {
    rm -f "$LOCK_FILE"
}

# Cleanup on exit
cleanup() {
    remove_lock
}

# Set trap for cleanup
trap cleanup EXIT INT TERM

# Sync backups using rsync
sync_backups() {
    log_info "Starting backup synchronization..."
    
    # Create external backup directory if it doesn't exist
    if [ ! -d "$EXTERNAL_BACKUP_DIR" ]; then
        log_info "Creating backup directory on external drive..."
        mkdir -p "$EXTERNAL_BACKUP_DIR"
    fi
    
    # Calculate space requirements
    local source_size=$(du -sh "$PRIMARY_BACKUP_DIR" 2>/dev/null | cut -f1)
    local available_space=$(df -h "/Volumes/${EXTERNAL_DRIVE_NAME}" | tail -1 | awk '{print $4}')
    
    log_info "Source size: $source_size"
    log_info "Available space on external drive: $available_space"
    
    # Perform sync using rsync
    log_info "Syncing backups to external drive..."
    
    rsync -av --delete \
        --exclude=".sync-lock" \
        --exclude="*.log" \
        --exclude=".DS_Store" \
        --exclude=".docker-backup-lock" \
        --progress \
        "$PRIMARY_BACKUP_DIR/" \
        "$EXTERNAL_BACKUP_DIR/"
    
    if [ $? -eq 0 ]; then
        log_info "Sync completed successfully!"
        
        # Verify sync
        local primary_count=$(find "$PRIMARY_BACKUP_DIR" -name "langfuse-*.tar.gz" | wc -l)
        local external_count=$(find "$EXTERNAL_BACKUP_DIR" -name "langfuse-*.tar.gz" | wc -l)
        
        log_info "Primary backups: $primary_count files"
        log_info "External backups: $external_count files"
        
        if [ "$primary_count" -eq "$external_count" ]; then
            log_info "Backup counts match ✓"
        else
            log_warn "Backup counts don't match!"
        fi
    else
        log_error "Sync failed!"
        return 1
    fi
}

# Apply retention policy on external drive
apply_retention_policy() {
    log_info "Applying retention policy on external drive..."
    
    local retention_days="${BACKUP_RETENTION_DAYS:-30}"
    
    # Find and remove old backups (older than retention period)
    find "$EXTERNAL_BACKUP_DIR" \
        -name "langfuse-*.tar.gz" \
        -type f \
        -mtime +${retention_days} \
        -exec rm -f {} \; \
        -exec echo "Removed old backup: {}" \;
        
    log_info "Retention policy applied (keeping last $retention_days days)"
}

# Create sync report
create_report() {
    local report_file="${EXTERNAL_BACKUP_DIR}/sync-report.txt"
    
    {
        echo "Langfuse Backup Sync Report"
        echo "==========================="
        echo "Date: $(date)"
        echo "Primary Location: $PRIMARY_BACKUP_DIR"
        echo "External Location: $EXTERNAL_BACKUP_DIR"
        echo ""
        echo "Backup Files:"
        echo "-------------"
        ls -lh "$EXTERNAL_BACKUP_DIR"/langfuse-*.tar.gz 2>/dev/null || echo "No backups found"
        echo ""
        echo "Disk Usage:"
        echo "-----------"
        df -h "/Volumes/${EXTERNAL_DRIVE_NAME}"
    } > "$report_file"
    
    log_info "Sync report created: $report_file"
}

# Monitor mode - wait for drive and sync
monitor_mode() {
    log_info "Monitor mode: Waiting for external drive..."
    
    local check_interval=30
    local max_checks=120  # 1 hour maximum
    local check_count=0
    
    while [ $check_count -lt $max_checks ]; do
        if check_external_drive; then
            log_info "External drive detected!"
            sync_backups
            apply_retention_policy
            create_report
            log_info "Monitor mode: Sync completed, exiting."
            exit 0
        fi
        
        check_count=$((check_count + 1))
        sleep $check_interval
    done
    
    log_warn "Monitor mode: Timeout reached without detecting drive."
    exit 1
}

# Main execution
main() {
    local mode="${1:-sync}"
    
    log_info "Langfuse External Drive Backup Sync"
    log_info "===================================="
    
    # Create lock
    create_lock
    
    case "$mode" in
        sync)
            if check_external_drive; then
                log_info "External drive found: /Volumes/${EXTERNAL_DRIVE_NAME}"
                sync_backups
                apply_retention_policy
                create_report
            else
                log_warn "External drive not found or not writable"
                log_info "Please ensure ${EXTERNAL_DRIVE_NAME} is connected and writable"
                exit 1
            fi
            ;;
        
        monitor)
            monitor_mode
            ;;
        
        check)
            if check_external_drive; then
                log_info "External drive is available and writable"
                exit 0
            else
                log_warn "External drive is not available or not writable"
                exit 1
            fi
            ;;
        
        *)
            log_error "Unknown mode: $mode"
            echo "Usage: $0 [sync|monitor|check]"
            echo "  sync    - Sync backups now (default)"
            echo "  monitor - Wait for drive and sync when detected"
            echo "  check   - Check if external drive is available"
            exit 1
            ;;
    esac
}

# Run main function
main "$@"