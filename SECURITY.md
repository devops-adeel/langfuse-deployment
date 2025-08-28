# Security Policy

## 🔐 Secret Management

This repository implements strict secret management to prevent accidental exposure of sensitive credentials.

### Approach

1. **All secrets stored in 1Password** - Never hardcode credentials
2. **Use secret references** - `op://vault/item/field` format
3. **Pre-commit scanning** - Blocks commits with detected secrets
4. **CI/CD enforcement** - Auto-closes PRs with exposed secrets
5. **Incident tracking** - Local logging of all detection events

### Monitored Secret Patterns

| Type | Pattern | Severity |
|------|---------|----------|
| Langfuse Public Key | `pk-lf-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` | High |
| Langfuse Secret Key | `sk-lf-[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}` | Critical |
| PostgreSQL Password | Connection strings with embedded passwords | Critical |
| ClickHouse Password | `CLICKHOUSE_PASSWORD=...` | Critical |
| MinIO/S3 Keys | `MINIO_*_SECRET`, `S3_*_SECRET` | Critical |
| Redis Auth | `REDIS_AUTH`, `REDIS_PASSWORD` | High |
| Encryption Keys | `ENCRYPTION_KEY`, `SALT`, `NEXTAUTH_SECRET` | Critical |
| SSH Private Keys | SSH private key headers (RSA/DSA/EC) | Critical |

### Allowed Patterns

The following patterns are explicitly allowed and will not trigger alerts:

- **1Password references**: `op://vault/item/field`
- **Environment variables**: `${VARIABLE_NAME}`
- **Placeholders**: `your-password-here`, `PLACEHOLDER_*`, `CHANGE_ME`
- **Test credentials**: `*-test-*` patterns

## 🛡️ Reporting Security Issues

### For Secret Exposure

If you discover exposed secrets:

1. **Do NOT** create a public issue
2. **Immediately** rotate the affected credentials
3. Follow the [Security Runbook](.security/RUNBOOK.md)
4. Contact the repository owner directly

### For Security Vulnerabilities

To report security vulnerabilities:

1. **Do NOT** create a public issue
2. Email security concerns to the repository owner
3. Include:
   - Description of the vulnerability
   - Steps to reproduce
   - Potential impact
   - Suggested remediation

## 🚀 Security Setup

### Prerequisites

- Python 3.x with pip
- 1Password CLI (`op`) installed and configured
- Git 2.x or higher

### Installation

```bash
# Install security tools
make security-init

# This will:
# 1. Install pre-commit framework
# 2. Configure git hooks
# 3. Verify Gitleaks is available
```

### Usage

```bash
# Run security scan manually
make security-scan

# Test with a dummy secret
make security-test

# View recent incidents
make security-log

# Audit entire repository
make security-audit
```

## 🔍 Security Tools

### Pre-commit Hooks

- **Gitleaks**: Scans for hardcoded secrets and credentials
- **detect-private-key**: Prevents committing SSH/GPG private keys
- **check-added-large-files**: Blocks files >1MB
- **YAML/JSON validation**: Ensures configuration integrity

### GitHub Actions

- Runs on all pushes and pull requests
- Daily scheduled scans for comprehensive coverage
- Automatic PR closure on secret detection
- Security issue creation with remediation steps

### Local Scanning

```bash
# Scan entire repository
gitleaks detect -s . -c .gitleaks.toml

# Scan staged changes
gitleaks protect -s . -c .gitleaks.toml

# Scan specific file
gitleaks detect -s path/to/file
```

## 📋 Security Checklist

### For Contributors

- [ ] Pre-commit hooks installed (`pre-commit install`)
- [ ] Using 1Password CLI for secrets
- [ ] Never copying actual secret values
- [ ] Running `make security-scan` before pushing
- [ ] Reviewing AI-generated code for embedded secrets

### For Maintainers

- [ ] GitHub Actions secret scanning enabled
- [ ] Branch protection rules configured
- [ ] Regular security audits performed
- [ ] Incident log reviewed monthly
- [ ] Dependencies kept up to date

## 🆘 Emergency Procedures

### If Secrets Are Exposed

1. **Rotate immediately** in 1Password
2. **Update all services** using the credentials
3. **Document incident** in `.security/incidents.log`
4. **Clean git history** if necessary (see Runbook)

### Quick Commands

```bash
# Check if you have secrets in uncommitted changes
gitleaks protect --staged

# Scan last 10 commits
gitleaks detect --log-opts="-10"

# Generate security report
gitleaks detect -r report.json -f json
```

## 📚 Resources

- [Security Runbook](.security/RUNBOOK.md) - Detailed incident response
- [1Password CLI](https://developer.1password.com/docs/cli/) - Secret management
- [Gitleaks](https://github.com/gitleaks/gitleaks) - Secret detection
- [Pre-commit](https://pre-commit.com/) - Git hook framework

## 🏆 Best Practices

1. **Never hardcode secrets** - Always use 1Password references
2. **Use environment variables** - `${VAR}` in Docker Compose
3. **Rotate regularly** - Even without exposure
4. **Review AI code** - Claude Code may embed secrets
5. **Test with dummy data** - Use test credentials for development

## 📊 Metrics

Security scanning is performed:
- **Every commit** (pre-commit hooks)
- **Every push** (GitHub Actions)
- **Daily** (scheduled scans)
- **On-demand** (`make security-scan`)

Target response times:
- **Detection**: < 1 second (pre-commit)
- **Rotation**: < 15 minutes (on exposure)
- **Remediation**: < 1 hour (full cleanup)

---

**Remember**: Security is everyone's responsibility. When in doubt, ask for help.
