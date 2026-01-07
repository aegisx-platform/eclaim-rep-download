# 🐳 Docker Setup Guide

Complete Docker setup for E-Claim Downloader with PostgreSQL database.

## 📋 Prerequisites

- Docker Desktop installed (or Docker Engine + Docker Compose)
- At least 2GB free disk space
- Ports 5001, 5432, 5050 available

---

## 🚀 Quick Start

### 1. Clone and Configure

```bash
# Copy environment template
cp .env.example .env

# Edit credentials
nano .env  # or vim, code, etc.
```

Update your E-Claim credentials in `.env`:
```bash
ECLAIM_USERNAME=your_actual_username
ECLAIM_PASSWORD=your_actual_password
```

### 2. Start All Services

```bash
# Build and start containers
docker-compose up -d

# View logs
docker-compose logs -f
```

### 3. Access Services

- **Web UI**: http://localhost:5001
- **Database**: postgresql://eclaim:eclaim_password@localhost:5432/eclaim_db
- **pgAdmin** (optional): http://localhost:5050
  - Email: `admin@eclaim.local`
  - Password: `admin`

---

## 🎯 Usage

### Web Interface

1. **Dashboard**: http://localhost:5001/dashboard
   - View downloaded files
   - See statistics

2. **Download Config**: http://localhost:5001/download-config
   - Select date range
   - Trigger bulk downloads

3. **Files**: http://localhost:5001/files
   - Browse downloaded files
   - Delete files

### CLI Commands (inside container)

```bash
# Access container shell
docker-compose exec web bash

# Analyze XLS file
python eclaim_import.py --analyze downloads/file.xls

# Import single file
python eclaim_import.py downloads/file.xls

# Import all files
python eclaim_import.py

# Exit container
exit
```

---

## 🗄️ Database Management

### Using psql

```bash
# Connect to database
docker-compose exec db psql -U eclaim -d eclaim_db

# View tables
\dt

# View imported files
SELECT * FROM eclaim_imported_files ORDER BY created_at DESC;

# Exit
\q
```

### Using pgAdmin (GUI)

1. Start pgAdmin: `docker-compose --profile tools up -d`
2. Open http://localhost:5050
3. Add New Server:
   - **Name**: E-Claim DB
   - **Host**: db
   - **Port**: 5432
   - **Username**: eclaim
   - **Password**: eclaim_password

### Backup Database

```bash
# Backup to file
docker-compose exec db pg_dump -U eclaim eclaim_db > backup.sql

# Restore from file
docker-compose exec -T db psql -U eclaim eclaim_db < backup.sql
```

---

## 🔧 Docker Commands

### Container Management

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# Restart services
docker-compose restart

# View status
docker-compose ps

# View logs
docker-compose logs -f web     # Flask app logs
docker-compose logs -f db      # PostgreSQL logs
```

### Rebuild After Code Changes

```bash
# Rebuild web container
docker-compose build web

# Restart with new build
docker-compose up -d --build web
```

### Reset Everything

```bash
# Stop and remove containers, networks
docker-compose down

# Remove volumes (WARNING: deletes all data!)
docker-compose down -v

# Clean restart
docker-compose up -d --build
```

---

## 📊 Monitoring

### Resource Usage

```bash
# View CPU/Memory usage
docker stats

# View disk usage
docker system df
```

### Health Checks

```bash
# Check service health
docker-compose ps

# Healthy services show:
# - State: Up (healthy)
```

---

## 🐛 Troubleshooting

### Port Already in Use

```
Error: Bind for 0.0.0.0:5001 failed: port is already allocated
```

**Solution:**
```bash
# Find process using port
lsof -i :5001

# Kill process or change port in docker-compose.yml
ports:
  - "5002:5001"  # Change host port to 5002
```

### Database Connection Failed

```
Error: could not connect to server: Connection refused
```

**Solution:**
```bash
# Check database is running
docker-compose ps db

# Check logs
docker-compose logs db

