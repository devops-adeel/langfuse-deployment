# Langfuse Deployment Repository

A production-ready deployment configuration for [Langfuse](https://github.com/langfuse/langfuse) with OrbStack optimizations, automated backups, and secure secret management via 1Password.

## 🚀 Quick Start

```bash
# 1. Initialize the repository
make init

# 2. Configure secrets in 1Password (see Secret Management section)

# 3. Deploy Langfuse
make deploy

# 4. Check health
make health

# 5. Access Langfuse
open https://langfuse.local
```

## 📋 Table of Contents

- [Features](#features)
- [Observability Integration](#-observability-integration)
- [Security](#-security)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Secret Management](#secret-management)
- [Usage](#usage)
- [Backup & Restore](#backup--restore)
- [Migration](#migration)
- [Architecture](#architecture)
- [Troubleshooting](#troubleshooting)

## ✨ Features

- **🔐 Secure Secret Management**: 1Password CLI integration for zero-secret deployment
- **🛡️ Secret Scanning**: Pre-commit hooks and CI/CD pipeline prevent accidental secret exposure
- **📍 Version Pinning**: Controlled updates with locked versions
- **💾 Automated Backups**: Daily backups with configurable retention using `offen/docker-volume-backup`
- **🔄 External Drive Sync**: Automatic backup synchronization to external storage
- **🏥 Health Monitoring**: Comprehensive health checks for all services
- **🌐 OrbStack Optimized**: Custom domains and networking for macOS
- **📊 Complete Stack**: PostgreSQL, ClickHouse, Redis, MinIO, and Langfuse services
- **🚦 Zero-Downtime Updates**: Rolling updates with automatic rollback
- **📝 Migration Support**: Seamless migration from existing Langfuse installations

## 🔗 Observability Integration

LLM observability that **integrates with [Grafana-OrbStack](../grafana-orbstack)** for complete AI system visibility.

### What Each System Provides

| Layer | Langfuse Provides | Grafana-OrbStack Provides |
|-------|------------------|--------------------------|
| **LLM** | Prompts, completions, token usage, costs | - |
| **Application** | LLM call traces, evaluations, scores | Service dependencies, distributed traces |
| **Infrastructure** | - | Container metrics, network I/O, resource usage |
| **Data** | - | GraphRAG performance, cache efficiency |
| **Automation** | - | Backup health, git hook triggers |

### Integration Features
- **Shared Trace IDs**: W3C Trace Context standard for end-to-end correlation
- **OTLP Export**: Langfuse traces visible in Grafana Tempo
- **Pre-configured Dashboards**: Ready-to-use Grafana dashboards for Langfuse metrics
- **Unified Debugging**: Link slow LLM responses to infrastructure bottlenecks

📚 **[Full Integration Guide](docs/INTEGRATION.md)** | 📊 **[Grafana Repository](../grafana-orbstack)**

## 🛡️ Security

![Gitleaks](https://img.shields.io/badge/protected%20by-gitleaks-blue)

This repository implements comprehensive secret scanning to prevent accidental exposure of credentials:

- **Pre-commit Hooks**: Blocks commits containing secrets locally
- **GitHub Actions**: Auto-closes PRs with detected secrets
- **1Password Integration**: All secrets stored securely, never in code

### Security Setup

```bash
# Install security tools and pre-commit hooks
make security-init

# Run manual security scan
make security-scan

# Test security detection
make security-test
```

For detailed security information, see [SECURITY.md](SECURITY.md) and the [Security Runbook](.security/RUNBOOK.md).

## 🛠 Prerequisites

### Required
- Docker Desktop or OrbStack (recommended for macOS)
- Docker Compose v2.x+
- 1Password account with CLI

### Installation

```bash
# macOS with Homebrew
brew install --cask docker        # Or OrbStack
brew install --cask 1password-cli

# Verify installations
docker --version
docker compose version
op --version
```

## 📦 Installation

### 1. Clone the Repository

```bash
git clone <your-repo-url> langfuse-deployment
cd langfuse-deployment
```

### 2. Initialize

```bash
make init
make security-init  # Install security hooks
```

This will:
- Make all scripts executable
- Check prerequisites
- Verify Docker installation
- Install pre-commit hooks for secret scanning

### 3. Configure 1Password Vault

Create a vault named `Langfuse-Prod` in 1Password with the following items:

#### PostgreSQL
- **Item Name**: PostgreSQL
- **Fields**:
  - `connection-string`: `postgresql://postgres:YOUR_PASSWORD@postgres:5432/postgres`
  - `password`: Strong password for PostgreSQL

#### Security
- **Item Name**: Security
- **Fields**:
  - `nextauth-secret`: Generate with `openssl rand -base64 32`
  - `salt`: Random salt string
  - `encryption-key`: Generate with `openssl rand -hex 32`

#### ClickHouse
- **Item Name**: ClickHouse
- **Fields**:
  - `password`: Strong password for ClickHouse

#### Redis
- **Item Name**: Redis
- **Fields**:
  - `password`: Strong password for Redis

#### MinIO
- **Item Name**: MinIO
- **Fields**:
  - `root-password`: MinIO admin password
  - `event-secret-key`: S3 secret key for events
  - `media-secret-key`: S3 secret key for media
  - `batch-secret-key`: S3 secret key for batch exports

#### API (Optional)
- **Item Name**: API
- **Fields**:
  - `public-key`: Langfuse public API key
  - `secret-key`: Langfuse secret API key

### 4. Deploy

```bash
make deploy
```

This will:
1. Check 1Password authentication
2. Inject secrets from 1Password
3. Pull required Docker images
4. Start all services with health checks
5. Clean up temporary secret files

## 🔐 Secret Management

### 1Password CLI Workflow

The deployment uses 1Password CLI to inject secrets at deployment time:

```bash
# Secret template → 1Password injection → Docker Compose
secrets/.env.1password.template → op inject → temporary .env → docker compose up
```

### Manual Secret Management (Alternative)

If you prefer not to use 1Password:

1. Copy the template:
   ```bash
   cp secrets/.env.1password.template secrets/.env.secrets
   ```

2. Replace all `op://` references with actual values

3. Deploy without 1Password:
   ```bash
   make up
   ```

## 📖 Usage

### Common Operations

```bash
# Deployment
make deploy              # Full deployment with 1Password
make deploy-no-backup    # Deploy without backup service
make up                  # Start with existing secrets

# Service Management
make stop               # Stop all services
make start              # Start stopped services
make restart            # Restart all services
make down               # Stop and remove containers

# Monitoring
make health             # Quick health check
make health-verbose     # Detailed health with resources
make ps                 # Show running containers
make logs               # Tail all logs
make logs-web          # Tail web service logs
make logs-errors       # Show recent errors

# Backups
make backup            # Manual backup
make backup-list       # List available backups
make restore           # Interactive restore
make backup-sync       # Sync to external drive

# Updates
make update-check      # Check for updates
make update            # Interactive update menu
make update-langfuse VERSION=3.98.0  # Update to specific version

# Database Access
make db-shell          # PostgreSQL shell
make clickhouse-shell  # ClickHouse shell
make redis-cli         # Redis CLI

# Utilities
make urls              # Show service URLs
make volumes           # List Docker volumes
make volume-sizes      # Show volume disk usage
make clean             # Clean stopped containers
```

### Service URLs

After deployment, services are available at:

| Service | URL | Purpose |
|---------|-----|---------|
| Langfuse Web | https://langfuse.local | Main application |
| MinIO Console | https://minio.local | Object storage UI |
| PostgreSQL | postgres.langfuse.local:5432 | Database |
| ClickHouse | https://clickhouse.local | Analytics database |
| Redis | redis.langfuse.local:6379 | Cache/Queue |

### Default Credentials

For development/testing with seed data:
- **Email**: demo@langfuse.com
- **Password**: password

## 💾 Backup & Restore

### Automated Backups

Backups run automatically at 2 AM daily using `offen/docker-volume-backup`:

- PostgreSQL data with pre-backup dump
- ClickHouse analytics data
- MinIO object storage
- Redis state (if configured)

### Configuration

Edit `backup/backup.conf`:

```bash
# Retention Policy
BACKUP_RETENTION_DAYS=7      # Daily backups
BACKUP_RETENTION_WEEKLY=4    # Weekly backups
BACKUP_RETENTION_MONTHLY=12  # Monthly backups

# Schedule (cron format)
BACKUP_CRON_DAILY="0 2 * * *"       # Daily at 2 AM
BACKUP_CRON_WEEKLY="0 3 * * 0"      # Weekly on Sunday
BACKUP_CRON_MONTHLY="0 4 1 * *"     # Monthly on 1st
```

### Manual Operations

```bash
# Create manual backup
make backup

# List backups
make backup-list

# Restore (interactive)
make restore

# Restore specific backup
./backup/restore.sh /path/to/backup.tar.gz
```

### External Drive Sync

Automatically sync to external drive when available:

```bash
# One-time sync
make backup-sync

# Monitor and sync when drive detected
make backup-monitor

# Check drive availability
./backup/external-drive-sync.sh check
```

## 🔄 Migration

### From Existing Langfuse Installation

If you have an existing Langfuse installation:

```bash
# Run migration wizard
make migrate
```

This will:
1. Create pre-migration backup
2. Extract secrets from old configuration
3. Stop old services (preserve volumes)
4. Guide through 1Password setup
5. Deploy from new repository
6. Verify deployment
7. Create migration report

### Manual Migration Steps

1. **Backup existing data**:
   ```bash
   cd /path/to/old/langfuse
   docker compose exec postgres pg_dump -U postgres > backup.sql
   ```

2. **Copy volumes** (if different project name):
   ```bash
   docker volume create langfuse-prod_langfuse_postgres_data
   docker run --rm -v old_postgres:/from -v langfuse-prod_langfuse_postgres_data:/to alpine cp -a /from/. /to
   ```

3. **Configure secrets in 1Password**

4. **Deploy new setup**:
   ```bash
   make deploy
   ```

## 🏗 Architecture

### Directory Structure

```
langfuse-deployment/
├── compose/                  # Docker Compose configurations
│   ├── docker-compose.yml          # Base services
│   ├── docker-compose.orbstack.yml # OrbStack optimizations
│   └── docker-compose.backup.yml   # Backup service
├── secrets/                  # Secret management
│   └── .env.1password.template     # 1Password references
├── backup/                   # Backup scripts
│   ├── backup.conf                 # Backup configuration
│   ├── restore.sh                  # Restore script
│   └── external-drive-sync.sh      # External sync
├── scripts/                  # Management scripts
│   ├── deploy.sh                   # Deployment with 1Password
│   ├── update.sh                   # Version updates
│   ├── health-check.sh             # Health monitoring
│   └── migrate.sh                  # Migration tool
├── versions.lock            # Pinned versions
├── Makefile                # Common operations
└── README.md               # This file
```

### Service Stack

| Service | Image | Version | Purpose |
|---------|-------|---------|---------|
| langfuse-web | langfuse/langfuse | 3.97.0 | Web application |
| langfuse-worker | langfuse/langfuse-worker | 3.97.0 | Background jobs |
| postgres | postgres | 15.7-alpine | Primary database |
| clickhouse | clickhouse/clickhouse-server | 24.3.3.102-alpine | Analytics |
| redis | redis | 7.2.5-alpine | Cache/Queue |
| minio | minio/minio | RELEASE.2024-08-17 | Object storage |
| backup | offen/docker-volume-backup | v2.43.0 | Automated backups |

### Data Persistence

All data is stored in Docker volumes:
- `langfuse_postgres_data` - PostgreSQL database
- `langfuse_clickhouse_data` - ClickHouse analytics
- `langfuse_clickhouse_logs` - ClickHouse logs
- `langfuse_minio_data` - Object storage

Backups are stored in:
- Primary: `~/LangfuseBackups/`
- External: `/Volumes/{DRIVE_NAME}/LangfuseBackups/`

## 🔧 Troubleshooting

### Common Issues

#### 1. 1Password CLI Not Authenticated

```bash
# Sign in to 1Password
op signin

# Verify authentication
op account list
```

#### 2. Port Conflicts

If port 3000 is already in use:
- Use OrbStack domains: `https://langfuse.local`
- Or modify port in `docker-compose.yml`

#### 3. Services Not Healthy

```bash
# Check detailed health
make health-verbose

# Check logs for errors
make logs-errors

# Restart services
make restart
```

#### 4. Backup Failures

```bash
# Check backup service logs
docker logs langfuse-prod-backup-1

# Verify volume mounts
make volumes

# Run manual backup with verbose output
docker compose run --rm backup-manual
```

#### 5. External Drive Not Writable (macOS)

```bash
# For read-only SanDisk issues
sudo mount -uw /Volumes/SanDisk

# Or use the fix script
./fix_sandisk_readonly.sh
```

### Getting Help

1. Check service logs:
   ```bash
   make logs
   ```

2. Run health check:
   ```bash
   make health-verbose
   ```

3. Check Langfuse documentation:
   - https://langfuse.com/docs
   - https://github.com/langfuse/langfuse

## 📝 Version History

| Date | Version | Changes |
|------|---------|---------|
| 2024-08-26 | 1.0.0 | Initial deployment repository |
| | | - Langfuse v3.97.0 |
| | | - 1Password integration |
| | | - Automated backups |
| | | - OrbStack optimizations |

## 🔒 Security Considerations

- **Secrets**: Never commit `.env` files or secrets to Git
- **1Password**: Use strong master password and 2FA
- **Network**: Services bound to localhost except web and MinIO
- **Backups**: Encrypt backups for sensitive data
- **Updates**: Regularly update all services for security patches

## 📄 License

This deployment configuration is provided as-is for use with Langfuse.
Langfuse itself is licensed under its own terms.

## 🤝 Contributing

Feel free to submit issues or pull requests for improvements to this deployment configuration.

---

**Made with ❤️ for reliable Langfuse deployments**
