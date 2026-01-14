# My Hospital Analytics - Technical Specification

## Overview
Transform the Benchmark page from a regional overview to a hospital-centric analytics dashboard where users analyze their own hospital's SMT Budget data and optionally compare with other hospitals.

## User Flow
```
1. Select MY hospital (required)
2. View MY hospital analytics (auto-load)
3. Compare with regional average (auto)
4. Add other hospitals to compare (optional)
```

## Data Source
- Primary: `smt_budget_transfers` table
- Metadata: `health_offices` table (hospital names, levels, provinces, health regions)

---

## API Endpoints

### 1. GET /api/benchmark/my-hospital
Get detailed analytics for a single hospital.

**Parameters:**
- `vendor_id` (required): Hospital vendor ID (5 or 10 digits)
- `fiscal_year` (required): Thai Buddhist Era year (e.g., 2569)

**Response:**
```json
{
  "success": true,
  "hospital": {
    "vendor_no": "0000010670",
    "name": "โรงพยาบาลขอนแก่น",
    "level": "A",
    "province": "ขอนแก่น",
    "health_region": 7
  },
  "summary": {
    "total_amount": 2190000000,
    "wait_amount": 186000000,
    "debt_amount": 70000000,
    "bond_amount": 0,
    "wait_ratio": 8.5,
    "debt_ratio": 3.2,
    "record_count": 1693,
    "growth_yoy": 18.4
  },
  "fund_breakdown": [
    {
      "fund_name": "กองทุนผู้ป่วยใน",
      "fund_group": 1,
      "amount": 980000000,
      "percentage": 44.7,
      "vs_region_avg": 8.0
    },
    ...
  ],
  "monthly_trend": [
    {
      "month": "2025-10",
      "total_amount": 180000000,
      "wait_amount": 15000000,
      "debt_amount": 5000000
    },
    ...
  ],
  "risk_score": {
    "score": 25,
    "level": "low",
    "indicators": [
      {"name": "Wait Ratio", "value": 8.5, "threshold": 10, "status": "pass"},
      {"name": "Debt Ratio", "value": 3.2, "threshold": 5, "status": "pass"},
      {"name": "Growth YoY", "value": 18.4, "threshold": 0, "status": "pass"}
    ]
  },
  "ranking": {
    "national": {"rank": 18, "total": 125, "percentile": 85},
    "regional": {"rank": 2, "total": 15, "percentile": 93}
  }
}
```

### 2. GET /api/benchmark/region-average
Get regional average for comparison.

**Parameters:**
- `health_region` (required): Health region number (1-13)
- `fiscal_year` (required): Thai Buddhist Era year

**Response:**
```json
{
  "success": true,
  "region": 7,
  "hospital_count": 15,
  "averages": {
    "total_amount": 1820000000,
    "wait_ratio": 8.6,
    "debt_ratio": 4.6
  },
  "fund_breakdown": [
    {
      "fund_name": "กองทุนผู้ป่วยใน",
      "avg_amount": 820000000,
      "avg_percentage": 45.0
    },
    ...
  ],
  "monthly_trend": [...]
}
```

### 3. GET /api/benchmark/compare
Get comparison data for multiple hospitals.

**Parameters:**
- `vendor_ids` (required): Comma-separated vendor IDs
- `fiscal_year` (required): Thai Buddhist Era year

**Response:**
```json
{
  "success": true,
  "hospitals": [
    {
      "vendor_no": "0000010670",
      "name": "โรงพยาบาลขอนแก่น",
      "total_amount": 2190000000,
      "wait_ratio": 8.5,
      "debt_ratio": 3.2,
      "growth_yoy": 18.4,
      "fund_breakdown": [...],
      "monthly_trend": [...]
    },
    ...
  ],
  "region_average": {...}
}
```

---

## UI Components

### 1. Hospital Selector
- Search by name or code
- Auto-complete from health_offices
- Save last selected hospital in localStorage

### 2. Summary Cards
- Total Revenue (with YoY growth badge)
- Wait Amount (with percentage)
- Debt Amount (with percentage)
- National Ranking (with percentile)

