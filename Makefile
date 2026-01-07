.PHONY: help build up down restart logs shell db-shell clean backup test

# Default target
help:
	@echo "E-Claim Downloader - Docker Commands"
	@echo ""
	@echo "Setup:"
	@echo "  make setup      - Initial setup (copy .env, build)"
	@echo "  make build      - Build Docker images"
	@echo "  make up         - Start all services"
	@echo "  make down       - Stop all services"
	@echo ""
	@echo "Development:"
	@echo "  make restart    - Restart services"
	@echo "  make logs       - View logs (all services)"
	@echo "  make logs-web   - View Flask logs"
	@echo "  make logs-db    - View PostgreSQL logs"
	@echo "  make shell      - Access web container shell"
	@echo "  make db-shell   - Access database shell"
	@echo ""
	@echo "Database:"
	@echo "  make db-backup  - Backup database"
	@echo "  make db-restore - Restore database from backup.sql"
	@echo "  make db-reset   - Reset database (WARNING: deletes data)"
	@echo ""
	@echo "Import:"
	@echo "  make import     - Import all files from downloads/"
	@echo "  make analyze    - Analyze a file (set FILE=path)"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean      - Remove containers and networks"
	@echo "  make clean-all  - Remove everything including volumes"
	@echo "  make ps         - Show running containers"
	@echo "  make stats      - Show resource usage"

# Initial setup
setup:
	@echo "==> Setting up E-Claim Downloader..."
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✓ Created .env file - PLEASE UPDATE CREDENTIALS!"; \
	else \
		echo "✓ .env file exists"; \
	fi
	@mkdir -p downloads logs backups
	@echo "✓ Created directories"
	@$(MAKE) build
	@echo ""
	@echo "==> Setup complete!"
	@echo "Next steps:"
	@echo "  1. Edit .env and update ECLAIM_USERNAME and ECLAIM_PASSWORD"
	@echo "  2. Run: make up"

# Build images
build:
	@echo "==> Building Docker images..."
	docker-compose build

# Start services
up:
	@echo "==> Starting services..."
	docker-compose up -d
	@echo ""
	@echo "✓ Services started!"
	@echo "  Web UI:    http://localhost:5001"
	@echo "  Database:  postgresql://eclaim:eclaim_password@localhost:5432/eclaim_db"
	@echo ""
	@echo "Run 'make logs' to view logs"

# Stop services
down:
	@echo "==> Stopping services..."
	docker-compose down

# Restart services
restart:
	@echo "==> Restarting services..."
	docker-compose restart

# View logs
logs:
	docker-compose logs -f

logs-web:
	docker-compose logs -f web

logs-db:
	docker-compose logs -f db

# Access shells
shell:
	@echo "==> Accessing web container shell..."
	docker-compose exec web bash

db-shell:
	@echo "==> Accessing PostgreSQL..."
	docker-compose exec db psql -U eclaim -d eclaim_db

# Container status
ps:
	docker-compose ps

stats:
	docker stats --no-stream

# Database operations
db-backup:
	@echo "==> Backing up database..."
	@mkdir -p backups
	@TIMESTAMP=$$(date +%Y%m%d_%H%M%S); \
	docker-compose exec -T db pg_dump -U eclaim eclaim_db > backups/db_$$TIMESTAMP.sql && \
	echo "✓ Backup saved to backups/db_$$TIMESTAMP.sql"

db-restore:
	@echo "==> Restoring database from backup.sql..."
	@if [ ! -f backup.sql ]; then \
		echo "Error: backup.sql not found"; \
		exit 1; \
	fi
	docker-compose exec -T db psql -U eclaim eclaim_db < backup.sql
	@echo "✓ Database restored"

db-reset:
	@echo "WARNING: This will delete all data!"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		docker-compose up -d; \
		echo "✓ Database reset complete"; \
	else \
		echo "Cancelled"; \
	fi

# Import operations
import:
	@echo "==> Importing all files from downloads/..."
	docker-compose exec web python eclaim_import.py

analyze:
	@if [ -z "$(FILE)" ]; then \
		echo "Error: Please specify FILE=path/to/file.xls"; \
		exit 1; \
	fi
	@echo "==> Analyzing $(FILE)..."
	docker-compose exec web python eclaim_import.py --analyze $(FILE)

# Cleanup
clean:
	@echo "==> Removing containers and networks..."
	docker-compose down

clean-all:
	@echo "WARNING: This will delete all data including volumes!"
	@read -p "Are you sure? (yes/no): " confirm; \
	if [ "$$confirm" = "yes" ]; then \
		docker-compose down -v; \
		echo "✓ Everything removed"; \
	else \
		echo "Cancelled"; \
	fi

# Testing
test:
	@echo "==> Running tests..."
	docker-compose exec web python -m pytest -v

# Show all make targets
list:
	@$(MAKE) -pRrq -f $(lastword $(MAKEFILE_LIST)) : 2>/dev/null | awk -v RS= -F: '/^# File/,/^# Finished Make data base/ {if ($$1 !~ "^[#.]") {print $$1}}' | sort | egrep -v -e '^[^[:alnum:]]' -e '^$@$$'
