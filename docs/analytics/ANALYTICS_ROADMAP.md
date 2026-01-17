# Analytics Roadmap - Hospital Decision Support

## Executive Summary

จากการวิเคราะห์ความต้องการของโรงพยาบาลในการประเมินประสิทธิภาพการเบิกเคลม พบว่าระบบปัจจุบันมี **Foundation ที่ดี** แต่ยังขาด **Advanced Analytics** ที่จะช่วยในการตัดสินใจเชิงกลยุทธ์

---

## Current State Assessment

### สิ่งที่มีแล้ว (Implemented)

| Feature | Status | Value |
|---------|--------|-------|
| Basic Dashboard | ✅ | Overview ภาพรวม |
| Monthly Trends | ✅ | ดู pattern |
| Fund Analysis | ✅ | วิเคราะห์กองทุน |
| DRG Analysis | ✅ | ดู case mix |
| Drug/Instrument | ✅ | Cost analysis |
| Denial Tracking | ✅ | ติดตาม denial |
| REP vs SMT Recon | ✅ | Reconciliation |

### สิ่งที่ขาด (Missing) - Priority Order

#### 1. 🔴 Critical - ต้องมีเพื่อการตัดสินใจ

| Feature | Why Needed | Impact |
|---------|-----------|--------|
| **Claim-level Drill-down** | ต้องดูรายละเอียดแต่ละ claim | ตรวจสอบปัญหาได้เร็ว |
| **Denial Root Cause** | ไม่รู้สาเหตุที่แท้จริง | แก้ปัญหาตรงจุด |
| **Revenue Forecasting** | ไม่มี projection | วางแผนงบไม่ได้ |
| **Alerting System** | ไม่มี notification | พลาดปัญหาสำคัญ |

#### 2. 🟡 Important - เพิ่มประสิทธิภาพ

| Feature | Why Needed | Impact |
|---------|-----------|--------|
| **YoY Comparison** | เปรียบเทียบปีต่อปี | ดู growth/decline |
| **Benchmark** | เทียบค่าเฉลี่ยประเทศ | รู้จุดยืน |
| **Custom Reports** | รายงานตามต้องการ | Flexible analysis |
| **Export to Excel** | ส่งออกข้อมูล | นำไปวิเคราะห์ต่อ |

#### 3. 🟢 Nice to Have - ยกระดับ

| Feature | Why Needed | Impact |
|---------|-----------|--------|
| **Predictive Analytics** | คาดการณ์ denial | Proactive |
| **Anomaly Detection** | ตรวจจับผิดปกติ | Early warning |
| **AI Recommendations** | แนะนำการปรับปรุง | Actionable insights |

---

## Recommended Development Phases

### Phase 1: Core Decision Support (Priority)

**เป้าหมาย:** ให้ข้อมูลที่ actionable ได้ทันที

#### 1.1 Claim Detail Viewer
```
/analytics/claims?filter=denial&date=2025-01
                         ↓
┌─────────────────────────────────────────────┐
│ Denied Claims - January 2025                │
├─────────────────────────────────────────────┤
│ TRAN_ID  │ HN      │ Amount  │ Deny Code   │
│ 12345    │ 001234  │ 5,000   │ E02         │
│ [View Details] [View History] [Flag]       │
└─────────────────────────────────────────────┘
```

**Value:** ตรวจสอบและแก้ไขปัญหาได้ระดับ claim

#### 1.2 Denial Root Cause Analysis
```
Denial Code: E02 (รหัสไม่ตรง)
                  ↓
Root Cause Analysis:
├── ICD-10 Mismatch: 45%
├── Procedure Code Error: 30%
├── DRG Inconsistency: 20%
└── Other: 5%

Recommendation: Review ICD-10 coding process
```

**Value:** รู้สาเหตุ แก้ตรงจุด

#### 1.3 Alert Dashboard
```
┌─────────────────────────────────────────────┐
│ 🔴 ALERTS                                    │
├─────────────────────────────────────────────┤
│ • Denial Rate > 10% this week               │
│ • Fund UC-01 variance > 15%                 │
│ • 50 claims pending > 30 days               │
└─────────────────────────────────────────────┘
```

