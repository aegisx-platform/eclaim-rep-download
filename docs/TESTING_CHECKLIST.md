# Testing Checklist - Installation Verification

Complete checklist for verifying E-Claim Revenue Intelligence installation on both PostgreSQL and MySQL.

---

## Pre-Installation Checklist

- [ ] Docker Desktop running
- [ ] Port 5001 available (web UI)
- [ ] Port 5432 (PostgreSQL) or 3306 (MySQL) available
- [ ] Git repository cloned
- [ ] `.env` file created from `.env.example`
- [ ] NHSO credentials configured in `.env` (optional for download features)

---

## PostgreSQL Installation Test

### 1. Container Startup ✅

```bash
docker-compose up -d
docker-compose logs -f web
```

**Expected:**
- [ ] `[entrypoint] Waiting for database...` appears
- [ ] `[entrypoint] Database is ready` appears
- [ ] `[migrate] Applied 7 migrations` (or `No pending migrations`)
- [ ] `[entrypoint] Scanning existing files...` appears
- [ ] `[entrypoint] Starting Flask application...` appears
- [ ] `* Running on http://0.0.0.0:5001` appears

**If fails:**
```bash
docker-compose logs db  # Check database logs
docker-compose ps       # Check container status
```

### 2. Migration Status ✅

```bash
docker-compose exec web python database/migrate.py --status
```

**Expected:**
- [ ] All 7 migrations show "Applied"
  - 001_initial_schema.sql
  - 002_stm_tables.sql
  - 003_job_history.sql
  - 004_system_alerts.sql
  - 005_download_history.sql
  - 006_nhso_error_codes.sql
  - 007_add_missing_columns.sql

### 3. Seed Data Import ✅

```bash
# Seed dimension tables
docker-compose exec web python database/migrate.py --seed
```

**Expected:**
- [ ] `✓ Seeded 2556 dim_date records`
- [ ] `✓ Seeded 8 fund_types`
- [ ] `✓ Seeded 6 service_types`

```bash
# Seed health offices
docker-compose exec web python database/seeds/health_offices_importer.py
```

**Expected:**
- [ ] `✓ Imported 9247 health offices` (or similar count)

```bash
# Seed error codes
docker-compose exec web python database/seeds/nhso_error_codes_importer.py
```

**Expected:**
- [ ] `✓ Imported 312 NHSO error codes` (or similar count)

### 4. Database Verification ✅

```bash
docker-compose exec db psql -U eclaim -d eclaim_db -c "
  SELECT 'dim_date' as table_name, COUNT(*) as records FROM dim_date
  UNION ALL SELECT 'fund_types', COUNT(*) FROM fund_types
  UNION ALL SELECT 'service_types', COUNT(*) FROM service_types
  UNION ALL SELECT 'health_offices', COUNT(*) FROM health_offices
  UNION ALL SELECT 'nhso_error_codes', COUNT(*) FROM nhso_error_codes;
"
```

**Expected counts:**
- [ ] dim_date: ~2,556
- [ ] fund_types: 8
- [ ] service_types: 6
- [ ] health_offices: ~9,247
- [ ] nhso_error_codes: ~312

### 5. Web UI Access ✅

```bash
open http://localhost:5001
```

**Pages to test:**
- [ ] `/` - Dashboard loads without errors
- [ ] `/setup` - Setup page shows 3 sections
- [ ] `/data-management` - All tabs load
- [ ] `/analytics` - Charts render (empty is OK)
- [ ] `/reconciliation` - Page loads

### 6. Hospital Settings Configuration ✅

**Via Web UI:**
```bash
open http://localhost:5001/setup
```

- [ ] "รหัสหน่วยบริการ (Hospital Code)" input visible
- [ ] Enter test code: `10670`
- [ ] Click **Save** button
- [ ] Hospital info displays:
  - [ ] Hospital name: "โรงพยาบาลศิริราช"
  - [ ] Level: "S"
  - [ ] Beds: "2,300 เตียง"

**Via API:**
```bash
# Set hospital code
curl -X POST http://localhost:5001/api/settings/hospital-code \
  -H "Content-Type: application/json" \
  -d '{"hospital_code": "10670"}'
```

**Expected response:**
- [ ] `"success": true`
- [ ] `"hospital_code": "10670"`

```bash
# Get hospital info
curl http://localhost:5001/api/settings/hospital-info | jq
```

**Expected response:**
- [ ] `"success": true`
- [ ] `"data"` object contains:
  - [ ] `"name": "โรงพยาบาลศิริราช"`
  - [ ] `"hospital_level": "S"`
  - [ ] `"actual_beds": 2300`
  - [ ] `"province": "กรุงเทพมหานคร"`

### 7. Per-Bed KPIs Feature ✅

**Check Dashboard:**
```bash
open http://localhost:5001
```

