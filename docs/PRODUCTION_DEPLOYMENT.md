# Production Deployment Guide

คู่มือการติดตั้งและ deploy ระบบ Revenue Intelligence System สำหรับ production environment

> ⚠️ **PRODUCTION ใช้ PRE-BUILT DOCKER IMAGES เท่านั้น**
> - ดึง images จาก `ghcr.io/aegisx-platform/eclaim-rep-download`
> - **ห้าม** git clone ใน production (ใช้สำหรับ development เท่านั้น)
> - **ห้าม** build from source

**Version:** v4.0.1
**Last Updated:** 2026-01-20

---

## Table of Contents

- [Quick Start](#quick-start)
- [Installation Methods](#installation-methods)
- [Permission Issues](#permission-issues)
- [Environment Setup](#environment-setup)
- [Security Hardening](#security-hardening)
- [HTTPS Setup](#https-setup)
- [Backup & Recovery](#backup--recovery)
- [Monitoring](#monitoring)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### One-Line Installation

```bash
# PostgreSQL (แนะนำ)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash

# MySQL
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --mysql

# External Database
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --no-db
```

**What happens:**
1. Downloads `docker-compose-deploy.yml` (uses pre-built image from ghcr.io)
2. Creates `.env` with credentials
3. Pulls `ghcr.io/aegisx-platform/eclaim-rep-download:latest`
4. Starts services
5. Imports seed data automatically

**Access:** http://localhost:5001

---

## Installation Methods

> **All methods use pre-built Docker images from `ghcr.io`**

### Method 1: One-Line Install Script (แนะนำ)

**ใช้สำหรับ:**
- ✅ Production servers
- ✅ Quick deployment
- ✅ Automatic setup

```bash
# Review script first (security best practice)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | less

# Run install
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash
```

### Method 2: Manual Setup (Full Control)

**ใช้สำหรับ:**
- ✅ Custom configurations
- ✅ Security-conscious deployments
- ✅ Specific version requirements

```bash
# 1. Create installation directory
mkdir -p ~/nhso-revenue
cd ~/nhso-revenue

# 2. Download docker-compose-deploy.yml (uses pre-built image)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/docker-compose-deploy.yml -o docker-compose.yml

# 3. Create directories
mkdir -p downloads/{rep,stm,smt} logs config

# 4. Create .env
cat > .env << 'EOF'
ECLAIM_USERNAME=your_username
ECLAIM_PASSWORD=your_password
VERSION=latest
WEB_PORT=5001
EOF

# 5. Edit credentials
nano .env

# 6. Pull pre-built image and start
docker compose pull
docker compose up -d

# 7. Wait for startup
docker compose logs -f web
# Wait for: "Starting Flask application..."

# 8. Import seed data
docker compose exec web python database/migrate.py --seed
docker compose exec web python database/seeds/health_offices_importer.py
docker compose exec web python database/seeds/nhso_error_codes_importer.py
```

**Pre-built images used:**
- `ghcr.io/aegisx-platform/eclaim-rep-download:latest`
- `ghcr.io/aegisx-platform/eclaim-rep-download:4.0.1` (specific version)
- `postgres:15-alpine` or `mysql:8.0`

---

## Permission Issues

### Issue: "Permission Denied" when Installing

**Symptom:**
```
mkdir: cannot create directory 'nhso-revenue': Permission denied
```

**Cause:**
- No write permission in current directory (`/app_data`, `/opt`, `/var`)

---

### Solution 1: Install in Home Directory (แนะนำ)

```bash
cd ~
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash
```

**Result:** Installed in `~/nhso-revenue`

---

### Solution 2: Custom Directory with Permission

```bash
# Specify directory you have permission to
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --dir ~/projects/nhso
```

---

### Solution 3: Use sudo with install.sh (Automated)

**⚠️ WARNING:** Use sudo ONLY when necessary. Review script thoroughly before running.

**✅ install.sh จะติดตั้งให้ครบ แล้วแสดงขั้นตอนต่อไปให้ทำเอง - ไม่ต้องเดา**

#### Step 1: Download and Review Script

**Important:** If you're in a directory without write permission (like `/app_data`), download to home directory first.

```bash
# Go to home directory (where you have write permission)
cd ~

# Download install script
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh -o install.sh

# If curl fails with "Failure writing output to destination":
# You don't have permission to write in current directory
# Use: cd ~ (go to home directory)

# Review code thoroughly (CRITICAL!)
less install.sh

# Check for suspicious commands
grep -E "rm -rf|curl.*\||eval" install.sh
```

**Alternative: Download with sudo (if needed)**
```bash
# If you must download in system directory
sudo curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh -o install.sh

# Review
less install.sh
```

#### Step 2: Run Installation with sudo

```bash
# Run install with sudo
sudo bash install.sh --dir /app_data/nhso-revenue

# When prompted, enter:
# ECLAIM_USERNAME: [your_citizen_id]
# ECLAIM_PASSWORD: [your_password]

# Wait for installation to complete...
```

**What happens (Automatic):**
1. ✅ Creates `/app_data/nhso-revenue` with proper permissions
2. ✅ Downloads docker-compose-deploy.yml
3. ✅ Creates directories: `downloads/`, `logs/`, `config/`
4. ✅ Creates `.env` file with your credentials
5. ✅ Pulls pre-built image: `ghcr.io/aegisx-platform/eclaim-rep-download:latest`
6. ✅ Starts services (Docker containers)
7. ✅ Imports seed data (9,247 hospitals + 312 error codes)
8. ✅ **Shows post-installation checklist** 👇

#### Step 3: Follow Post-Installation Instructions

**After installation completes, the script will show:**

```
⚠️  คุณใช้ sudo ติดตั้ง - ต้องทำขั้นตอนนี้ก่อนใช้งาน:

# 1. Fix file ownership
   sudo chown -R $USER:$USER /app_data/nhso-revenue

# 2. Add user to docker group
   sudo usermod -aG docker $USER

# 3. Logout and login again (สำคัญ!)
   exit
   # แล้ว SSH เข้ามาใหม่

# 4. Verify
   cd /app_data/nhso-revenue
   docker compose ps  # ต้องรันได้โดยไม่ต้อง sudo

❗ ถ้าไม่ทำขั้นตอนข้างบน จะใช้งานไม่ได้
```

**แค่ copy-paste คำสั่งที่ script แสดงให้:**

```bash
# 1. Fix ownership
sudo chown -R $USER:$USER /app_data/nhso-revenue

# 2. Add to docker group
sudo usermod -aG docker $USER

# 3. Logout and login (IMPORTANT!)
exit
# Then SSH back in

# 4. Verify installation
cd /app_data/nhso-revenue
docker compose ps  # Should work without sudo
curl http://localhost:5001/api/system/health  # Should return {"status": "healthy"}
```

#### Troubleshooting After sudo Install

> **💡 Good News:** install.sh จะบอกวิธีแก้ปัญหาทั้งหมดให้อัตโนมัติ - แค่ทำตามที่ script แสดง

**Problem: "curl: (23) Failure writing output to destination" (ก่อนรัน install.sh)**

```bash
# This means you don't have write permission in current directory

# Solution: Download to home directory instead
cd ~
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh -o install.sh

# OR: Use sudo curl
sudo curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh -o install.sh
```

**Problem: "permission denied" when running docker (หลัง install)**

```bash
# install.sh จะบอกให้ทำขั้นตอนนี้แล้ว แต่ถ้าลืมทำ:

# Check docker group membership
groups

# If 'docker' not listed:
sudo usermod -aG docker $USER

# MUST logout and login for changes to take effect
exit
# Then SSH again
```

**Problem: Files owned by root (หลัง install)**

```bash
# install.sh จะบอกให้ทำขั้นตอนนี้แล้ว:

# Fix ownership
sudo chown -R $USER:$USER /app_data/nhso-revenue

# Verify
ls -la /app_data/nhso-revenue
# Should show your username, not root
```

**Problem: Cannot edit .env file**

```bash
# Take ownership (install.sh บอกให้ทำแล้ว)
sudo chown $USER:$USER /app_data/nhso-revenue/.env
chmod 600 /app_data/nhso-revenue/.env

# Edit normally
nano /app_data/nhso-revenue/.env
```

---

#### Alternative: sudo bash -c (One-liner)

**⚠️ Less safe - harder to review:**

```bash
# This downloads and runs in one command
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh)"

# Still need to fix ownership after:
sudo chown -R $USER:$USER ~/nhso-revenue
sudo usermod -aG docker $USER
# Log out and log back in
```

**❌ WRONG - This won't work:**
```bash
sudo curl -fsSL ... | bash  # sudo only applies to curl, not bash
```

---

### Solution 4: Manual Setup in System Directory (Step-by-Step)

**Best for:** Full control over every step, security-conscious deployments

**Uses pre-built image:** `ghcr.io/aegisx-platform/eclaim-rep-download:latest`

#### Step 1: Create Directory Structure

```bash
# Create directory with sudo
sudo mkdir -p /app_data/nhso-revenue

# Create subdirectories
sudo mkdir -p /app_data/nhso-revenue/downloads/{rep,stm,smt}
sudo mkdir -p /app_data/nhso-revenue/logs
sudo mkdir -p /app_data/nhso-revenue/config
```

#### Step 2: Download docker-compose File

```bash
# Download docker-compose-deploy.yml
sudo curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/docker-compose-deploy.yml \
  -o /app_data/nhso-revenue/docker-compose.yml

# Verify download
cat /app_data/nhso-revenue/docker-compose.yml | head -20
```

#### Step 3: Fix Ownership (BEFORE creating .env)

```bash
# Change ownership to current user
sudo chown -R $USER:$USER /app_data/nhso-revenue

# Verify
ls -la /app_data/nhso-revenue
# Should show: drwxr-xr-x user user
```

#### Step 4: Add User to Docker Group

```bash
# Check current groups
groups

# If 'docker' not in the list, add user
sudo usermod -aG docker $USER

# Log out and log back in for changes to take effect
exit
# Then SSH/login again
```

#### Step 5: Create .env File

```bash
# Go to installation directory
cd /app_data/nhso-revenue

# Create .env file
cat > .env << 'EOF'
ECLAIM_USERNAME=your_username
ECLAIM_PASSWORD=your_password
VERSION=latest
WEB_PORT=5001
EOF

# Secure .env file
chmod 600 .env

# Edit with your actual credentials
nano .env
```

#### Step 6: Pull Image and Start Services

```bash
# Pull pre-built image
docker compose pull

# Verify image
docker images | grep eclaim-rep-download
# Should show: ghcr.io/aegisx-platform/eclaim-rep-download

# Start services
docker compose up -d

# Check status
docker compose ps
```

#### Step 7: Wait for Initialization

```bash
# Watch logs
docker compose logs -f web

# Wait for this message:
# "[entrypoint] Starting Flask application..."

# Press Ctrl+C to exit logs
```

#### Step 8: Import Seed Data

```bash
# Import dimension tables
docker compose exec web python database/migrate.py --seed

# Import health offices (9,247 hospitals)
docker compose exec web python database/seeds/health_offices_importer.py

# Import NHSO error codes
docker compose exec web python database/seeds/nhso_error_codes_importer.py
```

#### Step 9: Verify Installation

```bash
# Check web UI
curl http://localhost:5001/api/system/health

# Open in browser
# http://localhost:5001

# Go to setup page
# http://localhost:5001/setup
```

#### Troubleshooting Manual Setup

**Problem: "Permission denied" on docker compose**

```bash
# Verify user is in docker group
groups

# If not, add and re-login
sudo usermod -aG docker $USER
exit  # Log out
# Log back in
```

**Problem: Cannot write to /app_data/nhso-revenue**

```bash
# Check ownership
ls -la /app_data/nhso-revenue

# Should be owned by your user, not root
# If owned by root, fix it:
sudo chown -R $USER:$USER /app_data/nhso-revenue
```

**Problem: .env file has wrong permissions**

```bash
# Check permissions
ls -la /app_data/nhso-revenue/.env

# Should be: -rw------- (600)
# Fix if needed:
chmod 600 /app_data/nhso-revenue/.env
```

---

### Solution 5: Manual Setup for External Database (--no-db mode)

**Best for:** Using external/existing database, no need for database container

**Uses:** Pre-built image + external database connection

#### Quick Setup (Copy-Paste)

```bash
# 1. Create directory and fix ownership immediately
sudo mkdir -p /app_data/nhso-revenue && cd /app_data/nhso-revenue
sudo mkdir -p downloads/{rep,stm,smt} logs config
sudo chown -R $USER:$USER .

# 2. Download docker-compose for no-db mode
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/docker-compose-deploy-no-db.yml -o docker-compose.yml

# 3. Create .env file
cat > .env << 'EOF'
# Revenue Intelligence System
ECLAIM_USERNAME=your_username
ECLAIM_PASSWORD=your_password

# Docker Image Version
VERSION=latest
WEB_PORT=5001

# External Database Connection (แก้ไขให้ตรงกับ database ของคุณ)
DB_TYPE=postgresql
DB_HOST=your_db_host
DB_PORT=5432
DB_NAME=eclaim_db
DB_USER=eclaim
DB_PASSWORD=your_db_password
EOF

# 4. Edit .env with your actual values
nano .env
# แก้ไข: ECLAIM_USERNAME, ECLAIM_PASSWORD
# และ: DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD

# 5. Secure .env file
chmod 600 .env

# 6. Add to docker group (if not already)
sudo usermod -aG docker $USER
# Logout and login for this to take effect

# 7. Pull image and start
docker compose pull
docker compose up -d

# 8. Check logs
docker compose logs -f web
```

#### Verify Installation

```bash
# Check services
docker compose ps

# Check web health
curl http://localhost:5001/api/system/health

# Check database connection
docker compose logs web | grep -i "database"
```

#### External Database Requirements

Your external database must:
- ✅ Have schema initialized (run migrations)
- ✅ Allow connections from Docker container
- ✅ Have correct credentials in `.env`

**Initialize schema on external database:**
```bash
# If using external PostgreSQL
psql -h your_db_host -U eclaim -d eclaim_db < database/schema-postgresql-merged.sql

# If using external MySQL
mysql -h your_db_host -u eclaim -p eclaim_db < database/schema-mysql-merged.sql

# Or run migrations from container
docker compose exec web python database/migrate.py
```

---

### Common Permission Scenarios

| Scenario | Directory | Solution |
|----------|-----------|----------|
| Home directory | `~/nhso-revenue` | ✅ One-line install |
| User directory | `/home/user/apps` | ✅ One-line install |
| System directory | `/opt`, `/var`, `/app_data` | ⚠️ Use sudo + install.sh OR manual setup |
| NFS/Network mount | `/mnt/nas/apps` | ⚠️ Manual setup + check mount permissions |
| Docker volume | `/var/lib/docker/volumes` | ❌ Not recommended |

**Note:** All methods use pre-built Docker images from `ghcr.io`

---

## Environment Setup

### Production .env Configuration

```bash
# .env for production
ECLAIM_USERNAME=your_citizen_id
ECLAIM_PASSWORD=your_secure_password

# Database
DB_TYPE=postgresql
DB_HOST=db
DB_PORT=5432
DB_NAME=eclaim_db
DB_USER=eclaim
DB_PASSWORD=CHANGE_THIS_STRONG_PASSWORD  # ⚠️ CHANGE THIS!

# Flask
FLASK_ENV=production
SECRET_KEY=CHANGE_THIS_RANDOM_SECRET_KEY  # ⚠️ CHANGE THIS!
TZ=Asia/Bangkok

# Docker Image Version
VERSION=latest  # Or specific: 4.0.1
WEB_PORT=5001

# Optional: External Database
# DB_HOST=your-db-host.com
# DB_PORT=5432
```

**Generate Strong Passwords:**
```bash
# DB password
openssl rand -base64 32

# SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Directory Structure

```
/app_data/nhso-revenue/  # Or ~/nhso-revenue
├── docker-compose.yml   # Uses pre-built image
├── .env                 # Credentials (chmod 600)
├── downloads/
│   ├── rep/             # REP files
│   ├── stm/             # Statement files
│   └── smt/             # SMT files
├── logs/                # Application logs
└── config/              # Auto-generated settings
```

---

## Security Hardening

### 1. Secure .env File

```bash
chmod 600 .env
chown $USER:$USER .env

# Verify
ls -la .env
# Should show: -rw------- 1 user user
```

### 2. Firewall Configuration

```bash
# Ubuntu/Debian (ufw)
sudo ufw allow 5001/tcp comment 'NHSO Revenue Web'
sudo ufw allow from 192.168.1.0/24 to any port 5001  # Restrict to local network
sudo ufw enable

# Or iptables
sudo iptables -A INPUT -p tcp --dport 5001 -s 192.168.1.0/24 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 5001 -j DROP
```

### 3. Reverse Proxy with nginx (แนะนำสำหรับ Production)

```bash
# Install nginx
sudo apt-get install nginx

# Create nginx config
sudo nano /etc/nginx/sites-available/nhso-revenue
```

```nginx
# /etc/nginx/sites-available/nhso-revenue
server {
    listen 80;
    server_name eclaim.yourhospital.go.th;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name eclaim.yourhospital.go.th;

    # SSL certificates
    ssl_certificate /etc/letsencrypt/live/eclaim.yourhospital.go.th/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/eclaim.yourhospital.go.th/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy to Flask
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket/SSE support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
    }

    access_log /var/log/nginx/nhso-revenue-access.log;
    error_log /var/log/nginx/nhso-revenue-error.log;
}
```

```bash
# Enable site
sudo ln -s /etc/nginx/sites-available/nhso-revenue /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### 4. Let's Encrypt SSL (Free HTTPS)

```bash
# Install certbot
sudo apt-get install certbot python3-certbot-nginx

# Get certificate
sudo certbot --nginx -d eclaim.yourhospital.go.th

# Auto-renewal (certbot sets up cron automatically)
sudo certbot renew --dry-run
```

### 5. Network Isolation

```bash
# In docker-compose.yml, don't expose database port
# Access DB via: docker compose exec db psql -U eclaim
```

---

## HTTPS Setup

### Option 1: nginx Reverse Proxy (แนะนำ)

See [Security Hardening](#3-reverse-proxy-with-nginx-แนะนำสำหรับ-production) above.

### Option 2: Cloudflare Tunnel (Zero Trust)

```bash
# Install cloudflared
curl -L --output cloudflared.deb https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared.deb

# Login
cloudflared tunnel login

# Create tunnel
cloudflared tunnel create nhso-revenue

# Configure
cloudflared tunnel route dns nhso-revenue eclaim.yourhospital.go.th

# Run tunnel
cloudflared tunnel run nhso-revenue
```

---

## Backup & Recovery

### Database Backup

**PostgreSQL:**
```bash
# Manual backup
docker compose exec db pg_dump -U eclaim eclaim_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Compressed backup
docker compose exec db pg_dump -U eclaim eclaim_db | gzip > backup_$(date +%Y%m%d).sql.gz

# Automated daily backup (cron)
0 2 * * * cd /app_data/nhso-revenue && docker compose exec -T db pg_dump -U eclaim eclaim_db | gzip > backups/backup_$(date +\%Y\%m\%d).sql.gz
```

**MySQL:**
```bash
# Manual backup
docker compose exec db mysqldump -u eclaim -p eclaim_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Automated
0 2 * * * cd /app_data/nhso-revenue && docker compose exec -T db mysqldump -u eclaim -peclaim_password eclaim_db | gzip > backups/backup_$(date +\%Y\%m\%d).sql.gz
```

### Database Restore

**PostgreSQL:**
```bash
cat backup_20260120.sql | docker compose exec -T db psql -U eclaim -d eclaim_db

# From compressed
gunzip -c backup_20260120.sql.gz | docker compose exec -T db psql -U eclaim -d eclaim_db
```

**MySQL:**
```bash
cat backup_20260120.sql | docker compose exec -T db mysql -u eclaim -peclaim_password eclaim_db
```

### Full System Backup Script

```bash
#!/bin/bash
# /app_data/nhso-revenue/backup.sh

BACKUP_DIR="/backup/nhso-revenue"
DATE=$(date +%Y%m%d_%H%M%S)

mkdir -p $BACKUP_DIR/$DATE
cd /app_data/nhso-revenue

# Backup database
docker compose exec -T db pg_dump -U eclaim eclaim_db | gzip > $BACKUP_DIR/$DATE/database.sql.gz

# Backup files
tar -czf $BACKUP_DIR/$DATE/downloads.tar.gz downloads/
tar -czf $BACKUP_DIR/$DATE/config.tar.gz config/ .env

# Keep last 30 days
find $BACKUP_DIR -mtime +30 -type d -exec rm -rf {} +

echo "Backup completed: $BACKUP_DIR/$DATE"
```

**Add to cron:**
```bash
# Daily at 2 AM
0 2 * * * /app_data/nhso-revenue/backup.sh >> /var/log/nhso-backup.log 2>&1
```

---

## Monitoring

### Health Checks

```bash
# Service status
docker compose ps

# Web health
curl http://localhost:5001/api/system/health

# Database
docker compose exec db psql -U eclaim -d eclaim_db -c "SELECT 1;"
```

### Log Monitoring

```bash
# Real-time logs
docker compose logs -f web

# Search errors
docker compose logs web | grep -i error

# Save logs
docker compose logs --no-color > logs/docker_$(date +%Y%m%d).log
```

### Disk Space Monitoring

```bash
# Check disk
df -h

# Check downloads size
du -sh downloads/

# Clean old files (90+ days)
find downloads/ -type f -mtime +90 -delete
```

### Resource Usage

```bash
# Container stats
docker stats

# Memory
free -h

# CPU
top -b -n 1 | head -20
```

---

## Troubleshooting

### 1. Permission Denied

See [Permission Issues](#permission-issues) section above.

### 2. Port Already in Use

```bash
# Find process
sudo lsof -i :5001

# Change port in .env
echo "WEB_PORT=5002" >> .env
docker compose down && docker compose up -d
```

### 3. Database Connection Failed

```bash
# Check database logs
docker compose logs db

# Wait for DB ready
docker compose exec web python database/migrate.py --status

# Restart
docker compose restart
```

### 4. Out of Disk Space

```bash
# Check disk
df -h

# Clean Docker
docker system prune -a

# Clean old downloads
find downloads/ -type f -mtime +90 -delete

# Clean logs
find logs/ -name "*.log" -mtime +30 -delete
```

### 5. Slow Performance

**Database:**
```bash
# PostgreSQL vacuum
docker compose exec db psql -U eclaim -d eclaim_db -c "VACUUM ANALYZE;"

# Check stats
docker compose exec db psql -U eclaim -d eclaim_db -c "SELECT * FROM pg_stat_activity;"
```

**Memory:**
```bash
# Check memory
free -h

# Increase PostgreSQL shared_buffers (in docker-compose.yml)
# command: postgres -c shared_buffers=256MB -c max_connections=100

docker compose down && docker compose up -d
```

---

## Production Checklist

### Pre-Deployment

- [ ] Review and understand install script
- [ ] Strong passwords in `.env` (DB_PASSWORD, SECRET_KEY)
- [ ] Secure `.env` permissions (chmod 600)
- [ ] Firewall configured
- [ ] Reverse proxy setup (nginx + HTTPS)
- [ ] SSL certificate installed
- [ ] Backup strategy in place
- [ ] **Using pre-built images** (not git clone)

### Post-Deployment

- [ ] Services running (`docker compose ps`)
- [ ] Web UI accessible (http://localhost:5001)
- [ ] Database connected (check /setup)
- [ ] Seed data imported (health_offices, error_codes)
- [ ] Hospital Code configured
- [ ] NHSO credentials tested
- [ ] Scheduled backups working
- [ ] Monitoring in place
- [ ] Log rotation configured

### Security

- [ ] `.env` secured (chmod 600)
- [ ] Database not exposed to internet
- [ ] HTTPS enabled
- [ ] Security headers configured
- [ ] Access restricted to authorized users
- [ ] Firewall rules active

### Maintenance

- [ ] Backup schedule: Daily at 2 AM
- [ ] Log rotation: Keep 30 days
- [ ] File cleanup: Remove 90+ day old files
- [ ] Update check: Monthly
- [ ] Health check: Weekly

---

## Version Updates

```bash
# Set version in .env
echo "VERSION=4.0.1" >> .env

# Pull new image
docker compose pull

# Restart
docker compose up -d

# Check migrations
docker compose exec web python database/migrate.py --status
```

**Available versions:**
- `latest` - Latest stable release
- `4.0.1`, `4.0.0` - Specific versions
- `main` - Main branch (not recommended for production)
- `develop` - Development branch (not for production)

---

## Support

- **Documentation:** [github.com/aegisx-platform/eclaim-rep-download](https://github.com/aegisx-platform/eclaim-rep-download)
- **Issues:** [GitHub Issues](https://github.com/aegisx-platform/eclaim-rep-download/issues)
- **Security:** Report security issues to repository maintainer

---

## Important Notes

### ✅ Production Best Practices

- **Use pre-built images** from `ghcr.io/aegisx-platform/eclaim-rep-download`
- **Don't** use git clone (for development only)
- **Don't** build from source in production
- Use specific version tags (e.g., `4.0.1`) instead of `latest` for stability
- Review and secure `.env` file
- Enable HTTPS with nginx reverse proxy
- Schedule regular backups
- Monitor logs and resources

### 📚 For Development

See [Installation Guide](INSTALLATION_GUIDE.md) for git clone and development setup.

---

**Version:** v4.0.1
**Last Updated:** 2026-01-20

**[← Back to README](../README.md)**
