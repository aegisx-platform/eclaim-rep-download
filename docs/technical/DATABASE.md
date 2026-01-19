# 📊 Database Guide

## Database database schema

database schema ใช้โครงสร้างตารางของโรงพยาบาลเป็นหลัก พร้อมเพิ่ม tracking และ HIS reconciliation

### Schema Files

- **PostgreSQL**: `database/schema-postgresql-merged.sql`
- **MySQL**: `database/schema-mysql-merged.sql`

## Tables Overview

### 1. eclaim_imported_files

Track import status ของแต่ละไฟล์

```sql
CREATE TABLE eclaim_imported_files (
    id                  SERIAL PRIMARY KEY,
    filename            VARCHAR(255) NOT NULL UNIQUE,
    file_type           VARCHAR(20) NOT NULL,  -- OP, IP, ORF, IP_APPEAL, IP_APPEAL_NHSO
    hospital_code       VARCHAR(10) NOT NULL,
    file_date           DATE,
    file_sequence       VARCHAR(20),
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_records       INTEGER DEFAULT 0,
    imported_records    INTEGER DEFAULT 0,
    failed_records      INTEGER DEFAULT 0,
    file_created_at     TIMESTAMP,
    import_started_at   TIMESTAMP,
    import_completed_at TIMESTAMP,
    error_message       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Fields:**
- `filename` - ชื่อไฟล์ (unique)
- `file_type` - ประเภทไฟล์
- `status` - pending, processing, completed, failed, partial
- `imported_records` - จำนวน records ที่ import สำเร็จ

### 2. claim_rep_opip_nhso_item

ข้อมูล OP/IP claims (โครงสร้างของโรงพยาบาล + tracking fields)

```sql
CREATE TABLE claim_rep_opip_nhso_item (
    id                  SERIAL PRIMARY KEY,
    file_id             INTEGER,               -- NEW: Foreign key
    row_number          INTEGER,               -- NEW: Row tracking

    -- EXISTING: All hospital's original columns (182 columns)
    rep_no              VARCHAR(15),
    seq                 INTEGER,
    tran_id             VARCHAR(15),
    hn                  VARCHAR(15),
    an                  VARCHAR(15),
    pid                 VARCHAR(20),
    name                VARCHAR(100),
    ptype               VARCHAR(5),
    dateadm             TIMESTAMP,
    datedsc             TIMESTAMP,
    reimb_nhso          DECIMAL(10,2),
    reimb_agency        DECIMAL(10,2),
    -- ... 170+ more columns ...

    -- NEW: HIS Reconciliation
    his_matched         BOOLEAN DEFAULT FALSE,
    his_matched_at      TIMESTAMP,
    his_vn              VARCHAR(20),
    his_amount_diff     DECIMAL(10,2),
    reconcile_status    VARCHAR(20),
    reconcile_note      TEXT,

    lastupdate          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_opip_tran_file UNIQUE (tran_id, file_id),
    CONSTRAINT fk_opip_file FOREIGN KEY (file_id)
        REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);
```

**Total Columns:** 132 columns
- 4 tracking columns (file_id, row_number, his_matched_at, lastupdate)
- 6 HIS reconciliation columns
- 122 original hospital columns

### 3. claim_rep_orf_nhso_item

ข้อมูล OP Refer (โครงสร้างของโรงพยาบาล + tracking fields)

```sql
CREATE TABLE claim_rep_orf_nhso_item (
    id                  SERIAL PRIMARY KEY,
    file_id             INTEGER,               -- NEW: Foreign key
    row_number          INTEGER,               -- NEW: Row tracking

    -- EXISTING: All hospital's original columns (138 columns)
    rep_no              VARCHAR(15),
    no                  INTEGER,
    tran_id             VARCHAR(15),
    hn                  VARCHAR(15),
    pid                 VARCHAR(20),
    name                VARCHAR(100),
    service_date        TIMESTAMP,
    refer_no            VARCHAR(20),
    -- ... 130+ more columns ...

    -- NEW: HIS Reconciliation
    his_matched         BOOLEAN DEFAULT FALSE,
    his_matched_at      TIMESTAMP,
    his_vn              VARCHAR(20),
    his_amount_diff     DECIMAL(10,2),
    reconcile_status    VARCHAR(20),
    reconcile_note      TEXT,

    lastupdate          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT uq_orf_tran_file UNIQUE (tran_id, file_id),
    CONSTRAINT fk_orf_file FOREIGN KEY (file_id)
        REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);
