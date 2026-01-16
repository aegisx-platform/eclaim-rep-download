.PHONY: help setup build pull up down restart logs shell db-shell clean test migrate seed release import-rep import-stm import-smt reimport-all

# Configuration
COMPOSE_FILE ?= docker-compose.yml
COMPOSE_MYSQL = docker-compose-mysql.yml
COMPOSE_NO_DB = docker-compose-no-db.yml

# Colors for output
BOLD := $(shell tput bold)
GREEN := $(shell tput setaf 2)
YELLOW := $(shell tput setaf 3)
CYAN := $(shell tput setaf 6)
RESET := $(shell tput sgr0)

# Default target
.DEFAULT_GOAL := help

help:
	@echo "$(BOLD)E-Claim Downloader - Make Commands$(RESET)"
	@echo ""
	@echo "$(CYAN)Setup & Installation:$(RESET)"
	@echo "  make setup          - Initial setup (copy .env, create dirs)"
	@echo "  make setup-prod     - Setup for production (with VERSION)"
	@echo "  make setup-dev      - Setup for development (build mode)"
	@echo ""
	@echo "$(CYAN)Docker Management:$(RESET)"
	@echo "  make pull           - Pull latest Docker images from registry"
	@echo "  make build          - Build Docker images from source"
	@echo "  make up             - Start all services (default: PostgreSQL)"
	@echo "  make up-mysql       - Start with MySQL database"
	@echo "  make up-no-db       - Start without database (download only)"
	@echo "  make down           - Stop all services"
	@echo "  make restart        - Restart all services"
	@echo "  make restart-web    - Restart only web service"
	@echo ""
	@echo "$(CYAN)Logs & Monitoring:$(RESET)"
	@echo "  make logs           - View all logs (follow mode)"
	@echo "  make logs-web       - View Flask logs"
	@echo "  make logs-db        - View database logs"
	@echo "  make ps             - Show running containers"
	@echo "  make stats          - Show resource usage"
	@echo "  make health         - Check service health"
	@echo ""
	@echo "$(CYAN)Shell Access:$(RESET)"
	@echo "  make shell          - Access web container shell"
	@echo "  make shell-db       - Access database shell"
	@echo "  make python         - Open Python REPL in web container"
	@echo ""
	@echo "$(CYAN)Database Operations:$(RESET)"
	@echo "  make migrate        - Run database migrations"
	@echo "  make migrate-status - Check migration status"
	@echo "  make seed           - Import health offices seed data"
	@echo "  make seed-error-codes - Import NHSO error codes"
	@echo "  make seed-all       - Import all seed data"
	@echo "  make db-backup      - Backup database to backups/"
	@echo "  make db-restore     - Restore from backup.sql"
	@echo "  make db-reset       - Reset database (WARNING: deletes data)"
	@echo "  make db-status      - Show database status & record counts"
	@echo ""
	@echo "$(CYAN)Import & Download:$(RESET)"
	@echo "  make import-rep     - Import REP files from downloads/rep/"
	@echo "  make import-stm     - Import STM files from downloads/stm/"
	@echo "  make import-smt     - Fetch and import SMT budget from API"
	@echo "  make reimport-all   - Re-import all data (REP + STM + SMT)"
	@echo "  make import-file    - Import single file (FILE=path)"
	@echo "  make scan-files     - Scan downloads/ and register files to history"
	@echo "  make download       - Run manual download"
	@echo ""
	@echo "$(CYAN)Admin Tools:$(RESET)"
	@echo "  make pgadmin        - Start pgAdmin (PostgreSQL)"
	@echo "  make phpmyadmin     - Start phpMyAdmin (MySQL)"
	@echo "  make stop-admin     - Stop admin tools"
	@echo ""
	@echo "$(CYAN)Version Management:$(RESET)"
	@echo "  make version        - Show current version"
	@echo "  make update         - Update to newer version"
	@echo "  make update-latest  - Update to latest version"
	@echo ""
	@echo "$(CYAN)Release (Dev only):$(RESET)"
	@echo "  make release-patch  - Release patch version (x.y.Z)"
	@echo "  make release-minor  - Release minor version (x.Y.0)"
	@echo "  make release-major  - Release major version (X.0.0)"
	@echo "  make release V=x.y.z - Release specific version"
	@echo ""
	@echo "$(CYAN)Maintenance:$(RESET)"
	@echo "  make clean          - Remove containers and networks"
	@echo "  make clean-all      - Remove everything including volumes"
	@echo "  make clean-logs     - Clean old log files"
	@echo ""
	@echo "$(CYAN)Development:$(RESET)"
	@echo "  make dev            - Start in development mode (hot reload)"
	@echo "  make test           - Run tests"
	@echo "  make lint           - Run linters"
	@echo ""
	@echo "$(YELLOW)Examples:$(RESET)"
	@echo "  make setup && make up              # First time setup"
	@echo "  make import-file FILE=downloads/file.xls"
	@echo "  make update VERSION=v2.1.0         # Update to specific version"