### 3. Fund Breakdown Table
- Fund name, amount, percentage
- Comparison bar vs regional average
- Color coding: green (above avg), red (below avg)

### 4. Monthly Trend Chart
- Line chart with Chart.js
- Multiple lines: current year, previous year, regional average
- Toggle between different metrics (total, wait, debt)

### 5. Risk Assessment
- Score gauge (0-100)
- Color: green (<40), yellow (40-70), red (>70)
- Indicator table with pass/fail status

### 6. AI Insights
- Auto-generated insights based on data
- Strengths (green bullet points)
- Improvements needed (orange bullet points)
- Opportunities (blue bullet points)

### 7. Comparison Section (Optional)
- Quick add buttons: same province, same region, same level
- Manual search and select
- Comparison table with all metrics
- Multi-line trend chart

---

## Risk Score Calculation

```
Risk Score = (Wait Weight * Wait Score) + (Debt Weight * Debt Score) + (Growth Weight * Growth Score)

Where:
- Wait Score = min(100, (wait_ratio / 20) * 100)  // 20% = max risk
- Debt Score = min(100, (debt_ratio / 15) * 100)  // 15% = max risk
- Growth Score = max(0, (1 - growth_yoy / 50) * 100)  // negative growth = high risk

Weights:
- Wait: 30%
- Debt: 40%
- Growth: 30%

Risk Level:
- 0-40: Low (green)
- 41-70: Medium (yellow)
- 71-100: High (red)
```

---

## Implementation Order

1. API: /api/benchmark/my-hospital
2. API: /api/benchmark/region-average
3. UI: Hospital selector + Summary cards
4. UI: Fund breakdown table
5. UI: Monthly trend chart
6. UI: Risk assessment
7. API: /api/benchmark/compare
8. UI: Comparison section
9. AI Insights (static rules-based)

---

## Files to Modify

1. `app.py` - Add new API endpoints
2. `templates/benchmark.html` - Redesign UI
3. `static/js/benchmark.js` - New JavaScript (optional, can be inline)

---

## Database Queries

### Hospital Summary
```sql
SELECT
    vendor_no,
    COUNT(*) as records,
    SUM(total_amount) as total_amount,
    SUM(wait_amount) as wait_amount,
    SUM(debt_amount) as debt_amount,
    SUM(bond_amount) as bond_amount
FROM smt_budget_transfers
WHERE vendor_no = %s
  AND run_date >= %s AND run_date <= %s
GROUP BY vendor_no
```

### Fund Breakdown
```sql
SELECT
    fund_name,
    fund_group,
    fund_group_desc,
    SUM(total_amount) as amount,
    COUNT(*) as records
FROM smt_budget_transfers
WHERE vendor_no = %s
  AND run_date >= %s AND run_date <= %s
GROUP BY fund_name, fund_group, fund_group_desc
ORDER BY amount DESC
```

### Monthly Trend
```sql
SELECT
    TO_CHAR(run_date, 'YYYY-MM') as month,
    SUM(total_amount) as total_amount,
    SUM(wait_amount) as wait_amount,
    SUM(debt_amount) as debt_amount
FROM smt_budget_transfers
WHERE vendor_no = %s
  AND run_date >= %s AND run_date <= %s
GROUP BY TO_CHAR(run_date, 'YYYY-MM')
ORDER BY month
```

### Regional Average
```sql
WITH hospital_totals AS (
    SELECT
        s.vendor_no,
        SUM(s.total_amount) as total_amount,
        SUM(s.wait_amount) as wait_amount,
        SUM(s.debt_amount) as debt_amount
    FROM smt_budget_transfers s
    JOIN health_offices h ON h.hcode5 = LTRIM(s.vendor_no, '0')
    WHERE h.health_region = %s
      AND s.run_date >= %s AND s.run_date <= %s
    GROUP BY s.vendor_no
)
SELECT
    COUNT(*) as hospital_count,
    AVG(total_amount) as avg_total,
    AVG(wait_amount) as avg_wait,
    AVG(debt_amount) as avg_debt
FROM hospital_totals
```
