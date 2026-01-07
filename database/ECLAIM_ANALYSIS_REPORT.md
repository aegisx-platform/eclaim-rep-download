# E-Claim XLS Analysis Report

## 1. File Overview

### 1.1 File Types Summary

| File Type       | Count | Description                                      |
|-----------------|-------|--------------------------------------------------|
| **OP**          | 78    | Outpatient claims - การเบิกจ่ายผู้ป่วยนอก       |
| **IP**          | 27    | Inpatient claims - การเบิกจ่ายผู้ป่วยใน         |
| **ORF**         | 18    | OP Refer - การส่งต่อผู้ป่วยนอก                  |
| **IP_APPEAL**   | 1     | IP Appeal by Hospital - การอุทธรณ์โดย รพ.       |
| **IP_APPEAL_NHSO** | 2  | IP Appeal by NHSO - การอุทธรณ์โดย สปสช.         |
| **Total**       | 126   |                                                  |

### 1.2 Filename Pattern

```
eclaim_{hospital_code}_{type}_{date_BE}_{sequence}.xls

Example: eclaim_10670_IP_25680122_205506156.xls
- hospital_code: 10670 (Khon Kaen Hospital)
- type: IP (Inpatient)
- date_BE: 25680122 (Buddhist Era 2568, Jan 22)
- sequence: 205506156
```

### 1.3 File Structure

All files have:
- **Header rows**: 5-8 rows containing report metadata
- **Column headers**: Usually at row 5 (OP/IP) or row 7 (ORF)
- **Multi-row headers**: Some columns span multiple rows
- **Data rows**: Start after headers

---

## 2. Column Analysis by File Type

### 2.1 OP/IP Claims (120 columns)

Both OP and IP files share the same structure with 120 columns. Key differences are:
- IP has AN (Admission Number), OP has no AN
- IP has DRG/RW values, OP typically doesn't
- IP has discharge dates, OP typically has "-"

#### Core Identifier Fields
| Column | Thai Name          | Description                    | Example            |
|--------|-------------------|--------------------------------|--------------------|
| REP No.| -                 | Report number                  | 680100337          |
| TRAN_ID| -                 | Transaction ID (unique)        | 610629012          |
| HN     | -                 | Hospital Number                | 67000351           |
| AN     | -                 | Admission Number (IP only)     | 6803310            |
| PID    | -                 | Personal ID (13 digits)        | 1100400777018      |

#### Patient Information
| Column         | Thai Name          | Description               |
|----------------|-------------------|---------------------------|
| ชื่อ-สกุล      | -                 | Patient name              |
| ประเภทผู้ป่วย  | -                 | Patient type (OP/IP)      |
| วันเข้ารักษา   | -                 | Admission date            |
| วันจำหน่าย     | -                 | Discharge date            |

#### Rights & Hospital Codes
| Column    | Description                     |
|-----------|---------------------------------|
| สิทธิหลัก  | Main right: UCS, WEL, SSS, etc.|
| สิทธิย่อย  | Sub right code                  |
| HCODE     | Hospital code                   |
| HMAIN     | Main responsible hospital       |
| PROV1     | Province code 1                 |
| RG1       | Region code 1                   |

#### Billing & Reimbursement
| Column              | Thai Name                        |
|--------------------|---------------------------------|
| ชดเชยสุทธิ          | Net reimbursement               |
| เรียกเก็บ (1)       | Claim amount                    |
| ชำระเอง (3)         | Self-pay                        |
| ค่าพรบ. (10)        | PRB amount                      |
| เงินเดือน           | Salary deduction                |

#### Fund Categories
- **HC (High Cost)**: IPHC, OPHC, HC01-HC09
- **AE (Accident/Emergency)**: OPAE, IPNB, IPUC, CARAE, etc.
- **INST (Prosthetics)**: OPINST, INST
- **IP (Inpatient)**: IPAEC, IPAER, IPINRGC, IPINRGR, etc.
- **DMIS (Specific Diseases)**: CATARACT, DMISRC, RCUHOSC, etc.
- **DRUG**: Drug reimbursement
- **Deny**: Denied amounts per category

