---
paths:
  - "compose/**"
  - "versions.lock"
  - "Makefile"
  - "scripts/deploy.sh"
  - "scripts/update.sh"
  - "scripts/health-check.sh"
  - "clickhouse/**"
---

# Compose, services and versions (langfuse-prod)

> Moved from CLAUDE.md. Describes **this repo's `langfuse-prod` stack** (`compose/`, `Makefile`),
> which runs nothing. The live stack is compose project `langfuse` in
> `~/Documents/1-projects/langfuse`. See CLAUDE.md.

## Service Architecture

### Core Services
- **langfuse-web**: Main application (http://langfuse.local)
- **langfuse-worker**: Background job processor (http://worker.langfuse.local)

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
http://langfuse.local          # Main application
http://minio.local             # MinIO console
http://clickhouse.local        # ClickHouse HTTP interface
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


## Health Monitoring

The `scripts/health-check.sh` validates:
- Service container status
- Database connectivity
- Redis availability
- ClickHouse responsiveness
- MinIO accessibility
- Web interface reachability

Use `make health-verbose` for detailed resource usage.

