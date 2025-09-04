# Langfuse Deployment - Quick Reference Card

## 🌐 Service URLs

| Service | URL | Login | Purpose |
|---------|-----|-------|---------|
| **Langfuse** | http://langfuse.local | demo@langfuse.com / password | LLM observability platform |
| **MinIO** | http://minio.local | minioadmin / [1Password] | Object storage console |
| **PostgreSQL** | postgres.langfuse.local:5432 | postgres / [1Password] | Primary database |
| **ClickHouse** | http://clickhouse.local | default / [1Password] | Analytics database |
| **Redis** | redis.langfuse.local:6379 | - / [1Password] | Cache & queue |
| **Grafana** | http://grafana.local | admin / admin | Infrastructure monitoring |
| **Prometheus** | http://prometheus.local | - | Metrics storage |
| **Tempo** | http://tempo.local | - | Distributed tracing |

## 🛠 Essential Commands

### Deployment
```bash
make deploy              # Full deployment with 1Password
make up                  # Start services (secrets must exist)
make stop                # Stop all services
make down                # Stop and remove containers
make restart             # Restart all services
```

### Health & Monitoring
```bash
make health              # Quick health check
make health-verbose      # Detailed health with resources
make ps                  # Show running containers
make logs                # Tail all logs
make logs-web           # Tail Langfuse web logs
make logs-errors        # Show recent errors only
```

### Database Access
```bash
make db-shell            # PostgreSQL interactive shell
make clickhouse-shell    # ClickHouse interactive shell
make redis-cli           # Redis CLI
```

### Backup Operations
```bash
make backup              # Manual backup now
make backup-list         # List available backups
make restore             # Interactive restore
make backup-sync         # Sync to external drive
```

### Updates & Maintenance
```bash
make update-check        # Check for new versions
make update              # Interactive update menu
make clean               # Clean stopped containers
make volumes             # List Docker volumes
make volume-sizes        # Show volume disk usage
```

## 🚨 Emergency Procedures

### High Memory Usage
```bash
# 1. Check memory consumption
docker stats --no-stream | grep langfuse

# 2. Restart affected service
docker compose restart langfuse-web

# 3. Scale workers if needed
docker compose scale langfuse-worker=1
```

### Database Connection Issues
```bash
# 1. Check PostgreSQL health
docker compose exec postgres pg_isready

# 2. View connection count
make db-shell
SELECT count(*) FROM pg_stat_activity;

# 3. Restart if needed
docker compose restart postgres
```

### Trace Correlation Issues
```bash
# 1. Verify OTLP endpoint
curl -X POST http://alloy.local:4318/v1/traces \
  -H "Content-Type: application/json" \
  -d '{"resourceSpans":[]}'

# 2. Check Langfuse metadata
curl http://langfuse.local/api/public/traces | \
  jq '.data[0].metadata'

# 3. Verify Tempo ingestion
curl http://tempo.local/ready
```

### Backup Failures
```bash
# 1. Check backup service
docker logs langfuse-prod-backup-1 --tail 50

# 2. Manual backup
docker compose run --rm backup-manual

# 3. Verify backup location
ls -la ~/LangfuseBackups/
```

## 📊 Health Check Matrix

| Component | Check Command | Expected Output | Action if Failed |
|-----------|--------------|-----------------|------------------|
| **Langfuse Web** | `curl http://langfuse.local/api/health` | `{"status":"OK"}` | `make restart` |
| **PostgreSQL** | `make db-shell` → `\conninfo` | Connection info | Check passwords |
| **ClickHouse** | `curl http://clickhouse.local:8123/ping` | `Ok.` | Restart service |
| **Redis** | `docker exec redis-1 redis-cli ping` | `PONG` | Check password |
| **MinIO** | `curl http://minio.local/minio/health/live` | `{}` | Check credentials |
| **Grafana** | `curl http://grafana.local/api/health` | `{"database":"ok"}` | Check data sources |

## 🔄 Integration Points

### Trace Correlation
```python
# In your application
tempo_trace_id = "abc123..."
langfuse_trace_id = "lf_xyz..."

# View in Langfuse
open(f"http://langfuse.local/trace/{langfuse_trace_id}")

# View in Tempo
open(f"http://grafana.local/explore?traceID={tempo_trace_id}")
```

### Cost Analysis
```bash
# LLM costs (Langfuse)
curl http://langfuse.local/api/public/metrics/daily | \
  jq '.data[0].totalCost'

# Infrastructure costs (Prometheus)
curl 'http://prometheus.local/api/v1/query?query=\
  sum(rate(container_cpu_usage_seconds_total[24h]))*0.024'
```

## 📈 Key Metrics

### Langfuse Performance
- **Target latency**: <2s for dashboard loads
- **Token tracking**: 100% coverage
- **Cost accuracy**: ±5% of actual

### Infrastructure Targets
- **Memory usage**: <4GB normal, <8GB peak
- **CPU usage**: <50% average
- **Storage growth**: <1GB/day

### Backup SLAs
- **RPO**: 24 hours (daily backups)
- **RTO**: <1 hour (restore time)
- **Retention**: 7 daily, 4 weekly, 12 monthly

## 🔗 Quick Links

| Resource | Link |
|----------|------|
| **This Repository** | `/langfuse-deployment` |
| **Grafana Stack** | `../grafana-orbstack` |
| **Backup Location** | `~/LangfuseBackups/` |
| **1Password Vault** | `Langfuse-Prod` |
| **Docker Volumes** | `langfuse-prod_*` |
| **Logs Location** | `docker logs <container>` |

## 🆘 Support Escalation

1. **Check documentation**: `docs/INTEGRATION.md`
2. **View logs**: `make logs-errors`
3. **Check Grafana dashboards**: http://grafana.local/d/langfuse-ops
4. **Review GitHub issues**: https://github.com/langfuse/langfuse/issues
5. **Langfuse Discord**: https://discord.gg/langfuse

---
*Version: 1.0.0 | Updated: 2024-08 | [Full Documentation](../README.md)*