```

**Total Columns:** 121 columns

## Views for Reporting

### v_daily_claim_summary

สรุปข้อมูลรายวัน

```sql
CREATE VIEW v_daily_claim_summary AS
SELECT
    DATE(c.dateadm) as service_date,
    c.ptype,
    c.main_inscl,
    COUNT(*) as claim_count,
    SUM(c.reimb_nhso) as total_reimbursement,
    SUM(CASE WHEN c.error_code IS NOT NULL AND c.error_code != '-'
        THEN 1 ELSE 0 END) as error_count,
    SUM(CASE WHEN c.his_matched THEN 1 ELSE 0 END) as matched_count
FROM claim_rep_opip_nhso_item c
GROUP BY DATE(c.dateadm), c.ptype, c.main_inscl
ORDER BY service_date DESC, ptype, main_inscl;
```

### v_unmatched_claims

รายการ claims ที่ยังไม่ match กับ HIS

```sql
CREATE VIEW v_unmatched_claims AS
SELECT
    c.id, c.tran_id, c.hn, c.an, c.pid, c.name,
    c.ptype, c.dateadm, c.datedsc, c.reimb_nhso,
    c.error_code, f.filename, f.file_date
FROM claim_rep_opip_nhso_item c
LEFT JOIN eclaim_imported_files f ON c.file_id = f.id
WHERE c.his_matched = FALSE
ORDER BY c.dateadm DESC;
```

### v_import_status

สถิติการ import ตาม file type และ status

```sql
CREATE VIEW v_import_status AS
SELECT
    f.file_type, f.status,
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

## HIS Reconciliation

### Reconciliation Fields

| Field | Type | Description |
|-------|------|-------------|
| `his_matched` | BOOLEAN | สถานะการ match (TRUE = matched) |
| `his_matched_at` | TIMESTAMP | วันเวลาที่ match สำเร็จ |
| `his_vn` | VARCHAR(20) | Visit Number จากระบบ HIS |
| `his_amount_diff` | DECIMAL(10,2) | ผลต่างยอดเงิน (e-claim - HIS) |
| `reconcile_status` | VARCHAR(20) | สถานะ: pending/matched/mismatched/manual |
| `reconcile_note` | TEXT | หมายเหตุการ reconcile |

### Reconciliation Process

```sql
-- 1. Find unmatched claims
SELECT * FROM v_unmatched_claims WHERE ptype = 'OP';

-- 2. Match with HIS (example)
UPDATE claim_rep_opip_nhso_item c
SET
    his_matched = TRUE,
    his_matched_at = CURRENT_TIMESTAMP,
    his_vn = h.vn,
    his_amount_diff = c.reimb_nhso - h.total_amount,
    reconcile_status = CASE
        WHEN ABS(c.reimb_nhso - h.total_amount) < 0.01 THEN 'matched'
        ELSE 'mismatched'
    END
FROM his_opd_visits h
WHERE c.hn = h.hn
  AND DATE(c.dateadm) = DATE(h.vstdate)
  AND c.his_matched = FALSE;

-- 3. Check reconciliation results
SELECT
    reconcile_status,
    COUNT(*) as count,
    SUM(his_amount_diff) as total_diff
FROM claim_rep_opip_nhso_item
WHERE his_matched = TRUE
GROUP BY reconcile_status;
```

## Indexes

### Performance Indexes