# ==================== Setup Commands ====================

setup:
	@echo "$(BOLD)$(GREEN)==> Setting up E-Claim Downloader...$(RESET)"
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "$(GREEN)✓$(RESET) Created .env file"; \
		echo "$(YELLOW)⚠ PLEASE UPDATE CREDENTIALS in .env!$(RESET)"; \
	else \
		echo "$(GREEN)✓$(RESET) .env file exists"; \
	fi
	@mkdir -p downloads logs backups config
	@echo "$(GREEN)✓$(RESET) Created directories"
	@echo ""
	@echo "$(BOLD)Next steps:$(RESET)"
	@echo "  1. Edit .env and set ECLAIM_USERNAME and ECLAIM_PASSWORD"
	@echo "  2. Choose deployment mode:"
	@echo "     - Production: make setup-prod"
	@echo "     - Development: make setup-dev"

setup-prod:
	@echo "$(BOLD)$(GREEN)==> Production Setup$(RESET)"
	@$(MAKE) setup
	@if ! grep -q "^VERSION=" .env; then \
		echo "VERSION=latest" >> .env; \
		echo "$(GREEN)✓$(RESET) Added VERSION=latest to .env"; \
	fi
	@echo ""
	@echo "$(BOLD)Ready for production!$(RESET)"
	@echo "Run: make pull && make up"

setup-dev:
	@echo "$(BOLD)$(GREEN)==> Development Setup$(RESET)"
	@$(MAKE) setup
	@echo ""
	@echo "$(BOLD)Ready for development!$(RESET)"
	@echo "Run: make build && make dev"

# ==================== Docker Management ====================

pull:
	@echo "$(BOLD)$(GREEN)==> Pulling Docker images from registry...$(RESET)"
	docker-compose pull
	@echo "$(GREEN)✓$(RESET) Images pulled successfully"

build:
	@echo "$(BOLD)$(GREEN)==> Building Docker images from source...$(RESET)"
	docker-compose build --no-cache
	@echo "$(GREEN)✓$(RESET) Build complete"

up:
	@echo "$(BOLD)$(GREEN)==> Starting services (PostgreSQL)...$(RESET)"
	docker-compose up -d
	@sleep 3
	@$(MAKE) health
	@echo ""
	@echo "$(GREEN)✓ Services started!$(RESET)"
	@echo "  $(CYAN)Web UI:$(RESET)    http://localhost:5001"
	@echo "  $(CYAN)Database:$(RESET)  postgresql://localhost:5432/eclaim_db"
	@echo ""
	@echo "Run '$(BOLD)make logs$(RESET)' to view logs"
	@echo "Run '$(BOLD)make pgadmin$(RESET)' to start database admin UI"

