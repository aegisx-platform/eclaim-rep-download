# E-Claim Downloader & Data Import System

> 🏥 ระบบ download และ import ข้อมูล e-claim จาก NHSO อัตโนมัติ พร้อม Web UI สำหรับจัดการไฟล์และนำเข้าฐานข้อมูล

![Dashboard](screenshots/dashboard.jpeg)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

---

## ☕ Support This Project

If you find this project helpful, consider buying me a coffee!

<a href="https://www.buymeacoffee.com/sathit" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

**Developer:** Sathit Seethaphon | [aegisx platform](https://github.com/aegisx-platform)

---

## 📋 Table of Contents

- [Overview](#-overview)
- [Key Features](#-key-features)
- [Quick Start](#-quick-start)
- [Documentation](#-documentation)
- [Screenshots](#-screenshots)
- [Requirements](#-requirements)
- [Project Structure](#-project-structure)
- [License](#-license)
- [Contributing](#-contributing)
- [Support](#-support)

---

## 🌟 Overview

E-Claim Downloader เป็นระบบที่ออกแบบมาเพื่อช่วยโรงพยาบาลในการจัดการข้อมูล E-Claim จาก NHSO อย่างมีประสิทธิภาพ ด้วยระบบ Web UI ที่ใช้งานง่าย และรองรับการ import ข้อมูลเข้า database โดยตรง

**Version:** v2.0.0
**Last Updated:** 2026-01-08

### Why This System?

- ✅ **Save Time** - ไม่ต้อง download ไฟล์ทีละไฟล์จาก web browser
- ✅ **Automated** - ตั้งเวลา download อัตโนมัติได้
- ✅ **Data Management** - import เข้า database พร้อม HIS reconciliation
- ✅ **Multi-Database** - รองรับทั้ง PostgreSQL และ MySQL
- ✅ **Hospital Schema** - ใช้โครงสร้างตารางของโรงพยาบาลเป็นหลัก
- ✅ **Easy to Use** - Web UI ใช้งานง่าย พร้อม real-time monitoring

---

## ✨ Key Features

### 🌐 Web Dashboard
- สถิติและภาพรวมการ download
- จัดการไฟล์ (view, download, delete)
- Pagination & month/year filtering
- Real-time log viewer

### 📥 Download System
- Auto login & HTTP client (fast!)
- Single month หรือ bulk download (date range)
- Duplicate prevention & progress tracking
- Download history

### ⏰ Auto Scheduling
- ตั้งเวลา download ได้หลายช่วงต่อวัน
- Enable/disable toggle
- Auto-import option
- Next run time display

### 💾 Database Import
- **Schema V2**: ใช้โครงสร้างตารางของโรงพยาบาลเป็นหลัก
- **Multi-Database**: PostgreSQL และ MySQL
- **Complete Mapping**: Map ทุก columns (170+ fields)
- **All File Types**: OP, IP, ORF, IP_APPEAL, IP_APPEAL_NHSO
- **UPSERT Logic**: ป้องกัน duplicate
- **HIS Reconciliation**: Fields สำหรับ reconcile

### 🐳 Docker Deployment
- One-command deploy
- Full stack (Web + Database + Admin UI)
- Download-only mode
- Health checks & auto-restart

**[→ ดู Features ทั้งหมด](docs/FEATURES.md)**

---

## 🚀 Quick Start

### Docker Deployment (แนะนำ)

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-req-download.git
cd eclaim-req-download

# 2. Setup environment
cp .env.example .env
nano .env  # แก้ไข ECLAIM_USERNAME และ ECLAIM_PASSWORD

# 3. Start services (PostgreSQL)
docker-compose up -d

# หรือใช้ MySQL
docker-compose -f docker-compose-mysql.yml up -d

# หรือ download-only (ไม่มี database)
docker-compose -f docker-compose-no-db.yml up -d
```

**Access:**
- 🌐 **Web UI**: http://localhost:5001
- 🗄️ **Database**: localhost:5432 (PostgreSQL) or localhost:3306 (MySQL)
- 🔧 **Admin UI**: http://localhost:5050

**[→ Installation Guide](docs/INSTALLATION.md)**

---

## 📚 Documentation

### Getting Started
- **[Installation Guide](docs/INSTALLATION.md)** - ขั้นตอนการติดตั้ง (Docker & Manual)
- **[Configuration Guide](docs/CONFIGURATION.md)** - การตั้งค่าระบบ
- **[Usage Guide](docs/USAGE.md)** - วิธีใช้งาน Web UI และ features ต่างๆ

### Technical Documentation
- **[Features Documentation](docs/FEATURES.md)** - รายละเอียด features ทั้งหมด
- **[Database Guide](docs/DATABASE.md)** - Schema V2 และ HIS reconciliation
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - แก้ปัญหาและ debugging
- **[Development Guide](docs/DEVELOPMENT.md)** - สำหรับ developers

### Additional Resources
- **[Legal & Compliance](docs/LEGAL.md)** - กฎหมายและ PDPA compliance
- **[Docker Setup](DOCKER.md)** - Docker deployment guide
- **[Migration Guide](MIGRATE_V2.md)** - Migrate to Schema V2
- **[E-Claim Analysis](ECLAIM_ANALYSIS_REPORT.md)** - File structure analysis

---

## 📱 Screenshots

### Dashboard
![Dashboard](screenshots/dashboard.jpeg)
*Overview with statistics and recent files*

### Files Management
*Pagination, filtering, and import status*

### Download Configuration
*Date range selection and bulk download*

### Settings
*Credentials and scheduler configuration*

---

## 💻 Requirements

### Minimum Requirements
- **Docker** 20.10+ & **Docker Compose** 2.0+
- **OR** Python 3.12+ (for manual installation)
- 2GB RAM
- 10GB disk space

### Supported Databases
- PostgreSQL 13+ (recommended)
- MySQL 8.0+
- No database (download-only mode)

### Supported OS
- ✅ Linux (Ubuntu, Debian, CentOS)
- ✅ macOS
- ✅ Windows (with Docker Desktop or WSL2)

---

## 📁 Project Structure

```
eclaim-req-download/
├── app.py                          # Flask web application
├── eclaim_downloader_http.py       # HTTP downloader
├── eclaim_import.py                # CLI import tool
├── docker-compose*.yml             # Docker configurations
├── config/                         # Configuration files
├── database/                       # Database schemas
│   ├── schema-postgresql-merged.sql  # PostgreSQL V2
│   └── schema-mysql-merged.sql       # MySQL V2
├── docs/                           # Documentation
│   ├── FEATURES.md
│   ├── INSTALLATION.md
│   ├── CONFIGURATION.md
│   ├── USAGE.md
│   ├── DATABASE.md
│   ├── LEGAL.md
│   ├── TROUBLESHOOTING.md
│   └── DEVELOPMENT.md
├── utils/                          # Utility modules
│   ├── eclaim/                    # E-Claim modules
│   │   ├── parser.py
│   │   ├── importer.py
│   │   └── importer_v2.py         # V2 with hospital schema
│   ├── history_manager.py
│   ├── file_manager.py
│   ├── downloader_runner.py
│   ├── import_runner.py
│   ├── scheduler.py
│   └── settings_manager.py
├── templates/                      # HTML templates
└── static/                         # CSS & JavaScript
```

**[→ Detailed Structure](docs/DEVELOPMENT.md#project-structure)**

---

## 📊 Sample Statistics

จากการทดสอบจริงในโรงพยาบาล:

- **Total Files**: 382 ไฟล์
- **Total Records**: 40,006 records
- **Total Reimbursement**: ~141.6 million THB

**By Type:**
- OP: 252 files (14.1M THB)
- IP: 82 files (123.6M THB)
- ORF: 45 files
- IP_APPEAL_NHSO: 2 files (3.8M THB)

---

## 🏷️ Version History

### v2.0.0 (2026-01-08) - Schema V2 Release

**Major Changes:**
- ✨ **Schema V2**: ใช้โครงสร้างตารางของโรงพยาบาลเป็นหลัก
- ✨ **Complete Field Mapping**: Map ทุก columns (170+ fields)
- ✨ **Multi-Database**: PostgreSQL + MySQL support
- 🐛 **Import Fixes**: Date parsing, string truncation, data validation
- 📚 **Documentation**: แยก sections เป็นไฟล์แยก

### v1.1.0 (2026-01-07)
- ✨ Auto Download Scheduling
- ✨ Settings Page
- ✨ Pagination & Filtering
- ✨ Real-time Log Streaming
- 🐳 Docker Compose
- 📚 Legal & Compliance Docs

### v1.0.0 (Initial Release)
- 📥 E-Claim Downloader
- 🌐 Web UI Dashboard
- 💾 Database Import
- 🐳 Docker Support

---

## 📝 License

MIT License - see [LICENSE](LICENSE) file for details

---

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

**[→ Development Guide](docs/DEVELOPMENT.md)**

---

## 💬 Support

### Getting Help

- 📖 **Documentation**: [docs/](docs/)
- 🐛 **Issues**: [GitHub Issues](https://github.com/aegisx-platform/eclaim-req-download/issues)
- 💬 **Discussions**: [GitHub Discussions](https://github.com/aegisx-platform/eclaim-req-download/discussions)

### Report Issues

Include:
- Error message (full stack trace)
- Steps to reproduce
- Environment (OS, Docker version)
- Logs (sanitize sensitive data)

**[→ Troubleshooting Guide](docs/TROUBLESHOOTING.md)**

---

## 🙏 Acknowledgments

- NHSO E-Claim System
- Flask Framework
- PostgreSQL & MySQL Databases
- APScheduler Library
- Tailwind CSS
- Docker Community

---

## ⚖️ Legal Notice

This software is **legal** when used correctly with authorized credentials and for legitimate hospital purposes. Please comply with:

- ✅ **PDPA** (พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล)
- ✅ **Security Best Practices**
- ✅ **Access Control**

**[→ Legal & Compliance Guide](docs/LEGAL.md)**

---

**Made with ❤️ by [aegisx platform](https://github.com/aegisx-platform)**

**Last Updated:** 2026-01-08 | **Version:** v2.0.0