**Value:** ไม่พลาดปัญหาสำคัญ

### Phase 2: Strategic Analytics

**เป้าหมาย:** วางแผนระยะยาว

#### 2.1 Revenue Projection
```
Revenue Forecast (Next 6 Months)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Based on: Historical trends + Seasonality

Month     │ Projected │ Confidence
Jan 2025  │ ฿5.2M     │ 95%
Feb 2025  │ ฿5.0M     │ 92%
Mar 2025  │ ฿5.5M     │ 88%
...
```

#### 2.2 Comparative Analysis
```
Your Hospital vs Regional Average

Metric          │ You    │ Average │ Status
Reimb Rate      │ 92%    │ 89%     │ ✅ Above
Denial Rate     │ 6%     │ 5%      │ ⚠️ Below
CMI             │ 1.2    │ 1.1     │ ✅ Above
```

### Phase 3: Predictive & AI

**เป้าหมาย:** Proactive decision making

- Predict which claims will be denied
- Suggest optimal coding
- Identify revenue opportunities
- Automate routine analysis

---

## Technical Implementation Plan

### Database Enhancements

```sql
-- New tables needed
CREATE TABLE analytics_alerts (
    id SERIAL PRIMARY KEY,
    alert_type VARCHAR(50),
    severity VARCHAR(20),
    message TEXT,
    metric_value DECIMAL,
    threshold_value DECIMAL,
    created_at TIMESTAMP DEFAULT NOW(),
    acknowledged_at TIMESTAMP,
    acknowledged_by VARCHAR(100)
);

CREATE TABLE analytics_benchmarks (
    id SERIAL PRIMARY KEY,
    metric_name VARCHAR(100),
    region VARCHAR(50),
    fiscal_year INT,
    value DECIMAL,
    source VARCHAR(100),
    updated_at TIMESTAMP
);

-- New views
CREATE VIEW v_denial_root_cause AS
SELECT
    deny_code,
    error_code,
    COUNT(*) as count,
    SUM(claim_amount) as total_amount,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM eclaim_deny
GROUP BY deny_code, error_code
ORDER BY count DESC;
```

### API Enhancements

```python
# New endpoints needed

@app.route('/api/analytics/claims')
def api_claims_detail():
    """Paginated claim-level details with filters"""
    pass

@app.route('/api/analytics/denial-root-cause')
def api_denial_root_cause():
    """Denial root cause analysis"""
    pass

@app.route('/api/analytics/alerts')
def api_alerts():
    """Active alerts and warnings"""
    pass

@app.route('/api/analytics/forecast')
def api_revenue_forecast():
    """Revenue projection"""
    pass

@app.route('/api/analytics/benchmark')
def api_benchmark():
    """Comparison with benchmarks"""
    pass

@app.route('/api/export/<report_type>')
def api_export():
    """Export reports to Excel/CSV"""
    pass
```

---

## Success Metrics

### For Phase 1

| Metric | Current | Target |
|--------|---------|--------|
| Time to identify denial cause | Days | Minutes |
| Claims reviewed per day | 50 | 200 |
| Alert response time | N/A | < 24 hours |

### For Phase 2

| Metric | Current | Target |
|--------|---------|--------|
| Forecast accuracy | N/A | > 85% |
| Report generation time | Manual | Automated |
| Decision cycle time | Weekly | Daily |

---

## Estimated Effort

| Phase | Features | Effort | Timeline |
|-------|----------|--------|----------|
| Phase 1 | Core Decision Support | 2-3 weeks | Month 1 |
| Phase 2 | Strategic Analytics | 3-4 weeks | Month 2-3 |
| Phase 3 | Predictive/AI | 4-6 weeks | Month 4-6 |

---

## Recommended First Step

**เริ่มจาก Phase 1.1: Claim Detail Viewer**

เหตุผล:
1. ใช้ data ที่มีอยู่แล้ว
2. Value สูง - ช่วยแก้ปัญหาทันที
3. Foundation สำหรับ feature อื่น
4. Effort ต่ำ - ทำได้ใน 1 สัปดาห์

---

*Document Version: 1.0.0*
*Created: 2026-01-11*
*Author: Claude Opus 4.5 Analysis*
