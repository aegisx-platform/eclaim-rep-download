# E-Claim Data Analytics Guide

วิเคราะห์ข้อมูล E-Claim ที่โรงพยาบาลสามารถนำมาใช้งานได้

---

## 📊 ข้อมูลที่มีในระบบ

### 1. **OP/IP Claims** (`claim_rep_opip_nhso_item`)

**ข้อมูลผู้ป่วย:**
- HN, AN, PID
- ชื่อ-สกุล
- ประเภทผู้ป่วย (OP/IP)
- วันเข้า-จำหน่าย

**ข้อมูลทางการเงิน:**
- เรียกเก็บ (claim_drg, claim_central_reimb)
- ชดเชย (reimb_nhso, reimb_amt)
- จ่ายเอง (paid)
- แยกตามหมวด: DRG, ยา, HC, AE, DMIS, etc.

**ข้อมูลสิทธิ:**
- สิทธิหลัก/ย่อย (main_inscl, sub_inscl)
- กองทุน (main_fund, sub_fund)
- การมีสิทธิ/ใช้สิทธิ (chk_right, chk_use_right)

**ข้อมูลโรงพยาบาล:**
- HCODE, HMAIN (รพ.หลัก)
- HREF (รพ.ส่งต่อ)
- จังหวัด (PROV1, PROV2)

**ข้อมูลการรักษา:**
- DRG code & RW
- CA_TYPE
- Error code (ถ้ามีปัญหา)

### 2. **ORF - Refer Out** (`claim_rep_orf_nhso_item`)

**ข้อมูลส่งต่อ:**
- Refer number
- โรงพยาบาลต้นทาง-ปลายทาง (HREF, HMAIN)
- วันที่ส่งต่อ

**ข้อมูลทางการเงิน:**
- เรียกเก็บค่าส่งต่อ (claim_amt)
- ชดเชยส่งต่อ (reimb_total)
- แยกตามประเภทบริการ: HC01-08, AE, DMIS, etc.

### 3. **Import Tracking** (`eclaim_imported_files`)

- สถานะการ import (success/failed)
- จำนวน records ที่ import
- Error messages

---

## 💡 Dashboard Ideas - แนะนำ Dashboard ที่ควรมี

### 🎯 **Level 1: Dashboard พื้นฐาน (Must Have)**

#### 1. **Financial Overview - ภาพรวมการเงิน**

**KPIs:**
- 💰 ยอดเรียกเก็บรวม (Total Claims)
- 💵 ยอดชดเชยรวม (Total Reimbursement)
- 📊 อัตราชดเชย (Reimbursement Rate %)
- ⚠️ ยอดที่มีปัญหา (Claims with Errors)

**Charts:**
- Line chart: แนวโน้มรายเดือน (เรียกเก็บ vs ชดเชย)
- Bar chart: เปรียบเทียบ OP vs IP
- Pie chart: สัดส่วนแยกตามกองทุน

**SQL Example:**
```sql
SELECT
    DATE_TRUNC('month', dateadm) as month,
    SUM(claim_drg + claim_central_reimb) as total_claim,
    SUM(reimb_amt) as total_reimb,
    ROUND(SUM(reimb_amt) / NULLIF(SUM(claim_drg + claim_central_reimb), 0) * 100, 2) as reimb_rate
FROM claim_rep_opip_nhso_item
GROUP BY month
ORDER BY month DESC;
```

---

#### 2. **Patient Volume - สถิติผู้ป่วย**

**KPIs:**
- 👥 จำนวนผู้ป่วยทั้งหมด
- 🏥 แยก OP / IP
- 📈 Growth rate เทียบเดือนก่อน

**Charts:**
- Line chart: Trend ผู้ป่วยรายเดือน
- Bar chart: Top 10 DRG
- Heatmap: ผู้ป่วยแยกตามวันในสัปดาห์

**SQL Example:**
```sql
SELECT
    DATE_TRUNC('month', dateadm) as month,
    ptype,
    COUNT(DISTINCT pid) as patient_count,
    COUNT(*) as visit_count
FROM claim_rep_opip_nhso_item
GROUP BY month, ptype
ORDER BY month DESC;
```

---

#### 3. **Error Monitoring - ติดตาม Error**

**KPIs:**
- ⚠️ จำนวน Claims ที่มี Error
- 📊 Error Rate (%)
- 🔝 Top Error Codes

**Charts:**
- Table: Error codes พร้อมจำนวน
- Trend: Error rate รายเดือน
- Bar: Top 10 Error types

