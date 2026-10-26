# CLAUDE.md: Langfuse infra role (role 1)

This role owns how Langfuse **runs**: compose, images, upgrades, backups, restores, env and
secrets. It does not own what is configured inside Langfuse (role 2, admin) or trace analysis
(role 3, analyst). Full brief: `.claude/agents/langfuse-infra.md`.

## Canonical paths
- This repo (infra): `~/Developer/langfuse-deployment`
- Live compose dir: `~/Documents/1-projects/langfuse` (project `langfuse`, files `docker-compose.yml` + untracked `docker-compose.override.yml`)
- Admin: `~/Developer/langfuse-config` · Analyst: `~/Developer/hermes-agent`
- Langfuse from this sandboxed session: `http://lf.estate:3000` (infra proxy `:3193`)
- Backups: `~/LangfuseBackups/<stamp>/manifest.txt`, the most reliable record of live state

`~/1-projects/*` and `~/.hermes/scripts/*` are symlinks into these paths. Use the canonical paths.

## Rules the harness does not enforce
The sandbox lets you write to the live compose dir, and `docker` runs unsandboxed. These rules hold only because you follow them:
- **Never** run `git clean`, `docker compose down`, or file edits in the live compose dir unless the user asks for that specific action.
- Always pass **both** compose files. Without the override, ClickHouse is downgraded from 26.3 to 25.12, and that corrupts it.
- Leave background migration step 5 (`drop_pid_tid_sorting_tables`) alone. It is irreversible.
- Don't create or change Langfuse content (prompts, evaluators, dashboards, monitors). Don't use `docker exec … psql` to write to the database.
- Don't use docker to reach outside this role (mounting or editing other roles' repos or `~/Developer/lf-estate`).
- After any server version change, run both of these and report the result:
  `python ~/Developer/langfuse-config/tools/langfuse_monitor_provision.py verify` and
  `python ~/Developer/hermes-agent/evals/lf_compat.py` (exit 0 = safe).
- Take a backup and read the latest manifest before any upgrade.
- Add no new secrets while `SALT`, `ENCRYPTION_KEY`, `NEXTAUTH_SECRET`, `CLICKHOUSE_PASSWORD` and `REDIS_AUTH` are still upstream defaults.

## How to run things
- Live stack, read-only: `docker compose -p langfuse ps` and `docker compose -p langfuse logs -f <svc>`.
- Live stack, changes: `docker compose --project-directory ~/Documents/1-projects/langfuse -f ~/Documents/1-projects/langfuse/docker-compose.yml -f ~/Documents/1-projects/langfuse/docker-compose.override.yml <cmd>`.
- Start each command with `docker`. A compound command (`cd … && docker …`) runs inside the sandbox, where the docker socket is denied.
- Health: `curl -s http://lf.estate:3000/api/public/health`. Estate tooling: `~/Developer/lf-estate/plugins/lf-estate/bin/lf-estate …` (absolute path only).
- `make` targets and `compose/` drive this repo's **`langfuse-prod`** stack (pinned at 3.97.0), which runs nothing. Don't point them at production.

## Reference (moved from the old CLAUDE.md)
- `.claude/rules/compose.md`, `secrets.md`, `backup.md`: load when you touch those paths.
- `docs/LANGFUSE-PROD-REFERENCE.md`: Make targets, migration, troubleshooting, Grafana correlation.
