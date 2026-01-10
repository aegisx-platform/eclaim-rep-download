# 🚀 Installation Guide

## Docker Deployment (แนะนำ)

### แบบที่ 1: Full Stack with PostgreSQL 🏥

เหมาะสำหรับใช้งานจริงในโรงพยาบาล มีทั้ง download และ import เข้า database

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-req-download.git
cd eclaim-req-download

# 2. Setup environment
cp .env.example .env
nano .env  # แก้ไข ECLAIM_USERNAME และ ECLAIM_PASSWORD

# 3. Start all services
docker-compose up -d

# 4. Check logs
docker-compose logs -f
```

**เข้าใช้งาน:**
- 🌐 **Web UI**: http://localhost:5001
- 🗄️ **Database**: postgresql://eclaim:eclaim_password@localhost:5432/eclaim_db
- 🔧 **pgAdmin**: http://localhost:5050 (admin@eclaim.local / admin)

### แบบที่ 2: Full Stack with MySQL 🏥

ใช้ MySQL แทน PostgreSQL

```bash
# 1-2. เหมือนแบบที่ 1

# 3. Start with MySQL
docker-compose -f docker-compose-mysql.yml up -d

# 4. Check logs
docker-compose -f docker-compose-mysql.yml logs -f
```

**เข้าใช้งาน:**
- 🌐 **Web UI**: http://localhost:5001
- 🗄️ **Database**: mysql://eclaim:eclaim_password@localhost:3306/eclaim_db
- 🔧 **phpMyAdmin**: http://localhost:5050 (eclaim / eclaim_password)

### แบบที่ 3: Download Only (ไม่มี Database) 📥

เหมาะสำหรับ download ไฟล์อย่างเดียว ไม่ต้องการ import เข้า database

```bash
# 1-2. เหมือนแบบที่ 1

# 3. Start web service only
docker-compose -f docker-compose-no-db.yml up -d

# 4. Check logs
docker-compose -f docker-compose-no-db.yml logs -f
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