- [ ] Scroll to "ประสิทธิภาพต่อเตียง" section
- [ ] Hospital name badge shows: "โรงพยาบาลศิริราช"
- [ ] Beds badge shows: "2,300 เตียง"
- [ ] Four KPI cards visible:
  - [ ] รายได้/เตียง/เดือน (shows `-` if no data)
  - [ ] ส่วนต่าง/เตียง/เดือน (shows `-` if no data)
  - [ ] เคลม/เตียง (shows `-` if no data)
  - [ ] เฉลี่ย/เคลม (shows `-` if no data)

**If section is hidden:**
- Verify hospital code is set
- Verify health_offices seed data is imported
- Check browser console for errors

### 8. SMT Budget with Hospital Code ✅

**Via Web UI:**
```bash
open http://localhost:5001/setup
```

- [ ] Scroll to "Smart Money Transfer (SMT)" section
- [ ] Shows: "รหัสหน่วยบริการ: 10670"
- [ ] Click **"Fetch from API"**
- [ ] Budget data fetches successfully

**Via API:**
```bash
curl -X POST http://localhost:5001/api/smt/fetch \
  -H "Content-Type: application/json" \
  -d '{"budget_year": "2568", "save_db": true}'
```

**Expected:**
- [ ] `"success": true`
- [ ] `"records": <number>` (count of budget records)

### 9. Analytics API with Per-Bed Metrics ✅

```bash
curl http://localhost:5001/api/analytics/overview | jq
```

**Expected response includes:**
- [ ] `"hospital"` object:
  - [ ] `"hospital_code": "10670"`
  - [ ] `"hospital_name": "โรงพยาบาลศิริราช"`
  - [ ] `"actual_beds": 2300`
- [ ] `"per_bed"` object:
  - [ ] `"beds": 2300`
  - [ ] `"reimb_per_bed_month": <number>`
  - [ ] `"loss_per_bed_month": <number>`
  - [ ] `"claims_per_bed": <number>`
  - [ ] `"avg_per_claim": <number>`

---

## MySQL Installation Test

### 1. Switch to MySQL ✅

```bash
# Stop PostgreSQL
docker-compose down

# Start MySQL
docker-compose -f docker-compose-mysql.yml up -d
docker-compose logs -f web
```

**Expected:**
- [ ] Same startup sequence as PostgreSQL
- [ ] `[migrate] Applied 7 migrations`
- [ ] Flask starts successfully

### 2. Run ALL Tests Again ✅

**Repeat ALL PostgreSQL tests above (sections 2-9) for MySQL:**
- [ ] Migration status
- [ ] Seed data import
- [ ] Database verification
- [ ] Web UI access
- [ ] Hospital settings
- [ ] Per-bed KPIs
- [ ] SMT budget
- [ ] Analytics API

### 3. Database Verification (MySQL-specific) ✅

```bash
docker-compose exec db mysql -u eclaim -peclaim_password eclaim_db -e "
  SELECT 'dim_date' as table_name, COUNT(*) as records FROM dim_date
  UNION ALL SELECT 'fund_types', COUNT(*) FROM fund_types
  UNION ALL SELECT 'service_types', COUNT(*) FROM service_types
  UNION ALL SELECT 'health_offices', COUNT(*) FROM health_offices
  UNION ALL SELECT 'nhso_error_codes', COUNT(*) FROM nhso_error_codes;
"
```

**Expected:**
- [ ] Same counts as PostgreSQL

### 4. Switch Back to PostgreSQL ✅

```bash
docker-compose -f docker-compose-mysql.yml down
docker-compose up -d
```

- [ ] PostgreSQL starts successfully
- [ ] Data is preserved (if not removed with `-v`)

---

## Feature-Specific Tests

### NHSO Credentials (Optional)

**Via Web UI:**
```bash
open http://localhost:5001/data-management?tab=settings
```

- [ ] Add credential with Citizen ID + Password
- [ ] Click **"Test Connection"**
- [ ] Shows: "Connection successful!" (if credentials valid)
- [ ] Can add multiple credentials

**Via API:**
```bash
curl -X POST http://localhost:5001/api/settings/test-connection
```

- [ ] Returns `"success": true` if credentials valid

### Download REP Files

**Via Web UI:**
```bash
open http://localhost:5001/data-management?tab=download
```

- [ ] Select month/year
- [ ] Select schemes (UCS, OFC, SSS, LGO)
- [ ] Click **"Download"**
- [ ] Files download to `downloads/rep/`

### Import REP Files

**Via CLI:**
```bash
docker-compose exec web python eclaim_import.py downloads/rep/eclaim_UC_202401_001_01.xls
```

- [ ] Shows progress: `Importing...`
- [ ] Shows: `✓ Imported successfully`

**Via Web UI:**
```bash
open http://localhost:5001/data-management?tab=rep
```

