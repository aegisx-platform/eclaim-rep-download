# Database Migration Guide - Schema V2

## Overview

Schema V2 ใช้โครงสร้างตารางเดิมของโรงพยาบาล (`claim_rep_opip_nhso_item`, `claim_rep_orf_nhso_item`) และเพิ่ม tracking capabilities

## สิ่งที่เปลี่ยนแปลง

### ✅ เพิ่ม (ไม่ได้เปลี่ยนอะไรเดิม)

**1. Table ใหม่: `eclaim_imported_files`**
```sql
-- Tracking table สำหรับเก็บประวัติการ import
CREATE TABLE eclaim_imported_files (...)
```

**2. Columns เพิ่มใน `claim_rep_opip_nhso_item`:**
- `file_id` - Reference ไปยัง `eclaim_imported_files`
- `row_number` - Row number ในไฟล์ Excel
- `his_matched` - สถานะ match กับ HIS
- `his_matched_at` - เวลาที่ match
- `his_vn` - VN จาก HIS
- `his_amount_diff` - ผลต่างยอดเงิน
- `reconcile_status` - สถานะการ reconcile
- `reconcile_note` - หมายเหตุ

**3. Columns เพิ่มใน `claim_rep_orf_nhso_item`:**
- เหมือนข้อ 2

**4. Indexes เพิ่ม:**
- `idx_file_id` - Query ตาม file
- `idx_reconcile` - Query HIS reconciliation
- `uq_tran_file` - UNIQUE constraint สำหรับ UPSERT

## Migration Steps

### สำหรับ MySQL (แนะนำ)

#### Step 1: Backup ข้อมูลเดิม

```bash
# Backup database
mysqldump -u eclaim -p eclaim_db > backup_before_migration.sql

# หรือ backup เฉพาะตาราง
mysqldump -u eclaim -p eclaim_db claim_rep_opip_nhso_item claim_rep_orf_nhso_item > backup_tables.sql
```

#### Step 2: เลือกวิธี Migration

**Option A: ใช้โครงสร้างใหม่ทั้งหมด (แนะนำ)**

```bash
# 1. สำรองข้อมูลเดิม (ถ้ามี)
mysqldump -u eclaim -p eclaim_db > backup_full.sql

# 2. Drop database เดิม
mysql -u eclaim -p -e "DROP DATABASE IF EXISTS eclaim_db;"

# 3. Create database ใหม่
mysql -u eclaim -p -e "CREATE DATABASE eclaim_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"

# 4. Import schema ใหม่
mysql -u eclaim -p eclaim_db < database/schema-mysql-merged.sql

# 5. (Optional) Import ข้อมูลเดิมกลับมา ถ้ามี
# mysql -u eclaim -p eclaim_db < backup_tables.sql
```

**Option B: เพิ่ม columns ลงในตารางเดิม**

```bash
mysql -u eclaim -p eclaim_db
```

```sql
-- 1. สร้าง tracking table
CREATE TABLE IF NOT EXISTS eclaim_imported_files (
    id INT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    filename VARCHAR(255) NOT NULL UNIQUE,
    file_type VARCHAR(20) NOT NULL,
    hospital_code VARCHAR(10) NOT NULL,
    file_date DATE,
    file_sequence VARCHAR(20),
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_records INT DEFAULT 0,
    imported_records INT DEFAULT 0,
    failed_records INT DEFAULT 0,
    file_created_at TIMESTAMP NULL,
    import_started_at TIMESTAMP NULL,
    import_completed_at TIMESTAMP NULL,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_file_type CHECK (file_type IN ('OP', 'IP', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'partial')),
    INDEX idx_file_type (file_type),
    INDEX idx_status (status),
    INDEX idx_file_date (file_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 2. เพิ่ม columns ลงใน claim_rep_opip_nhso_item
ALTER TABLE claim_rep_opip_nhso_item
ADD COLUMN file_id INT UNSIGNED NULL COMMENT 'Reference to eclaim_imported_files' AFTER id,
ADD COLUMN row_number INT NULL COMMENT 'Row number in original file' AFTER file_id,
ADD COLUMN his_matched BOOLEAN DEFAULT FALSE COMMENT 'Matched with HIS data',
ADD COLUMN his_matched_at DATETIME NULL COMMENT 'When matched',
ADD COLUMN his_vn VARCHAR(20) NULL COMMENT 'VN from HIS',
ADD COLUMN his_amount_diff DOUBLE(10,2) NULL COMMENT 'Difference in amount',
ADD COLUMN reconcile_status VARCHAR(20) NULL COMMENT 'pending/matched/mismatched',
ADD COLUMN reconcile_note TEXT NULL COMMENT 'Reconciliation notes',
ADD FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL,
ADD INDEX idx_file_id (file_id),
ADD INDEX idx_reconcile (his_matched, reconcile_status),
ADD UNIQUE KEY uq_tran_file (tran_id, file_id);

-- 3. เพิ่ม columns ลงใน claim_rep_orf_nhso_item
ALTER TABLE claim_rep_orf_nhso_item
ADD COLUMN file_id INT UNSIGNED NULL COMMENT 'Reference to eclaim_imported_files' AFTER id,
ADD COLUMN row_number INT NULL COMMENT 'Row number in original file' AFTER file_id,
ADD COLUMN his_matched BOOLEAN DEFAULT FALSE COMMENT 'Matched with HIS data',
ADD COLUMN his_matched_at DATETIME NULL COMMENT 'When matched',
ADD COLUMN his_vn VARCHAR(20) NULL COMMENT 'VN from HIS',
ADD COLUMN his_amount_diff DOUBLE(10,2) NULL COMMENT 'Difference in amount',
ADD COLUMN reconcile_status VARCHAR(20) NULL COMMENT 'pending/matched/mismatched',
ADD COLUMN reconcile_note TEXT NULL COMMENT 'Reconciliation notes',
ADD FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL,
ADD INDEX idx_file_id (file_id),
ADD INDEX idx_reconcile (his_matched, reconcile_status),
ADD UNIQUE KEY uq_tran_file (tran_id, file_id);

-- 4. Create views
CREATE OR REPLACE VIEW v_daily_claim_summary AS
SELECT
    DATE(c.dateadm) as service_date,
    c.ptype,
    c.main_inscl,
    COUNT(*) as claim_count,
    SUM(c.reimb_nhso) as total_reimbursement,
    SUM(CASE WHEN c.error_code IS NOT NULL AND c.error_code != '-' THEN 1 ELSE 0 END) as error_count,
    SUM(CASE WHEN c.his_matched THEN 1 ELSE 0 END) as matched_count
FROM claim_rep_opip_nhso_item c
GROUP BY DATE(c.dateadm), c.ptype, c.main_inscl
ORDER BY service_date DESC, ptype, main_inscl;

CREATE OR REPLACE VIEW v_import_status AS
SELECT
    f.file_type,
    f.status,
    COUNT(*) as file_count,
    SUM(f.total_records) as total_records,
    SUM(f.imported_records) as imported_records,
    SUM(f.failed_records) as failed_records,
    MIN(f.file_date) as earliest_file,
    MAX(f.file_date) as latest_file
FROM eclaim_imported_files f
GROUP BY f.file_type, f.status
ORDER BY f.file_type, f.status;
```