up-mysql:
	@echo "$(BOLD)$(GREEN)==> Starting services (MySQL)...$(RESET)"
	docker-compose -f $(COMPOSE_MYSQL) up -d
	@sleep 3
	@echo "$(GREEN)✓ Services started!$(RESET)"
	@echo "  $(CYAN)Web UI:$(RESET)    http://localhost:5001"
	@echo "  $(CYAN)Database:$(RESET)  mysql://localhost:3306/eclaim_db"
	@echo ""
	@echo "Run '$(BOLD)make phpmyadmin$(RESET)' to start database admin UI"

up-no-db:
	@echo "$(BOLD)$(GREEN)==> Starting services (No Database)...$(RESET)"
	docker-compose -f $(COMPOSE_NO_DB) up -d
	@sleep 2
	@echo "$(GREEN)✓ Services started!$(RESET)"
	@echo "  $(CYAN)Web UI:$(RESET) http://localhost:5001"
	@echo ""
	@echo "$(YELLOW)Note:$(RESET) Running in download-only mode (no database import)"

down:
	@echo "$(BOLD)==> Stopping services...$(RESET)"
	docker-compose down
	docker-compose -f $(COMPOSE_MYSQL) down 2>/dev/null || true
	docker-compose -f $(COMPOSE_NO_DB) down 2>/dev/null || true
	@echo "$(GREEN)✓$(RESET) Services stopped"

restart:
	@echo "$(BOLD)==> Restarting all services...$(RESET)"
	docker-compose restart
	@echo "$(GREEN)✓$(RESET) Services restarted"

restart-web:
	@echo "$(BOLD)==> Restarting web service...$(RESET)"
	docker-compose restart web
	@echo "$(GREEN)✓$(RESET) Web service restarted"

# ==================== Logs & Monitoring ====================

logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

logs-db:
	docker-compose logs -f db

ps:
	@echo "$(BOLD)Container Status:$(RESET)"
	@docker-compose ps

stats:
	@echo "$(BOLD)Resource Usage:$(RESET)"
	@docker stats --no-stream

health:
	@echo "$(BOLD)Health Check:$(RESET)"
	@docker-compose ps | grep -q "Up (healthy)" && \
		echo "$(GREEN)✓$(RESET) All services healthy" || \
		echo "$(YELLOW)⚠$(RESET) Some services not ready yet"

# ==================== Shell Access ====================

shell:
	@echo "$(BOLD)==> Accessing web container shell...$(RESET)"
	docker-compose exec web bash

shell-db:
	@echo "$(BOLD)==> Accessing database shell...$(RESET)"
	@if docker-compose ps | grep -q postgres; then \
		docker-compose exec db psql -U eclaim -d eclaim_db; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q mysql; then \
		docker-compose -f $(COMPOSE_MYSQL) exec db mysql -u eclaim -p eclaim_db; \
	else \
		echo "$(YELLOW)No database running$(RESET)"; \
	fi

python:
	@echo "$(BOLD)==> Opening Python REPL...$(RESET)"
	docker-compose exec web python

# ==================== Database Operations ====================

migrate:
	@echo "$(BOLD)$(GREEN)==> Running database migrations...$(RESET)"
	@if docker-compose ps | grep -q "web.*Up"; then \
		docker-compose exec web python database/migrate.py; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q "web.*Up"; then \
		docker-compose -f $(COMPOSE_MYSQL) exec web python database/migrate.py; \
	else \
		echo "$(YELLOW)No web container running. Start with: make up$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) Migrations complete"

migrate-status:
	@echo "$(BOLD)$(GREEN)==> Checking migration status...$(RESET)"
	@if docker-compose ps | grep -q "web.*Up"; then \
		docker-compose exec web python database/migrate.py --status; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q "web.*Up"; then \
		docker-compose -f $(COMPOSE_MYSQL) exec web python database/migrate.py --status; \
	else \
		echo "$(YELLOW)No web container running. Start with: make up$(RESET)"; \
		exit 1; \
	fi

