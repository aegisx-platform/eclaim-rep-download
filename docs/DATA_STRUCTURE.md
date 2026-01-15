# E-Claim Data Structure Documentation

## Overview

This document describes the complete data structure for the E-Claim system database, including tables, column mappings, master data, and analytics views.

## Database Schema

### Main Tables

| Table | Description | Record Count |
|-------|-------------|--------------|
| `eclaim_imported_files` | Tracks imported file metadata | 803 |
| `claim_rep_opip_nhso_item` | OP/IP claim detail records | 44,966 |
| `claim_rep_orf_nhso_item` | ORF (OP Refer) claim records | 1,720 |
| `eclaim_summary` | Summary records per file | 6,189 |
| `eclaim_drug` | Drug detail records | 1,646,542 |
| `eclaim_instrument` | Medical instrument records | 48,841 |
| `eclaim_deny` | Denied claims records | 5,019 |
| `eclaim_zero_paid` | Zero-paid claims records | 132,503 |

---

## claim_rep_opip_nhso_item (OP/IP Records)

This is the main table containing claim detail records with **120 columns** mapped from E-Claim Excel files.

### Column Groups

#### 1. Basic Information (Columns 0-13)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `rep_no` | REP No. | 0 |
| `seq` | ลำดับที่ | 1 |
| `tran_id` | TRAN_ID (Primary Key) | 2 |
| `hn` | HN (Hospital Number) | 3 |
| `an` | AN (Admission Number) | 4 |
| `pid` | PID (เลขประจำตัวประชาชน) | 5 |
| `name` | ชื่อ-สกุล | 6 |
| `ptype` | ประเภทผู้ป่วย (OP/IP) | 7 |
| `dateadm` | วันเข้ารักษา | 8 |
| `datedsc` | วันจำหน่าย | 9 |
| `reimb_nhso` | ชดเชยสุทธิ (สปสช.) | 10 |
| `reimb_agency` | ชดเชยสุทธิ (หน่วยงาน) | 11 |
| `claim_from` | ชดเชยจาก | 12 |
| `error_code` | Error Code | 13 |

#### 2. Fund & Service Info (Columns 14-22)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `main_fund` | กองทุนหลัก | 14 |
| `sub_fund` | กองทุนย่อย | 15 |
| `service_type` | ประเภทบริการ | 16 |
| `chk_refer` | การรับส่งต่อ | 17 |
| `chk_right` | การมีสิทธิ | 18 |
| `chk_use_right` | การใช้สิทธิ | 19 |
| `chk` | CHK | 20 |
| `main_inscl` | สิทธิหลัก | 21 |
| `sub_inscl` | สิทธิย่อย | 22 |
| `scheme` | รหัสสิทธิ (UCS/LGO/SSS/OFC) | - |

#### 3. Hospital Codes (Columns 23-34)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `href` | HREF (Hospital Refer) | 23 |
| `hcode` | HCODE (Hospital Code) | 24 |
| `hmain` | HMAIN | 25 |
| `prov1` | PROV1 (รหัสจังหวัด) | 26 |
| `rg1` | RG1 (เขตสุขภาพ) | 27 |
| `hmain2` | HMAIN2 | 28 |
| `prov2` | PROV2 | 29 |
| `rg2` | RG2 | 30 |
| `hmain3` | DMIS/HMAIN3 | 31 |
| `da` | DA | 32 |
| `projcode` | PROJ (รหัสโครงการ) | 33 |
| `pa` | PA | 34 |

#### 4. DRG Info (Columns 35-37)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `drg` | DRG (Diagnosis Related Group) | 35 |
| `rw` | RW (Relative Weight) | 36 |
| `ca_type` | CA_TYPE | 37 |

