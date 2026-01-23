# Installation Guide

คู่มือการติดตั้ง Revenue Intelligence System v4.0.0

---

## Table of Contents

- [Requirements](#requirements)
- [Quick Install](#quick-install-แนะนำ)
- [Manual Install](#manual-install-สำหรับ-developer)
- [Post-Installation](#post-installation)
- [Update & Upgrade](#update--upgrade)
- [Uninstall](#uninstall)
- [Troubleshooting](#troubleshooting)

---

## Requirements

### System Requirements

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| RAM | 2 GB | 4 GB |
| Disk | 10 GB | 50 GB |
| CPU | 2 cores | 4 cores |

### Software Requirements

- **Docker** 20.10+
- **Docker Compose** 2.0+

### ตรวจสอบ Docker

```bash
docker --version
# Docker version 24.0.0 or higher

docker compose version
# Docker Compose version v2.20.0 or higher
```

### ติดตั้ง Docker

**Ubuntu/Debian:**
```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
# Log out and log back in
```

**macOS / Windows:**
- Download [Docker Desktop](https://www.docker.com/products/docker-desktop/)

---

## Quick Install (แนะนำ)

### One-Line Install

```bash
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash
```

### ติดตั้งด้วย sudo (ถ้าต้องการ)

ถ้าต้องการติดตั้งใน directory ที่ต้องใช้ sudo:

```bash
# วิธีที่ 1: Download และ review ก่อน (แนะนำ)
cd ~
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh -o install.sh
less install.sh  # Review script
sudo bash install.sh --dir /app_data/nhso-revenue

# หลังติดตั้ง script จะแสดงขั้นตอนต่อไป:
# 1. Fix ownership: sudo chown -R $USER:$USER /app_data/nhso-revenue
# 2. Add to docker group: sudo usermod -aG docker $USER
# 3. Logout and login again

# วิธีที่ 2: One-liner (ไม่แนะนำ - ยากต่อการ review)
sudo bash -c "$(curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh)"
```

> ⚠️ **หมายเหตุ:**
> - `sudo curl ... | bash` จะไม่ทำงาน เพราะ sudo ใช้กับ curl อย่างเดียว
> - install.sh จะแสดงขั้นตอนหลังติดตั้งให้ทำ (fix ownership, docker group, logout/login)
> - **ต้อง** ทำตามที่ script บอกก่อนใช้งาน มิฉะนั้นจะใช้ docker ไม่ได้

### ตัวอย่างการติดตั้ง

```
$ curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash

╔═══════════════════════════════════════════════════════════╗
║        Revenue Intelligence System - Quick Install          ║
╚═══════════════════════════════════════════════════════════╝

การติดตั้ง:
  📁 โฟลเดอร์: /home/user/nhso-revenue
  🗄️  Database: PostgreSQL
  🐳 Version:  latest

ยืนยันการติดตั้ง? (Y/n): y

[1/5] Checking requirements...
✓ Docker found

[2/5] Creating installation directory...
✓ Created: /home/user/nhso-revenue

[3/5] Downloading configuration...
✓ Downloaded docker-compose.yml (postgresql)
✓ Created directories

[4/5] Configuring credentials...

กรุณาใส่ข้อมูลเข้าสู่ระบบ E-Claim:

ECLAIM_USERNAME: hospital_user
ECLAIM_PASSWORD: ********
✓ Created .env

[5/5] Starting services...
[+] Pulling web...
[+] Running 2/2
 ✔ Container nhso-db   Started
 ✔ Container nhso-web  Started

╔═══════════════════════════════════════════════════════════╗
║              Installation Complete!                       ║
╚═══════════════════════════════════════════════════════════╝

🌐 เข้าใช้งาน: http://localhost:5001
```

### Installation Options

| Option | Command | Description |
|--------|---------|-------------|
| PostgreSQL | (default) | สร้าง PostgreSQL container ใน compose |
| MySQL | `--mysql` | สร้าง MySQL container ใน compose |
| External DB | `--no-db` | เชื่อมต่อ Database ภายนอก (ไม่สร้าง container DB) |
| Custom Dir | `--dir NAME` | กำหนดชื่อโฟลเดอร์ |

> **หมายเหตุ:** `--no-db` จะสร้าง template ใน `.env` ให้แก้ไข DB_HOST, DB_PORT, DB_NAME, DB_USER, DB_PASSWORD ก่อนใช้งาน

**Examples:**

```bash
# PostgreSQL (default)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash

# MySQL
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --mysql

# Download only (no database)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --no-db

# Custom directory
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --dir my-hospital

# Combined options
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --mysql --dir hospital-nhso
```

### โครงสร้างหลังติดตั้ง

```
nhso-revenue/
├── docker-compose.yml    # Docker configuration
├── .env                  # Credentials & settings
├── downloads/            # Downloaded files
│   ├── rep/              # REP files
│   ├── stm/              # Statement files
│   └── smt/              # SMT Budget files
├── logs/                 # Application logs
└── config/               # User settings
```

---

## Manual Install (สำหรับ Developer)

### Clone & Run

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-rep-download.git
cd eclaim-rep-download

# 2. Setup environment
cp .env.example .env
nano .env  # แก้ไข ECLAIM_USERNAME และ ECLAIM_PASSWORD

# 3. Start services
docker-compose up -d
```

### Database Options

```bash
# PostgreSQL (default)
docker-compose up -d

# MySQL
docker-compose -f docker-compose-mysql.yml up -d

# Download only (no database)
docker-compose -f docker-compose-no-db.yml up -d
```

### Without Docker (Python)

```bash
# 1. Create virtual environment
python3.12 -m venv venv
source venv/bin/activate

# 2. Install dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env
nano .env

# 4. Setup database (optional)
psql -U postgres -c "CREATE DATABASE eclaim_db"
psql -U postgres -d eclaim_db -f database/schema-postgresql-merged.sql

# 5. Run
python app.py
```

---

## Post-Installation

### เข้าใช้งาน

เปิด browser: **http://localhost:5001**

| Page | URL | Description |
|------|-----|-------------|
| Dashboard | /dashboard | หน้าหลัก KPIs |
| Analytics | /analytics | วิเคราะห์ข้อมูล |
| Reconciliation | /reconciliation | กระทบยอด |
| Data Management | /data-management | จัดการข้อมูล |

### Commands พื้นฐาน

```bash
cd nhso-revenue

# ดู logs
docker compose logs -f web

# หยุด services
docker compose down

# เริ่ม services
docker compose up -d

# Restart
docker compose restart

# ดู status
docker compose ps
```

### เปลี่ยน Port

แก้ไข `.env`:
```env
WEB_PORT=8080
```

แล้ว restart:
```bash
docker compose down && docker compose up -d
```

---

## Update & Upgrade

### Update to Latest

```bash
cd nhso-revenue
docker compose pull
docker compose up -d
```

### Update to Specific Version

แก้ไข `.env`:
```env
VERSION=v4.0.0
```

แล้ว:
```bash
docker compose pull
docker compose up -d
```

---

## Uninstall

### หยุด Services

```bash
cd nhso-revenue
docker compose down
```

### ลบทุกอย่าง (รวม database)

```bash
docker compose down -v
cd ..
rm -rf nhso-revenue
```

### ลบ Docker Images

```bash
docker rmi ghcr.io/aegisx-platform/eclaim-rep-download:latest
docker rmi postgres:15-alpine
```

---

## Troubleshooting

### Docker Not Found

```
Error: Docker is not installed
```

**Solution:** ติดตั้ง Docker ตาม [Requirements](#requirements)

### Permission Denied

```
permission denied while trying to connect to Docker daemon
```

**Solution:**
```bash
sudo usermod -aG docker $USER
# Log out and log back in
```

### Port Already in Use

```
Error: port 5001 is already allocated
```

**Solution:** แก้ไข port ใน `.env`:
```env
WEB_PORT=5002
```

### Database Connection Failed

```
connection to server at "db" failed
```

**Solution:**
```bash
# รอ database เริ่มเสร็จ
docker compose logs db

# Restart
docker compose restart
```

### Login Failed

```
Login failed: Invalid username or password
```

**Solution:**
1. ตรวจสอบ `.env` ว่า credentials ถูกต้อง
2. ทดสอบ login ที่ https://eclaim.nhso.go.th

### Reset Everything

```bash
cd nhso-revenue
docker compose down -v
rm -f config/settings.json
docker compose up -d
```

---

## Support

- **Docs:** [github.com/aegisx-platform/eclaim-rep-download/docs](https://github.com/aegisx-platform/eclaim-rep-download/tree/main/docs)
- **Issues:** [GitHub Issues](https://github.com/aegisx-platform/eclaim-rep-download/issues)

---

**Version:** v3.1.0 | **Last Updated:** 2026-01-15

**[← Back to README](../README.md)**