seed:
	@echo "$(BOLD)$(GREEN)==> Importing health offices seed data...$(RESET)"
	@if docker-compose ps | grep -q "web.*Up"; then \
		docker-compose exec web python database/seeds/health_offices_importer.py; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q "web.*Up"; then \
		docker-compose -f $(COMPOSE_MYSQL) exec web python database/seeds/health_offices_importer.py; \
	else \
		echo "$(YELLOW)No web container running. Start with: make up$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) Seed data import complete"

seed-error-codes:
	@echo "$(BOLD)$(GREEN)==> Importing NHSO error codes...$(RESET)"
	@if docker-compose ps | grep -q "web.*Up"; then \
		docker-compose exec web python database/seeds/nhso_error_codes_importer.py; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q "web.*Up"; then \
		docker-compose -f $(COMPOSE_MYSQL) exec web python database/seeds/nhso_error_codes_importer.py; \
	else \
		echo "$(YELLOW)No web container running. Start with: make up$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) Error codes import complete"

seed-all:
	@$(MAKE) seed
	@$(MAKE) seed-error-codes

db-backup:
	@echo "$(BOLD)$(GREEN)==> Backing up database...$(RESET)"
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	if docker-compose ps | grep -q postgres; then \
		docker-compose exec -T db pg_dump -U eclaim eclaim_db > backups/db_$$TIMESTAMP.sql && \
		echo "$(GREEN)✓$(RESET) PostgreSQL backup saved to backups/db_$$TIMESTAMP.sql"; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q mysql; then \
		docker-compose -f $(COMPOSE_MYSQL) exec -T db mysqldump -u eclaim -p eclaim_db > backups/db_$$TIMESTAMP.sql && \
		echo "$(GREEN)✓$(RESET) MySQL backup saved to backups/db_$$TIMESTAMP.sql"; \
	else \
		echo "$(YELLOW)No database running$(RESET)"; \
	fi

db-restore:
	@if [ ! -f backup.sql ]; then \
		echo "$(YELLOW)Error: backup.sql not found$(RESET)"; \
		exit 1; \
	fi
	@echo "$(BOLD)$(GREEN)==> Restoring database from backup.sql...$(RESET)"
	@if docker-compose ps | grep -q postgres; then \
		docker-compose exec -T db psql -U eclaim eclaim_db < backup.sql; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q mysql; then \
		docker-compose -f $(COMPOSE_MYSQL) exec -T db mysql -u eclaim -p eclaim_db < backup.sql; \
	else \
		echo "$(YELLOW)No database running$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) Database restored"

db-reset:
	@echo "$(YELLOW)WARNING: This will delete all data!$(RESET)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		docker-compose up -d; \
		echo "$(GREEN)✓$(RESET) Database reset complete"; \
	else \
		echo "Cancelled"; \
	fi

db-status:
	@echo "$(BOLD)Database Status:$(RESET)"
	@if docker-compose ps | grep -q postgres; then \
		docker-compose exec -T db psql -U eclaim -d eclaim_db -c "\
			SELECT 'OP/IP Records' as table_name, COUNT(*) as count FROM claim_rep_opip_nhso_item \
			UNION ALL \
			SELECT 'ORF Records', COUNT(*) FROM claim_rep_orf_nhso_item \
			UNION ALL \
			SELECT 'Imported Files', COUNT(*) FROM eclaim_imported_files;"; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q mysql; then \
		docker-compose -f $(COMPOSE_MYSQL) exec -T db mysql -u eclaim -p eclaim_db -e "\
			SELECT 'OP/IP Records' as table_name, COUNT(*) as count FROM claim_rep_opip_nhso_item \
			UNION ALL \
			SELECT 'ORF Records', COUNT(*) FROM claim_rep_orf_nhso_item \
			UNION ALL \
			SELECT 'Imported Files', COUNT(*) FROM eclaim_imported_files;"; \
	else \
		echo "$(YELLOW)No database running$(RESET)"; \
	fi