#### 5. Claim/Reimbursement (Columns 38-53)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `claim_drg` | เรียกเก็บ (1) - กลุ่มที่ไม่ใช่ค่ารถ+ยา+อุปกรณ์ | 38 |
| `claim_xdrg` | เรียกเก็บ (1.2) - กลุ่มค่ารถ+ยา+อุปกรณ์ | 39 |
| `claim_net` | เรียกเก็บ (1.3) - รวมยอดเรียกเก็บ | 40 |
| `claim_central_reimb` | เรียกเก็บ central reimburse (2) | 41 |
| `paid` | ชำระเอง (3) | 42 |
| `pay_point` | อัตราจ่าย/Point (4) | 43 |
| `ps_chk` | ล่าช้า PS (5) - flag | 44 |
| `ps_percent` | ล่าช้า PS (5) - เปอร์เซ็นต์ | 45 |
| `ccuf` | CCUF (6) | 46 |
| `adjrw_nhso` | AdjRW_NHSO (7) | 47 |
| `adjrw2` | AdjRW2 (8 = 6x7) | 48 |
| `reimb_amt` | จ่ายชดเชย (9 = 4x5x8) | 49 |
| `act_amt` | ค่าพรบ. (10) | 50 |
| `salary_rate` | เงินเดือน - ร้อยละ | 51 |
| `salary_amt` | เงินเดือน - จำนวนเงิน (11) | 52 |
| `reimb_diff_salary` | ยอดชดเชยหลังหักเงินเดือน (12) | 53 |

#### 6. HC - ค่าใช้จ่ายสูง (Columns 54-55)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `iphc` | IPHC (IP High Cost) | 54 |
| `ophc` | OPHC (OP High Cost) | 55 |

#### 7. AE - อุบัติเหตุฉุกเฉิน (Columns 56-63)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `ae_opae` | OPAE (OP Accident Emergency) | 56 |
| `ae_ipnb` | IPNB | 57 |
| `ae_ipuc` | IPUC | 58 |
| `ae_ip3sss` | IP3SSS | 59 |
| `ae_ip7sss` | IP7SSS | 60 |
| `ae_carae` | CARAE | 61 |
| `ae_caref` | CAREF | 62 |
| `ae_caref_puc` | CAREF-PUC | 63 |

#### 8. INST - อวัยวะเทียม/อุปกรณ์ (Columns 64-65)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `opinst` | OPINST (OP Instrument) | 64 |
| `inst` | INST (IP Instrument) | 65 |

#### 9. IP - ผู้ป่วยใน (Columns 66-74)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `ipaec` | IPAEC | 66 |
| `ipaer` | IPAER | 67 |
| `ipinrgc` | IPINRGC | 68 |
| `ipinrgr` | IPINRGR | 69 |
| `ipinspsn` | IPINSPSN | 70 |
| `ipprcc` | IPPRCC | 71 |
| `ipprcc_puc` | IPPRCC-PUC | 72 |
| `ipbkk_inst` | IPBKK-INST | 73 |
| `ip_ontop` | IP-ONTOP | 74 |

#### 10. DMIS - โรคเฉพาะ (Columns 75-95)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `cataract_amt` | CATARACT (ต้อกระจก) | 75 |
| `cataract_oth` | CATARACT - ค่าภาระงาน(สสจ.) | 76 |
| `cataract_hosp` | CATARACT - ค่าภาระงาน(รพ.) | 77 |
| `dmis_catinst` | CATINST | 78 |
| `dmisrc_amt` | DMISRC | 79 |
| `dmisrc_workload` | DMISRC - ค่าภาระงาน | 80 |
| `rcuhosc_amt` | RCUHOSC | 81 |
| `rcuhosc_workload` | RCUHOSC - ค่าภาระงาน | 82 |
| `rcuhosr_amt` | RCUHOSR | 83 |
| `rcuhosr_workload` | RCUHOSR - ค่าภาระงาน | 84 |
| `dmis_llop` | LLOP | 85 |
| `dmis_llrgc` | LLRGC | 86 |
| `dmis_llrgr` | LLRGR | 87 |
| `dmis_lp` | LP | 88 |
| `dmis_stroke_drug` | STROKE-STEMI DRUG | 89 |
| `dmis_dmidml` | DMIDML | 90 |
| `dmis_pp` | PP | 91 |
| `dmis_dmishd` | DMISHD (Hemodialysis) | 92 |
| `dmis_dmicnt` | DMICNT (Continuous) | 93 |
| `dmis_paliative` | Paliative Care | 94 |
| `dmis_dm` | DM (เบาหวาน) | 95 |

#### 11. DRUG (Column 96)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `drug` | DRUG (ยา) | 96 |

#### 12. OPBKK - กรุงเทพ (Columns 97-103)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `opbkk_hc` | OPBKK - HC | 97 |
| `opbkk_dent` | OPBKK - DENT (ทันตกรรม) | 98 |
| `opbkk_drug` | OPBKK - DRUG | 99 |
| `opbkk_fs` | OPBKK - FS | 100 |
| `opbkk_others` | OPBKK - OTHERS | 101 |
| `opbkk_hsub` | OPBKK - HSUB | 102 |
| `opbkk_nhso` | OPBKK - NHSO | 103 |

