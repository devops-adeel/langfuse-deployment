# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

This is a production-ready deployment configuration for **Langfuse** - an open-source LLM engineering platform for observability, tracing, prompt management, and evaluations. The deployment is optimized for OrbStack on macOS with enterprise-grade security through 1Password integration, automated backups, and comprehensive monitoring.

### Key Architectural Decisions
- **Zero-Secret Deployment**: Uses 1Password CLI for runtime secret injection - secrets never touch the codebase
- **OrbStack Optimized**: Leverages domain-based routing (*.local) instead of port mappings for cleaner development
- **Security-First**: Gitleaks scanning in pre-commit hooks and CI/CD prevents accidental secret exposure
- **Multi-Tier Backup**: Automated daily/weekly/monthly backups with external drive synchronization
- **Observability Integration**: Works with Grafana-OrbStack for distributed tracing and complete system visibility

## Essential Commands

### Deployment & Operations
```bash
# Full deployment with 1Password secret injection
make deploy

# Deploy without backup service
make deploy-no-backup

# Start services (requires existing .env.secrets)
make up

# Stop services (preserves volumes)
make down

# Health monitoring
make health                  # Quick health check
make health-verbose         # Detailed with resource usage
make logs                   # Tail all logs
make logs-errors           # Show recent errors
```

### Backup & Recovery
```bash
# Manual backup
make backup

# List available backups
make backup-list

# Interactive restore
make restore

# Sync to external drive
make backup-sync

# Monitor for external drive
make backup-monitor
```

### Updates & Migration
```bash
# Check for updates
make update-check

# Interactive update menu
make update

# Update to specific version
make update-langfuse VERSION=3.98.0

# Migrate from existing Langfuse
make migrate
```

### Security Operations
```bash
# Install security tools and pre-commit hooks
make security-init

# Run security scan
make security-scan

# Test security detection
make security-test

# Full security audit
make security-audit

# Guide for rotating secrets
make security-rotate
```

### Database Access
```bash
make db-shell              # PostgreSQL shell
make clickhouse-shell      # ClickHouse shell
make redis-cli            # Redis CLI
```

## Secret Management Architecture

### 1Password Injection Pattern
The deployment uses a three-phase secret injection process:
```
secrets/.env.1password.template → op inject → temporary .env → docker compose up → cleanup
```

**Never store actual secrets in code!** All secrets are referenced as:
```env
DATABASE_URL=op://Langfuse-Prod/PostgreSQL/connection-string
```

### Required 1Password Vault Structure
Create vault `Langfuse-Prod` with these items:
- **PostgreSQL**: connection-string, password
- **Security**: nextauth-secret, salt, encryption-key
- **ClickHouse**: password
- **Redis**: password
- **MinIO**: root-password, event-secret-key, media-secret-key, batch-secret-key

The `scripts/deploy.sh` handles the injection, deployment, and cleanup automatically.

## Service Architecture

