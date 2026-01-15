# Installation Guide

คู่มือการติดตั้ง NHSO Revenue Intelligence

---

## Quick Install (แนะนำ)

### One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash
```

Script จะทำการ:
1. ✅ ตรวจสอบ Docker
2. ✅ สร้างโฟลเดอร์ `nhso-revenue/`
3. ✅ Download docker-compose.yml
4. ✅ ถาม credentials และสร้าง .env
5. ✅ สร้างโฟลเดอร์ downloads, logs, config
6. ✅ Pull Docker image และ start services

### Options

```bash
# PostgreSQL (default)
curl -fsSL .../install.sh | bash

# MySQL
curl -fsSL .../install.sh | bash -s -- --mysql

# Download only (no database)
curl -fsSL .../install.sh | bash -s -- --no-db

# Custom directory
curl -fsSL .../install.sh | bash -s -- --dir my-hospital
```

### หลังติดตั้งเสร็จ

```
nhso-revenue/
├── docker-compose.yml    # Docker configuration
├── .env                  # Credentials
├── downloads/            # Downloaded files
│   ├── rep/
│   ├── stm/
│   └── smt/
├── logs/                 # Application logs
└── config/               # User settings
```

**เข้าใช้งาน:** http://localhost:5001

---

## Manual Install (สำหรับ Developer)

### PostgreSQL

```bash
git clone https://github.com/aegisx-platform/eclaim-rep-download.git
cd eclaim-rep-download
cp .env.example .env
nano .env  # แก้ไข ECLAIM_USERNAME และ ECLAIM_PASSWORD
docker-compose up -d
```

### MySQL

```bash
docker-compose -f docker-compose-mysql.yml up -d
```

### Download Only

```bash
docker-compose -f docker-compose-no-db.yml up -d
```

**เข้าใช้งาน:**
- 🌐 **Web UI**: http://localhost:5001

## Manual Installation (Without Docker)

### Prerequisites

- Python 3.12+
- PostgreSQL 13+ หรือ MySQL 8.0+ (optional)
- Git

### Installation Steps

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-req-download.git
cd eclaim-req-download

# 2. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure credentials
cp .env.example .env
nano .env  # Update ECLAIM_USERNAME and ECLAIM_PASSWORD

# 5. (Optional) Setup database
# For PostgreSQL:
createdb eclaim_db
psql -U postgres -d eclaim_db -f database/schema-postgresql-merged.sql

# For MySQL:
mysql -u root -p -e "CREATE DATABASE eclaim_db CHARACTER SET utf8mb4;"
mysql -u root -p eclaim_db < database/schema-mysql-merged.sql

# 6. Run Flask app
python app.py
```

**Access:** http://localhost:5001

## Migrating to database schema

If you have existing database, see [Migration Guide](MIGRATION_V2.md) or [Quick Start Guide](../MIGRATE_V2.md).

### Fresh Install with database schema

database schema uses your hospital's existing table structure. It will be created automatically on first run.

### Option A: Fresh Install (Recommended)

```bash

```

### Option B: Manual Migration

See [MIGRATE_V2.md](../MIGRATE_V2.md) for detailed steps.

## Verification

### Check Services

```bash
# Docker deployment
docker-compose ps

# Manual installation
curl http://localhost:5001/dashboard
```

### Check Database

```bash
# PostgreSQL
docker-compose exec db psql -U eclaim -d eclaim_db -c "\dt"

# MySQL
docker-compose exec db mysql -u eclaim -p eclaim_db -e "SHOW TABLES;"
```

Expected tables:
- `eclaim_imported_files`
- `claim_rep_opip_nhso_item`
- `claim_rep_orf_nhso_item`

## Stopping Services

```bash
# Docker
docker-compose down

# Manual
# Press Ctrl+C in the terminal running Flask
```

## Removing Everything

```bash
# Stop and remove containers, networks, volumes
docker-compose down -v

# Remove downloaded files
rm -rf downloads/*

# Remove logs
rm -rf logs/*
```

---

**[← Back to Main README](../README.md)** | **[Next: Configuration →](CONFIGURATION.md)**