**SQL Example:**
```sql
SELECT
    error_code,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage,
    SUM(claim_drg) as total_claim_amount
FROM claim_rep_opip_nhso_item
WHERE error_code IS NOT NULL AND error_code != ''
GROUP BY error_code
ORDER BY count DESC
LIMIT 20;
```

---

### 🎯 **Level 2: Dashboard ขั้นสูง (Should Have)**

#### 4. **DRG Analysis - วิเคราะห์ DRG**

**Insights:**
- 💰 Top 10 DRG ที่สร้างรายได้สูงสุด
- 📊 Average RW by DRG
- 🔄 DRG Distribution

**Charts:**
- Bar chart: Top Revenue DRGs
- Scatter plot: RW vs Count
- Box plot: RW distribution

**SQL Example:**
```sql
SELECT
    drg,
    COUNT(*) as case_count,
    AVG(rw) as avg_rw,
    SUM(claim_drg) as total_claim,
    SUM(reimb_amt) as total_reimb
FROM claim_rep_opip_nhso_item
WHERE drg IS NOT NULL
GROUP BY drg
ORDER BY total_claim DESC
LIMIT 20;
```

---

#### 5. **Rights & Funds Analysis - วิเคราะห์สิทธิ**

**Insights:**
- 📋 แยกตามสิทธิหลัก/ย่อย
- 💰 รายได้แยกตามกองทุน
- 📊 จำนวนผู้ป่วยแต่ละสิทธิ

**Charts:**
- Pie: สัดส่วนสิทธิ
- Stacked bar: รายได้แต่ละกองทุน
- Table: รายละเอียดแต่ละสิทธิ

**SQL Example:**
```sql
SELECT
    main_inscl,
    sub_inscl,
    main_fund,
    COUNT(DISTINCT pid) as patient_count,
    COUNT(*) as visit_count,
    SUM(reimb_amt) as total_reimb
FROM claim_rep_opip_nhso_item
GROUP BY main_inscl, sub_inscl, main_fund
ORDER BY total_reimb DESC;
```

---

#### 6. **Refer Analysis - วิเคราะห์ส่งต่อ (ORF)**

**Insights:**
- 🏥 Top รพ.ที่ส่งต่อไป/รับส่งต่อ
- 💰 ต้นทุนส่งต่อ
- 📊 Refer rate

**Charts:**
- Sankey diagram: Flow ของการส่งต่อ
- Bar: Top destination hospitals
- Line: Refer trend

**SQL Example:**
```sql
SELECT
    href as destination_hospital,
    COUNT(*) as refer_count,
    SUM(claim_amt) as total_claim,
    SUM(reimb_total) as total_reimb
FROM claim_rep_orf_nhso_item
GROUP BY href
ORDER BY refer_count DESC
LIMIT 20;
```

---

### 🎯 **Level 3: Dashboard Advanced (Nice to Have)**

#### 7. **Geographic Analysis - แผนที่จังหวัด**

**Insights:**
- 🗺️ กระจายผู้ป่วยตามจังหวัด
- 🏠 HMAIN distribution
- 📍 Refer patterns by province

**Visualization:**
- Choropleth map: ผู้ป่วยแยกจังหวัด
- Network graph: Refer network

---

#### 8. **Service Type Breakdown - แยกตามประเภทบริการ**

**Insights:**
- 💊 ยา (drug)
- 🏥 HC (health center)
- 🚑 AE (accident & emergency)
- 🔬 DMIS (special procedures)

**Charts:**
- Waterfall chart: Revenue breakdown
- Stacked area: Trend by service type

**SQL Example:**
```sql
SELECT
    DATE_TRUNC('month', dateadm) as month,
    SUM(drug) as drug_amt,
    SUM(ophc + iphc) as hc_amt,
    SUM(ae_opae + ae_ipnb) as ae_amt,
    SUM(dmis_dm + dmis_dmidml) as dmis_amt
FROM claim_rep_opip_nhso_item
GROUP BY month
ORDER BY month DESC;
```

---

#### 9. **Reconciliation Status - สถานะ HIS Reconcile**

**Insights:**
- ✅ Matched vs ❌ Unmatched
- 💰 Amount differences
- 📊 Reconcile success rate

**SQL Example:**
```sql
SELECT
    reconcile_status,
    COUNT(*) as count,
    SUM(CASE WHEN his_matched THEN 1 ELSE 0 END) as matched_count,
    AVG(his_amount_diff) as avg_diff
FROM claim_rep_opip_nhso_item
GROUP BY reconcile_status;
```

