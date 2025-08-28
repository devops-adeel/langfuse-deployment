# Security Incident Response Runbook

## 🚨 Secret Exposure Response

### Immediate Actions (Within 15 minutes)

#### 1. Identify the Exposed Secret
```bash
# Check recent commits for secrets
git log --oneline -10

# Run local scan to identify all secrets
make security-scan

# Check specific file
gitleaks detect -s path/to/file
```

#### 2. Determine Exposure Scope
- [ ] Was the secret pushed to GitHub?
- [ ] How long was it exposed?
- [ ] Which services use this credential?
- [ ] Is the repository public?

### Remediation Steps

#### If Secret Was NOT Pushed to GitHub

1. **Reset to before the secret was added:**
   ```bash
   git reset --soft HEAD~1  # Undo last commit, keep changes
   ```

2. **Remove the secret from files:**
   ```bash
   # Find all occurrences
   grep -r "sk-lf-" . --exclude-dir=.git

   # Edit files to use 1Password references
   vim affected-file.env
   ```

3. **Verify clean:**
   ```bash
   make security-test
   pre-commit run --all-files
   ```

#### If Secret WAS Pushed to GitHub

1. **Rotate the credential IMMEDIATELY in 1Password:**
   - Open 1Password
   - Find the compromised item
   - Generate new password/key
   - Save with timestamp note

2. **Update all services:**
   ```bash
   # Inject new secrets and restart services
   cd ~/Documents/1_projects/langfuse-deployment
   op inject -i secrets/.env.1password.core -o .env
   docker compose down
   docker compose up -d
   ```

3. **Remove from Git history (if needed):**
   ```bash
   # For recent commits (last few)
   git rebase -i HEAD~3
   # Mark commit with secret as 'edit'
   # Remove secret when prompted
   # Continue rebase

   # For deeper history - use BFG Repo-Cleaner
   brew install bfg
   bfg --delete-files .env
   bfg --replace-text passwords.txt  # File with secrets to remove
   git push --force
   ```

4. **Document the incident:**
   ```bash
   echo "[$(date)] Secret exposed: [TYPE] in [FILE] by [USER]" >> .security/incidents.log
   ```

### Prevention Checklist

#### Initial Setup (One time)
- [ ] Install pre-commit hooks: `make security-init`
- [ ] Test detection works: `make security-test`
- [ ] Configure Git to use 1Password: `op plugin init git`

#### Before Every Commit
- [ ] Never copy actual secret values
- [ ] Use `op://` references exclusively
- [ ] Run `make security-scan` if unsure

#### Common Mistakes to Avoid

1. **Claude Code retrieving secrets:**
   - Never let AI tools run `op inject` or `op read`
   - Always review AI-generated environment files
   - Check for hardcoded values before committing

2. **Testing with real secrets:**
   - Use test credentials (sk-lf-test-*)
   - Keep production secrets only in 1Password

3. **Docker Compose files:**
   - Use `${VARIABLE}` syntax
   - Never hardcode credentials

## 📊 Incident Log Format

Create entries in `.security/incidents.log`:

```
[YYYY-MM-DD HH:MM:SS] BLOCKED|EXPOSED
Type: <secret-type>
File: <filepath>
Line: <line-number>
Action: <action-taken>
Rotated: YES|NO|N/A
---
```

## 🔍 Detection Commands

### Manual Scanning
```bash
# Full repository scan
gitleaks detect -s . -c .gitleaks.toml

# Scan specific commit
gitleaks detect -s . --commit=<SHA>

# Scan uncommitted changes
gitleaks protect -s . -c .gitleaks.toml

# Scan with verbose output
gitleaks detect -s . -v
```

### Check Git History
```bash
# Search for Langfuse keys in history
git log -p -S "sk-lf-"

# Search for any potential secrets
git secrets --scan-history
```

## 🛠️ Recovery Tools

### BFG Repo-Cleaner (for history rewriting)
```bash
# Install
brew install bfg

# Remove specific strings
echo "sk-lf-actual-secret-here" > passwords.txt
bfg --replace-text passwords.txt
git push --force

# Remove files
bfg --delete-files .env
```

### Git Filter-Branch (alternative)
```bash
git filter-branch --force --index-filter \
  "git rm --cached --ignore-unmatch .env" \
  --prune-empty --tag-name-filter cat -- --all
```

## 📞 Escalation Path

1. **Low Risk** (blocked by pre-commit): Log and continue
2. **Medium Risk** (in local commits): Reset and clean
3. **High Risk** (pushed to GitHub): Rotate immediately
4. **Critical** (exposed in public repo > 1 hour):
   - Rotate ALL related credentials
   - Audit access logs
   - Consider security audit

## 🔗 Resources

- [1Password CLI Docs](https://developer.1password.com/docs/cli/)
- [Gitleaks Documentation](https://github.com/gitleaks/gitleaks)
- [GitHub: Removing sensitive data](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)
- [BFG Repo-Cleaner](https://rtyley.github.io/bfg-repo-cleaner/)

## ⚡ Quick Commands

```bash
# Emergency secret rotation
make security-rotate

# Full security audit
make security-audit

# Test with dummy secret
echo "sk-lf-""12345678""-1234-1234-1234-""123456789012" | gitleaks protect --stdin

# Check if hooks are installed
ls -la .git/hooks/pre-commit
```

---

**Remember:** Speed matters when secrets are exposed. Act immediately, rotate first, investigate second.
