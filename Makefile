# Langfuse Deployment Makefile
# Common operations for managing Langfuse deployment

# Variables
COMPOSE_PROJECT_NAME ?= langfuse-prod
COMPOSE_DIR = compose
COMPOSE_FILES = -f docker-compose.yml -f docker-compose.backup.yml
SCRIPTS_DIR = scripts
BACKUP_DIR = backup

# Colors for output
RED = \033[0;31m
GREEN = \033[0;32m
YELLOW = \033[1;33m
BLUE = \033[0;34m
NC = \033[0m # No Color

# Default target
.DEFAULT_GOAL := help

# Ensure scripts are executable
.PHONY: init
init: ## Initialize repository (make scripts executable, check prerequisites)
	@echo "$(BLUE)Initializing deployment repository...$(NC)"
	@chmod +x $(SCRIPTS_DIR)/*.sh
	@chmod +x $(BACKUP_DIR)/*.sh
	@echo "$(GREEN)✓ Scripts are now executable$(NC)"
	@echo "$(BLUE)Checking prerequisites...$(NC)"
	@command -v docker >/dev/null 2>&1 || { echo "$(RED)Docker is not installed$(NC)"; exit 1; }
	@command -v op >/dev/null 2>&1 || echo "$(YELLOW)⚠ 1Password CLI not installed (optional)$(NC)"
	@echo "$(GREEN)✓ Initialization complete$(NC)"

# Deployment operations
.PHONY: deploy
deploy: ## Deploy Langfuse with 1Password secrets injection
	@echo "$(BLUE)Deploying Langfuse...$(NC)"
	@$(SCRIPTS_DIR)/deploy.sh

.PHONY: deploy-no-backup
deploy-no-backup: ## Deploy without backup service
	@echo "$(BLUE)Deploying Langfuse without backup service...$(NC)"
	@$(SCRIPTS_DIR)/deploy.sh core

.PHONY: up
up: ## Start services without 1Password (requires .env.secrets)
	@echo "$(BLUE)Starting services...$(NC)"
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) up -d

.PHONY: down
down: ## Stop and remove containers (preserves volumes)
	@echo "$(YELLOW)Stopping services...$(NC)"
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) down

.PHONY: stop
stop: ## Stop services without removing containers
	@echo "$(YELLOW)Stopping services...$(NC)"
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) stop

.PHONY: start
start: ## Start stopped services
	@echo "$(BLUE)Starting services...$(NC)"
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) start

.PHONY: restart
restart: stop start ## Restart all services
	@echo "$(GREEN)✓ Services restarted$(NC)"

# Health and monitoring
.PHONY: health
health: ## Check health status of all services
	@$(SCRIPTS_DIR)/health-check.sh

.PHONY: health-verbose
health-verbose: ## Detailed health check with resource usage
	@$(SCRIPTS_DIR)/health-check.sh --verbose

.PHONY: ps
ps: ## Show running containers
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) ps

.PHONY: logs
logs: ## Tail logs from all services
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) logs -f

.PHONY: logs-web
logs-web: ## Tail logs from Langfuse web service
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) logs -f langfuse-web

.PHONY: logs-worker
logs-worker: ## Tail logs from Langfuse worker service
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) logs -f langfuse-worker

.PHONY: logs-errors
logs-errors: ## Show recent errors from all services
	@echo "$(YELLOW)Recent errors (last 30 minutes):$(NC)"
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) logs --since 30m 2>&1 | grep -iE "error|fatal|panic|exception" || echo "$(GREEN)No errors found$(NC)"

# Backup operations
.PHONY: backup
backup: ## Trigger manual backup
	@echo "$(BLUE)Starting manual backup...$(NC)"
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) run --rm backup-manual
	@echo "$(GREEN)✓ Backup completed$(NC)"

.PHONY: backup-list
backup-list: ## List available backups
	@echo "$(BLUE)Available backups:$(NC)"
	@ls -lht ~/LangfuseBackups/langfuse-*.tar.gz 2>/dev/null | head -20 || echo "$(YELLOW)No backups found$(NC)"

.PHONY: restore
restore: ## Restore from backup (interactive)
	@echo "$(YELLOW)Starting restore process...$(NC)"
	@$(BACKUP_DIR)/restore.sh

.PHONY: backup-sync
backup-sync: ## Sync backups to external drive
	@echo "$(BLUE)Syncing to external drive...$(NC)"
	@$(BACKUP_DIR)/external-drive-sync.sh sync

.PHONY: backup-monitor
backup-monitor: ## Monitor for external drive and sync
	@echo "$(BLUE)Monitoring for external drive...$(NC)"
	@$(BACKUP_DIR)/external-drive-sync.sh monitor

# Update operations
.PHONY: update-check
update-check: ## Check for Langfuse updates
	@$(SCRIPTS_DIR)/update.sh check

.PHONY: update
update: ## Interactive update menu
	@$(SCRIPTS_DIR)/update.sh interactive

.PHONY: update-langfuse
update-langfuse: ## Update Langfuse to specific version (use: make update-langfuse VERSION=3.98.0)
	@if [ -z "$(VERSION)" ]; then \
		echo "$(RED)Error: VERSION not specified$(NC)"; \
		echo "Usage: make update-langfuse VERSION=3.98.0"; \
		exit 1; \
	fi
	@$(SCRIPTS_DIR)/update.sh apply LANGFUSE $(VERSION)

# Migration operations
.PHONY: migrate
migrate: ## Migrate from old Langfuse setup
	@echo "$(BLUE)Starting migration...$(NC)"
	@$(SCRIPTS_DIR)/migrate.sh

# Database operations
.PHONY: db-shell
db-shell: ## Open PostgreSQL shell
	@echo "$(BLUE)Connecting to PostgreSQL...$(NC)"
	@docker exec -it $(COMPOSE_PROJECT_NAME)-postgres-1 psql -U postgres

.PHONY: clickhouse-shell
clickhouse-shell: ## Open ClickHouse shell
	@echo "$(BLUE)Connecting to ClickHouse...$(NC)"
	@docker exec -it $(COMPOSE_PROJECT_NAME)-clickhouse-1 clickhouse-client

.PHONY: redis-cli
redis-cli: ## Open Redis CLI
	@echo "$(BLUE)Connecting to Redis...$(NC)"
	@docker exec -it $(COMPOSE_PROJECT_NAME)-redis-1 redis-cli

# Volume operations
.PHONY: volumes
volumes: ## List Docker volumes
	@echo "$(BLUE)Langfuse volumes:$(NC)"
	@docker volume ls --filter "label=com.docker.compose.project=$(COMPOSE_PROJECT_NAME)"

.PHONY: volume-sizes
volume-sizes: ## Show volume disk usage
	@echo "$(BLUE)Volume sizes:$(NC)"
	@for vol in $$(docker volume ls --filter "label=com.docker.compose.project=$(COMPOSE_PROJECT_NAME)" -q); do \
		size=$$(docker run --rm -v $$vol:/data alpine du -sh /data 2>/dev/null | cut -f1); \
		echo "  $$vol: $$size"; \
	done

# Cleanup operations
.PHONY: clean
clean: ## Remove stopped containers and unused networks
	@echo "$(YELLOW)Cleaning up...$(NC)"
	@docker system prune -f
	@echo "$(GREEN)✓ Cleanup complete$(NC)"

.PHONY: clean-all
clean-all: ## Remove everything including volumes (DESTRUCTIVE!)
	@echo "$(RED)WARNING: This will delete all data!$(NC)"
	@echo "Type 'destroy' to confirm:"
	@read confirm && [ "$$confirm" = "destroy" ] || { echo "Cancelled"; exit 1; }
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) down -v
	@echo "$(RED)All containers and volumes removed$(NC)"

# Secrets management
.PHONY: secrets-check
secrets-check: ## Check 1Password configuration
	@echo "$(BLUE)Checking 1Password setup...$(NC)"
	@command -v op >/dev/null 2>&1 || { echo "$(RED)1Password CLI not installed$(NC)"; exit 1; }
	@op account list >/dev/null 2>&1 || { echo "$(YELLOW)Not signed in to 1Password$(NC)"; exit 1; }
	@echo "$(GREEN)✓ 1Password is configured$(NC)"

.PHONY: secrets-template
secrets-template: ## Show secret template structure
	@echo "$(BLUE)1Password secret template:$(NC)"
	@cat secrets/.env.1password.template

# Development helpers
.PHONY: exec-web
exec-web: ## Execute shell in web container
	@docker exec -it $(COMPOSE_PROJECT_NAME)-langfuse-web-1 sh

.PHONY: exec-worker
exec-worker: ## Execute shell in worker container
	@docker exec -it $(COMPOSE_PROJECT_NAME)-langfuse-worker-1 sh

.PHONY: pull
pull: ## Pull latest images
	@echo "$(BLUE)Pulling latest images...$(NC)"
	@cd $(COMPOSE_DIR) && docker compose $(COMPOSE_FILES) -p $(COMPOSE_PROJECT_NAME) pull

# URLs and access
.PHONY: urls
urls: ## Show service URLs
	@echo "$(BLUE)Service URLs:$(NC)"
	@echo "  Langfuse Web:  $(GREEN)https://langfuse.local$(NC)"
	@echo "  MinIO Console: $(GREEN)https://minio.local$(NC)"
	@echo "  PostgreSQL:    $(GREEN)postgres.langfuse.local:5432$(NC)"
	@echo "  ClickHouse:    $(GREEN)https://clickhouse.local$(NC)"
	@echo "  Redis:         $(GREEN)redis.langfuse.local:6379$(NC)"
	@echo ""
	@echo "$(BLUE)Default credentials:$(NC)"
	@echo "  Email:    demo@langfuse.com"
	@echo "  Password: password"

# Git operations
.PHONY: git-status
git-status: ## Show git status
	@git status

.PHONY: git-commit
git-commit: ## Commit changes
	@git add -A && git commit

# Help target
.PHONY: help
help: ## Show this help message
	@echo "$(BLUE)Langfuse Deployment Makefile$(NC)"
	@echo "=============================="
	@echo ""
	@echo "$(GREEN)Available targets:$(NC)"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  $(BLUE)%-20s$(NC) %s\n", $$1, $$2}'
	@echo ""
	@echo "$(YELLOW)Examples:$(NC)"
	@echo "  make deploy           # Deploy with 1Password"
	@echo "  make health          # Check service health"
	@echo "  make backup          # Create manual backup"
	@echo "  make logs            # View all logs"
	@echo "  make update-check    # Check for updates"

# Shortcuts
.PHONY: h
h: help ## Alias for help

.PHONY: d
d: deploy ## Alias for deploy

.PHONY: l
l: logs ## Alias for logs

.PHONY: b
b: backup ## Alias for backup