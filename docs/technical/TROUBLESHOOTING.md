# 🐛 Troubleshooting Guide

## Web UI Issues

### Web UI ไม่โหลด

**Problem:** ไม่สามารถเข้า http://localhost:5001 ได้

```bash
# 1. ตรวจสอบ containers
docker-compose ps

# 2. Check if web service is running
docker-compose ps web

# 3. Restart services
docker-compose restart web

# 4. ดู logs
docker-compose logs -f web
```

**Common causes:**
- Port 5001 ถูกใช้โดยโปรแกรมอื่น
- Container crashed (check logs)
- Missing dependencies

### Error: Port already in use

```bash
# หา process ที่ใช้ port 5001
lsof -i :5001

# Kill process
kill -9 <PID>

# หรือเปลี่ยน port ใน docker-compose.yml
ports:
  - "5002:5001"  # Use port 5002 instead
```

## Database Issues

### Database เชื่อมต่อไม่ได้

```bash
# 1. ตรวจสอบ database service
docker-compose ps db

# 2. Check database logs
docker-compose logs db

# 3. Restart database
docker-compose restart db

# 4. ทดสอบ connection
docker-compose exec web python -c "from config.database import get_db_config; print(get_db_config())"
```

### Error: password authentication failed

**Fix credentials:**
```bash
# 1. Update .env file
nano .env

# 2. Restart services
docker-compose down
docker-compose up -d
```

### Tables don't exist

```bash
# 1. Check if schema was imported
docker-compose exec db psql -U eclaim -d eclaim_db -c "\dt"

# 2. Re-import schema
docker-compose exec -T db psql -U eclaim -d eclaim_db < database/schema-postgresql-merged.sql

# For MySQL:
docker-compose exec -T db mysql -u eclaim -p eclaim_db < database/schema-mysql-merged.sql
```

## Import Issues

### Import failed with error

```bash
# 1. Check import logs
docker-compose logs web | grep import

# 2. Check file format
python eclaim_import.py --analyze downloads/file.xls

# 3. Verify database connection
docker-compose exec db psql -U eclaim -d eclaim_db -c "SELECT COUNT(*) FROM eclaim_imported_files;"
```

### Error: duplicate key value

**File already imported:**
```bash
# Delete tracking record to re-import
docker-compose exec db psql -U eclaim -d eclaim_db -c \
  "DELETE FROM eclaim_imported_files WHERE filename = 'your_file.xls';"

# Then import again
docker-compose exec web python eclaim_import.py downloads/your_file.xls
```

### Import very slow

```bash
# Check database indexes
docker-compose exec db psql -U eclaim -d eclaim_db -c "\di"

# Check table sizes
docker-compose exec db psql -U eclaim -d eclaim_db -c \
  "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
   FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

## Download Issues

### Download stuck or timeout

```bash
# 1. Check download logs
docker-compose logs -f web | grep download

# 2. Test NHSO connection
docker-compose exec web curl -I https://eclaim.nhso.go.th

# 3. Restart downloader
docker-compose restart web
```

### Login failed

**Check credentials:**
```bash
# 1. Verify settings
cat config/settings.json

# 2. Test login manually
docker-compose exec web python -c "
from eclaim_downloader_http import EClaimDownloader
d = EClaimDownloader()
print('Testing login...')
"
```

### No files downloaded

**Possible reasons:**
- Wrong month/year selected
- No new files available
- All files already downloaded (check history)

```bash
# Check download history
cat download_history.json | python3 -m json.tool
```

## Scheduler Issues

### Scheduler ไม่ทำงาน

```bash
# 1. Check scheduler status
curl http://localhost:5001/api/schedule | python3 -m json.tool

# 2. Check scheduler logs
docker-compose logs -f web | grep scheduler

# 3. Verify settings
cat config/settings.json | python3 -m json.tool

# 4. Restart web service
docker-compose restart web
```

### Schedule time not updated

**Restart required:**
```bash
# After changing schedule, always restart
docker-compose restart web
```

### Scheduler runs but no download

```bash
# Check for errors
docker-compose logs web | grep -A 10 "scheduled download"

# Verify credentials
cat config/settings.json | grep -E "username|password"
```

## Performance Issues

### High memory usage

```bash
# Check container stats
docker stats

# Limit memory in docker-compose.yml
services:
  web:
    mem_limit: 2g

# Restart with limit
docker-compose down
docker-compose up -d
```

### High disk usage

```bash
# Check disk usage
du -sh downloads/
du -sh logs/

# Clean old files
find downloads/ -name "*.xls" -mtime +90 -delete
find logs/ -name "*.log" -mtime +30 -delete
```

## Docker Issues

### Container keeps restarting

```bash
# Check exit code
docker-compose ps

# View logs
docker-compose logs --tail=100 web

# Check health
docker inspect <container_id> | grep Health
```

### Cannot remove container

```bash
# Force remove
docker-compose down --remove-orphans

# Force remove volumes
docker-compose down -v

# Clean Docker system
docker system prune -a
```

## Common Error Messages

### "ModuleNotFoundError"

**Missing dependencies:**
```bash
# Rebuild container
docker-compose build --no-cache web
docker-compose up -d
```

### "Permission denied"

**File permissions:**
```bash
# Fix permissions
chmod -R 755 downloads/
chmod -R 755 logs/
chmod 644 config/settings.json
```

### "Connection refused"

**Network issues:**
```bash
# Check network
docker network ls
docker network inspect eclaim-req-download_eclaim-network

# Recreate network
docker-compose down
docker-compose up -d
```

## Logging & Debugging

### Enable debug logging

**Edit `.env`:**
```bash
FLASK_ENV=development
LOG_LEVEL=DEBUG
```

**Restart:**
```bash
docker-compose restart web
```

### View all logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f web
docker-compose logs -f db

# Last 100 lines
docker-compose logs --tail=100

# Since specific time
docker-compose logs --since 2026-01-08T10:00:00
```

### Log files location

```
logs/
├── downloader.log      # Download activity
├── import.log          # Import activity
└── app.log             # Application logs
```

## Getting Help

### Gather diagnostic information

```bash
# System info
docker --version
docker-compose --version
uname -a

# Container status
docker-compose ps

# Logs
docker-compose logs --tail=50 > logs_dump.txt

# Database status
docker-compose exec db psql -U eclaim -d eclaim_db -c "\dt"
docker-compose exec db psql -U eclaim -d eclaim_db -c "SELECT COUNT(*) FROM eclaim_imported_files;"
```

### Report an issue

Include:
1. Error message (full stack trace)
2. Steps to reproduce
3. Environment (OS, Docker version)
4. Logs (sanitize sensitive data)
5. Screenshots (if applicable)

**GitHub Issues:** https://github.com/aegisx-platform/eclaim-req-download/issues

---

**[← Back: Legal & Compliance](LEGAL.md)** | **[Next: Development Guide →](DEVELOPMENT.md)**