### Core Services
- **langfuse-web**: Main application (https://langfuse.local)
- **langfuse-worker**: Background job processor (https://worker.langfuse.local)

### Data Layer
- **PostgreSQL** (v17-alpine): Primary database for application data
- **ClickHouse** (v24.3.3): Analytics and high-volume event storage
- **Redis** (v7.2.5): Cache and queue management
- **MinIO**: S3-compatible object storage for media/exports

### Supporting Services
- **backup**: Automated backup service using offen/docker-volume-backup
- Runs daily at 2 AM with configurable retention policies

### Version Management
All service versions are pinned in `versions.lock` for controlled updates.

## OrbStack-Specific Configuration

### Domain-Based Access (No Port Mappings)
```
https://langfuse.local          # Main application
https://minio.local             # MinIO console
https://clickhouse.local        # ClickHouse HTTP interface
postgres.langfuse.local:5432    # PostgreSQL
redis.langfuse.local:6379       # Redis
```

### Docker Compose Structure
- `compose/docker-compose.yml`: Base services configuration
- `compose/docker-compose.backup.yml`: Backup service overlay

OrbStack automatically provides domains via labels:
```yaml
labels:
  - dev.orbstack.domains=langfuse.local
```

## Deployment Workflow

The `scripts/deploy.sh` orchestrates:
1. **Authentication Check**: Verifies 1Password CLI access
2. **Secret Injection**: Creates temporary .env from template
3. **Image Pull**: Updates all Docker images
4. **Service Start**: Launches with health checks
5. **Validation**: Waits for all services to be healthy
6. **Cleanup**: Removes temporary secret files

On failure, automatic rollback preserves data integrity.

## Backup & Recovery System

### Automated Backup Strategy
- **Daily**: 7 days retention (2 AM)
- **Weekly**: 4 weeks retention (Sundays)
- **Monthly**: 12 months retention (1st of month)

Configuration in `backup/backup.conf`

### Backup Locations
- Primary: `~/LangfuseBackups/`
- External: `/Volumes/{DRIVE_NAME}/LangfuseBackups/`

### Recovery Process
The `backup/restore.sh` script:
1. Lists available backups
2. Creates pre-restore backup
3. Stops services
4. Restores selected backup
5. Restarts and validates services

## Security Implementation

### Pre-Commit Hooks
Gitleaks scans every commit to prevent secrets from entering the repository.

### CI/CD Pipeline
GitHub Actions automatically:
- Scans PRs for secrets
- Auto-closes PRs with detected secrets
- Logs incidents to `.security/incidents.log`

### Security Runbook
Detailed procedures in `.security/RUNBOOK.md` for incident response.

## Integration with Grafana-OrbStack

### Observability Stack Integration
- **Langfuse**: LLM traces, prompts, completions, costs
- **Grafana**: Infrastructure metrics, distributed traces, logs

### Trace Correlation
Uses W3C Trace Context standard for end-to-end visibility:
```python
# Share trace ID between systems
langfuse.update_current_trace(
    metadata={
        "tempo_trace_id": format(span_context.trace_id, '032x')
    }
)
```

See `docs/INTEGRATION.md` for complete setup.

## Migration Support

The `scripts/migrate.sh` provides guided migration from existing Langfuse installations:
1. Creates pre-migration backup
2. Extracts secrets from old configuration
3. Guides through 1Password setup
4. Migrates data volumes
5. Validates new deployment

## Health Monitoring

The `scripts/health-check.sh` validates:
- Service container status
- Database connectivity
- Redis availability
- ClickHouse responsiveness
- MinIO accessibility
- Web interface reachability

Use `make health-verbose` for detailed resource usage.

## Common Development Tasks

### View Service URLs
```bash
make urls
```

### Check Volume Sizes
```bash
make volume-sizes
```

### Pull Latest Images
```bash
make pull
```

### Clean Stopped Containers
```bash
make clean
```

## Troubleshooting Patterns

### 1Password Not Authenticated
```bash
op signin
op account list
```

### Services Not Healthy
```bash
make health-verbose
make logs-errors
make restart
```

### Backup Failures
```bash
docker logs langfuse-prod-backup-1
make volumes
```

### External Drive Issues (macOS)
```bash
# For read-only SanDisk
sudo mount -uw /Volumes/SanDisk
```

## Important Files

- `Makefile`: All common operations
- `versions.lock`: Pinned service versions
- `secrets/.env.1password.template`: Secret references
- `backup/backup.conf`: Backup configuration
- `scripts/deploy.sh`: Deployment orchestration
- `scripts/health-check.sh`: Health monitoring
- `scripts/migrate.sh`: Migration tool
- `scripts/update.sh`: Version updates

## Testing Considerations

This is a deployment repository without application code. Testing focuses on:
- Security scanning validation (`make security-test`)
- Deployment verification (`make health`)
- Backup/restore procedures
- Secret rotation workflows

## Notes for Future Development

- Always use `make deploy` for production deployments to ensure proper secret handling
- Never bypass the 1Password injection system
- Test version updates in development before production
- Maintain the security-first approach in all changes
- Keep `versions.lock` updated for controlled releases
- Document any new services in both docker-compose files and this CLAUDE.md