---

#### 10. **Import Quality - คุณภาพการ Import**

**Insights:**
- 📁 Files imported successfully
- ⚠️ Failed imports
- 📊 Import performance

**SQL Example:**
```sql
SELECT
    file_type,
    status,
    COUNT(*) as file_count,
    SUM(total_records) as total_records,
    SUM(imported_records) as imported_records,
    ROUND(AVG(imported_records::float / NULLIF(total_records, 0) * 100), 2) as success_rate
FROM eclaim_imported_files
GROUP BY file_type, status
ORDER BY file_type, status;
```

---

## 🛠️ แนะนำเครื่องมือสำหรับทำ Dashboard

### **Option 1: Metabase (แนะนำ - ฟรี & ง่าย)**

**ข้อดี:**
- ✅ Open source & ฟรี
- ✅ ติดตั้งง่าย (Docker)
- ✅ UI สวย ใช้งานง่าย
- ✅ รองรับ PostgreSQL/MySQL
- ✅ Auto-refresh dashboards
- ✅ Share dashboard ได้

**ติดตั้ง:**
```bash
docker run -d -p 3000:3000 \
  -e MB_DB_TYPE=postgres \
  -e MB_DB_DBNAME=metabase \
  -e MB_DB_PORT=5432 \
  -e MB_DB_USER=metabase \
  -e MB_DB_PASS=password \
  -e MB_DB_HOST=db \
  --name metabase metabase/metabase
```

---

### **Option 2: Grafana (Advanced)**

**ข้อดี:**
- ✅ Powerful visualization
- ✅ Real-time monitoring
- ✅ Alert capabilities
- ✅ Plugin ecosystem

**ติดตั้ง:**
```bash
docker run -d -p 3000:3000 \
  --name=grafana \
  grafana/grafana
```

---

### **Option 3: Superset (Apache)**

**ข้อดี:**
- ✅ Feature-rich
- ✅ Advanced SQL editor
- ✅ Complex visualizations

---

### **Option 4: Custom Dashboard (Flask + Chart.js)**

เพิ่มใน Flask app ปัจจุบัน:
- ✅ Integrated กับ app
- ✅ Control เต็มที่
- ✅ Lightweight

---

## 📈 Quick Start Dashboard Template

### **Minimal Dashboard (3 หน้า)**

#### **1. Home - Overview**
- Total Claims YTD
- Total Reimbursement YTD
- Error Rate
- Recent imports

#### **2. Financial - การเงิน**
- Monthly trend
- OP vs IP comparison
- Top DRGs
- Revenue by fund

#### **3. Operations - ปฏิบัติการ**
- Error summary
- Import status
- Refer statistics

---

## 🎨 Dashboard Design Tips

1. **Keep it Simple** - เริ่มจาก KPIs สำคัญก่อน
2. **Use Colors Wisely** - สีแดง = warning, เขียว = good, เทา = neutral
3. **Show Trends** - ไม่ใช่แค่ตัวเลข แต่แสดง trend ด้วย
4. **Make it Actionable** - Dashboard ต้องช่วยตัดสินใจได้
5. **Auto-refresh** - อัพเดทอัตโนมัติทุก 5-15 นาที
6. **Mobile Responsive** - ดูบนมือถือได้

---

## 📊 Priority Recommendations

**สำหรับโรงพยาบาล ควรเริ่มจาก:**

1. ✅ **Financial Overview** - ต้องมี เพราะเกี่ยวกับเงิน
2. ✅ **Error Monitoring** - ต้องแก้ error ให้ได้เงิน
3. ✅ **Patient Volume** - ดู capacity และ trend
4. ⭐ **DRG Analysis** - เพิ่มประสิทธิภาพการเงิน
5. ⭐ **Refer Analysis** - ควบคุมต้นทุนส่งต่อ

---

## 🚀 Next Steps

1. เลือกเครื่องมือ (แนะนำ Metabase)
2. Setup Metabase container
3. Connect to database
4. สร้าง 3 dashboards พื้นฐาน
5. แชร์ให้ผู้บริหารดู
6. รับ feedback และปรับปรุง

---

**ต้องการความช่วยเหลือเพิ่มเติม?**
- ติดตั้ง Metabase
- เขียน SQL queries
- ออกแบบ dashboard
- Integrate เข้า Flask app

บอกได้เลยครับ! 🎯
