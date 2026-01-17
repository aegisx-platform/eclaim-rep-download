# Business Model - E-Claim REP Download System

> On-Premise Healthcare Data Management Solution

## Table of Contents

1. [Product Overview](#product-overview)
2. [Target Market](#target-market)
3. [Revenue Streams](#revenue-streams)
4. [Pricing Strategy](#pricing-strategy)
5. [Go-to-Market Strategy](#go-to-market-strategy)
6. [Growth Roadmap](#growth-roadmap)

---

## Product Overview

### Value Proposition

**E-Claim REP Download System** เป็นระบบจัดการข้อมูล E-Claim จาก สปสช. แบบ On-Premise ที่ออกแบบมาเพื่อโรงพยาบาลในประเทศไทย

**ปัญหาที่แก้ไข:**
- ⏰ ดาวน์โหลดข้อมูลจาก NHSO ด้วยตนเองทุกเดือน (Manual download)
- 📊 นำเข้าข้อมูลเข้าฐานข้อมูลโรงพยาบาลช้าและมีข้อผิดพลาด
- 💾 ไม่มีระบบติดตามและวิเคราะห์ข้อมูลการเบิกจ่าย
- 🔒 ความกังวลเรื่องความปลอดภัยของข้อมูลผู้ป่วย (PDPA)

**โซลูชันที่นำเสนอ:**
- ✅ ดาวน์โหลดอัตโนมัติตามกำหนดเวลา (Scheduled downloads)
- ✅ นำเข้าข้อมูลอัตโนมัติพร้อม data validation
- ✅ Dashboard วิเคราะห์ข้อมูลแบบ real-time
- ✅ On-Premise deployment = ข้อมูลไม่ออกจากโรงพยาบาล
- ✅ รองรับทั้ง PostgreSQL และ MySQL
- ✅ REST API สำหรับ integration กับระบบ HIS

### Key Features

| Feature | Description | Business Value |
|---------|-------------|----------------|
| **Automated Download** | ดาวน์โหลด REP/STM/SMT files อัตโนมัติ | ประหยัดเวลา 4-8 ชม/เดือน |
| **Smart Import** | นำเข้าข้อมูลพร้อม deduplication | ลด error rate 95% |
| **Analytics Dashboard** | วิเคราะห์การเบิกจ่าย, denial rate, trends | เพิ่ม revenue recovery 10-15% |
| **Multi-Database** | รองรับ PostgreSQL & MySQL | ไม่ต้องเปลี่ยน infrastructure |
| **HIS Integration** | REST API สำหรับเชื่อมต่อระบบ HIS | Seamless data flow |
| **PDPA Compliant** | On-premise, encrypted, audit logs | ปลอดภัยตามกฎหมาย |
| **Docker Deployment** | One-click installation | ติดตั้งภายใน 30 นาที |

---

## Target Market

### Primary Target Segments

#### 1. โรงพยาบาลชุมชน (Community Hospitals)
- **ขนาด:** 30-120 เตียง
- **จำนวนในไทย:** ~800 แห่ง
- **Pain Points:**
  - มีเจ้าหน้าที่ IT จำกัด (1-3 คน)
  - ต้องการระบบที่ติดตั้งและใช้งานง่าย
  - งบประมาณจำกัด
- **Package:** Starter - Professional
- **Price Range:** 50,000 - 150,000 บาท

#### 2. โรงพยาบาลทั่วไป (General Hospitals)
- **ขนาด:** 120-500 เตียง
- **จำนวนในไทย:** ~120 แห่ง
- **Pain Points:**
  - ข้อมูล E-Claim ปริมาณมาก (10,000+ claims/เดือน)
  - ต้องการ integration กับ HIS
  - ต้องการ custom reports
- **Package:** Professional - Enterprise
- **Price Range:** 150,000 - 350,000 บาท

#### 3. โรงพยาบาลศูนย์/มหาวิทยาลัย (Regional/Teaching Hospitals)
- **ขนาด:** 500+ เตียง
- **จำนวนในไทย:** ~25 แห่ง
- **Pain Points:**
  - ระบบซับซ้อน ต้องการ high availability
  - Multi-department access control
  - Custom development needs
- **Package:** Enterprise + Custom
- **Price Range:** 350,000 - 800,000 บาท

### Secondary Target Segments

#### 4. โรงพยาบาลเอกชน (Private Hospitals)
- **จำนวน:** ~400 แห่ง
- **Characteristics:**
  - งบประมาณยืดหยุ่นกว่า
  - ต้องการ premium support
  - ROI เป็นปัจจัยสำคัญ

#### 5. Medical Billing Companies
- **จำนวน:** ~50 บริษัท
- **Characteristics:**
  - ให้บริการหลายโรงพยาบาล
  - ต้องการ multi-tenant support
  - Volume-based pricing

### Market Size Estimation

```
Total Addressable Market (TAM):
├── รพ.ชุมชน: 800 × 100,000 = 80,000,000 บาท
├── รพ.ทั่วไป: 120 × 250,000 = 30,000,000 บาท
├── รพ.ศูนย์: 25 × 500,000 = 12,500,000 บาท
└── รพ.เอกชน: 400 × 150,000 = 60,000,000 บาท
─────────────────────────────────────────────
Total: ~180 ล้านบาท/ปี (initial license sales)

Recurring Revenue (Year 2+):
└── 20% AMS × 180M = 36 ล้านบาท/ปี
```

**Serviceable Obtainable Market (SOM):**
- Year 1: 5-10% market share = 50-100 ลูกค้า = 9-18 ล้านบาท
- Year 2: 15-20% market share = 150-200 ลูกค้า = 27-36 ล้านบาท
- Year 3: 25-30% market share = 250-300 ลูกค้า = 45-54 ล้านบาท

---

## Revenue Streams

### 1. License Revenue (One-time)

| Package | Target Segment | Price Range | Features Included |
|---------|----------------|-------------|-------------------|
| **Starter** | รพ.ชุมชนขนาดเล็ก (30-60 เตียง) | 50,000-80,000 | Core features, 1 database, 3mo support |
| **Professional** | รพ.ชุมชน-ทั่วไป (60-200 เตียง) | 120,000-180,000 | HIS API, Custom config, 12mo support |
| **Enterprise** | รพ.ทั่วไป-ศูนย์ (200+ เตียง) | 250,000-500,000 | Multi-DB, HA setup, 24mo priority support |
| **Custom** | รพ.ศูนย์/มหาวิทยาลัย | 500,000+ | Full customization, dedicated support |

**License Model:**
- ✅ **Perpetual License** (แนะนำ): ซื้อครั้งเดียว ใช้งานตลอดไป
- ⚠️ **Subscription** (optional): รายปี สำหรับลูกค้าที่ต้องการ budget flexibility

### 2. Implementation Services (One-time)

| Service | Description | Price Range |
|---------|-------------|-------------|
| **Basic Installation** | Docker deployment, training 1 วัน | 15,000-25,000 |
| **Standard Installation** | Installation + config + training 2 วัน | 30,000-50,000 |
| **Enterprise Installation** | Full setup + HIS integration + training 5 วัน | 80,000-150,000 |
| **Data Migration** | Import historical data | 20,000-100,000 |

### 3. Annual Maintenance & Support (Recurring)

| Service Tier | Price (per year) | What's Included |
|--------------|------------------|-----------------|
| **Basic AMS** | 15-20% of license | Software updates, email support (2 business days) |
| **Standard AMS** | 20-25% of license | Updates, phone/email support (1 business day), 4 health checks/year |
| **Premium AMS** | 25-30% of license | Updates, 24/7 support hotline, monthly health checks, priority bug fixes |

**Example Calculation:**
```
Professional Package (150,000 บาท) × 20% AMS = 30,000 บาท/ปี
Enterprise Package (400,000 บาท) × 25% AMS = 100,000 บาท/ปี
```

### 4. Custom Development (Project-based)

| Type | Examples | Price Range |
|------|----------|-------------|
| **Custom Reports** | BI reports, dashboards | 50,000-200,000 |
| **HIS Integration** | Bidirectional sync | 100,000-300,000 |
| **Custom Features** | New modules, workflows | 150,000-500,000+ |

### 5. Training & Consulting (Per Day)

| Service | Rate |
|---------|------|
| On-site Training | 15,000-25,000/วัน |
| Remote Consulting | 10,000-15,000/วัน |
| Workshop (10+ ppl) | 50,000-100,000/วัน |

---

## Pricing Strategy

### Pricing Methodology

**Value-Based Pricing:**
```
ประโยชน์ที่ลูกค้าได้รับ:
├── ประหยัดเวลาเจ้าหน้าที่: 8 ชม/เดือน × 300 บาท/ชม × 12 เดือน = 28,800 บาท/ปี
├── ลด error rate: 50 errors/เดือน × 500 บาท/error × 12 เดือน = 300,000 บาท/ปี
├── เพิ่ม revenue recovery: 5,000,000 รายได้/ปี × 10% = 500,000 บาท/ปี
└── ลดค่าใช้จ่าย IT: Custom development ประมาณ 1,000,000 บาท
──────────────────────────────────────────────────────────────────────
Total Value: ~1,800,000 บาท/ปี

Our Price: 150,000 บาท (8% ของ value) = ROI: 1,100% ในปีแรก
```

### Discount Policy

| Scenario | Discount |
|----------|----------|
| Early Adopter (first 20 customers) | 20-30% off |
| Volume License (5+ hospitals in group) | 15-25% off |
| Government/Education | 10-15% off |
| Referral (from existing customer) | 10% off |
| Annual Prepayment (AMS) | 10% off |
| Multi-year AMS Contract (3+ years) | 15-20% off |

### Payment Terms

**Standard Terms:**
- 40% Down payment (upon contract signing)
- 40% Upon installation completion
- 20% Upon acceptance (30 days after go-live)

**Flexible Terms (for larger deals):**
- 30-30-30-10 (over 6 months)
- Annual AMS: prepay for discount, or quarterly billing

---

## Go-to-Market Strategy

### Phase 1: Foundation (Months 0-6)

**Goal:** Establish credibility, get first 10-20 customers

**Tactics:**
1. **Direct Sales:**
   - Founder-led sales to 5-10 pilot customers
   - Target: รพ.ชุมชนที่มีความสัมพันธ์ดี
   - Offer: 30% early adopter discount

2. **Content Marketing:**
   - Blog posts about E-Claim pain points
   - Case studies from pilot customers
   - YouTube tutorials (Thai language)

3. **Events:**
   - Present at hospital conferences (งาน TAHG, งานโรงพยาบาล)
   - Workshop: "E-Claim Automation Best Practices"

**KPIs:**
- 10-20 paying customers
- 3-5 case studies published
- 80%+ customer satisfaction

### Phase 2: Scale (Months 6-18)

**Goal:** Build partner network, reach 50-100 customers

**Tactics:**
1. **Partner Program Launch:**
   - Recruit 5-10 implementation partners
   - Provide training & certification
   - Joint marketing campaigns

2. **Channel Sales:**
   - Medical IT distributors
   - HIS vendors (as add-on product)
   - Consulting firms serving hospitals

3. **Digital Marketing:**
   - Google Ads (Thai keywords)
   - Facebook/LINE for healthcare IT
   - SEO for hospital administrators

**KPIs:**
- 5-10 active partners
- 50-100 total customers
- 30% revenue from partners

### Phase 3: Expansion (Months 18-36)

**Goal:** Market leadership, 150-300 customers

**Tactics:**
1. **Regional Expansion:**
   - Regional partners in each province cluster
   - Local support teams

2. **Product Expansion:**
   - SaaS version (for privacy-flexible customers)
   - Mobile app for on-the-go monitoring
   - Integration marketplace

3. **Strategic Partnerships:**
   - HIS vendors (bundle deals)
   - Hospital groups (enterprise agreements)
   - Ministry of Public Health (reference customer)

**KPIs:**
- 15-20 active partners
- 150-300 total customers
- 50% revenue from recurring sources (AMS + subscriptions)

---

## Growth Roadmap

### Year 1: Product-Market Fit
```
Q1-Q2: Foundation
├── Launch Starter + Professional packages
├── Direct sales: 10-15 customers
├── Build case studies
└── Revenue: 1.5-2M บาท

Q3-Q4: Early Scaling
├── Launch Partner Program
├── Recruit 3-5 partners
├── Total customers: 30-50
└── Revenue: 3-5M บาท (cumulative 4.5-7M)
```

### Year 2: Scale & Partnership
```
Q1-Q2: Partner Growth
├── 5-10 active partners
├── Launch Enterprise package
├── Total customers: 80-120
└── Revenue: 12-18M บาท

Q3-Q4: Market Expansion
├── 10-15 active partners
├── Regional coverage
├── Total customers: 120-180
└── Revenue: 18-27M บาท (cumulative 30-45M)
```

### Year 3: Market Leadership
```
Q1-Q2: Product Expansion
├── Launch SaaS version
├── Mobile app release
├── Total customers: 200-250
└── Revenue: 25-35M บาท

Q3-Q4: Strategic Partnerships
├── HIS vendor integrations
├── Hospital group deals
├── Total customers: 250-300+
└── Revenue: 35-45M บาท (cumulative 60-80M)
```

### Long-term Vision (Year 4+)

**Product Evolution:**
- AI-powered denial prediction
- Automated claim appeal generation
- National healthcare data analytics platform

**Market Evolution:**
- 30-40% market share in Thailand
- Expand to similar systems in Southeast Asia
- Platform for third-party healthcare apps

**Revenue Goals:**
- Year 4: 80-120M บาท
- Year 5: 120-180M บาท
- Recurring revenue: 60-70% of total

---

## Competitive Advantages

### 1. Technology
- ✅ Modern tech stack (Flask, Docker, PostgreSQL)
- ✅ Open architecture (REST API)
- ✅ Multi-database support
- ✅ One-click deployment

### 2. Domain Expertise
- ✅ Deep understanding of Thai E-Claim process
- ✅ NHSO integration expertise
- ✅ Hospital workflow knowledge
- ✅ PDPA compliance built-in

### 3. Business Model
- ✅ On-premise = data privacy guaranteed
- ✅ Perpetual license = lower TCO
- ✅ Partner-friendly revenue sharing
- ✅ Flexible pricing for all hospital sizes

### 4. Customer Success
- ✅ Fast implementation (30 min to 7 days)
- ✅ Thai language support
- ✅ Local support team
- ✅ Continuous innovation

---

## Risk Management

### Market Risks

| Risk | Mitigation |
|------|------------|
| Government changes E-Claim system | Build flexible parser, quick adaptation capability |
| Competitors with lower prices | Focus on value & ROI, not price war |
| Slow adoption by hospitals | Freemium tier, trial programs, strong case studies |

### Technical Risks

| Risk | Mitigation |
|------|------------|
| NHSO website changes | Automated monitoring, quick updates |
| Database compatibility issues | Extensive testing, multiple DB support |
| Security vulnerabilities | Regular audits, penetration testing |

### Business Risks

| Risk | Mitigation |
|------|------------|
| Partner conflicts | Clear agreements, territory management |
| Revenue concentration (few large customers) | Diversify customer base, long-term contracts |
| Key person dependency | Document everything, build team |

---

## Next Steps

### Immediate Actions (Month 1)
- [ ] Finalize pricing packages
- [ ] Create sales collateral (brochure, demo video, case studies)
- [ ] Set up CRM system (HubSpot/Salesforce)
- [ ] Draft partner agreement template
- [ ] Build pilot customer list (10-15 targets)

### Short-term (Months 1-3)
- [ ] Close 3-5 pilot customers
- [ ] Collect feedback and testimonials
- [ ] Refine product based on feedback
- [ ] Recruit 1-2 pilot partners
- [ ] Launch marketing website

### Medium-term (Months 3-6)
- [ ] Reach 10-15 total customers
- [ ] Launch partner program officially
- [ ] Hire sales/support team
- [ ] Develop partner portal
- [ ] Plan for Year 2 expansion

---

**Document Version:** 1.0
**Last Updated:** 2026-01-17
**Owner:** Product & Business Development Team
