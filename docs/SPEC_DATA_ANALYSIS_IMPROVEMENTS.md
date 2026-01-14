# Data Analysis Improvements Specification

## Overview

ปรับปรุงหน้า Data Analysis ให้วิเคราะห์ข้อมูลได้ละเอียดขึ้น โดยใช้ประโยชน์จากโครงสร้างฐานข้อมูลที่มีอยู่

## Current State

หน้า Data Analysis มี 4 tabs:
1. **Summary** - สรุปยอด REP/Statement/SMT
2. **Reconciliation** - เทียบ REP vs Statement
3. **Search Transaction** - ค้นหา TRAN_ID/HN/AN/PID
4. **File Viewer** - ดูข้อมูลในไฟล์

## Proposed Improvements

### 1. Claims Detail Tab (ใหม่)

**Purpose:** ดูรายละเอียด claims แบบละเอียด พร้อม filters หลายมิติ

**Features:**
- Filter ตาม: scheme (UCS/OFC/SSS/LGO), ptype (OP/IP), dateadm range
- Filter ตาม: error_code, reconcile_status
- แสดงข้อมูล: tran_id, hn, name, dateadm, claim_net, reimb_nhso, error_code
- Pagination และ Export CSV

**API Endpoint:** `/api/analysis/claims`

**Database Query:**
```sql
SELECT tran_id, hn, name, ptype, main_inscl as scheme, dateadm,
       claim_net, reimb_nhso, error_code, reconcile_status
FROM claim_rep_opip_nhso_item
WHERE 1=1
  AND (main_inscl = :scheme OR :scheme IS NULL)
  AND (ptype = :ptype OR :ptype IS NULL)
  AND (dateadm >= :date_from OR :date_from IS NULL)
  AND (dateadm <= :date_to OR :date_to IS NULL)
ORDER BY dateadm DESC
LIMIT :limit OFFSET :offset
```

---

### 2. Financial Breakdown Tab (ใหม่)

**Purpose:** วิเคราะห์ยอดเงินแยกตามประเภทบริการ

**Features:**
- แสดง breakdown ตาม service category:
  - High Cost Care (iphc + ophc)
  - Emergency (ae_opae + ae_ipnb + ae_ipuc + ...)
  - DMIS (dmis_* columns)
  - Prosthetics (inst + opinst)
  - Drug costs
- Filter: scheme, ptype, date range
- Chart visualization (bar/pie)

**API Endpoint:** `/api/analysis/financial-breakdown`

**Database Query:**
```sql
SELECT
    main_inscl as scheme,
    ptype,
    COUNT(*) as total_cases,
    SUM(COALESCE(iphc, 0) + COALESCE(ophc, 0)) as high_cost_care,
    SUM(COALESCE(ae_opae, 0) + COALESCE(ae_ipnb, 0) + COALESCE(ae_ipuc, 0) +
        COALESCE(ae_ip3sss, 0) + COALESCE(ae_ip7sss, 0)) as emergency,
    SUM(COALESCE(inst, 0) + COALESCE(opinst, 0)) as prosthetics,
    SUM(COALESCE(drug, 0)) as drug_costs,
    SUM(COALESCE(dmis_stroke_drug, 0) + COALESCE(dmis_pp, 0) + COALESCE(dmis_dm, 0)) as dmis,
    SUM(claim_net) as total_claimed,
    SUM(reimb_nhso) as total_reimbursed
FROM claim_rep_opip_nhso_item
WHERE dateadm >= :date_from AND dateadm <= :date_to
GROUP BY main_inscl, ptype
```

---

### 3. Error/Denial Dashboard Tab (ใหม่)

**Purpose:** วิเคราะห์ปัญหาการเบิก (errors & denials)

**Features:**
- Top 10 Error codes พร้อมจำนวนและยอดเงิน
- Denial breakdown: deny_hc, deny_ae, deny_inst, deny_dmis
- Trend over time (monthly)
- Filter: scheme, ptype, date range

**API Endpoint:** `/api/analysis/errors`

**Database Queries:**

Top Error Codes:
```sql
SELECT error_code, COUNT(*) as count, SUM(claim_net) as affected_amount
FROM claim_rep_opip_nhso_item
WHERE error_code IS NOT NULL AND error_code != '-'
  AND dateadm >= :date_from AND dateadm <= :date_to
GROUP BY error_code
ORDER BY count DESC
LIMIT 10
```

