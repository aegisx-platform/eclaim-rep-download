# Installation & Verification Guide

Complete step-by-step guide for installing E-Claim Revenue Intelligence system with both PostgreSQL and MySQL.

---

## Prerequisites

- Docker & Docker Compose installed
- Git installed
- 8GB RAM minimum
- Port 5001 available (web UI)
- Port 5432 (PostgreSQL) or 3306 (MySQL) available

---

## Quick Start (PostgreSQL - Recommended)

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-rep-download.git
cd eclaim-rep-download

# 2. Create .env file
cp .env.example .env
nano .env  # Set ECLAIM_USERNAME and ECLAIM_PASSWORD

# 3. Start services (auto-runs migrations)
docker-compose up -d

# 4. Wait for startup (watch logs)
docker-compose logs -f web
# Wait for: "[entrypoint] Starting Flask application..."
# Press Ctrl+C to exit logs

# 5. Run ALL seed data (REQUIRED)
docker-compose exec web python database/migrate.py --seed
docker-compose exec web python database/seeds/health_offices_importer.py
docker-compose exec web python database/seeds/nhso_error_codes_importer.py

# 6. Access web UI
open http://localhost:5001
```

---

## Detailed Installation Steps

### Step 1: Environment Setup

```bash
# Clone repository
git clone https://github.com/aegisx-platform/eclaim-rep-download.git
cd eclaim-rep-download

# Create .env file from template
cp .env.example .env
```

Edit `.env` file:
```bash
# NHSO E-Claim Credentials
ECLAIM_USERNAME=your_citizen_id
ECLAIM_PASSWORD=your_password

# Database (PostgreSQL default)
DB_TYPE=postgresql
DB_HOST=db
DB_PORT=5432
DB_NAME=eclaim_db
DB_USER=eclaim
DB_PASSWORD=eclaim_password

# Flask
FLASK_ENV=production
TZ=Asia/Bangkok
```

### Step 2: Start Services

**PostgreSQL (Default):**
```bash
docker-compose up -d
```

**MySQL (Alternative):**
```bash
docker-compose -f docker-compose-mysql.yml up -d
```

**Download-only (No Database):**
```bash
docker-compose -f docker-compose-no-db.yml up -d
```

### Step 3: Wait for Initialization

```bash
# Watch logs for completion
docker-compose logs -f web

# Expected output:
# [entrypoint] Waiting for database...
# [entrypoint] Database is ready
# [entrypoint] Running migrations...
# [migrate] Applied 7 migrations
# [entrypoint] Scanning existing files...
# [entrypoint] Starting Flask application...
# * Running on http://0.0.0.0:5001
```

Press `Ctrl+C` when you see "Starting Flask application"

### Step 4: Run Seed Data (REQUIRED)

**Option A: Using docker-compose exec (Standard)**
```bash
# 1. Seed dimension tables (dim_date, fund_types, service_types)
docker-compose exec web python database/migrate.py --seed

# 2. Seed health offices (9,000+ hospitals from MOPH)
docker-compose exec web python database/seeds/health_offices_importer.py

# 3. Seed NHSO error codes (300+ error code descriptions)
docker-compose exec web python database/seeds/nhso_error_codes_importer.py
```

**Option B: Using Make (if available)**
```bash
make seed-all
```

**Expected output:**
```
✓ Seeded 2,556 dim_date records
✓ Seeded 8 fund_types
✓ Seeded 6 service_types
✓ Imported 9,247 health offices
✓ Imported 312 NHSO error codes
```

### Step 5: Configure Hospital Settings

**Open Setup Page:**
```bash
open http://localhost:5001/setup
```

**Or go to Settings Tab:**
```bash
open http://localhost:5001/data-management?tab=settings
```

**Configure Hospital Code (5 digits):**
1. Enter your hospital's 5-digit code (e.g., `10670`)
2. Click **Save**
3. Verify hospital name appears (e.g., "รพ.ศิริราช")
4. Check bed count and level are correct

**Why is Hospital Code Required?**
- **SMT Budget**: Fetches Smart Money Transfer data from NHSO API
- **Per-Bed KPIs**: Calculates revenue/bed, loss/bed, claims/bed metrics
- **Analytics**: Enables hospital-specific performance metrics

### Step 6: Configure NHSO Credentials (Optional)

If you want to download E-Claim files:

1. Go to **Settings** tab
2. Add NHSO credentials (Citizen ID + Password)
3. Click **Test Connection** to verify
4. Can add multiple accounts (system rotates to avoid blocking)

---

## Verification Checklist

### ✅ Database Migration Status

```bash
docker-compose exec web python database/migrate.py --status
```

**Expected output:**
```
✓ 001_initial_schema.sql - Applied
✓ 002_stm_tables.sql - Applied
✓ 003_job_history.sql - Applied
✓ 004_system_alerts.sql - Applied
✓ 005_download_history.sql - Applied
✓ 006_nhso_error_codes.sql - Applied
✓ 007_add_missing_columns.sql - Applied