# ==================== Import & Download ====================

import:
	@echo "$(BOLD)$(GREEN)==> Importing all files from downloads/...$(RESET)"
	docker-compose exec web python eclaim_import.py downloads/
	@echo "$(GREEN)✓$(RESET) Import complete"

import-rep:
	@echo "$(BOLD)$(GREEN)==> Importing REP files from downloads/rep/...$(RESET)"
	@if docker-compose ps | grep -q "web.*Up"; then \
		docker-compose exec -T web bash -c 'for f in downloads/rep/eclaim_*.xls; do [ -f "$$f" ] && python eclaim_import.py "$$f" 2>&1 | grep -E "✓|✗|records"; done'; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q "web.*Up"; then \
		docker-compose -f $(COMPOSE_MYSQL) exec -T web bash -c 'for f in downloads/rep/eclaim_*.xls; do [ -f "$$f" ] && python eclaim_import.py "$$f" 2>&1 | grep -E "✓|✗|records"; done'; \
	else \
		echo "$(YELLOW)No web container running. Start with: make up$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) REP import complete"

import-stm:
	@echo "$(BOLD)$(GREEN)==> Importing STM files from downloads/stm/...$(RESET)"
	@if docker-compose ps | grep -q "web.*Up"; then \
		docker-compose exec -T web python stm_import.py downloads/stm/; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q "web.*Up"; then \
		docker-compose -f $(COMPOSE_MYSQL) exec -T web python stm_import.py downloads/stm/; \
	else \
		echo "$(YELLOW)No web container running. Start with: make up$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) STM import complete"

import-smt:
	@echo "$(BOLD)$(GREEN)==> Fetching and importing SMT budget data...$(RESET)"
	@VENDOR_ID=$$(docker-compose exec -T web python -c "import json; s=json.load(open('config/settings.json')); print(s.get('smt_vendor_id',''))" 2>/dev/null || echo ""); \
	if [ -z "$$VENDOR_ID" ]; then \
		VENDOR_ID=$$(docker-compose -f $(COMPOSE_MYSQL) exec -T web python -c "import json; s=json.load(open('config/settings.json')); print(s.get('smt_vendor_id',''))" 2>/dev/null || echo ""); \
	fi; \
	if [ -z "$$VENDOR_ID" ]; then \
		echo "$(YELLOW)Error: SMT Vendor ID not configured$(RESET)"; \
		echo "Please set 'smt_vendor_id' in Settings page or config/settings.json"; \
		exit 1; \
	fi; \
	echo "Using Vendor ID: $$VENDOR_ID"; \
	if docker-compose ps | grep -q "web.*Up"; then \
		docker-compose exec -T web python smt_budget_fetcher.py --vendor-id $$VENDOR_ID --save-db; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q "web.*Up"; then \
		docker-compose -f $(COMPOSE_MYSQL) exec -T web python smt_budget_fetcher.py --vendor-id $$VENDOR_ID --save-db; \
	else \
		echo "$(YELLOW)No web container running. Start with: make up$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) SMT import complete"

reimport-all:
	@echo "$(BOLD)$(GREEN)==> Re-importing all data (REP, STM, SMT)...$(RESET)"
	@echo ""
	@echo "$(CYAN)Step 1/3: Importing REP files...$(RESET)"
	@$(MAKE) import-rep
	@echo ""
	@echo "$(CYAN)Step 2/3: Importing STM files...$(RESET)"
	@$(MAKE) import-stm
	@echo ""
	@echo "$(CYAN)Step 3/3: Fetching SMT budget...$(RESET)"
	@$(MAKE) import-smt
	@echo ""
	@echo "$(GREEN)✓$(RESET) All imports complete!"
	@$(MAKE) db-status

