# Master Data Documentation

## Overview

Master Data tables ใช้สำหรับ reference และ lookup ในการวิเคราะห์ข้อมูล E-Claim ประกอบด้วย 8 tables:

| Table | Description | Records | Status |
|-------|-------------|---------|--------|
| `icd10_codes` | รหัสโรค ICD-10-TM | 40,488 | ✅ Complete |
| `icd9cm_procedures` | รหัสหัตถการ ICD-9-CM | 3,882 | ✅ Complete |
| `tmt_drugs` | รหัสยา TMT | 35,092 | ✅ Complete |
| `dim_date` | มิติวันที่ | 2,557 | ✅ Complete |
| `nhso_error_codes` | รหัส Error สปสช. | 63 | ⚠️ Partial |
| `fund_types` | ประเภทกองทุน | 24 | ⚠️ Partial |
| `service_types` | ประเภทบริการ | 6 | ✅ Complete |
| `drg_codes` | รหัส DRG | 0 | ❌ Pending |

---

## 1. ICD-10 Codes (รหัสโรค)

### Table Structure

```sql
CREATE TABLE icd10_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,      -- รหัส ICD-10 เช่น A00.0
    description_en TEXT,                    -- คำอธิบายภาษาอังกฤษ
    description_th TEXT,                    -- คำอธิบายภาษาไทย
    chapter VARCHAR(200),                   -- Chapter เช่น "Certain infectious diseases"
    block_name VARCHAR(200),                -- Block เช่น "Intestinal Infectious Diseases"
    category VARCHAR(50),                   -- หมวดหมู่
    level INTEGER,                          -- ระดับ (1-4)
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Data Source

- **Source**: Thai Health Coding Center (THCC)
- **File**: `ICD10TM-Public.xlsx`
- **Download**: https://github.com/rathpanyowat/ICD-10-TM-Rath
- **Version**: ICD-10-TM 2016

### Import Command

```bash
# Download file
curl -L -o downloads/ICD10TM-Public.xlsx \
  "https://github.com/rathpanyowat/ICD-10-TM-Rath/raw/master/ICD10TM-Public.xlsx"

# Import (inside Docker)
docker-compose exec web python utils/masterdata_importer.py
```

### Sample Data

| code | description_en | chapter |
|------|----------------|---------|
| A00.0 | Cholera due to Vibrio cholerae 01, biovar cholerae | Certain infectious and parasitic diseases |
| I10 | Essential (primary) hypertension | Diseases of the circulatory system |
| E11.9 | Type 2 diabetes mellitus without complications | Endocrine, nutritional and metabolic diseases |

### Usage Example

```sql
-- Join with claims to get diagnosis descriptions
SELECT
    c.tran_id,
    c.hn,
    i.code,
    i.description_en as diagnosis