Denial Summary:
```sql
SELECT
    SUM(CASE WHEN deny_hc IS NOT NULL AND deny_hc != '' THEN 1 ELSE 0 END) as deny_hc_count,
    SUM(CASE WHEN deny_ae IS NOT NULL AND deny_ae != '' THEN 1 ELSE 0 END) as deny_ae_count,
    SUM(CASE WHEN deny_inst IS NOT NULL AND deny_inst != '' THEN 1 ELSE 0 END) as deny_inst_count,
    SUM(CASE WHEN deny_dmis IS NOT NULL AND deny_dmis != '' THEN 1 ELSE 0 END) as deny_dmis_count
FROM claim_rep_opip_nhso_item
WHERE dateadm >= :date_from AND dateadm <= :date_to
```

---

### 4. Facility Analysis Tab (ใหม่)

**Purpose:** วิเคราะห์ข้อมูลตามสถานพยาบาล

**Features:**
- Summary by hcode (treating facility)
- Compare hmain vs hcode (registered vs treating)
- Filter by province (prov1, prov2), region (rg1, rg2)
- Join with health_offices for facility names

**API Endpoint:** `/api/analysis/facilities`

**Database Query:**
```sql
SELECT
    c.hcode,
    h.name as facility_name,
    h.province,
    COUNT(*) as total_cases,
    SUM(c.claim_net) as total_claimed,
    SUM(c.reimb_nhso) as total_reimbursed,
    SUM(CASE WHEN c.error_code IS NOT NULL AND c.error_code != '-' THEN 1 ELSE 0 END) as error_count
FROM claim_rep_opip_nhso_item c
LEFT JOIN health_offices h ON c.hcode = h.hcode5
WHERE c.dateadm >= :date_from AND c.dateadm <= :date_to
GROUP BY c.hcode, h.name, h.province
ORDER BY total_cases DESC
```

---

### 5. HIS Reconciliation Dashboard (ปรับปรุง)

**Purpose:** ติดตามสถานะการ match กับระบบ HIS

**Features:**
- สถิติ: matched, unmatched, amount diff
- Filter: reconcile_status (pending/matched/mismatched/manual)
- แสดง records ที่มี his_amount_diff > threshold
- Bulk update reconcile_status

**API Endpoint:** `/api/analysis/his-reconciliation`

**Database Query:**
```sql
SELECT
    reconcile_status,
    COUNT(*) as count,
    SUM(claim_net) as total_amount,
    SUM(CASE WHEN his_amount_diff != 0 THEN 1 ELSE 0 END) as diff_count,
    SUM(ABS(his_amount_diff)) as total_diff
FROM claim_rep_opip_nhso_item
GROUP BY reconcile_status
```

---

## Implementation Priority

1. **Phase 1:** Claims Detail Tab + Financial Breakdown
2. **Phase 2:** Error/Denial Dashboard
3. **Phase 3:** Facility Analysis + HIS Reconciliation improvements

## UI Components

### Shared Filter Bar
```html
<div class="filter-bar">
  <select id="filter-scheme">UCS/OFC/SSS/LGO</select>
  <select id="filter-ptype">OP/IP</select>
  <input type="date" id="filter-date-from">
  <input type="date" id="filter-date-to">
  <button onclick="loadData()">Apply</button>
</div>
```

### Summary Cards
- Total Cases
- Total Claimed
- Total Reimbursed
- Error Rate %

### Data Table with Pagination
- Sortable columns
- Export CSV button
- Row click for detail modal

---

## File Changes Required

### Backend (app.py)
- Add new API endpoints:
  - `/api/analysis/claims`
  - `/api/analysis/financial-breakdown`
  - `/api/analysis/errors`
  - `/api/analysis/facilities`
  - `/api/analysis/his-reconciliation`

### Frontend
- `templates/data_analysis.html` - Add new tabs
- `static/js/data_analysis.js` - Add tab switching and data loading functions

### Database
- Migration `002_add_scheme_to_orf.sql` - เพิ่ม scheme column ให้ ORF (เสร็จแล้ว)
