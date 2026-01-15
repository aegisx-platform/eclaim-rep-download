# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v3.1.0...HEAD
[3.1.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v3.0.0...v3.1.0
[3.0.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v2.0.0...v3.0.0
[2.0.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/aegisx-platform/eclaim-rep-download/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/aegisx-platform/eclaim-rep-download/releases/tag/v1.0.0