### 2.2 OP Refer (ORF) - 114 columns

ORF has a different structure focused on referral cases.

#### Unique ORF Fields
| Column              | Description                           |
|--------------------|---------------------------------------|
| เลขที่ใบส่งต่อ      | Referral document number              |
| หน่วยบริการ         | Service unit information              |
| DX                  | Diagnosis codes                       |
| Proc.              | Procedure codes                       |
| รายการ OPREF       | OP Refer amount                       |

#### 16 Expense Categories (with claimable/non-claimable)
1. ค่าห้อง/ค่าอาหาร - Room & Food
2. อวัยวะเทียม - Prosthetics
3. ยาและสารอาหารทางเส้นเลือด - IV Drugs
4. ยาที่นำไปใช้ต่อที่บ้าน - Take-home drugs
5. เวชภัณฑ์ที่ไม่ใช่ยา - Medical supplies
6. บริการโลหิต - Blood services
7. ตรวจวินิจฉัยทางเทคนิคการแพทย์ - Lab
8. ตรวจวินิจฉัยทางรังสีวิทยา - Radiology
9. ตรวจวินิจฉัยโดยวิธีพิเศษ - Special diagnostics
10. อุปกรณ์และเครื่องมือ - Equipment
11. ทำหัตถการและวิสัญญี - Procedures & Anesthesia
12. ค่าบริการทางพยาบาล - Nursing
13. ค่าบริการทันตกรรม - Dental
14. กายภาพบำบัด - Physical therapy
15. ฝังเข็ม - Acupuncture
16. ห้องผ่าตัดและห้องคลอด - OR & Delivery

---

## 3. Key Fields for HIS Reconciliation

### 3.1 Primary Match Keys
1. **HN** - Hospital Number (most reliable)
2. **AN** - Admission Number (for IP)
3. **PID** - National ID (13-digit)
4. **TRAN_ID** - E-Claim transaction ID

### 3.2 Secondary Match Fields
- **วันเข้ารักษา** - Admission date
- **วันจำหน่าย** - Discharge date
- **ชื่อ-สกุล** - Patient name (fuzzy match)

### 3.3 Amount Validation Fields
- **ชดเชยสุทธิ** - Net reimbursement
- **เรียกเก็บ** - Claimed amount
- **ชำระเอง** - Self-pay amount

---

## 4. Database Schema Design

### 4.1 Design Decisions

| Decision | Rationale |
|----------|-----------|
| **Unified OP/IP table** | 95% columns overlap, simplifies queries |
| **Separate ORF table** | Different structure, unique expense categories |
| **TRAN_ID as natural key** | Unique per transaction, stable |
| **Composite unique on (tran_id, file_id)** | Allows re-import of same file |
| **Reconciliation fields in main table** | Avoids JOINs for common queries |

### 4.2 Table Structure

```
eclaim_imported_files
├── id (PK)
├── filename (UNIQUE)
├── file_type
├── status (pending/processing/completed/failed)
└── timestamps

eclaim_claims (OP + IP + Appeal)
├── id (PK)
├── file_id (FK)
├── tran_id (natural key)
├── Core identifiers (HN, AN, PID)
├── Patient info
├── Rights & hospital codes
├── Billing amounts
├── Fund amounts (~50 columns)
├── HIS reconciliation fields
└── timestamps

eclaim_op_refer (ORF)
├── id (PK)
├── file_id (FK)
├── tran_id (natural key)
├── Core identifiers
├── Referral info
├── 16 expense categories (x2 for claimable/non-claimable)
├── HIS reconciliation fields
└── timestamps
```

### 4.3 ER Diagram (Text)

