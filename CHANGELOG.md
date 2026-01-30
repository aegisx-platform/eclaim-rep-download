# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [4.1.0] - 2026-01-29

### Security Fixes 🔒

- **Critical**: Added `@login_required` and `@require_admin` to `/api/clear-all` endpoint - Previously accessible without authentication
- **Fixed**: Password no longer shown in logs during admin creation - Now displays `[SAVED TO FILE - not shown in logs]`
- **Fixed**: 7 bare `except:` clauses replaced with specific exception handling across multiple files:
  - `utils/eclaim/importer_v2.py` (3 instances)
  - `utils/stm_importer.py` (2 instances)
  - `utils/import_runner.py` (1 instance)
  - `utils/unified_import_runner.py` (1 instance)

### Fixed

- **DB_TYPE Centralization**: All files now import `DB_TYPE` from `config.database` instead of reading from environment directly
  - Ensures switching between PostgreSQL and MySQL works consistently across all modules
  - Files updated: `utils/dim_date_generator.py`, `utils/eclaim/importer_v2.py`, `utils/stm_importer.py`, `database/migrate.py`, `bulk_downloader.py`, `eclaim_import.py`, `stm_import.py`, `smt_budget_fetcher.py`
- **GitHub Actions**: Fixed security-scan workflow permissions for SARIF upload to GitHub Security tab
- **GitHub Actions**: Made Gitleaks secret scanning non-blocking (requires paid license for organizations)

### Tested

- ✅ Fresh installation via `install.sh` verified working
- ✅ PostgreSQL mode tested and verified
- ✅ MySQL mode tested and verified
- ✅ All migrations run successfully
- ✅ Seed data imports correctly (dim_date, health_offices, nhso_error_codes)

---

## [4.0.0] - 2026-01-19

### Major Architectural Refactoring 🎉

This release introduces a complete architectural overhaul with **modular blueprint structure**, resulting in **83.4% code reduction** in the main application file and significantly improved maintainability.

### Added

#### Modular Blueprint Architecture
- **12 domain-separated blueprints** for API routes:
  - `routes/analytics_api.py` (53 routes) - Analytics and reporting
  - `routes/downloads_api.py` (35 routes) - Download management
  - `routes/imports_api.py` (19 routes) - Import operations
  - `routes/master_data_api.py` (17 routes) - Master data management
  - `routes/files_api.py` (15 routes) - File operations
  - `routes/benchmark_api.py` (7 routes) - Hospital benchmarking
  - `routes/alerts_api.py` (7 routes) - System notifications
  - `routes/smt_api.py` (6 routes) - SMT budget operations
  - `routes/stm_api.py` (6 routes) - Statement operations
  - `routes/system_api.py` (5 routes) - System health monitoring
  - `routes/rep_api.py` (4 routes) - REP data operations
  - `routes/jobs_api.py` (3 routes) - Background job tracking

#### Documentation
- **NEW:** `docs/technical/ARCHITECTURE.md` - Complete architecture documentation
- Updated all documentation to reflect new structure
- Added blueprint-specific documentation

### Changed

#### Code Organization
- **app.py**: Reduced from 13,657 lines to 2,266 lines (83.4% reduction)
- **184 API routes** extracted into domain-separated blueprints
- **38 core routes** remain in app.py (authentication, page rendering, file serving, setup)
- Clear separation of concerns by domain

#### Benefits
- **Improved Maintainability**: Each blueprint has a single, well-defined responsibility
- **Better Scalability**: Easy to add new features without affecting core app
- **Enhanced Team Collaboration**: Multiple developers can work on different blueprints simultaneously
- **Easier Testing**: Each blueprint can be tested independently
- **Better Code Navigation**: Find routes by domain instead of searching through monolithic file
- **Reduced Merge Conflicts**: Changes are isolated to specific blueprints

### Technical Details

#### Blueprint Categories
1. **Domain Blueprints**: Core business logic (analytics, downloads, imports, files)
2. **Data Source Blueprints**: Data-specific operations (REP, STM, SMT)
3. **Utility Blueprints**: Supporting services (master data, benchmark, jobs, alerts, system)
4. **External Integration**: API integration (external API, settings, API keys)

#### Manager Sharing Pattern
- Blueprints access shared managers via `current_app.config`
- Connection pooling for database access
- Centralized configuration management

### Migration Notes

#### Backward Compatibility
- ✅ **No breaking changes** to API contracts
- ✅ All existing endpoints preserved
- ✅ Legacy route aliases maintained
- ✅ Direct upgrade path from v3.x

#### Upgrade Steps
```bash
# Pull new version
docker pull ghcr.io/aegisx-platform/eclaim-rep-download:4.0.0

# Restart services
docker-compose down
docker-compose up -d
```

No configuration changes required. All existing integrations continue to work.

### Statistics
- **Total commits**: 33 commits across 3 phases
- **Lines removed**: 11,391 lines from app.py
- **Blueprints created**: 12 modular blueprints
- **Routes extracted**: 184 API routes
- **Code reduction**: 83.4% in main application file

### Commit History Summary

