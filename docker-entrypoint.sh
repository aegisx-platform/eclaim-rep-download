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

# Function to wait for database
wait_for_db() {
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
    echo "[entrypoint] Running database migrations..."

    if python database/migrate.py; then
        echo "[entrypoint] Migrations completed successfully!"
        return 0
    else
        echo "[entrypoint] WARNING: Migration failed, but continuing..."
        return 0  # Don't fail startup if migrations fail
    fi
}

# Function to scan and register existing files
scan_files() {
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
    # Step 1: Wait for database
    if ! wait_for_db; then
        echo "[entrypoint] Cannot connect to database, exiting."
        exit 1
    fi

    # Step 2: Run migrations
    run_migrations

    # Step 3: Scan and register existing files
    scan_files

    # Step 4: Start the application
    echo "[entrypoint] Starting Flask application..."
    exec "$@"
}

# Run main with all arguments
main "$@"