```
┌─────────────────────────┐
│  eclaim_imported_files  │
├─────────────────────────┤
│ PK id                   │
│    filename (UNIQUE)    │
│    file_type            │──────┐
│    status               │      │
│    hospital_code        │      │
│    file_date            │      │
│    total_records        │      │
│    imported_records     │      │
│    timestamps           │      │
└─────────────────────────┘      │
                                 │
        ┌────────────────────────┼────────────────────────┐
        │                        │                        │
        │ 1:N                    │ 1:N                    │
        ▼                        ▼                        ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ eclaim_claims │    │ eclaim_claims │    │eclaim_op_refer│
│    (OP)       │    │    (IP)       │    │    (ORF)      │
├───────────────┤    ├───────────────┤    ├───────────────┤
│ PK id         │    │ PK id         │    │ PK id         │
│ FK file_id    │    │ FK file_id    │    │ FK file_id    │
│    tran_id    │    │    tran_id    │    │    tran_id    │
│    hn         │◄───┤    hn         │    │    hn         │
│    pid        │    │    an         │    │    pid        │
│    ...        │    │    drg        │    │    refer_doc  │
│               │    │    rw         │    │    16 expense │
│ HIS Reconcile │    │ HIS Reconcile │    │    categories │
│    his_hn     │    │    his_hn     │    │ HIS Reconcile │
│    his_vn     │    │    his_an     │    │    his_hn     │
│    matched    │    │    matched    │    │    his_vn     │
└───────────────┘    └───────────────┘    └───────────────┘

                          ┌──────────────────┐
                          │   HIS Database   │
                          ├──────────────────┤
                          │  Patient (HN)    │
                          │  Visit (VN)      │
                          │  Admission (AN)  │
                          │  Billing         │
                          └──────────────────┘
```

---

## 5. Import Strategy

### 5.1 Import Process Flow

```
1. Detect new files in downloads folder
        │
        ▼
2. Parse filename → extract metadata
   (file_type, date, hospital_code)
        │
        ▼
3. Create record in eclaim_imported_files
   (status = 'processing')
        │
        ▼
4. Read XLS file
   - Detect header row (row 5 or 7)
   - Map columns to database fields
        │
        ▼
5. Validate & Transform data
   - Convert dates (Thai to CE)
   - Clean numeric values
   - Handle null/empty values
        │
        ▼
6. Insert into appropriate table
   - eclaim_claims (OP, IP, Appeal)
   - eclaim_op_refer (ORF)
        │
        ▼
7. Update import status
   (status = 'completed' or 'failed')
        │
        ▼
8. Run reconciliation (optional)
```

### 5.2 Handling Duplicates

```sql
-- Strategy: UPSERT based on (tran_id, file_id)

INSERT INTO eclaim_claims (...)
VALUES (...)
ON CONFLICT (tran_id, file_id) DO UPDATE SET
    net_reimbursement = EXCLUDED.net_reimbursement,
    error_code = EXCLUDED.error_code,
    updated_at = CURRENT_TIMESTAMP;
```

### 5.3 Re-import Handling

Options:
1. **Skip existing**: Don't import if file already exists
2. **Replace**: Delete existing records and re-import
3. **Update**: Use UPSERT to update existing records

Recommended: **Option 3 (Update)** - preserves reconciliation data

### 5.4 Validation Rules

| Field | Validation |
|-------|------------|
| TRAN_ID | Required, not null |
| HN | Should exist in HIS patient table |
| PID | 13-digit format |
| Dates | Valid date format |
| Amounts | Numeric, >= 0 |
| Patient Type | 'OP' or 'IP' |
| Rights | Valid right codes (UCS, WEL, etc.) |

---

## 6. Reconciliation Strategy

### 6.1 Matching Algorithm

```sql
-- Step 1: Exact match by HN + Date
UPDATE eclaim_claims c
SET
    his_matched = TRUE,
    his_hn = h.hn,
    his_vn = h.vn,
    reconcile_status = 'matched'
FROM his_visits h
WHERE c.hn = h.hn
  AND DATE(c.admission_date) = DATE(h.visit_date)
  AND c.his_matched = FALSE;

-- Step 2: Match by AN (for IP)
UPDATE eclaim_claims c
SET
    his_matched = TRUE,
    his_an = h.an,
    reconcile_status = 'matched'
FROM his_admissions h
WHERE c.an = h.an
  AND c.patient_type = 'IP'
  AND c.his_matched = FALSE;

-- Step 3: Match by PID + Date (fallback)
UPDATE eclaim_claims c
SET
    his_matched = TRUE,
    his_hn = h.hn,
    reconcile_status = 'matched'
FROM his_patients p
JOIN his_visits h ON p.hn = h.hn
WHERE c.pid = p.national_id
  AND DATE(c.admission_date) = DATE(h.visit_date)
  AND c.his_matched = FALSE;
```