#### 13. Deny (Columns 104-108)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `deny_hc` | Deny - HC | 104 |
| `deny_ae` | Deny - AE | 105 |
| `deny_inst` | Deny - INST | 106 |
| `deny_ip` | Deny - IP | 107 |
| `deny_dmis` | Deny - DMIS | 108 |

#### 14. Base Rate (Columns 109-111)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `baserate_old` | base rate เดิม | 109 |
| `baserate_add` | base rate ที่ได้รับเพิ่ม | 110 |
| `baserate_total` | base rate สุทธิ | 111 |

#### 15. Others (Columns 112-119)

| DB Column | Description (TH) | Excel Index |
|-----------|-----------------|-------------|
| `fs` | FS | 112 |
| `va` | VA | 113 |
| `remark` | Remark | 114 |
| `audit_results` | AUDIT RESULTS | 115 |
| `payment_type` | รูปแบบการจ่าย | 116 |
| `seq_no` | SEQ NO | 117 |
| `invoice_no` | INVOICE NO | 118 |
| `invoice_lt` | INVOICE LT | 119 |

---

## claim_rep_orf_nhso_item (ORF Records)

ORF (OP Refer) records contain 113 columns for referral cases.

### Key Column Groups

| Group | Description | Columns |
|-------|-------------|---------|
| Basic Info | REP, TRAN_ID, HN, PID | 0-7 |
| Referral Info | ใบส่งต่อ, HREF | 8-19 |
| Claim Info | ยอดเรียกเก็บ, ชำระเอง | 20-32 |
| Central Reimburse | OPHC, AE04, OPINST, DMIS | 33-61 |
| OPREFER Details | ค่าใช้จ่าย 19 หมวด | 62-100 |
| Others | Error, VA, Audit, Invoice | 101-112 |

---

## Master Data Tables

### 1. icd10_codes (ICD-10 Diagnosis Codes)

```sql
SELECT code, description_en, description_th, category
FROM icd10_codes
LIMIT 5;
```

| Column | Type | Description |
|--------|------|-------------|
| code | VARCHAR(10) | รหัส ICD-10 (Primary Key) |
| description_en | TEXT | คำอธิบายภาษาอังกฤษ |
| description_th | TEXT | คำอธิบายภาษาไทย |
| category | VARCHAR(50) | หมวดหมู่โรค |
| chapter | VARCHAR(10) | Chapter (A-Z) |

### 2. icd9cm_procedures (ICD-9-CM Procedure Codes)

| Column | Type | Description |
|--------|------|-------------|
| code | VARCHAR(10) | รหัส ICD-9-CM (Primary Key) |
| description_en | TEXT | คำอธิบายภาษาอังกฤษ |
| description_th | TEXT | คำอธิบายภาษาไทย |
| category | VARCHAR(50) | หมวดหมู่หัตถการ |

### 3. drg_codes (DRG Codes)

| Column | Type | Description |
|--------|------|-------------|
| drg_code | VARCHAR(10) | รหัส DRG (Primary Key) |
| drg_name | TEXT | ชื่อ DRG |
| mdc | VARCHAR(10) | Major Diagnostic Category |
| relative_weight | DECIMAL(8,4) | RW มาตรฐาน |
| los_mean | DECIMAL(8,2) | จำนวนวันนอนเฉลี่ย |

### 4. nhso_error_codes (Error Codes)

| Column | Type | Description |
|--------|------|-------------|
| error_code | VARCHAR(20) | รหัส Error (Primary Key) |
| error_description | TEXT | คำอธิบาย Error |
| error_category | VARCHAR(50) | หมวดหมู่ Error |
| action_required | TEXT | วิธีแก้ไข |

### 5. fund_types (Fund Types)

| Column | Type | Description |
|--------|------|-------------|
| fund_code | VARCHAR(10) | รหัสกองทุน (Primary Key) |
| fund_name | TEXT | ชื่อกองทุน |
| fund_type | VARCHAR(20) | ประเภท (main/sub) |
| parent_fund_code | VARCHAR(10) | รหัสกองทุนหลัก |

### 6. service_types (Service Types)