scan-files:
	@echo "$(BOLD)$(GREEN)==> Scanning files and registering to history...$(RESET)"
	@if docker-compose ps | grep -q "web.*Up"; then \
		docker-compose exec web curl -s -X POST http://localhost:5001/api/files/scan | python -m json.tool; \
	elif docker-compose -f $(COMPOSE_MYSQL) ps | grep -q "web.*Up"; then \
		docker-compose -f $(COMPOSE_MYSQL) exec web curl -s -X POST http://localhost:5001/api/files/scan | python -m json.tool; \
	else \
		echo "$(YELLOW)No web container running. Start with: make up$(RESET)"; \
		exit 1; \
	fi
	@echo "$(GREEN)✓$(RESET) File scan complete"

import-file:
	@if [ -z "$(FILE)" ]; then \
		echo "$(YELLOW)Error: Please specify FILE=path$(RESET)"; \
		echo "Example: make import-file FILE=downloads/file.xls"; \
		exit 1; \
	fi
	@echo "$(BOLD)$(GREEN)==> Importing $(FILE)...$(RESET)"
	docker-compose exec web python eclaim_import.py $(FILE)
	@echo "$(GREEN)✓$(RESET) Import complete"

download:
	@echo "$(BOLD)$(GREEN)==> Running manual download...$(RESET)"
	docker-compose exec web python eclaim_downloader_http.py
	@echo "$(GREEN)✓$(RESET) Download complete"

# ==================== Admin Tools ====================

pgadmin:
	@echo "$(BOLD)$(GREEN)==> Starting pgAdmin...$(RESET)"
	docker-compose --profile tools up -d pgadmin
	@sleep 2
	@echo "$(GREEN)✓$(RESET) pgAdmin started at http://localhost:5050"
	@echo "  Email: admin@eclaim.local"
	@echo "  Password: admin"

phpmyadmin:
	@echo "$(BOLD)$(GREEN)==> Starting phpMyAdmin...$(RESET)"
	docker-compose -f $(COMPOSE_MYSQL) --profile tools up -d phpmyadmin
	@sleep 2
	@echo "$(GREEN)✓$(RESET) phpMyAdmin started at http://localhost:5050"

stop-admin:
	@echo "$(BOLD)==> Stopping admin tools...$(RESET)"
	docker-compose stop pgadmin 2>/dev/null || true
	docker-compose -f $(COMPOSE_MYSQL) stop phpmyadmin 2>/dev/null || true
	@echo "$(GREEN)✓$(RESET) Admin tools stopped"

# ==================== Version Management ====================

version:
	@if [ -f .env ] && grep -q "^VERSION=" .env; then \
		VERSION=$$(grep "^VERSION=" .env | cut -d'=' -f2); \
		echo "$(BOLD)Current version:$(RESET) $$VERSION"; \
	else \
		echo "$(YELLOW)VERSION not set in .env (using latest)$(RESET)"; \
	fi
	@echo ""
	@docker-compose images web 2>/dev/null | tail -n +2 || echo "No images found"

update:
	@if [ -z "$(VERSION)" ]; then \
		echo "$(YELLOW)Error: Please specify VERSION$(RESET)"; \
		echo "Example: make update VERSION=v2.1.0"; \
		exit 1; \
	fi
	@echo "$(BOLD)$(GREEN)==> Updating to $(VERSION)...$(RESET)"
	@if grep -q "^VERSION=" .env; then \
		sed -i.bak "s/^VERSION=.*/VERSION=$(VERSION)/" .env && rm .env.bak; \
	else \
		echo "VERSION=$(VERSION)" >> .env; \
	fi
	@echo "$(GREEN)✓$(RESET) Updated .env to VERSION=$(VERSION)"
	@$(MAKE) pull
	@$(MAKE) down
	@$(MAKE) up
	@echo ""
	@echo "$(GREEN)✓$(RESET) Update complete!"

update-latest:
	@$(MAKE) update VERSION=latest

# ==================== Release (Dev only) ====================

