# Production Deployment Guide

คู่มือการติดตั้งและ deploy ระบบ NHSO Revenue Intelligence สำหรับ production environment

**Version:** v4.0.0
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

### One-Line Installation (สำหรับ Production)

```bash
# PostgreSQL (แนะนำ)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash

# MySQL
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --mysql

# External Database (ใช้ database ที่มีอยู่แล้ว)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --no-db
```

**Installation Flow:**
```
[1/7] Check requirements (Docker)
[2/7] Create installation directory
[3/7] Download docker-compose config
[4/7] Configure credentials (ECLAIM_USERNAME, ECLAIM_PASSWORD)
[5/7] Start services
[6/7] Wait for database initialization
[7/7] Import seed data (dim_date, health_offices, error_codes)
→ Ready! Access at http://localhost:5001
```

---

## Installation Methods

### Method 1: One-Line Install (แนะนำสำหรับผู้ใช้ทั่วไป)

**ข้อดี:**
- ✅ ติดตั้งครั้งเดียวเสร็จ
- ✅ Auto-seed data
- ✅ Guided setup

**ข้อเสี้ย:**
- ❌ ต้อง review code ก่อน (security concern)

```bash
# Review script ก่อนรัน (แนะนำ)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | less

# Run install
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash
```

### Method 2: Download & Run (แนะนำสำหรับ Production Server)

**ข้อดี:**
- ✅ Review code ก่อนรัน
- ✅ Full control
- ✅ Can modify script if needed

```bash
# 1. Download script
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh -o install.sh

# 2. Review script (IMPORTANT!)
less install.sh
# หรือ
cat install.sh | grep -E "rm -rf|sudo|curl"  # Check suspicious commands

# 3. Run install
bash install.sh

# 4. Cleanup
rm install.sh
```

### Method 3: Git Clone (แนะนำสำหรับ Developer)

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-rep-download.git
cd eclaim-rep-download

# 2. Setup environment
cp .env.example .env
nano .env  # Edit ECLAIM_USERNAME and ECLAIM_PASSWORD

# 3. Start services
docker-compose up -d

# 4. Run seed data
make seed-all
# หรือ
docker-compose exec web python database/migrate.py --seed
docker-compose exec web python database/seeds/health_offices_importer.py
docker-compose exec web python database/seeds/nhso_error_codes_importer.py

# 5. Set Hospital Code
open http://localhost:5001/setup
```

---

## Permission Issues

### Issue: "Permission Denied" when Installing

**Symptom:**
```bash
dixon@server:/app_data$ curl -fsSL ... | bash -s -- --no-db
...
[2/5] Creating installation directory...
mkdir: cannot create directory 'nhso-revenue': Permission denied
```

**สาเหตุ:**
- User ไม่มี permission เขียนไฟล์ใน current directory (เช่น `/app_data`, `/opt`, `/var`)

**Solutions:**

#### Solution 1: ติดตั้งใน Home Directory (แนะนำ)

```bash
# ไปที่ home directory
cd ~

# Run install
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash

# Access
cd ~/nhso-revenue
docker compose logs -f web
```

#### Solution 2: ใช้ Custom Directory ที่มี Permission

```bash
# ระบุ directory ที่มี permission
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --dir ~/projects/nhso

# หรือ
mkdir -p ~/projects/nhso
cd ~/projects/nhso
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --dir .
```

#### Solution 3: ใช้ sudo (ถ้าจำเป็น)

**⚠️ WARNING:** ใช้ sudo เฉพาะเมื่อจำเป็นและ **ต้อง review script ก่อน**

```bash
# วิธีที่ 1: Download แล้ว sudo run
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh -o install.sh
less install.sh  # REVIEW FIRST!
sudo bash install.sh --dir /app_data/nhso-revenue
rm install.sh

# วิธีที่ 2: sudo bash -c
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh)"

# ❌ WRONG: sudo curl ... | bash (sudo ใช้กับ curl เท่านั้น)
sudo curl -fsSL ... | bash  # This will NOT work
```

**หลังใช้ sudo ต้อง fix permission:**
```bash
# Fix ownership
sudo chown -R $USER:$USER /app_data/nhso-revenue

# Fix docker permission
sudo usermod -aG docker $USER
# Log out and log back in
```

#### Solution 4: Git Clone แล้ว Copy Config (Safest)

```bash
# 1. Clone ที่ home directory
cd ~
git clone https://github.com/aegisx-platform/eclaim-rep-download.git

# 2. Copy compose file ไปยัง target directory
sudo mkdir -p /app_data/nhso-revenue
sudo cp ~/eclaim-rep-download/docker-compose-deploy.yml /app_data/nhso-revenue/docker-compose.yml

# 3. Setup directories
cd /app_data/nhso-revenue
sudo mkdir -p downloads/{rep,stm,smt} logs config
sudo chown -R $USER:$USER .

# 4. Create .env
cat > .env << EOF
ECLAIM_USERNAME=your_username
ECLAIM_PASSWORD=your_password
VERSION=latest
WEB_PORT=5001
EOF