### สำหรับ PostgreSQL

เหมือน MySQL แต่ใช้ไฟล์ `database/schema-postgresql-merged.sql`

```bash
# Backup
pg_dump -U eclaim -d eclaim_db > backup_before_migration.sql

# Drop & recreate (Option A)
psql -U eclaim -d postgres -c "DROP DATABASE IF EXISTS eclaim_db;"
psql -U eclaim -d postgres -c "CREATE DATABASE eclaim_db;"
psql -U eclaim -d eclaim_db -f database/schema-postgresql-merged.sql
```

## Verification

หลัง migration ให้ตรวจสอบ:

```sql
-- 1. Check tables exist
SHOW TABLES LIKE 'claim_%';  -- MySQL
\dt claim_*                   -- PostgreSQL

-- 2. Check columns added
DESCRIBE claim_rep_opip_nhso_item;  -- MySQL
\d claim_rep_opip_nhso_item          -- PostgreSQL

-- 3. Check tracking table
SELECT * FROM eclaim_imported_files LIMIT 5;

-- 4. Test import (จะสร้าง file_id อัตโนมัติ)
-- Run via CLI or Web UI
```

## Using New Schema

### Import ไฟล์ใหม่

```bash
# CLI
python eclaim_import.py downloads/eclaim_10670_OP_25690106_212004432.xls

# Check result
python -c "
from config.database import get_db_config
import pymysql
conn = pymysql.connect(**get_db_config())
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM claim_rep_opip_nhso_item WHERE file_id IS NOT NULL')
print(f'Records with file_id: {cursor.fetchone()[0]}')
"
```

### Web UI (ทำงานเหมือนเดิม)

1. ไปที่ http://localhost:5001/files
2. กด "Import All" หรือ import ทีละไฟล์
3. ระบบจะใช้ importer_v2 อัตโนมัติ

## Rollback (ถ้าต้องการ)

```bash
# Restore จาก backup
mysql -u eclaim -p eclaim_db < backup_before_migration.sql

# PostgreSQL
psql -U eclaim -d eclaim_db < backup_before_migration.sql
```

## Key Benefits

✅ **ใช้โครงสร้างเดิมทั้งหมด** - ไม่ต้อง migrate ข้อมูล
✅ **เพิ่ม tracking** - รู้ว่า record มาจากไฟล์ไหน
✅ **HIS Reconciliation** - พร้อมสำหรับ reconcile กับ HIS
✅ **รองรับ 2 DB** - MySQL และ PostgreSQL
✅ **UPSERT** - Import ซ้ำได้ ไม่ duplicate
✅ **Field mapping ครบ** - 170+ columns

## Troubleshooting

### Error: Table doesn't exist

```sql
-- Check current tables
SHOW TABLES;

-- ถ้าไม่มี ให้ import schema
mysql -u eclaim -p eclaim_db < database/schema-mysql-merged.sql
```

### Error: Column doesn't exist

```sql
-- Check columns
DESCRIBE claim_rep_opip_nhso_item;

-- ถ้าขาด file_id ให้รัน ALTER TABLE
-- (ดูคำสั่งใน Option B ข้างบน)
```

### Error: Foreign key constraint fails

```sql
-- Check if tracking table exists
SELECT * FROM eclaim_imported_files;

-- If not, create it first (see Option B above)
```
