# E-Claim Excel Column Analysis for Database Schema

## Overview

This document provides detailed column analysis of E-Claim Excel files (OP, IP, ORF) downloaded from NHSO system for creating database schema.

## File Types and Sheets

| File Type | Available Sheets |
|-----------|-----------------|
| OP (ผู้ป่วยนอก) | Detail, Summary, Data Drug, Data sheet 0 |
| IP (ผู้ป่วยใน) | Detail, Summary, Data Instrument, Data Drug, Data DENY, Data sheet 0 |
| ORF (ส่งต่อ) | Detail, Summary, Data Drug |

---

## 1. Summary Sheet (OP/IP/ORF)

Multi-level header structure with financial summary data.

### Column Structure (57 columns for OP/IP, 55 for ORF)

| Col | Field Name (Thai) | Field Name (English) | Data Type | Sample |
|-----|-------------------|---------------------|-----------|--------|
| 0 | งวด | period | VARCHAR(10) | '-' |
| 1 | HCODE | hospital_code | VARCHAR(5) | '10670' |
| 2 | REP NO. | rep_no | VARCHAR(15) | '690100001' |
| **ข้อมูลปกติ (Normal Data)** |
| 3 | จำนวนราย > ทั้งหมด | total_cases | INTEGER | 36 |
| 4 | จำนวนราย > ผ่าน | passed_cases | INTEGER | 36 |
| 5 | จำนวนราย > ไม่ผ่าน | failed_cases | INTEGER | 0 |
| 6 | HC > เรียกเก็บ | hc_claim | DECIMAL(15,2) | 68060 |
| 7 | HC > ชดเชย | hc_reimburse | DECIMAL(15,2) | 65461.99 |
| 8 | AE > เรียกเก็บ | ae_claim | DECIMAL(15,2) | 7720 |
| 9 | AE > ชดเชย | ae_reimburse | DECIMAL(15,2) | 4880 |
| 10 | INST > เรียกเก็บ | inst_claim | DECIMAL(15,2) | 0 |
| 11 | INST > ชดเชย | inst_reimburse | DECIMAL(15,2) | 0 |
| 12 | IP > เรียกเก็บ | ip_claim | DECIMAL(15,2) | 0 |
| 13 | IP > ชดเชย | ip_reimburse | DECIMAL(15,2) | 0 |
| 14 | DMIS > เรียกเก็บ | dmis_claim | DECIMAL(15,2) | 0 |
| 15 | DMIS > ชดเชย | dmis_reimburse | DECIMAL(15,2) | 0 |
| 16 | PP > เรียกเก็บ | pp_claim | DECIMAL(15,2) | 0 |
| 17 | PP > ชดเชย | pp_reimburse | DECIMAL(15,2) | 0 |
| 18 | DRUG > เรียกเก็บ | drug_claim | DECIMAL(15,2) | 8510.86 |
| 19 | DRUG > ชดเชย | drug_reimburse | DECIMAL(15,2) | 9165.36 |
| 20 | จ่ายชดเชยต้นสังกัด | reimburse_original | DECIMAL(15,2) | 0 |
| 21 | จ่ายชดเชยทั้งสิ้น | reimburse_total | DECIMAL(15,2) | 79507.35 |
| **ข้อมูลอุทธรณ์ (Appeal Data)** |
| 22 | จำนวนราย > ทั้งหมด | appeal_total_cases | INTEGER | 0 |
| 23 | จำนวนราย > ผ่าน | appeal_passed_cases | INTEGER | 0 |
| 24 | จำนวนราย > ไม่ผ่าน | appeal_failed_cases | INTEGER | 0 |
| 25-38 | ข้อมูลเดิม (HC, AE, INST, IP, DMIS, PP, DRUG) | appeal_old_* | DECIMAL(15,2) | 0 |
| 39 | ข้อมูลเดิม > จ่ายชดเชย | appeal_old_reimburse | DECIMAL(15,2) | 0 |
| 40-53 | ข้อมูลใหม่ที่ขออุทธรณ์ (HC, AE, INST, IP, DMIS, PP, DRUG) | appeal_new_* | DECIMAL(15,2) | 0 |
| 54 | ข้อมูลใหม่ > จ่ายชดเชย | appeal_new_reimburse | DECIMAL(15,2) | 0 |
| **ชดเชยสุทธิ (Net Reimbursement)** |
| 55 | จ่ายเพิ่ม | additional_payment | DECIMAL(15,2) | 0 |
| 56 | เรียกคืน | refund | DECIMAL(15,2) | 0 |