- [ ] Click **"Import All"**
- [ ] Progress modal shows
- [ ] Files marked as "Imported"

### Import STM Files

```bash
docker-compose exec web python stm_import.py downloads/stm/
```

- [ ] Imports all `.txt` files
- [ ] Shows record counts

### Analytics Dashboard

```bash
open http://localhost:5001
```

**After importing data:**
- [ ] Top 5 KPI cards show real numbers (not `-`)
- [ ] "ประสิทธิภาพต่อเตียง" section shows real calculations
- [ ] "Claims Performance" section shows metrics
- [ ] Charts render with data:
  - [ ] Monthly Revenue Trend
  - [ ] Fund Comparison
  - [ ] Service Type Distribution
  - [ ] Top Denial Reasons

---

## Regression Tests

### Backward Compatibility

**Old SMT vendor_id field:**
```bash
# Should still work if set before hospital_code
curl -X POST http://localhost:5001/api/smt/settings \
  -H "Content-Type: application/json" \
  -d '{"smt_vendor_id": "10670", "smt_auto_save_db": true}'
```

- [ ] Settings save successfully
- [ ] `get_hospital_code()` returns `10670`

**Hospital code takes precedence:**
```bash
# Set hospital_code
curl -X POST http://localhost:5001/api/settings/hospital-code \
  -H "Content-Type: application/json" \
  -d '{"hospital_code": "10771"}'

# Check that hospital_code is used
curl http://localhost:5001/api/settings/hospital-code | jq
```

- [ ] Returns `"hospital_code": "10771"`
- [ ] SMT uses this code instead of old smt_vendor_id

### Settings Persistence

```bash
# Set hospital code
curl -X POST http://localhost:5001/api/settings/hospital-code \
  -H "Content-Type: application/json" \
  -d '{"hospital_code": "10670"}'

# Restart container
docker-compose restart web

# Verify setting persists
curl http://localhost:5001/api/settings/hospital-code | jq
```

- [ ] Still returns `"hospital_code": "10670"`

---

## Performance Tests

### Large Dataset Import

```bash
# Import 100 REP files
docker-compose exec web bash -c 'for f in downloads/rep/*.xls; do python eclaim_import.py "$f"; done'
```

- [ ] Completes without memory errors
- [ ] Each file imports in <30 seconds
- [ ] Database stays under 2GB

### Concurrent Requests

```bash
# Run 10 concurrent API calls
for i in {1..10}; do
  curl http://localhost:5001/api/analytics/overview &
done
wait
```

- [ ] All requests complete successfully
- [ ] No timeout errors
- [ ] Response time <2 seconds

---

## Security Tests

### Default Passwords Changed

- [ ] `.env` has strong DB password (not `eclaim_password`)
- [ ] Production uses `FLASK_ENV=production`

### Port Exposure

```bash
docker-compose ps
```

- [ ] Only port 5001 exposed externally
- [ ] Database port NOT exposed (unless intentional)

---

## Cleanup Tests

### Container Removal

```bash
docker-compose down
```

- [ ] Containers stop gracefully
- [ ] No error messages

### Volume Preservation

```bash
docker-compose down
docker-compose up -d
```

- [ ] Data persists (migrations, seeds, settings)

### Full Reset

```bash
docker-compose down -v
```

- [ ] All volumes removed
- [ ] Fresh start works

---

## Common Issues & Solutions

### Issue: Migration fails with "table already exists"

**Solution:**
```bash
docker-compose exec web python database/migrate.py --force
```

### Issue: Seed import shows "0 records"

**Solution:**
```bash
# Check file exists
docker-compose exec web ls -la database/seeds/

# Re-run with verbose output
docker-compose logs web
```

### Issue: Hospital code not found

**Solution:**
```bash
# Verify health_offices has data
docker-compose exec db psql -U eclaim -d eclaim_db -c "SELECT COUNT(*) FROM health_offices;"

# Re-import if zero
docker-compose exec web python database/seeds/health_offices_importer.py
```

### Issue: Per-bed section hidden

**Checklist:**
1. Hospital code configured?
2. health_offices seeded?
3. Hospital has beds > 0?
4. Browser cache cleared?

---

## Sign-Off Checklist

**Installation Complete:**
- [ ] PostgreSQL installation tested ✅
- [ ] MySQL installation tested ✅
- [ ] All seed data imported ✅
- [ ] Hospital settings configured ✅
- [ ] Per-bed KPIs working ✅
- [ ] SMT budget working ✅
- [ ] Web UI accessible ✅
- [ ] No console errors ✅
- [ ] Documentation reviewed ✅

**Ready for:**
- [ ] Development
- [ ] Staging deployment
- [ ] Production deployment

---

**Tester:** _________________
**Date:** _________________
**Environment:** [ ] PostgreSQL  [ ] MySQL
**Version:** _________________
**Status:** [ ] Pass  [ ] Fail

**Notes:**
