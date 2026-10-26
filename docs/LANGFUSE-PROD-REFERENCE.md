# langfuse-prod reference

> Moved from CLAUDE.md. Describes **this repo's `langfuse-prod` stack** (`compose/`, `Makefile`),
> which runs nothing. The live stack is compose project `langfuse` in
> `~/Documents/1-projects/langfuse`. See CLAUDE.md.

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