---

## 2. Data Drug Sheet (OP/IP/ORF)

Drug dispensing data with multi-row headers.

### Column Structure (22 columns for OP/IP, 21 for ORF)

| Col | Row3 Header | Row4 Header | Field Name (English) | Data Type | Sample |
|-----|-------------|-------------|---------------------|-----------|--------|
| 0 | ลำดับที่ | - | seq_no | INTEGER | 1 |
| 1 | TRAN_ID | - | tran_id | VARCHAR(20) | '731938385' |
| 2 | HN | - | hn | VARCHAR(15) | '68067169' |
| 3 | AN | - | an | VARCHAR(20) | null / 'ODS6812152123' |
| 4 | วันเข้ารักษา | - | admit_date | DATE | '20/12/2568' (Thai) |
| 5 | PID | - | pid | VARCHAR(13) | '3440300677538' |
| 6 | ชื่อ - สกุล | - | patient_name | VARCHAR(100) | 'นาย ทองดำ สร้อยอั้ว' |
| 7 | ลำดับที่ (ยา) | - | drug_seq_no | INTEGER | 1 |
| 8 | รายการยา | รหัสยา รพ. (Working Code) | drug_code | VARCHAR(20) | 'GBPTT3' |
| 9 | - | TMT | tmt_code | VARCHAR(10) | '477458' |
| 10 | - | ชื่อสามัญ | generic_name | VARCHAR(200) | 'gabapentin' |
| 11 | - | ชื่อการค้า | trade_name | VARCHAR(100) | 'VULTIN 300' |
| 12 | - | ประเภทยา | drug_type | VARCHAR(10) | 'ED' |
| 13 | - | ชนิดยา | drug_category | VARCHAR(50) | 'COVID,DrugsFS,UCEP' |
| 14 | - | Dosageform | dosage_form | VARCHAR(50) | null |
| 15 | เรียกเก็บ | จำนวน (1) | claim_qty | DECIMAL(10,2) | 0 |
| 16 | - | ราคาต่อหน่วย (2) | unit_price | DECIMAL(15,2) | 1.75 |
| 17 | - | รวมเงินที่ขอเบิก (3) | claim_amount | DECIMAL(15,2) | 157.5 |
| 18 | ชดเชย สปสช. | ราคาเพดาน (4) | ceiling_price | DECIMAL(15,2) | 0 |
| 19 | - | รวมชดเชย (5) = (1)*(4) | reimburse_amount | DECIMAL(15,2) | 270 |
| 20 | ชดเชยต้นสังกัด | - | original_reimburse | DECIMAL(15,2) | 0 |
| 21 | Error Code | - | error_code | VARCHAR(50) | null |

**Note:** ORF file has 21 columns (no ชดเชยต้นสังกัด column)

---

## 3. Data Instrument Sheet (IP only)

Medical instrument/equipment dispensing data.

### Column Structure (16 columns)

| Col | Row3 Header | Row4/Row5 Header | Field Name (English) | Data Type | Sample |
|-----|-------------|------------------|---------------------|-----------|--------|
| 0 | ลำดับที่ | - | seq_no | INTEGER | 1 |
| 1 | TRAN_ID | - | tran_id | VARCHAR(20) | '732072602' |
| 2 | HN | - | hn | VARCHAR(15) | '68034879' |
| 3 | AN | - | an | VARCHAR(20) | 'ODS6812170126' |
| 4 | วันเข้ารักษา | - | admit_date | DATE | '17/12/2568' |
| 5 | PID | - | pid | VARCHAR(13) | '3401200004605' |
| 6 | ชื่อ - สกุล | - | patient_name | VARCHAR(100) | 'นาย อนุพงษ์ ใจตรง' |
| 7 | ลำดับที่ (อุปกรณ์) | - | inst_seq_no | INTEGER | 1 |
| 8 | เรียกเก็บ > อุปกรณ์ | รหัส | inst_code | VARCHAR(10) | '6002' |
| 9 | - | ชื่ออุปกรณ์ | inst_name | VARCHAR(200) | 'สายสวนปัสสาวะ ชนิดใช้ในไต' |
| 10 | - | จำนวนชิ้น | claim_qty | INTEGER | 2 |
| 11 | - | จำนวนเงิน | claim_amount | DECIMAL(15,2) | 7400 |
| 12 | จ่ายชดเชย | จำนวนชิ้น | reimburse_qty | INTEGER | 0 |
| 13 | - | จำนวนเงิน | reimburse_amount | DECIMAL(15,2) | 0 |
| 14 | ปฏิเสธ | - | deny_flag | VARCHAR(10) | '-' |
| 15 | Error Code | - | error_code | VARCHAR(50) | null |

