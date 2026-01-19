# NHSO Revenue Intelligence

> ระบบวิเคราะห์รายได้จากการเบิกจ่าย สปสช. - Hospital Revenue Analytics for NHSO E-Claim Reimbursements

![Dashboard](screenshots/dashboard.jpeg)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)

---

## Support This Project

If you find this project helpful, consider buying me a coffee!

<a href="https://www.buymeacoffee.com/sathit" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

**Developer:** Sathit Seethaphon | [aegisx platform](https://github.com/aegisx-platform)

---

## Table of Contents

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

## Overview

**NHSO Revenue Intelligence** (เดิมชื่อ E-Claim Downloader) เป็นระบบวิเคราะห์รายได้จากการเบิกจ่าย สปสช. สำหรับโรงพยาบาล ครอบคลุมตั้งแต่การ download ข้อมูล E-Claim, import เข้าฐานข้อมูล, วิเคราะห์รายได้, จนถึงกระทบยอดกับข้อมูล SMT Budget

**Version:** v4.0.0
**Last Updated:** 2026-01-19

### Data Sources

| Source | URL | Description |
|--------|-----|-------------|
| E-Claim | [eclaim.nhso.go.th](https://eclaim.nhso.go.th) | ข้อมูลการเบิกจ่าย (REP) |
| SMT Budget | [smt.nhso.go.th](https://smt.nhso.go.th) | ข้อมูลงบประมาณที่จ่ายจริง |

### Why This System?

- **Revenue Analytics** - วิเคราะห์รายได้จากการเบิกจ่ายแบบ real-time
- **Reconciliation** - กระทบยอด REP vs SMT อัตโนมัติ
- **Dashboard & KPIs** - ภาพรวมสำหรับผู้บริหารโรงพยาบาล
- **Automated Downloads** - ตั้งเวลา download อัตโนมัติได้
- **Multi-Database** - รองรับทั้ง PostgreSQL และ MySQL
- **Hospital Schema** - ใช้โครงสร้างตารางของโรงพยาบาลเป็นหลัก

---

## Key Features

### Revenue Dashboard
- **KPI Cards**: Total Claims, Total Reimbursement, Denial Rate, Loss Rate
- **Per-Bed KPIs**: รายได้/เตียง/เดือน, ส่วนต่าง/เตียง/เดือน, เคลม/เตียง, เฉลี่ย/เคลม
- **Hospital Settings**: ตั้งค่ารหัสโรงพยาบาล (Hospital Code) สำหรับ SMT และ Per-Bed metrics
- **Service Type Distribution**: OP, IP, Refer, Emergency
- **Top Funds by Revenue**: แยกตามกองทุน
- **Quick Actions**: เข้าถึง Analytics, Reconciliation, Download

### Analytics Dashboard
- **Monthly Trends**: เทรนด์รายเดือน
- **DRG Analysis**: Top DRG, RW Distribution
- **Drug Analysis**: ยาที่เบิกมากที่สุด
- **Denial Analysis**: สาเหตุการปฏิเสธ
- **Fund Analysis**: วิเคราะห์ตามกองทุน
- **Fiscal Year Filter**: กรองตามปีงบประมาณ

### Reconciliation (REP vs SMT)
- **Claims vs Payments**: เปรียบเทียบยอดเบิก vs ยอดจ่าย
- **Monthly Comparison**: กระทบยอดรายเดือน
- **Discrepancy Detection**: ตรวจหาความต่าง
- **Export Reports**: ส่งออกรายงาน

### Data Management (All-in-One)
- **Download Tab**: Single month & Bulk download
- **Files Tab**: จัดการไฟล์ & Import status
- **SMT Sync Tab**: ดึงข้อมูล SMT Budget
- **Settings Tab**: Credentials & Scheduler

### Benchmark & Analytics
- **My Hospital Analytics**: วิเคราะห์ข้อมูลเฉพาะโรงพยาบาล
- **Benchmark Page**: เปรียบเทียบกับโรงพยาบาลอื่นในกลุ่มเดียวกัน
- **Job History**: ประวัติการ download/import ทั้งหมด

### Master Data
- **ICD-10 Codes**: รหัสโรค ICD-10 TM
- **ICD-9 CM Procedures**: รหัสหัตถการ
- **TMT Drugs**: รหัสยา TMT
- **Health Offices**: ข้อมูลหน่วยบริการ

### Auto Scheduling
- ตั้งเวลา download ได้หลายช่วงต่อวัน
- Auto-import option
- Next run time display

### Database Import
- **Multi-Database**: PostgreSQL และ MySQL
- **Complete Mapping**: Map ทุก columns (170+ fields)
- **All File Types**: OP, IP, ORF, IP_APPEAL
- **UPSERT Logic**: ป้องกัน duplicate

---

## Quick Start

### One-Line Install (Recommended)

```bash
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash
```

**What happens:**
1. ✅ ติดตั้ง Docker containers (PostgreSQL + Web UI)
2. ✅ รัน migrations อัตโนมัติ (7 migrations)
3. ✅ Import seed data อัตโนมัติ (9,247 hospitals + 312 error codes)
4. ✅ แสดงขั้นตอนต่อไป (Hospital Code setup)

**Next Steps หลังติดตั้ง:**
- 🏥 **[ตั้งค่ารหัสโรงพยาบาล](http://localhost:5001/setup)** - จำเป็นสำหรับ SMT Budget และ Per-Bed KPIs
- 🔑 **ตั้งค่า NHSO Credentials** (ถ้าต้องการดาวน์โหลดไฟล์)

📚 **ดูคู่มือเต็ม:** [docs/INSTALLATION_GUIDE.md](docs/INSTALLATION_GUIDE.md)

**Installation Flow:**
```
[1/7] Check Docker ✓
[2/7] Create directory ✓
[3/7] Download config ✓
[4/7] Configure credentials ✓
[5/7] Start services (docker-compose up) ✓
[6/7] Wait for migrations (auto) ✓
[7/7] Import seed data (auto) ✓
  • dim_date, fund_types, service_types
  • health_offices (9,247 hospitals)
  • nhso_error_codes (312 codes)
→ Ready! Go to /setup to configure Hospital Code
```

**Options:**
```bash
# MySQL instead of PostgreSQL
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --mysql

# Download-only (no database)
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --no-db

# Custom directory
curl -fsSL https://raw.githubusercontent.com/aegisx-platform/eclaim-rep-download/main/install.sh | bash -s -- --dir my-nhso
```

### Manual Docker Deployment

```bash
# 1. Clone repository
git clone https://github.com/aegisx-platform/eclaim-rep-download.git
cd eclaim-rep-download

# 2. Setup environment
cp .env.example .env
nano .env  # Set ECLAIM_USERNAME and ECLAIM_PASSWORD

# 3. Start services (auto-runs migrations)
docker-compose up -d

# 4. Wait for startup (until you see "Starting Flask application")
docker-compose logs -f web
# Press Ctrl+C when ready

# 5. Import seed data (REQUIRED - 3 commands)
docker-compose exec web python database/migrate.py --seed
docker-compose exec web python database/seeds/health_offices_importer.py
docker-compose exec web python database/seeds/nhso_error_codes_importer.py

# Or use make:
make seed-all

# 6. Set Hospital Code
# Go to http://localhost:5001/setup and enter your 5-digit hospital code

# Other options:
# - MySQL: docker-compose -f docker-compose-mysql.yml up -d
# - Download-only: docker-compose -f docker-compose-no-db.yml up -d
```

**Why Seed Data is Required:**
- `dim_date`, `fund_types`, `service_types` - Dimension tables for analytics
- `health_offices` - 9,247 hospitals for Hospital Code lookup
- `nhso_error_codes` - 312 error codes for denial analysis

### Access Points

| Service | URL | Description |
|---------|-----|-------------|
| Web UI | http://localhost:5001 | Main application |
| **Setup** | **http://localhost:5001/setup** | **Hospital Code setup (ตั้งค่าครั้งแรก)** |
| Dashboard | http://localhost:5001/dashboard | Revenue KPIs + Per-Bed metrics |
| Analytics | http://localhost:5001/analytics | Detailed analytics |
| Reconciliation | http://localhost:5001/reconciliation | REP vs SMT |
| Data Management | http://localhost:5001/data-management | Download, Files, Settings |

---

## Navigation Structure

```
NHSO Revenue Intelligence
├── Setup              - 🏥 Hospital Code + Database + Configuration
├── Dashboard          - Revenue KPIs + Per-Bed Performance
├── Analytics          - Detailed Charts & Analysis
├── Reconciliation     - REP vs SMT Comparison
└── Data Management    - Download, Files, SMT, Settings
    ├── Download       - Single/Bulk download + Scheduler
    ├── Files          - File list + Import status
    ├── SMT Sync       - Budget data sync
    └── Settings       - Hospital Settings + Credentials + Database info
```

---

## Documentation

### Getting Started
- **[Installation Guide](docs/INSTALLATION_GUIDE.md)** - Complete installation & verification (PostgreSQL & MySQL)
- **[Testing Checklist](docs/TESTING_CHECKLIST.md)** - Step-by-step testing guide
- **[Configuration Guide](docs/CONFIGURATION.md)** - System configuration
- **[Usage Guide](docs/USAGE.md)** - How to use features

### Hospital Analytics (สำหรับผู้บริหาร รพ.)
- **[Hospital Analytics Guide](docs/HOSPITAL_ANALYTICS_GUIDE.md)** - คู่มือวิเคราะห์การเบิกเคลม
- **[Analytics Roadmap](docs/ANALYTICS_ROADMAP.md)** - แผนพัฒนา Analytics

### Technical Documentation
- **[Features Documentation](docs/FEATURES.md)** - All features detail
- **[Database Guide](docs/DATABASE.md)** - Schema & HIS reconciliation
- **[Analytics Guide](docs/ANALYTICS.md)** - Analytics dashboard guide
- **[Troubleshooting](docs/TROUBLESHOOTING.md)** - Problem solving

### Additional Resources
- **[Legal & Compliance](docs/LEGAL.md)** - PDPA compliance
- **[Docker Setup](DOCKER.md)** - Docker deployment
- **[E-Claim Analysis](ECLAIM_ANALYSIS_REPORT.md)** - File structure

---

## Screenshots

### Revenue Dashboard
![Dashboard](screenshots/dashboard.jpeg)
*Revenue KPIs, Service Distribution, Top Funds*

### Analytics Dashboard
*Monthly Trends, DRG Analysis, Drug Analysis*

### Reconciliation
*REP vs SMT Comparison, Discrepancy Detection*

### Data Management
*Download, Files, SMT Sync, Settings - All in one page*

---

## Requirements

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
- Linux (Ubuntu, Debian, CentOS)
- macOS
- Windows (with Docker Desktop or WSL2)

---

## Project Structure

### v4.0.0 Architecture

```
eclaim-rep-download/
├── app.py                          # Flask application (2,266 lines - 83.4% smaller!)
│                                   # Core routes only: auth, pages, setup
├── routes/                         # 🆕 Modular Blueprint Architecture (12 blueprints)
│   ├── analytics_api.py            # Analytics & reporting (53 routes)
│   ├── downloads_api.py            # Download management (35 routes)
│   ├── imports_api.py              # Import operations (19 routes)
│   ├── master_data_api.py          # Master data management (17 routes)
│   ├── files_api.py                # File operations (15 routes)
│   ├── benchmark_api.py            # Hospital benchmarking (7 routes)
│   ├── alerts_api.py               # System notifications (7 routes)
│   ├── smt_api.py                  # SMT budget operations (6 routes)
│   ├── stm_api.py                  # Statement operations (6 routes)
│   ├── system_api.py               # System health (5 routes)
│   ├── rep_api.py                  # REP data operations (4 routes)
│   ├── jobs_api.py                 # Background jobs (3 routes)
│   ├── external_api.py             # HIS integration API (7 routes)
│   ├── settings.py                 # Settings API (15 routes)
│   ├── settings_pages.py           # Settings pages (8 routes)
│   └── api_keys_management.py      # API key management (6 routes)
│
├── utils/                          # Business logic & managers
│   ├── eclaim/                     # E-Claim processing
│   │   ├── parser.py               # Excel parser
│   │   └── importer_v2.py          # Database importer
│   ├── download_manager/           # Download orchestration
│   │   ├── manager.py              # Download manager v2
│   │   ├── session.py              # Session management
│   │   └── parallel_bridge.py      # Parallel downloads
│   ├── history_manager.py          # Download history
│   ├── file_manager.py             # File operations
│   ├── downloader_runner.py        # Download runner
│   ├── import_runner.py            # Import runner
│   ├── unified_import_runner.py    # Unified import (REP/STM/SMT)
│   ├── stm_import_runner.py        # STM-specific import
│   ├── scheduler.py                # APScheduler
│   ├── settings_manager.py         # Settings CRUD
│   ├── job_history_manager.py      # Job tracking
│   ├── alert_manager.py            # Alert system
│   ├── license_checker.py          # License validation
│   └── auth.py                     # Authentication
│
├── config/                         # Configuration
│   ├── database.py                 # DB configuration
│   ├── db_pool.py                  # Connection pooling
│   └── settings.json               # User settings (not in git)
│
├── database/                       # Database
│   ├── migrations/                 # Migration system
│   │   ├── postgresql/             # PostgreSQL migrations
│   │   └── mysql/                  # MySQL migrations
│   ├── seeds/                      # Seed data
│   │   ├── postgresql/
│   │   └── mysql/
│   └── migrate.py                  # Migration runner
│
├── templates/                      # Jinja2 templates
│   ├── base.html                   # Base layout
│   ├── dashboard.html              # Revenue dashboard
│   ├── data_analysis.html          # Analytics page
│   ├── data_management.html        # Data management (all-in-one)
│   ├── benchmark.html              # Hospital benchmarking
│   ├── settings/                   # Settings pages
│   │   ├── index.html
│   │   ├── hospital.html
│   │   ├── credentials.html
│   │   ├── license.html
│   │   └── users.html
│   └── master_data/                # Master data pages
│
├── static/                         # Frontend assets
│   ├── js/                         # JavaScript
│   │   ├── app.js                  # Main application
│   │   ├── csrf.js                 # CSRF protection
│   │   └── upload-multiple.js      # File upload
│   └── swagger/                    # API documentation
│       └── openapi.yaml            # OpenAPI 3.0 spec
│
├── docs/                           # Documentation
│   ├── technical/                  # Technical docs
│   │   ├── ARCHITECTURE.md         # 🆕 System architecture
│   │   ├── API_DOCUMENTATION.md
│   │   └── DATABASE_SCHEMA.md
│   ├── business/                   # Business docs
│   │   ├── LICENSE_MANAGEMENT.md
│   │   └── VALUE_PROPOSITION.md
│   └── INSTALLATION_GUIDE.md       # Installation guide
│
├── docker-compose.yml              # PostgreSQL stack
├── docker-compose-mysql.yml        # MySQL stack
├── docker-compose-https.yml        # 🆕 HTTPS with nginx
├── Dockerfile                      # Container image
└── VERSION                         # Version: 4.0.0
```

### Key Improvements in v4.0.0

✅ **83.4% Code Reduction** - app.py: 13,657 → 2,266 lines
✅ **12 Modular Blueprints** - Clear separation of concerns
✅ **184 Routes Extracted** - Domain-separated API routes
✅ **Better Maintainability** - Each blueprint has single responsibility
✅ **Easier Testing** - Independent blueprint testing
✅ **Team Collaboration** - Multiple developers, fewer conflicts

See **[Architecture Documentation](docs/technical/ARCHITECTURE.md)** for details.

---

## Version History

See **[CHANGELOG.md](CHANGELOG.md)** for detailed version history.

### Latest: v3.2.0 (2026-01-17)

**New Features:**
- **🏥 Hospital Settings & Per-Bed KPIs**
  - Global Hospital Code setting (ใช้ทั้ง SMT และ Per-Bed KPIs)
  - Per-bed performance metrics: รายได้/เตียง/เดือน, ส่วนต่าง/เตียง/เดือน, เคลม/เตียง
  - Auto-fetch hospital info from health_offices (9,247 hospitals)
- **📦 Auto-Seed Data in install.sh**
  - Automatic seed data import on installation
  - Post-install guidance for Hospital Code setup
- **📚 Complete Documentation**
  - Installation Guide (15KB)
  - Testing Checklist (12KB)

**Improvements:**
- Setup page with Hospital Code configuration
- Dashboard shows hospital name and bed count
- SMT uses global hospital_code instead of vendor_id
- Analytics API includes hospital and per_bed objects

### Previous Releases

| Version | Date | Highlights |
|---------|------|------------|
| v3.1.0 | 2026-01-15 | TRAN_ID search, Job History, Benchmark, Master data |
| v3.0.0 | 2026-01-11 | Revenue Intelligence, Dashboard, Reconciliation |
| v2.0.0 | 2026-01-08 | Hospital Schema, Complete Field Mapping |
| v1.1.0 | 2026-01-05 | Bulk Download, Auto Scheduler |
| v1.0.0 | 2026-01-01 | Initial Release |

---

## License

MIT License - see [LICENSE](LICENSE) file for details

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit changes (`git commit -m 'Add AmazingFeature'`)
4. Push to branch (`git push origin feature/AmazingFeature`)
5. Open Pull Request

---

## Support

### Getting Help

- **Documentation**: [docs/](docs/)
- **Issues**: [GitHub Issues](https://github.com/aegisx-platform/eclaim-rep-download/issues)
- **Discussions**: [GitHub Discussions](https://github.com/aegisx-platform/eclaim-rep-download/discussions)

### Report Issues

Include:
- Error message (full stack trace)
- Steps to reproduce
- Environment (OS, Docker version)
- Logs (sanitize sensitive data)

---

## Acknowledgments

- NHSO E-Claim System (eclaim.nhso.go.th)
- NHSO SMT Budget System (smt.nhso.go.th)
- Flask Framework
- Chart.js
- Tailwind CSS
- PostgreSQL & MySQL

---

## Legal Notice

This software is **legal** when used correctly with authorized credentials and for legitimate hospital purposes. Please comply with:

- **PDPA** (พ.ร.บ. คุ้มครองข้อมูลส่วนบุคคล)
- **Security Best Practices**
- **Access Control**

**[Legal & Compliance Guide](docs/LEGAL.md)**

---

**Made with love by [aegisx platform](https://github.com/aegisx-platform)**

**Last Updated:** 2026-01-17 | **Version:** v3.2.0