**Phase 1: Large API Routes**
- Analytics API extraction (53 routes)
- Downloads API extraction (20 routes)
- Imports API extraction (10 routes)
- Files API extraction (15 routes)

**Phase 2: Data Source Blueprints**
- REP API extraction (4 routes)
- STM API extraction (6 routes)
- SMT API extraction (6 routes)

**Phase 3: Utility Blueprints**
- Master Data API extraction (17 routes)
- Benchmark API extraction (7 routes)
- Jobs API extraction (3 routes)
- Alerts API extraction (7 routes)
- System API extraction (5 routes)

### Breaking Changes
None. This release is fully backward compatible.

### Deprecations
None.

---

## [3.1.0] - 2026-01-15

### Added
- **TRAN_ID Search**: เพิ่มช่องค้นหา TRAN_ID แยกจาก REP No ในหน้า Data Management
- **Job History Tracking**: บันทึกประวัติการ download/import ทุกประเภท (REP, Statement, SMT)
- **Reimport Script**: Script สำหรับ re-import additional sheets (drug, instrument, deny, zero_paid)
- **Benchmark Page**: หน้า Benchmark เปรียบเทียบข้อมูลกับโรงพยาบาลอื่น
- **My Hospital Analytics**: หน้าวิเคราะห์ข้อมูลเฉพาะโรงพยาบาล
- **Master Data Import**: นำเข้าข้อมูล ICD-10, ICD-9 CM, TMT drugs, Health offices

### Changed
- **Fiscal Year Filter**: ปรับปรุง filter ปีงบประมาณให้ครอบคลุมทุกหน้า
- **SMT Filter**: เพิ่ม filter สำหรับ SMT files และ database records
- **Statement Filter**: ปรับปรุง filter สำหรับ Statement files

### Fixed
- **Header Row Skip**: แก้ไขการ import additional sheets ให้ข้าม header rows ที่ซ้ำใน Excel
- **Connection Pool**: แก้ไขปัญหา database connection pool exhaustion
- **DNS Resolution**: แก้ไขปัญหา DNS resolution ใน Docker container
- **Duplicate Import**: แก้ไขปัญหา duplicate key constraint เมื่อ re-import ไฟล์

## [3.0.0] - 2026-01-11

### Added
- **Revenue Dashboard**: หน้า Dashboard แสดง KPIs รายได้จากการเบิกจ่าย
- **Analytics Dashboard**: หน้าวิเคราะห์ข้อมูลเชิงลึก (Monthly Trends, DRG, Drug, Denial)
- **Reconciliation**: หน้ากระทบยอด REP vs SMT
- **SMT Budget Integration**: เชื่อมต่อข้อมูล SMT Budget จาก smt.nhso.go.th
- **Combined Data Management**: รวมหน้า Download, Files, SMT, Settings เป็นหน้าเดียว

### Changed
- **Rebrand**: เปลี่ยนชื่อจาก "E-Claim Downloader" เป็น "NHSO Revenue Intelligence"
- **Navigation**: ปรับโครงสร้างเมนูเป็น 4 หน้าหลัก (Dashboard, Analytics, Reconciliation, Data Management)
- **UI/UX**: ปรับปรุง UI ให้ทันสมัยด้วย Tailwind CSS

## [2.0.0] - 2026-01-08

### Added
- **Hospital Schema**: ใช้โครงสร้างตารางของโรงพยาบาลเป็นหลัก
- **Complete Field Mapping**: Map ครบทุก columns (170+ fields)
- **Multi-Database Support**: รองรับทั้ง PostgreSQL และ MySQL
- **UPSERT Logic**: ป้องกัน duplicate records

### Changed
- **Importer V2**: ปรับปรุง importer ให้รองรับ schema ใหม่
- **Column Mapping**: ปรับ mapping ให้ตรงกับ Excel columns ที่มี newline characters

### Fixed
- **Date Parsing**: แก้ไขการ parse วันที่ภาษาไทย (พ.ศ.)
- **String Truncation**: แก้ไขการตัด string ที่ยาวเกินไป

## [1.1.0] - 2026-01-05

### Added
- **Bulk Download**: Download หลายเดือนพร้อมกัน
- **Auto Scheduler**: ตั้งเวลา download อัตโนมัติ
- **Auto Import**: Import อัตโนมัติหลัง download

### Changed
- **HTTP Client**: เปลี่ยนจาก Playwright เป็น requests library

## [1.0.0] - 2026-01-01

### Added
- **E-Claim Downloader**: Download ไฟล์ E-Claim จาก eclaim.nhso.go.th
- **Web UI**: หน้า Dashboard สำหรับจัดการ downloads
- **Database Import**: Import ข้อมูลเข้า PostgreSQL/MySQL
- **Docker Support**: รองรับการ deploy ด้วย Docker
- **File Types**: รองรับ OP, IP, ORF, IP_APPEAL

[Unreleased]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v4.1.0...HEAD
[4.1.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v4.0.0...v4.1.0
[4.0.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v3.1.0...v4.0.0
[3.1.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v2.0.0...v3.0.0
[2.0.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/aegisx-platform/eclaim-rep-download/releases/tag/v1.0.0