---

## 4. Data DENY Sheet (IP only)

Denied claims data.

### Column Structure (13 columns)

| Col | Field Name (Thai) | Field Name (English) | Data Type | Sample |
|-----|-------------------|---------------------|-----------|--------|
| 0 | ลำดับที่ | seq_no | INTEGER | 1 |
| 1 | TRAN_ID | tran_id | VARCHAR(20) | '732077716' |
| 2 | HCODE | hospital_code | VARCHAR(5) | '10670' |
| 3 | HN | hn | VARCHAR(15) | '64125857' |
| 4 | AN | an | VARCHAR(20) | 'ODS6812091749' |
| 5 | วันเข้ารักษา | admit_date | DATE | '09/12/2568' |
| 6 | PID | pid | VARCHAR(13) | '3401200670389' |
| 7 | ชื่อ - สกุล | patient_name | VARCHAR(100) | 'นาย ภูวดี นิลศิริ' |
| 8 | กองทุน | fund_code | VARCHAR(20) | 'IPINRGR' |
| 9 | รหัสเบิก | claim_code | VARCHAR(20) | 'IP01' |
| 10 | หมวดค่าใช้จ่าย | expense_category | INTEGER | null |
| 11 | จำนวนขอเบิก | claim_amount | DECIMAL(15,2) | 0 |
| 12 | DENY | deny_code | VARCHAR(20) | 'G40' |

---

## 5. Data Sheet 0 (OP/IP) - Zero Paid

Claims paid 0 baht.

### Column Structure (16 columns)

| Col | Field Name (Thai) | Field Name (English) | Data Type | Sample |
|-----|-------------------|---------------------|-----------|--------|
| 0 | ลำดับที่ | seq_no | INTEGER | 1 |
| 1 | TRAN_ID | tran_id | VARCHAR(20) | '731959440' |
| 2 | HCODE | hospital_code | VARCHAR(5) | '10670' |
| 3 | HN | hn | VARCHAR(15) | '68067257' |
| 4 | AN | an | VARCHAR(20) | null / 'ODS6812170925' |
| 5 | วันเข้ารักษา | admit_date | DATE | '22/12/2568' |
| 6 | PID | pid | VARCHAR(13) | '1101800554793' |
| 7 | ชื่อ - สกุล | patient_name | VARCHAR(100) | 'น.ส. สุภาพร ทาอ้าย' |
| 8 | กองทุน | fund_code | VARCHAR(20) | 'OPAE' |
| 9 | รหัสเบิก | claim_code | VARCHAR(20) | '55020' |
| 10 | TMT | tmt_code | VARCHAR(10) | null / '848962' |
| 11 | หมวดค่าใช้จ่าย | expense_category | INTEGER | 12 |
| 12 | จำนวนขอเบิก | claim_qty | INTEGER | 1 |
| 13 | จำนวนจ่าย | paid_qty | INTEGER | 0 |
| 14 | เงินที่จ่าย | paid_amount | DECIMAL(15,2) | 0 |
| 15 | เหตุผล | reason | VARCHAR(200) | null |

---

## Database Schema Recommendations

### Table 1: eclaim_summary

```sql
CREATE TABLE eclaim_summary (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id),
    file_type VARCHAR(10) NOT NULL,  -- 'OP', 'IP', 'ORF'
    period VARCHAR(10),
    hospital_code VARCHAR(5),
    rep_no VARCHAR(15),

    -- Normal Data
    total_cases INTEGER,
    passed_cases INTEGER,
    failed_cases INTEGER,

    hc_claim DECIMAL(15,2),
    hc_reimburse DECIMAL(15,2),
    ae_claim DECIMAL(15,2),
    ae_reimburse DECIMAL(15,2),
    inst_claim DECIMAL(15,2),
    inst_reimburse DECIMAL(15,2),
    ip_claim DECIMAL(15,2),
    ip_reimburse DECIMAL(15,2),
    dmis_claim DECIMAL(15,2),
    dmis_reimburse DECIMAL(15,2),
    pp_claim DECIMAL(15,2),
    pp_reimburse DECIMAL(15,2),
    drug_claim DECIMAL(15,2),
    drug_reimburse DECIMAL(15,2),

    reimburse_original DECIMAL(15,2),
    reimburse_total DECIMAL(15,2),

    -- Appeal Data
    appeal_total_cases INTEGER,
    appeal_passed_cases INTEGER,
    appeal_failed_cases INTEGER,

    -- ... (appeal_old_* and appeal_new_* fields)

    additional_payment DECIMAL(15,2),
    refund DECIMAL(15,2),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(file_id)
);
```