| Column | Type | Description |
|--------|------|-------------|
| service_code | VARCHAR(5) | รหัสบริการ (Primary Key) |
| service_name | TEXT | ชื่อประเภทบริการ |
| service_category | VARCHAR(50) | หมวดหมู่ |

### 7. tmt_drugs (TMT Drug Codes)

| Column | Type | Description |
|--------|------|-------------|
| tmt_code | VARCHAR(50) | รหัส TMT (Primary Key) |
| generic_name | TEXT | ชื่อสามัญ |
| trade_name | TEXT | ชื่อการค้า |
| dosage_form | VARCHAR(100) | รูปแบบยา |
| strength | VARCHAR(100) | ความแรง |
| unit | VARCHAR(50) | หน่วย |

### 8. dim_date (Date Dimension)

| Column | Type | Description |
|--------|------|-------------|
| date_key | DATE | วันที่ (Primary Key) |
| date_thai | VARCHAR(50) | วันที่ไทย |
| day_of_week | INTEGER | วันในสัปดาห์ (1-7) |
| day_name_th | VARCHAR(20) | ชื่อวัน (จันทร์-อาทิตย์) |
| month_thai | INTEGER | เดือนไทย (1-12) |
| month_name_th | VARCHAR(20) | ชื่อเดือน |
| year_thai | INTEGER | ปีพุทธศักราช |
| year_gregorian | INTEGER | ปีคริสต์ศักราช |
| quarter | INTEGER | ไตรมาส (1-4) |
| fiscal_year | INTEGER | ปีงบประมาณ |
| is_weekend | BOOLEAN | วันหยุดสุดสัปดาห์ |
| is_holiday | BOOLEAN | วันหยุดราชการ |

---

## Analytics Views

### 1. v_daily_claims_summary

รายงานสรุปรายวัน

```sql
SELECT * FROM v_daily_claims_summary
WHERE claim_date >= '2025-10-01'
ORDER BY claim_date DESC;
```

| Column | Description |
|--------|-------------|
| claim_date | วันที่เข้ารักษา |
| op_cases | จำนวน OP |
| ip_cases | จำนวน IP |
| total_cases | จำนวนรวม |
| total_reimb | ยอดชดเชยรวม |
| avg_reimb | ชดเชยเฉลี่ย/ราย |

### 2. v_monthly_claims_summary

รายงานสรุปรายเดือน

```sql
SELECT * FROM v_monthly_claims_summary
WHERE year_month >= '2025-10'
ORDER BY year_month DESC;
```

### 3. v_fund_analysis

วิเคราะห์ตามกองทุน

```sql
SELECT * FROM v_fund_analysis
ORDER BY total_reimb DESC;
```

### 4. v_service_type_analysis

วิเคราะห์ตามประเภทบริการ

```sql
SELECT * FROM v_service_type_analysis
ORDER BY total_cases DESC;
```

### 5. v_drg_analysis

วิเคราะห์ตาม DRG

```sql
SELECT * FROM v_drg_analysis
ORDER BY total_cases DESC
LIMIT 20;
```

### 6. v_error_analysis

วิเคราะห์ Error Codes

```sql
SELECT * FROM v_error_analysis
WHERE error_code IS NOT NULL
ORDER BY error_count DESC;
```

### 7. v_scheme_comparison

เปรียบเทียบสิทธิ (UCS, LGO, SSS, OFC)

```sql
SELECT * FROM v_scheme_comparison;
```

### 8. v_hc_ae_inst_analysis

วิเคราะห์ HC, AE, INST

```sql
SELECT * FROM v_hc_ae_inst_analysis
WHERE month >= '2025-10';
```

### 9. v_dmis_analysis

วิเคราะห์โรคเฉพาะ (DMIS)

```sql
SELECT * FROM v_dmis_analysis
ORDER BY year_month DESC;
```

### 10. v_baserate_analysis

วิเคราะห์ Base Rate

```sql
SELECT * FROM v_baserate_analysis
WHERE year_month >= '2025-10';
```

### 11. v_deny_analysis

วิเคราะห์ Deny

```sql
SELECT * FROM v_deny_analysis
ORDER BY total_deny_amount DESC;
```

### 12. v_reimb_trend

Trend การเบิกจ่าย

```sql
SELECT * FROM v_reimb_trend
ORDER BY claim_date DESC;
```

---