# 5. Start
docker compose up -d
```

### Common Permission Scenarios

| Scenario | Directory | Solution |
|----------|-----------|----------|
| Home directory | `~/nhso-revenue` | ✅ Direct install |
| User directory | `/home/user/apps` | ✅ Direct install |
| System directory | `/opt`, `/var`, `/app_data` | ⚠️ Use sudo or git clone |
| NFS/Network mount | `/mnt/nas/apps` | ⚠️ Check mount permissions |
| Docker volume | `/var/lib/docker/volumes` | ❌ Not recommended |

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

# Docker
VERSION=latest  # หรือ v4.0.0 สำหรับ production
WEB_PORT=5001

# Optional: External Database
# DB_HOST=your-db-host.com
# DB_PORT=5432
# DB_NAME=eclaim_db
# DB_USER=eclaim
# DB_PASSWORD=your_password
```

**Generate Strong Passwords:**
```bash
# Generate random DB password
openssl rand -base64 32

# Generate SECRET_KEY
python3 -c "import secrets; print(secrets.token_hex(32))"
```

### Directory Structure

```
/app_data/nhso-revenue/  # Or ~/nhso-revenue
├── docker-compose.yml   # Docker configuration
├── .env                 # Credentials (MUST be secured!)
├── downloads/           # Downloaded files
│   ├── rep/             # REP files (OP/IP)
│   ├── stm/             # Statement files
│   └── smt/             # SMT Budget files
├── logs/                # Application logs
└── config/              # User settings
    └── settings.json    # Auto-generated
```

---

## Security Hardening

### 1. Secure .env File

```bash
# Set restrictive permissions
chmod 600 .env
chown $USER:$USER .env

# Verify
ls -la .env
# Should show: -rw------- 1 user user
```

### 2. Firewall Configuration

```bash
# Ubuntu/Debian with ufw
sudo ufw allow 5001/tcp comment 'NHSO Revenue Web UI'
sudo ufw allow from 192.168.1.0/24 to any port 5001  # Restrict to local network
sudo ufw enable

# Or with iptables
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

    # Redirect to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name eclaim.yourhospital.go.th;

    # SSL certificates (ใช้ Let's Encrypt)
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

        # WebSocket support (for SSE logs)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_buffering off;
    }

    # Access log
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

# Auto-renewal (certbot ตั้ง cron ให้อัตโนมัติ)
sudo certbot renew --dry-run
```

### 5. Network Isolation

```bash
# Restrict database to localhost only
# In docker-compose.yml, remove ports: for db service
# Access DB via docker exec only
```

### 6. Disable Debug Mode

```bash
# In .env
FLASK_ENV=production  # NOT development
FLASK_DEBUG=0
```

---

## HTTPS Setup

### Option 1: nginx Reverse Proxy (แนะนำ)

