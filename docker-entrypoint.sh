#!/bin/bash
set -e

echo "============================================"
echo "E-Claim System Starting..."
echo "============================================"
echo "DB_TYPE: ${DB_TYPE:-postgresql}"
echo "DB_HOST: ${DB_HOST:-db}"
echo "DB_PORT: ${DB_PORT:-5432}"
echo "DB_NAME: ${DB_NAME:-eclaim_db}"
echo "============================================"

# Function to generate SECRET_KEY if not set
generate_secret_key() {
    # Check if SECRET_KEY is not set or is using default value
    if [ -z "$SECRET_KEY" ] || [ "$SECRET_KEY" = "please-change-this-secret-key-in-production" ]; then
        echo "[entrypoint] SECRET_KEY not set or using default, generating new one..."

        # Generate random SECRET_KEY
        NEW_SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")

        # Export for current session
        export SECRET_KEY="$NEW_SECRET_KEY"

        # Save to credentials file
        echo "" >> .admin-credentials
        echo "# Generated SECRET_KEY ($(date '+%Y-%m-%d %H:%M:%S'))" >> .admin-credentials
        echo "SECRET_KEY=$NEW_SECRET_KEY" >> .admin-credentials

        echo "[entrypoint] ✓ Generated new SECRET_KEY and saved to .admin-credentials"
        echo "[entrypoint] IMPORTANT: Add this to your .env file for persistence:"
        echo "[entrypoint] SECRET_KEY=$NEW_SECRET_KEY"
    else
        echo "[entrypoint] SECRET_KEY already configured"
    fi
}

# Function to migrate settings from old location
migrate_settings() {
    if [ -f "config/settings.json" ] && [ ! -f "data/settings.json" ]; then
        echo "[entrypoint] Migrating settings.json to data/ directory..."
        mkdir -p data
        cp config/settings.json data/settings.json
        echo "[entrypoint] Settings migrated successfully"
    elif [ -f "data/settings.json" ]; then
        echo "[entrypoint] Settings already in data/ directory"
    else
        echo "[entrypoint] No existing settings found, will be created on first run"
    fi
}

# Function to wait for database
wait_for_db() {
    # Skip database check if DB_TYPE is none
    if [ "$DB_TYPE" = "none" ]; then
        echo "[entrypoint] DB_TYPE=none, skipping database check"
        return 0
    fi

    echo "[entrypoint] Waiting for database to be ready..."

    local max_retries=30
    local retry=0

    while [ $retry -lt $max_retries ]; do
        if [ "$DB_TYPE" = "mysql" ]; then
            if python -c "
import pymysql
try:
    conn = pymysql.connect(
        host='${DB_HOST:-db}',
        port=${DB_PORT:-3306},
        user='${DB_USER:-eclaim}',
        password='${DB_PASSWORD:-eclaim_password}',
        database='${DB_NAME:-eclaim_db}'
    )
    conn.close()
    exit(0)
except Exception as e:
    exit(1)
" 2>/dev/null; then
                echo "[entrypoint] MySQL is ready!"
                return 0
            fi
        else
            if python -c "
import psycopg2
try:
    conn = psycopg2.connect(
        host='${DB_HOST:-db}',
        port=${DB_PORT:-5432},
        user='${DB_USER:-eclaim}',
        password='${DB_PASSWORD:-eclaim_password}',
        dbname='${DB_NAME:-eclaim_db}'
    )
    conn.close()
    exit(0)
except Exception as e:
    exit(1)
" 2>/dev/null; then
                echo "[entrypoint] PostgreSQL is ready!"
                return 0
            fi
        fi

        retry=$((retry + 1))
        echo "[entrypoint] Database not ready, waiting... ($retry/$max_retries)"
        sleep 2
    done

    echo "[entrypoint] ERROR: Database not available after $max_retries retries"
    return 1
}

# Function to run migrations
run_migrations() {
    # Skip migrations if DB_TYPE is none
    if [ "$DB_TYPE" = "none" ]; then
        echo "[entrypoint] DB_TYPE=none, skipping migrations"
        return 0
    fi

    echo "[entrypoint] Running database migrations..."

    if python database/migrate.py; then
        echo "[entrypoint] Migrations completed successfully!"
        return 0
    else
        echo "[entrypoint] WARNING: Migration failed, but continuing..."
        return 0  # Don't fail startup if migrations fail
    fi
}

# Function to create default admin user
create_default_admin() {
    # Skip admin creation if DB_TYPE is none
    if [ "$DB_TYPE" = "none" ]; then
        echo "[entrypoint] DB_TYPE=none, skipping admin user creation"
        return 0
    fi

    echo "[entrypoint] Checking for admin user..."

    if python utils/create_default_admin.py; then
        echo "[entrypoint] Admin user setup completed!"
        return 0
    else
        echo "[entrypoint] WARNING: Admin user creation failed, but continuing..."
        return 0  # Don't fail startup
    fi
}

# Function to scan and register existing files
scan_files() {
    # Skip file scanning if DB_TYPE is none
    if [ "$DB_TYPE" = "none" ]; then
        echo "[entrypoint] DB_TYPE=none, skipping file scanning"
        return 0
    fi

    echo "[entrypoint] Scanning and registering download files to database..."

    python -c "
from utils.history_manager_db import HistoryManagerDB
import os

# Scan REP files
if os.path.exists('downloads/rep'):
    hm_rep = HistoryManagerDB(download_type='rep')
    result = hm_rep.scan_and_register_files('downloads/rep')
    print(f'[entrypoint] REP files: added={result[\"added\"]}, skipped={result[\"skipped\"]}')

# Scan STM files
if os.path.exists('downloads/stm'):
    hm_stm = HistoryManagerDB(download_type='stm')
    result = hm_stm.scan_and_register_files('downloads/stm')
    print(f'[entrypoint] STM files: added={result[\"added\"]}, skipped={result[\"skipped\"]}')

print('[entrypoint] File scanning completed!')
" 2>/dev/null || echo "[entrypoint] WARNING: File scanning failed, but continuing..."
}

# Main startup sequence
main() {
    # Step 0: Generate SECRET_KEY if needed
    generate_secret_key

    # Step 1: Migrate settings if needed
    migrate_settings

    # Step 2: Wait for database
    if ! wait_for_db; then
        echo "[entrypoint] Cannot connect to database, exiting."
        exit 1
    fi

    # Step 3: Run migrations
    run_migrations

    # Step 4: Create default admin user (if first installation)
    create_default_admin

    # Step 5: Scan and register existing files
    scan_files

    # Step 6: Start the application
    echo "[entrypoint] Starting Flask application..."
    exec "$@"
}

# Run main with all arguments
main "$@"