## Insurance Schemes

| Code | Name (TH) | Name (EN) |
|------|-----------|-----------|
| UCS | หลักประกันสุขภาพถ้วนหน้า | Universal Coverage Scheme |
| LGO | องค์กรปกครองส่วนท้องถิ่น | Local Government Organizations |
| SSS | ประกันสังคม | Social Security Scheme |
| OFC | ข้าราชการ | Civil Servant Medical Benefit Scheme |

---

## File Types

| Type | Description |
|------|-------------|
| OP | ผู้ป่วยนอก (Outpatient) |
| IP | ผู้ป่วยใน (Inpatient) |
| ORF | OP Refer (ส่งต่อผู้ป่วยนอก) |
| OPLGO | OP อปท. |
| IPLGO | IP อปท. |
| OPSSS | OP ประกันสังคม |
| IPSSS | IP ประกันสังคม |
| OPBKK | OP กรุงเทพ |
| IPBKK | IP กรุงเทพ |
| OP_APPEAL | OP อุทธรณ์ |
| IP_APPEAL | IP อุทธรณ์ |

---

## Sample Queries

### 1. Daily Reimbursement Summary

```sql
SELECT
    dateadm::date as claim_date,
    scheme,
    COUNT(*) as cases,
    SUM(reimb_nhso) as total_reimb,
    AVG(reimb_nhso) as avg_reimb
FROM claim_rep_opip_nhso_item
WHERE dateadm >= '2025-10-01'
GROUP BY dateadm::date, scheme
ORDER BY claim_date DESC;
```

### 2. Top 10 DRG by Cases

```sql
SELECT
    drg,
    COUNT(*) as cases,
    SUM(reimb_nhso) as total_reimb,
    AVG(rw) as avg_rw
FROM claim_rep_opip_nhso_item
WHERE drg IS NOT NULL
GROUP BY drg
ORDER BY cases DESC
LIMIT 10;
```

### 3. Error Analysis

```sql
SELECT
    error_code,
    COUNT(*) as error_count,
    SUM(reimb_nhso) as affected_amount
FROM claim_rep_opip_nhso_item
WHERE error_code IS NOT NULL AND error_code != ''
GROUP BY error_code
ORDER BY error_count DESC
LIMIT 20;
```

### 4. Monthly Trend by Scheme

```sql
SELECT
    TO_CHAR(dateadm, 'YYYY-MM') as month,
    scheme,
    COUNT(*) as cases,
    SUM(reimb_nhso) as total_reimb
FROM claim_rep_opip_nhso_item
GROUP BY TO_CHAR(dateadm, 'YYYY-MM'), scheme
ORDER BY month DESC, scheme;
```

### 5. High Cost (HC) Analysis

```sql
SELECT
    TO_CHAR(dateadm, 'YYYY-MM') as month,
    COUNT(*) FILTER (WHERE ophc > 0) as ophc_cases,
    SUM(ophc) as ophc_total,
    COUNT(*) FILTER (WHERE iphc > 0) as iphc_cases,
    SUM(iphc) as iphc_total
FROM claim_rep_opip_nhso_item
GROUP BY TO_CHAR(dateadm, 'YYYY-MM')
ORDER BY month DESC;
```

---

## Data Import Process

1. **Download** - Excel files are downloaded from NHSO E-Claim system
2. **Parse** - Files are parsed using pandas with index-based column mapping
3. **Transform** - Data is transformed and validated
4. **Load** - Data is loaded into PostgreSQL using UPSERT (ON CONFLICT)

### File Naming Convention

```
eclaim_{HCODE}_{TYPE}_{YYYYMMDD}_{REPNO}.xls
```

Example: `eclaim_10670_IP_25681001_191042462.xls`
- HCODE: 10670 (Hospital Code)
- TYPE: IP (Inpatient)
- DATE: 25681001 (Thai year 2568, October 1)
- REPNO: 191042462 (REP Number)

---

## Database Connection

```python
from config.database import get_db_config, DB_TYPE
import psycopg2

db_config = get_db_config()
conn = psycopg2.connect(**db_config)
```

Or via Docker:

```bash
docker-compose exec db psql -U eclaim -d eclaim_db
```

---

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 2.0 | 2026-01-15 | Added 120-column mapping, Master Data tables, Analytics Views |
| 1.0 | 2025-12-01 | Initial 49-column mapping |