See [Security Hardening](#3-reverse-proxy-with-nginx-แนะนำสำหรับ-production) above.

### Option 2: Docker Compose with nginx SSL

```bash
# Use docker-compose-https.yml
docker-compose -f docker-compose-https.yml up -d
```

**Requires:**
- SSL certificate files in `certs/` directory
- Edit `docker-compose-https.yml` with your domain

---

## Backup & Recovery

### Database Backup

**PostgreSQL:**
```bash
# Manual backup
docker compose exec db pg_dump -U eclaim eclaim_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Automated daily backup (cron)
0 2 * * * cd /app_data/nhso-revenue && docker compose exec -T db pg_dump -U eclaim eclaim_db > backups/backup_$(date +\%Y\%m\%d).sql

# Backup with compression
docker compose exec db pg_dump -U eclaim eclaim_db | gzip > backup_$(date +%Y%m%d).sql.gz
```

**MySQL:**
```bash
# Manual backup
docker compose exec db mysqldump -u eclaim -p eclaim_db > backup_$(date +%Y%m%d_%H%M%S).sql

# Automated
0 2 * * * cd /app_data/nhso-revenue && docker compose exec -T db mysqldump -u eclaim -peclaim_password eclaim_db > backups/backup_$(date +\%Y\%m\%d).sql
```

### Database Restore

**PostgreSQL:**
```bash
# Restore from backup
cat backup_20260120.sql | docker compose exec -T db psql -U eclaim -d eclaim_db

# Or from compressed backup
gunzip -c backup_20260120.sql.gz | docker compose exec -T db psql -U eclaim -d eclaim_db
```

**MySQL:**
```bash
# Restore
cat backup_20260120.sql | docker compose exec -T db mysql -u eclaim -peclaim_password eclaim_db
```

### Full System Backup

```bash
# Backup ทุกอย่าง (database + files + config)
#!/bin/bash
BACKUP_DIR="/backup/nhso-revenue"
DATE=$(date +%Y%m%d_%H%M%S)

# Create backup directory
mkdir -p $BACKUP_DIR/$DATE

# Backup database
cd /app_data/nhso-revenue
docker compose exec -T db pg_dump -U eclaim eclaim_db | gzip > $BACKUP_DIR/$DATE/database.sql.gz

# Backup files
tar -czf $BACKUP_DIR/$DATE/downloads.tar.gz downloads/
tar -czf $BACKUP_DIR/$DATE/config.tar.gz config/ .env

# Keep only last 30 days
find $BACKUP_DIR -mtime +30 -type d -exec rm -rf {} +

echo "Backup completed: $BACKUP_DIR/$DATE"
```

**Add to cron:**
```bash
# Daily backup at 2 AM
0 2 * * * /app_data/nhso-revenue/backup.sh >> /var/log/nhso-backup.log 2>&1
```

---

## Monitoring

### Health Checks

```bash
# Check service status
docker compose ps

# Check web health
curl http://localhost:5001/api/system/health

# Check database
docker compose exec db psql -U eclaim -d eclaim_db -c "SELECT 1;"
```

### Log Monitoring

```bash
# View real-time logs
docker compose logs -f web

# View specific service
docker compose logs -f db

# Search for errors
docker compose logs web | grep -i error

# Save logs
docker compose logs --no-color > logs/docker_$(date +%Y%m%d).log
```

### Disk Space Monitoring

```bash
# Check disk usage
df -h

# Check downloads/ size
du -sh downloads/

# Clean old files (older than 90 days)
find downloads/ -type f -mtime +90 -delete
```

### System Resources

```bash
# Check container resources
docker stats

# Check memory usage
free -h

# Check CPU usage
top -b -n 1 | head -20
```

---

## Troubleshooting

### 1. Permission Denied on Startup

**Symptom:**
```
Error: Cannot create directory: Permission denied
```

**Solution:**
```bash
# Fix ownership
sudo chown -R $USER:$USER /app_data/nhso-revenue

# Fix docker permission
sudo usermod -aG docker $USER
# Log out and log back in
```

### 2. Port Already in Use

**Symptom:**
```
Error: port 5001 is already allocated
```

**Solution:**
```bash
# Find process using port
sudo lsof -i :5001

# Kill process or change port in .env
echo "WEB_PORT=5002" >> .env
docker compose down && docker compose up -d
```

### 3. Database Connection Failed

**Symptom:**
```
connection to server at "db" failed
```

**Solution:**
```bash
# Check database logs
docker compose logs db

# Wait for database to be ready
docker compose exec web python database/migrate.py --status

# Restart services
docker compose restart
```

### 4. Out of Disk Space

**Symptom:**
```
Error: no space left on device
```

**Solution:**
```bash
# Check disk space
df -h

# Clean old Docker images
docker system prune -a

# Clean old downloads
find downloads/ -type f -mtime +90 -delete

# Clean logs
find logs/ -name "*.log" -mtime +30 -delete
```

### 5. Slow Performance

**Causes & Solutions:**

**Database slow:**
```bash
# Check PostgreSQL stats
docker compose exec db psql -U eclaim -d eclaim_db -c "SELECT * FROM pg_stat_activity;"

# Vacuum database
docker compose exec db psql -U eclaim -d eclaim_db -c "VACUUM ANALYZE;"
```

**Memory issues:**
```bash
# Check memory
free -h

# Increase PostgreSQL shared_buffers (in docker-compose.yml)
# Add: command: postgres -c shared_buffers=256MB -c max_connections=100

# Restart
docker compose down && docker compose up -d
```

**Disk I/O issues:**
```bash
# Check I/O
iostat -x 1

# Move downloads/ to faster disk
# Or use SSD for database volume
```

---

## Production Checklist

### Pre-Deployment

- [ ] Review installation script
- [ ] Strong passwords in `.env` (DB_PASSWORD, SECRET_KEY)
- [ ] Secure `.env` permissions (chmod 600)
- [ ] Firewall configured
- [ ] Reverse proxy setup (nginx + HTTPS)
- [ ] SSL certificate installed
- [ ] Backup strategy in place

### Post-Deployment

- [ ] Services running (`docker compose ps`)
- [ ] Web UI accessible (http://localhost:5001)
- [ ] Database connected (check /setup page)
- [ ] Seed data imported (health_offices, error_codes)
- [ ] Hospital Code configured
- [ ] NHSO credentials tested
- [ ] Scheduled backups working
- [ ] Monitoring in place
- [ ] Log rotation configured

### Security

- [ ] `.env` file secured (chmod 600)
- [ ] Database not exposed to internet
- [ ] HTTPS enabled
- [ ] Security headers configured
- [ ] Access restricted to authorized users
- [ ] API keys secured (if using External API)

### Maintenance

- [ ] Backup schedule: Daily at 2 AM
- [ ] Log rotation: Keep 30 days
- [ ] File cleanup: Remove files older than 90 days
- [ ] Update check: Monthly
- [ ] Health check: Weekly

---

## Support

- **Documentation:** [github.com/aegisx-platform/eclaim-rep-download](https://github.com/aegisx-platform/eclaim-rep-download)
- **Issues:** [GitHub Issues](https://github.com/aegisx-platform/eclaim-rep-download/issues)
- **Security:** Report security issues to repository maintainer

---

**Version:** v4.0.0
**Last Updated:** 2026-01-20

**[← Back to README](../README.md)**