```sql
-- File tracking
CREATE INDEX idx_opip_file_id ON claim_rep_opip_nhso_item(file_id);
CREATE INDEX idx_orf_file_id ON claim_rep_orf_nhso_item(file_id);

-- Query optimization
CREATE INDEX idx_opip_rep_no ON claim_rep_opip_nhso_item(rep_no, tran_id);
CREATE INDEX idx_opip_hn ON claim_rep_opip_nhso_item(hn);
CREATE INDEX idx_opip_pid ON claim_rep_opip_nhso_item(pid);
CREATE INDEX idx_opip_dateadm ON claim_rep_opip_nhso_item(dateadm);
CREATE INDEX idx_opip_an ON claim_rep_opip_nhso_item(an);
CREATE INDEX idx_opip_tran_id ON claim_rep_opip_nhso_item(tran_id);
CREATE INDEX idx_opip_error_code ON claim_rep_opip_nhso_item(error_code);

-- HIS reconciliation
CREATE INDEX idx_opip_reconcile ON claim_rep_opip_nhso_item(his_matched, reconcile_status);
CREATE INDEX idx_orf_reconcile ON claim_rep_orf_nhso_item(his_matched, reconcile_status);
```

## Column Mapping

### Excel to Database Mapping

| Excel Column (Thai) | Database Column |
|---------------------|-----------------|
| ชื่อ-สกุล | name |
| วันเข้ารักษา | dateadm |
| วันจำหน่าย | datedsc |
| ชดเชยสุทธิ (บาท) (สปสช.) | reimb_nhso |
| ชดเชยสุทธิ (บาท) (ต้นสังกัด) | reimb_agency |
| สิทธิหลัก | main_inscl |
| ประเภทผู้ป่วย | ptype |
| REP No. | rep_no |
| TRAN_ID | tran_id |
| HN | hn |
| AN | an |
| CID | pid |

**Total Mappings:** 170+ columns

See: `utils/eclaim/importer_v2.py` for complete mapping

## Database Queries

### Common Queries

#### Count imported files

```sql
SELECT
    file_type,
    COUNT(*) as file_count,
    SUM(imported_records) as total_records
FROM eclaim_imported_files
WHERE status = 'completed'
GROUP BY file_type;
```

#### Recent claims

```sql
SELECT
    c.tran_id, c.hn, c.name, c.dateadm, c.reimb_nhso,
    f.filename
FROM claim_rep_opip_nhso_item c
JOIN eclaim_imported_files f ON c.file_id = f.id
ORDER BY c.dateadm DESC
LIMIT 100;
```

#### Error analysis

```sql
SELECT
    error_code,
    COUNT(*) as count
FROM claim_rep_opip_nhso_item
WHERE error_code IS NOT NULL AND error_code != '-'
GROUP BY error_code
ORDER BY count DESC;
```

#### Monthly summary

```sql
SELECT
    TO_CHAR(dateadm, 'YYYY-MM') as month,
    ptype,
    COUNT(*) as claim_count,
    SUM(reimb_nhso) as total_reimb
FROM claim_rep_opip_nhso_item
GROUP BY TO_CHAR(dateadm, 'YYYY-MM'), ptype
ORDER BY month DESC, ptype;
```

## Backup & Restore

### Backup

```bash
# PostgreSQL
docker-compose exec db pg_dump -U eclaim eclaim_db > backup_$(date +%Y%m%d).sql

# MySQL
docker-compose exec db mysqldump -u eclaim -p eclaim_db > backup_$(date +%Y%m%d).sql
```

### Restore

```bash
# PostgreSQL
docker-compose exec -T db psql -U eclaim -d eclaim_db < backup.sql

# MySQL
docker-compose exec -T db mysql -u eclaim -p eclaim_db < backup.sql
```

### Automated Backup Script

```bash
#!/bin/bash
# backup.sh
BACKUP_DIR="/backups"
DATE=$(date +%Y%m%d_%H%M%S)

docker-compose exec -T db pg_dump -U eclaim eclaim_db \
  | gzip > "$BACKUP_DIR/eclaim_${DATE}.sql.gz"

# Keep only last 30 days
find "$BACKUP_DIR" -name "eclaim_*.sql.gz" -mtime +30 -delete
```

## Migration Guide

See [MIGRATE_V2.md](../MIGRATE_V2.md) for:
- Migrating from old schema to V2
- Fresh installation with V2
- Rollback procedures

---

**[← Back: Usage Guide](USAGE.md)** | **[Next: Legal & Compliance →](LEGAL.md)**