### 6.2 Amount Reconciliation

```sql
-- Calculate difference
UPDATE eclaim_claims c
SET his_amount_diff = c.net_reimbursement - h.total_charge
FROM his_billing h
WHERE c.his_vn = h.vn;

-- Flag significant differences (> 100 baht)
UPDATE eclaim_claims
SET reconcile_status = 'review'
WHERE ABS(his_amount_diff) > 100;
```

### 6.3 Reconciliation Status

| Status | Description |
|--------|-------------|
| pending | Not yet processed |
| matched | Successfully matched with HIS |
| mismatched | Matched but amounts differ |
| manual | Requires manual review |
| not_found | No matching record in HIS |

---

## 7. Sample Python Import Code

```python
import pandas as pd
import psycopg2
from datetime import datetime
import re

def parse_filename(filename):
    """Extract metadata from filename"""
    # eclaim_10670_IP_25680122_205506156.xls
    pattern = r'eclaim_(\d+)_([A-Z_]+)_(\d{8})_(\d+)\.xls'
    match = re.match(pattern, filename)
    if match:
        return {
            'hospital_code': match.group(1),
            'file_type': match.group(2),
            'file_date': parse_be_date(match.group(3)),
            'sequence': match.group(4)
        }
    return None

def parse_be_date(date_str):
    """Convert Buddhist Era date to CE date"""
    # 25680122 -> 2025-01-22
    be_year = int(date_str[:4])
    ce_year = be_year - 543
    month = int(date_str[4:6])
    day = int(date_str[6:8])
    return datetime(ce_year, month, day).date()

def detect_header_row(df):
    """Find the row containing column headers"""
    for i in range(10):
        row_values = df.iloc[i].astype(str).tolist()
        if 'HN' in row_values or 'PID' in row_values:
            return i
    return 5  # default

def import_xls_file(filepath, conn):
    """Import single XLS file to database"""
    filename = os.path.basename(filepath)
    metadata = parse_filename(filename)

    # Create import record
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO eclaim_imported_files
        (filename, file_type, hospital_code, file_date, status)
        VALUES (%s, %s, %s, %s, 'processing')
        RETURNING id
    """, (filename, metadata['file_type'],
          metadata['hospital_code'], metadata['file_date']))
    file_id = cur.fetchone()[0]

    # Read Excel
    df = pd.read_excel(filepath, engine='xlrd', header=None)
    header_row = detect_header_row(df)

    # Map columns and import
    # ... (implementation details)

    # Update status
    cur.execute("""
        UPDATE eclaim_imported_files
        SET status = 'completed',
            total_records = %s,
            imported_records = %s
        WHERE id = %s
    """, (len(df), imported_count, file_id))

    conn.commit()
```

---

## 8. Recommended Next Steps

### Phase 1: Basic Import
1. Set up PostgreSQL database
2. Run schema.sql to create tables
3. Implement basic Python importer
4. Test with sample files

### Phase 2: Validation & Error Handling
1. Add data validation rules
2. Implement error logging
3. Handle edge cases (missing data, invalid formats)
4. Create error reports

### Phase 3: HIS Integration
1. Define HIS database structure (or use existing)
2. Implement matching queries
3. Build reconciliation reports
4. Create reconciliation dashboard

### Phase 4: Automation
1. Schedule automatic file detection
2. Implement import queue
3. Set up monitoring/alerts
4. Create backup strategy

---

## 9. Files Created

| File | Description |
|------|-------------|
| `/database/schema.sql` | Complete PostgreSQL schema |
| `/database/ECLAIM_ANALYSIS_REPORT.md` | This analysis report |

---

*Report generated: 2026-01-07*
*Hospital: 10670 (Khon Kaen)*
*Total files analyzed: 126*