# Get current version from VERSION file
CURRENT_VERSION := $(shell cat VERSION 2>/dev/null || echo "0.0.0")
MAJOR := $(shell echo $(CURRENT_VERSION) | cut -d. -f1)
MINOR := $(shell echo $(CURRENT_VERSION) | cut -d. -f2)
PATCH := $(shell echo $(CURRENT_VERSION) | cut -d. -f3)

release-patch:
	@NEW_PATCH=$$(($(PATCH) + 1)); \
	$(MAKE) release V=$(MAJOR).$(MINOR).$$NEW_PATCH

release-minor:
	@NEW_MINOR=$$(($(MINOR) + 1)); \
	$(MAKE) release V=$(MAJOR).$$NEW_MINOR.0

release-major:
	@NEW_MAJOR=$$(($(MAJOR) + 1)); \
	$(MAKE) release V=$$NEW_MAJOR.0.0

release:
	@if [ -z "$(V)" ]; then \
		echo "$(YELLOW)Error: Please specify version V=x.y.z$(RESET)"; \
		echo "Example: make release V=3.2.0"; \
		echo "Or use: make release-patch / release-minor / release-major"; \
		exit 1; \
	fi
	@echo "$(BOLD)$(GREEN)==> Releasing v$(V)...$(RESET)"
	@echo ""
	@echo "$(CYAN)Current version:$(RESET) $(CURRENT_VERSION)"
	@echo "$(CYAN)New version:$(RESET)     $(V)"
	@echo ""
	@read -p "Continue? (y/n): " confirm; \
	if [ "$$confirm" != "y" ]; then \
		echo "Cancelled"; \
		exit 1; \
	fi
	@echo "$(V)" > VERSION
	@git add VERSION
	@git commit -m "chore: bump version to $(V)"
	@git tag -a "v$(V)" -m "Release v$(V)"
	@echo ""
	@echo "$(GREEN)✓$(RESET) Version $(V) tagged!"
	@echo ""
	@echo "$(BOLD)Next steps:$(RESET)"
	@echo "  1. Push to origin:     git push origin develop"
	@echo "  2. Create PR to main"
	@echo "  3. After merge, push tag: git push origin v$(V)"
	@echo ""
	@echo "$(YELLOW)Or push tag now to trigger release:$(RESET)"
	@echo "  git push origin v$(V)"

# ==================== Maintenance ====================

clean:
	@echo "$(BOLD)==> Removing containers and networks...$(RESET)"
	docker-compose down
	docker-compose -f $(COMPOSE_MYSQL) down 2>/dev/null || true
	docker-compose -f $(COMPOSE_NO_DB) down 2>/dev/null || true
	@echo "$(GREEN)✓$(RESET) Cleanup complete"

clean-all:
	@echo "$(YELLOW)WARNING: This will delete all data including volumes!$(RESET)"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		docker-compose -f $(COMPOSE_MYSQL) down -v 2>/dev/null || true; \
		docker-compose -f $(COMPOSE_NO_DB) down -v 2>/dev/null || true; \
		echo "$(GREEN)✓$(RESET) Everything removed"; \
	else \
		echo "Cancelled"; \
	fi

clean-logs:
	@echo "$(BOLD)==> Cleaning old log files...$(RESET)"
	@find logs/ -name "*.log" -mtime +30 -delete 2>/dev/null || true
	@echo "$(GREEN)✓$(RESET) Old logs cleaned (kept last 30 days)"

# ==================== Development ====================

dev:
	@echo "$(BOLD)$(GREEN)==> Starting in development mode...$(RESET)"
	docker-compose up
	# No -d flag = see logs in real-time

test:
	@echo "$(BOLD)$(GREEN)==> Running tests...$(RESET)"
	docker-compose exec web python -m pytest -v tests/ || true

lint:
	@echo "$(BOLD)$(GREEN)==> Running linters...$(RESET)"
	@docker-compose exec web python -m flake8 . --exclude=venv,__pycache__ --max-line-length=120 || true
	@echo "$(GREEN)✓$(RESET) Linting complete"
