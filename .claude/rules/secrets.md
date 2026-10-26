---
paths:
  - "secrets/**"
  - "scripts/deploy.sh"
  - "scripts/migrate.sh"
  - ".security/**"
  - ".github/**"
  - ".gitleaks.toml"
  - ".pre-commit-config.yaml"
  - "SECURITY.md"
---

# Secrets and security (langfuse-prod)

> Moved from CLAUDE.md. Describes **this repo's `langfuse-prod` stack** (`compose/`, `Makefile`),
> which runs nothing. The live stack is compose project `langfuse` in
> `~/Documents/1-projects/langfuse`. See CLAUDE.md.

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