FROM claim_rep_opip_nhso_item c
LEFT JOIN icd10_codes i ON c.drg LIKE i.code || '%'
WHERE c.dateadm >= '2025-10-01';
```

---

## 2. ICD-9-CM Procedures (รหัสหัตถการ)

### Table Structure

```sql
CREATE TABLE icd9cm_procedures (
    id SERIAL PRIMARY KEY,
    code VARCHAR(10) UNIQUE NOT NULL,      -- รหัส ICD-9-CM เช่น 00.01
    description_en TEXT,                    -- คำอธิบายภาษาอังกฤษ
    description_th TEXT,                    -- คำอธิบายภาษาไทย
    category VARCHAR(50),                   -- หมวดหมู่
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Data Source

- **Source**: CMS (Centers for Medicare & Medicaid Services)
- **File**: `CMS32_DESC_LONG_SG.txt`
- **Download**: https://github.com/ufbmi/icd-tools
- **Version**: ICD-9-CM Version 32 (2014)

### Import Command

```bash
# Download file
curl -L -o downloads/icd9cm_procedures.txt \
  "https://raw.githubusercontent.com/ufbmi/icd-tools/master/icd-9-cm-v32/CMS32_DESC_LONG_SG.txt"

# Import
docker-compose exec web python utils/masterdata_importer.py
```

### Sample Data

| code | description_en |
|------|----------------|
| 00.01 | Therapeutic ultrasound of vessels of head and neck |
| 36.01 | Single vessel percutaneous transluminal coronary angioplasty |
| 81.54 | Total knee replacement |

---

## 3. TMT Drugs (รหัสยามาตรฐาน)

### Table Structure

```sql
CREATE TABLE tmt_drugs (
    id SERIAL PRIMARY KEY,
    tmt_code VARCHAR(50) UNIQUE NOT NULL,   -- รหัส TMT เช่น 228497
    fsn TEXT,                                -- Full Specified Name
    generic_name VARCHAR(500),               -- ชื่อสามัญ
    trade_name VARCHAR(300),                 -- ชื่อการค้า
    strength VARCHAR(100),                   -- ความแรง เช่น "500 mg"
    dosage_form VARCHAR(100),                -- รูปแบบยา เช่น "tablet"
    package_size VARCHAR(50),                -- ขนาดบรรจุ
    package_unit VARCHAR(50),                -- หน่วยบรรจุ
    manufacturer VARCHAR(200),               -- ผู้ผลิต
    change_date DATE,                        -- วันที่อัพเดท
    issue_date DATE,                         -- วันที่ออก
    effective_date DATE,                     -- วันที่มีผล
    invalid_date DATE,                       -- วันที่หมดอายุ
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Data Source

- **Source**: TMT Center (สถาบันวิจัยระบบสาธารณสุข)
- **Website**: http://tmt.this.or.th/
- **File**: `TMTRF20251201_FULL.xls`
- **Version**: TMT Release December 2025

### File Types

| File | Description | Usage |
|------|-------------|-------|
| `TMTRF*_FULL.xls` | รายการทั้งหมด (รวม invalid) | Full import |
| `TMTRF*_SNAPSHOT.xls` | เฉพาะรายการที่ยังใช้งาน | Active drugs only |
| `TMTRF*_DELTA.xls` | รายการที่เปลี่ยนแปลง | Incremental update |

### Import Command

```bash
# Full import (replace all)
docker-compose exec web python utils/tmt_importer.py downloads/TMTRF20251201_FULL.xls --type full

# Delta import (update only changes)
docker-compose exec web python utils/tmt_importer.py downloads/TMTRF20251201_DELTA.xls --type delta
```

### Sample Data

| tmt_code | trade_name | generic_name | strength | dosage_form |
|----------|------------|--------------|----------|-------------|
| 228497 | ACETA | paracetamol | 500 mg | tablet |
| 227162 | AAMOX 500 | amoxicillin | 500 mg | film-coated tablet |
| 861134 | VIVACOR | rosuvastatin | 10 mg | film-coated tablet |

### Usage Example

```sql
-- Search drugs by generic name
SELECT tmt_code, trade_name, generic_name, strength
FROM tmt_drugs
WHERE generic_name ILIKE '%paracetamol%'
AND is_active = true;

-- Match with E-Claim drug data
SELECT
    d.drug_code,
    t.generic_name,
    t.trade_name,
    d.quantity,
    d.amount
FROM eclaim_drug d
LEFT JOIN tmt_drugs t ON d.drug_code = t.tmt_code
WHERE d.file_id = 123;
```

### Update Schedule

TMT ออกเวอร์ชันใหม่ทุกเดือน ควรอัพเดทเป็นประจำ:

```bash
# Download latest from http://tmt.this.or.th/
# Then run delta import
docker-compose exec web python utils/tmt_importer.py downloads/TMTRF_NEW_DELTA.xls --type delta
```

---

## 4. Date Dimension (มิติวันที่)

### Table Structure

```sql
CREATE TABLE dim_date (
    date_key DATE PRIMARY KEY,              -- วันที่ (Primary Key)
    date_thai VARCHAR(50),                  -- วันที่ไทย "1 มกราคม 2568"
    day_of_week INTEGER,                    -- วันในสัปดาห์ (1-7)
    day_name_th VARCHAR(20),                -- ชื่อวัน "จันทร์"
    day_name_en VARCHAR(20),                -- ชื่อวัน "Monday"
    month_thai INTEGER,                     -- เดือน (1-12)
    month_name_th VARCHAR(20),              -- ชื่อเดือน "มกราคม"
    month_name_en VARCHAR(20),              -- ชื่อเดือน "January"
    year_thai INTEGER,                      -- ปีพุทธศักราช
    year_gregorian INTEGER,                 -- ปีคริสต์ศักราช
    quarter INTEGER,                        -- ไตรมาส (1-4)
    fiscal_year INTEGER,                    -- ปีงบประมาณ
    is_weekend BOOLEAN,                     -- วันหยุดสุดสัปดาห์
    is_holiday BOOLEAN                      -- วันหยุดราชการ
);
```

### Data Range

- **Start**: 2020-01-01 (พ.ศ. 2563)
- **End**: 2026-12-31 (พ.ศ. 2569)
- **Total**: 2,557 days (7 years)

### Usage Example

```sql
-- Monthly claims with Thai month names
SELECT
    d.month_name_th,
    d.year_thai,
    COUNT(*) as cases,
    SUM(c.reimb_nhso) as total_reimb
FROM claim_rep_opip_nhso_item c
JOIN dim_date d ON c.dateadm::date = d.date_key
GROUP BY d.year_thai, d.month_thai, d.month_name_th
ORDER BY d.year_thai DESC, d.month_thai DESC;
```

---

## 5. NHSO Error Codes (รหัส Error)

### Table Structure

```sql
CREATE TABLE nhso_error_codes (
    id SERIAL PRIMARY KEY,
    error_code VARCHAR(20) UNIQUE NOT NULL,
    error_description_th VARCHAR(500),
    error_description_en VARCHAR(500),
    error_category VARCHAR(50),
    error_severity VARCHAR(20),
    resolution_guide TEXT,
    is_active BOOLEAN DEFAULT true
);
```

### Current Status

- **Imported**: 63 codes (extracted from actual E-Claim data)
- **Status**: ⚠️ Partial - ขาดคำอธิบายละเอียด

### TODO

ต้องเพิ่มคำอธิบาย Error จากเอกสาร สปสช.:

```sql
-- Update error descriptions
UPDATE nhso_error_codes SET
    error_description_th = 'ไม่พบข้อมูลสิทธิ'
WHERE error_code = '566';
```

---

## 6. Fund Types (ประเภทกองทุน)

### Table Structure

```sql
CREATE TABLE fund_types (
    id SERIAL PRIMARY KEY,
    fund_code VARCHAR(20) UNIQUE NOT NULL,
    fund_name_th VARCHAR(200),
    fund_name_en VARCHAR(200),
    fund_category VARCHAR(50),              -- 'main' or 'sub'
    parent_fund_code VARCHAR(20),
    description TEXT,
    is_active BOOLEAN DEFAULT true
);
```

### Current Status

- **Imported**: 24 common fund codes
- **Status**: ⚠️ Partial - อาจมีกองทุนเพิ่มเติม

### Sample Data

| fund_code | fund_name_th | fund_category |
|-----------|--------------|---------------|
| OP | ผู้ป่วยนอก | main |
| IP | ผู้ป่วยใน | main |
| AE01 | อุบัติเหตุฉุกเฉินผู้ป่วยใน | main |
| DRUG | ยา | main |
| IPNB-FIX | IP Non-Bangkok Fixed | sub |

---

## 7. Service Types (ประเภทบริการ)

### Table Structure

```sql
CREATE TABLE service_types (
    id SERIAL PRIMARY KEY,
    service_code VARCHAR(10) UNIQUE NOT NULL,
    service_name_th VARCHAR(200),
    service_name_en VARCHAR(200),
    service_category VARCHAR(50),
    is_active BOOLEAN DEFAULT true
);
```

### Current Data

| service_code | service_name_th | service_name_en | service_category |
|--------------|-----------------|-----------------|------------------|
| E | ฉุกเฉิน | Emergency | OP |
| R | ส่งต่อ | Refer | OP/IP |
| P | แพ็คเกจ | Package | IP |
| A | อุบัติเหตุ | Accident | OP |
| C | ทำคลอด | Childbirth | IP |
| N | ปกติ | Normal | OP |

---

## 8. DRG Codes (รหัสกลุ่มวินิจฉัยโรคร่วม)

### Table Structure

```sql
CREATE TABLE drg_codes (
    id SERIAL PRIMARY KEY,
    drg_code VARCHAR(10) UNIQUE NOT NULL,
    drg_name TEXT,
    mdc VARCHAR(10),                        -- Major Diagnostic Category
    mdc_name TEXT,
    drg_type VARCHAR(20),                   -- Medical/Surgical
    relative_weight DECIMAL(8,4),           -- RW มาตรฐาน
    los_mean DECIMAL(8,2),                  -- จำนวนวันนอนเฉลี่ย
    los_low INTEGER,                        -- วันนอนต่ำ
    los_high INTEGER,                       -- วันนอนสูง
    is_active BOOLEAN DEFAULT true
);
```

### Current Status

- **Status**: ❌ Pending - ยังไม่ได้นำเข้า

### How to Get DRG Data

1. **Option 1**: ดาวน์โหลด TDRG Seeker จาก https://www.tcmc.or.th/download-tcmc
   - Extract ข้อมูล DRG จากโปรแกรม

2. **Option 2**: ขอไฟล์โดยตรงจาก สปสช. หรือ TCMC
   - Email: info@tcmc.or.th

3. **Option 3**: Extract จากเอกสาร PDF
   - TDRG V 6.3 Manual มี DRG listing

---

## Import Scripts

### All-in-One Import

```bash
# Import all available master data
docker-compose exec web python utils/masterdata_importer.py
```

### Individual Imports

```bash
# TMT Drugs
docker-compose exec web python utils/tmt_importer.py downloads/TMTRF_FULL.xls --type full

# ICD-10 and ICD-9-CM
docker-compose exec web python utils/masterdata_importer.py
```

---

## Maintenance

### Monthly Updates

1. **TMT Drugs**: ดาวน์โหลด DELTA file ทุกเดือนจาก http://tmt.this.or.th/
2. **Error Codes**: Extract รหัสใหม่จากข้อมูล E-Claim ที่ import

### Annual Updates

1. **ICD-10-TM**: ตรวจสอบเวอร์ชันใหม่จาก THCC
2. **DRG**: อัพเดทเมื่อ สปสช. ออก TDRG เวอร์ชันใหม่

---

## Data Quality Notes

1. **ICD-10-TM**: ใช้ version 2016 ซึ่งเป็น version ล่าสุดจาก THCC
2. **ICD-9-CM**: CMS version 32 (2014) - ใช้สำหรับ procedure codes
3. **TMT**: อัพเดทล่าสุด December 2025
4. **DRG**: รอนำเข้า - ต้องขอจาก TCMC

---

## Version History

| Date | Changes |
|------|---------|
| 2026-01-15 | Initial import: ICD-10-TM, ICD-9-CM, TMT, dim_date |
| 2026-01-15 | Added service_types, fund_types, error_codes from E-Claim data |
