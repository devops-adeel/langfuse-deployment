---
paths:
  - "backup/**"
  - "compose/docker-compose.backup.yml"
---

# Backup and restore (langfuse-prod)

> Moved from CLAUDE.md. Describes **this repo's `langfuse-prod` stack** (`compose/`, `Makefile`),
> which runs nothing. The live stack is compose project `langfuse` in
> `~/Documents/1-projects/langfuse`. See CLAUDE.md.

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

## Backup Troubleshooting

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