### Table 2: eclaim_drug

```sql
CREATE TABLE eclaim_drug (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id),
    file_type VARCHAR(10) NOT NULL,  -- 'OP', 'IP', 'ORF'
    row_number INTEGER,

    seq_no INTEGER,
    tran_id VARCHAR(20),
    hn VARCHAR(15),
    an VARCHAR(20),
    admit_date DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),

    drug_seq_no INTEGER,
    drug_code VARCHAR(20),
    tmt_code VARCHAR(10),
    generic_name VARCHAR(200),
    trade_name VARCHAR(100),
    drug_type VARCHAR(10),
    drug_category VARCHAR(50),
    dosage_form VARCHAR(50),

    claim_qty DECIMAL(10,2),
    unit_price DECIMAL(15,2),
    claim_amount DECIMAL(15,2),

    ceiling_price DECIMAL(15,2),
    reimburse_amount DECIMAL(15,2),
    original_reimburse DECIMAL(15,2),

    error_code VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(file_id, tran_id, drug_seq_no)
);
```

### Table 3: eclaim_instrument (IP only)

```sql
CREATE TABLE eclaim_instrument (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id),
    row_number INTEGER,

    seq_no INTEGER,
    tran_id VARCHAR(20),
    hn VARCHAR(15),
    an VARCHAR(20),
    admit_date DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),

    inst_seq_no INTEGER,
    inst_code VARCHAR(10),
    inst_name VARCHAR(200),

    claim_qty INTEGER,
    claim_amount DECIMAL(15,2),

    reimburse_qty INTEGER,
    reimburse_amount DECIMAL(15,2),

    deny_flag VARCHAR(10),
    error_code VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(file_id, tran_id, inst_seq_no)
);
```

### Table 4: eclaim_deny (IP only)

```sql
CREATE TABLE eclaim_deny (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id),
    row_number INTEGER,

    seq_no INTEGER,
    tran_id VARCHAR(20),
    hospital_code VARCHAR(5),
    hn VARCHAR(15),
    an VARCHAR(20),
    admit_date DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),

    fund_code VARCHAR(20),
    claim_code VARCHAR(20),
    expense_category INTEGER,
    claim_amount DECIMAL(15,2),

    deny_code VARCHAR(20),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(file_id, tran_id, claim_code)
);
```

### Table 5: eclaim_zero_paid

```sql
CREATE TABLE eclaim_zero_paid (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id),
    file_type VARCHAR(10) NOT NULL,  -- 'OP', 'IP'
    row_number INTEGER,

    seq_no INTEGER,
    tran_id VARCHAR(20),
    hospital_code VARCHAR(5),
    hn VARCHAR(15),
    an VARCHAR(20),
    admit_date DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),

    fund_code VARCHAR(20),
    claim_code VARCHAR(20),
    tmt_code VARCHAR(10),
    expense_category INTEGER,

    claim_qty INTEGER,
    paid_qty INTEGER,
    paid_amount DECIMAL(15,2),

    reason VARCHAR(200),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    UNIQUE(file_id, tran_id, claim_code)
);
```

---

## Excel Column Name Notes

**IMPORTANT:** Excel column names contain special characters that must be matched exactly:

1. Newline characters (`\n`) in column names:
   - `'รหัสยา รพ.\n(Workig Code)'` - note typo "Workig"
   - `'จำนวน \n(1)'` - space before newline
   - `'ราคาเพดาน \n(4)'`
   - `'รวมชดเชย \n(5) = (1)*(4)'`

2. Spaces in column names:
   - `'ชื่อ - สกุล'` - spaces around dash

3. Multi-row headers:
   - Row 3: Main category headers
   - Row 4: Sub-category headers (for drug columns)
   - Row 5: Detail headers (for instrument columns)

4. Data rows start at:
   - Row 6 (0-indexed) for most sheets
   - Skip rows 0-5 when importing data