Total: 7/7 migrations applied
```

### ✅ Seed Data Verification

**PostgreSQL:**
```bash
docker-compose exec db psql -U eclaim -d eclaim_db -c "
  SELECT 'dim_date' as table_name, COUNT(*) as records FROM dim_date
  UNION ALL SELECT 'fund_types', COUNT(*) FROM fund_types
  UNION ALL SELECT 'service_types', COUNT(*) FROM service_types
  UNION ALL SELECT 'health_offices', COUNT(*) FROM health_offices
  UNION ALL SELECT 'nhso_error_codes', COUNT(*) FROM nhso_error_codes;
"
```

**MySQL:**
```bash
docker-compose exec db mysql -u eclaim -peclaim_password eclaim_db -e "
  SELECT 'dim_date' as table_name, COUNT(*) as records FROM dim_date
  UNION ALL SELECT 'fund_types', COUNT(*) FROM fund_types
  UNION ALL SELECT 'service_types', COUNT(*) FROM service_types
  UNION ALL SELECT 'health_offices', COUNT(*) FROM health_offices
  UNION ALL SELECT 'nhso_error_codes', COUNT(*) FROM nhso_error_codes;
"
```

**Expected counts:**
| Table | Records |
|-------|---------|
| dim_date | ~2,556 (7 years) |
| fund_types | 8 |
| service_types | 6 |
| health_offices | ~9,247 |
| nhso_error_codes | ~312 |

### ✅ Hospital Settings Verification

**Test API endpoint:**
```bash
# Set hospital code
curl -X POST http://localhost:5001/api/settings/hospital-code \
  -H "Content-Type: application/json" \
  -d '{"hospital_code": "10670"}'

# Get hospital info
curl http://localhost:5001/api/settings/hospital-info | jq
```

**Expected response:**
```json
{
  "success": true,
  "hospital_code": "10670",
  "data": {
    "h5_code": "10670",
    "h9_code": "0000010670",
    "name": "โรงพยาบาลศิริราช",
    "hospital_level": "S",
    "actual_beds": 2300,
    "province": "กรุงเทพมหานคร",
    "health_region": "13"
  }
}
```

### ✅ Web UI Access

**Open in browser:**
```bash
open http://localhost:5001
```

**Pages to verify:**
- ✅ Dashboard - Shows KPI cards (all should show `-` if no data)
- ✅ Data Management - All tabs load without errors
- ✅ Analytics - Charts render (empty if no data)
- ✅ Setup - Shows 3 sections (Database, Data Files, Configuration)

### ✅ Per-Bed KPIs Feature

**After setting hospital code, dashboard should show:**
- ✅ "ประสิทธิภาพต่อเตียง" section appears
- ✅ Hospital name badge displays correctly
- ✅ Bed count badge shows (e.g., "2,300 เตียง")
- ✅ Four KPI cards: รายได้/เตียง/เดือน, ส่วนต่าง/เตียง/เดือน, เคลม/เตียง, เฉลี่ย/เคลม

**If section is hidden:**
- Hospital code not configured → Go to Settings and set it
- No bed data in health_offices → Check seed data import

### ✅ SMT Budget Feature

**Test SMT fetch with hospital code:**
```bash
# Using hospital code from settings
curl -X POST http://localhost:5001/api/smt/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "budget_year": "2568",
    "save_db": true
  }'
```

**Or specify vendor_id explicitly:**
```bash
curl -X POST http://localhost:5001/api/smt/fetch \
  -H "Content-Type: application/json" \
  -d '{
    "vendor_id": "10670",
    "budget_year": "2568",
    "save_db": true
  }'
```

---

## Testing Both Database Systems

### Test PostgreSQL

```bash
# Start PostgreSQL
docker-compose up -d

# Run seeds
docker-compose exec web python database/migrate.py --seed
docker-compose exec web python database/seeds/health_offices_importer.py
docker-compose exec web python database/seeds/nhso_error_codes_importer.py

# Set hospital code
curl -X POST http://localhost:5001/api/settings/hospital-code \
  -H "Content-Type: application/json" \
  -d '{"hospital_code": "10670"}'

# Verify hospital info
curl http://localhost:5001/api/settings/hospital-info | jq

# Check web UI
open http://localhost:5001
```

### Switch to MySQL

```bash
# Stop PostgreSQL
docker-compose down

# Start MySQL
docker-compose -f docker-compose-mysql.yml up -d

# Wait for startup
docker-compose logs -f web
# Press Ctrl+C when ready

# Run seeds (SAME COMMANDS)
docker-compose exec web python database/migrate.py --seed
docker-compose exec web python database/seeds/health_offices_importer.py
docker-compose exec web python database/seeds/nhso_error_codes_importer.py

# Set hospital code
curl -X POST http://localhost:5001/api/settings/hospital-code \
  -H "Content-Type: application/json" \
  -d '{"hospital_code": "10670"}'