# Restart database
docker-compose restart db
```

### Web Container Keeps Restarting

```bash
# View logs
docker-compose logs web

# Common issues:
# 1. Database not ready - wait 30 seconds
# 2. Missing dependencies - rebuild
docker-compose build web
```

### Import Fails Inside Container

```bash
# Check file permissions
docker-compose exec web ls -la downloads/

# If permission denied:
chmod -R 755 downloads/
docker-compose restart web
```

---

## 🔐 Security Notes

### Production Deployment

**DO NOT use default passwords in production!**

Change in `docker-compose.yml`:
```yaml
environment:
  POSTGRES_PASSWORD: <strong_random_password>
  DB_PASSWORD: <strong_random_password>
  PGADMIN_DEFAULT_PASSWORD: <strong_random_password>
```

### Network Security

For production:
1. Remove port mappings (5432, 5050) if not needed externally
2. Use Docker secrets for passwords
3. Enable SSL/TLS for PostgreSQL
4. Use HTTPS for Flask (nginx reverse proxy)

---

## 📁 Volume Persistence

Data is persisted in Docker volumes:

| Volume | Contains | Backup? |
|--------|----------|---------|
| `postgres_data` | Database files | ✅ Yes |
| `./downloads` | Downloaded XLS files | ✅ Yes |
| `./logs` | Application logs | ⚠️ Optional |

### Backup Strategy

```bash
# 1. Backup database
docker-compose exec db pg_dump -U eclaim eclaim_db > db_backup.sql

# 2. Backup downloads folder
tar -czf downloads_backup.tar.gz downloads/

# 3. Backup both
./backup.sh  # See below
```

**backup.sh** (create this):
```bash
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker-compose exec db pg_dump -U eclaim eclaim_db > "backups/db_${DATE}.sql"
tar -czf "backups/downloads_${DATE}.tar.gz" downloads/
echo "Backup completed: ${DATE}"
```

---

## 🚦 Development Workflow

### Hot Reload

Code changes are automatically detected (volume mount):
```yaml
volumes:
  - .:/app  # Source code mounted
```

Flask will auto-reload on file changes.

### Debugging

```bash
# View live logs
docker-compose logs -f web

# Enter container for debugging
docker-compose exec web bash

# Run Python debugger
docker-compose exec web python -m pdb app.py
```

---

## 📈 Scaling (Optional)

### Multiple Workers

```bash
# Scale web service
docker-compose up -d --scale web=3

# Load balancer needed (nginx)
```

---

## 🧪 Testing

### Run Tests Inside Container

```bash
# Unit tests
docker-compose exec web python -m pytest

# Integration tests
docker-compose exec web python -m pytest tests/integration/
```

---

## 📝 Environment Variables

Full list of configurable variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `ECLAIM_USERNAME` | - | E-Claim login username |
| `ECLAIM_PASSWORD` | - | E-Claim login password |
| `DB_TYPE` | postgresql | Database type |
| `DB_HOST` | db | Database host |
| `DB_PORT` | 5432 | Database port |
| `DB_NAME` | eclaim_db | Database name |
| `DB_USER` | eclaim | Database user |
| `DB_PASSWORD` | eclaim_password | Database password |
| `FLASK_ENV` | development | Flask environment |

---

## 🆘 Support

### Logs Location

- Flask logs: `docker-compose logs web`
- PostgreSQL logs: `docker-compose logs db`
- Application logs: `./logs/` directory

### Common Issues

1. **"Container exits immediately"** → Check logs: `docker-compose logs web`
2. **"Database not responding"** → Wait 30s for initialization
3. **"Permission denied"** → Check file ownership: `ls -la downloads/`

---

## 🔄 Updates

### Update Application

```bash
# Pull latest code
git pull

# Rebuild and restart
docker-compose up -d --build
```

### Update Dependencies

Edit `requirements.txt`, then:
```bash
docker-compose build web
docker-compose up -d web
```

---

*Last updated: 2026-01-07*