# Verify
curl http://localhost:5001/api/settings/hospital-info | jq
open http://localhost:5001
```

### Switch Back to PostgreSQL

```bash
docker-compose -f docker-compose-mysql.yml down
docker-compose up -d
# Note: Data does NOT transfer between databases
```

---

## Optional: Import Existing Data

### Import REP Files

```bash
# Import all REP files in downloads/rep/
docker-compose exec web bash -c 'for f in downloads/rep/*.xls; do python eclaim_import.py "$f"; done'

# Or use make
make import-rep
```

### Import STM Files

```bash
# Import all statement files
docker-compose exec web python stm_import.py downloads/stm/

# Or use make
make import-stm
```

### Fetch SMT Budget

```bash
# Fetch current fiscal year (uses hospital_code from settings)
docker-compose exec web python smt_budget_fetcher.py --save-db

# Or specify vendor ID
docker-compose exec web python smt_budget_fetcher.py --vendor-id 10670 --save-db

# Or use make
make import-smt
```

---

## Troubleshooting

### Database Connection Failed

```bash
# Check database status
docker-compose ps

# View database logs
docker-compose logs db

# Restart database
docker-compose restart db

# Wait for database
docker-compose exec web python database/migrate.py --status
```

### Migrations Not Applied

```bash
# Check migration status
docker-compose exec web python database/migrate.py --status

# Force re-run all migrations
docker-compose exec web python database/migrate.py --force

# Check logs
docker-compose logs web | grep migrate
```

### Seed Data Failed

```bash
# Check if tables exist
docker-compose exec db psql -U eclaim -d eclaim_db -c "\dt"

# Re-run specific seed
docker-compose exec web python database/migrate.py --seed
docker-compose exec web python database/seeds/health_offices_importer.py

# Check seed file exists
docker-compose exec web ls -la database/seeds/
```

### Hospital Code Not Found

```bash
# Check health_offices table
docker-compose exec db psql -U eclaim -d eclaim_db -c "
  SELECT h5_code, name, hospital_level, actual_beds
  FROM health_offices
  WHERE h5_code = '10670';
"

# If empty, re-run health offices seed
docker-compose exec web python database/seeds/health_offices_importer.py
```

### Per-Bed KPIs Not Showing

**Checklist:**
1. ✅ Hospital code configured? → Check Settings
2. ✅ health_offices table seeded? → Run health_offices_importer.py
3. ✅ Hospital has bed data? → Check health_offices.actual_beds > 0
4. ✅ Claims data imported? → Import REP files first

### Web UI Not Loading

```bash
# Check Flask status
docker-compose logs web

# Check port binding
docker-compose ps
# Should show: 0.0.0.0:5001->5001/tcp

# Restart web service
docker-compose restart web

# Full restart
docker-compose down && docker-compose up -d
```

---

## Clean Installation (Reset Everything)

```bash
# Stop and remove all containers + volumes
docker-compose down -v

# Remove downloaded files (optional)
rm -rf downloads/rep/* downloads/stm/* downloads/smt/*

# Remove logs (optional)
rm -rf logs/*

# Start fresh
docker-compose up -d

# Re-run all seeds
make seed-all
# Or manually:
# docker-compose exec web python database/migrate.py --seed
# docker-compose exec web python database/seeds/health_offices_importer.py
# docker-compose exec web python database/seeds/nhso_error_codes_importer.py
```

---

## Production Deployment

### Environment Variables

```bash
# .env for production
FLASK_ENV=production
DB_PASSWORD=strong_random_password_here
TZ=Asia/Bangkok

# Optional: Use external database
DB_HOST=your-db-host.com
DB_PORT=5432
```

### Security Considerations

1. **Change default passwords** in `.env`
2. **Use HTTPS** with reverse proxy (nginx/Caddy)
3. **Restrict database access** to localhost only
4. **Backup database** regularly
5. **Monitor logs** for errors

### Backup & Restore

**Backup PostgreSQL:**
```bash
docker-compose exec db pg_dump -U eclaim eclaim_db > backup_$(date +%Y%m%d).sql
```

**Restore PostgreSQL:**
```bash
cat backup_20260117.sql | docker-compose exec -T db psql -U eclaim -d eclaim_db
```

**Backup MySQL:**
```bash
docker-compose exec db mysqldump -u eclaim -peclaim_password eclaim_db > backup_$(date +%Y%m%d).sql
```

**Restore MySQL:**
```bash
cat backup_20260117.sql | docker-compose exec -T db mysql -u eclaim -peclaim_password eclaim_db
```

---

## Version Updates

```bash
# Set version in .env
echo "VERSION=v3.0.0" >> .env

# Pull new image
docker-compose pull

# Restart with new version
docker-compose up -d

# Check migrations
docker-compose exec web python database/migrate.py --status

# Run new migrations if any
docker-compose exec web python database/migrate.py
```

---

## Support

- GitHub Issues: https://github.com/aegisx-platform/eclaim-rep-download/issues
- Documentation: Check `CLAUDE.md` and `README.md`
- Logs: `docker-compose logs web` and `logs/` directory
