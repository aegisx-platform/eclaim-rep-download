-- =============================================================================
-- E-Claim Database Schema for NHSO (สปสช.) Data
-- Hospital: 10670 (Khon Kaen Hospital)
-- Created: 2026-01-07
-- =============================================================================

-- ============================================================================
-- 1. IMPORT TRACKING TABLE - Track imported files and their status
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_imported_files (
    id                  SERIAL PRIMARY KEY,

    -- File identification
    filename            VARCHAR(255) NOT NULL UNIQUE,
    file_type           VARCHAR(20) NOT NULL,  -- 'OP', 'IP', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO'
    hospital_code       VARCHAR(10) NOT NULL,  -- e.g., '10670'

    -- File metadata from filename
    file_date           DATE,                  -- Date extracted from filename (25680123 -> 2025-01-23)
    file_sequence       VARCHAR(20),           -- Sequence number from filename

    -- Import status
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    total_records       INTEGER DEFAULT 0,
    imported_records    INTEGER DEFAULT 0,
    failed_records      INTEGER DEFAULT 0,

    -- Timestamps
    file_created_at     TIMESTAMP,             -- When file was created/downloaded
    import_started_at   TIMESTAMP,
    import_completed_at TIMESTAMP,

    -- Error tracking
    error_message       TEXT,

    -- Audit
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT chk_file_type CHECK (file_type IN ('OP', 'IP', 'OPLGO', 'IPLGO', 'OPSSS', 'IPSSS', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO', 'OP_APPEAL')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'partial'))
);

CREATE INDEX idx_imported_files_type ON eclaim_imported_files(file_type);
CREATE INDEX idx_imported_files_status ON eclaim_imported_files(status);
CREATE INDEX idx_imported_files_date ON eclaim_imported_files(file_date);

COMMENT ON TABLE eclaim_imported_files IS 'Track all imported E-Claim files from NHSO';

-- ============================================================================
-- 2. COMMON CLAIM DATA TABLE - Unified table for OP and IP claims
-- ============================================================================
-- Design Decision: Using a unified table because OP and IP share ~95% columns
-- Separating would create redundancy and complicate reconciliation queries

CREATE TABLE IF NOT EXISTS eclaim_claims (
    id                      BIGSERIAL PRIMARY KEY,

    -- Source file reference
    file_id                 INTEGER NOT NULL REFERENCES eclaim_imported_files(id),
    row_number              INTEGER NOT NULL,                -- Row number in original file

    -- =====================================================
    -- CORE IDENTIFIERS (Key fields for HIS reconciliation)
    -- =====================================================
    rep_no                  VARCHAR(20),        -- REP No. - Report number
    tran_id                 VARCHAR(20) NOT NULL,   -- TRAN_ID - Transaction ID (unique per claim)
    hn                      VARCHAR(20),        -- HN - Hospital Number
    an                      VARCHAR(20),        -- AN - Admission Number (for IP)
    pid                     VARCHAR(20),        -- PID - Personal ID (13-digit ID)

    -- =====================================================
    -- PATIENT INFORMATION
    -- =====================================================
    patient_name            VARCHAR(255),       -- ชื่อ-สกุล
    patient_type            VARCHAR(5),         -- ประเภทผู้ป่วย: 'OP' or 'IP'

    -- =====================================================
    -- VISIT DATES
    -- =====================================================
    admission_date          TIMESTAMP,          -- วันเข้ารักษา
    discharge_date          TIMESTAMP,          -- วันจำหน่าย

    -- =====================================================
    -- REIMBURSEMENT AMOUNTS
    -- =====================================================
    net_reimbursement       DECIMAL(12,2),      -- ชดเชยสุทธิ (สปสช.)
    net_reimbursement_org   DECIMAL(12,2),      -- ชดเชยสุทธิ (ต้นสังกัด)
    reimburse_from          VARCHAR(20),        -- ชดเชยจาก: 'NHSO', 'HSUB', etc.

    -- =====================================================
    -- CLAIM STATUS & ERRORS
    -- =====================================================
    error_code              VARCHAR(50),        -- Error Code
    chk                     VARCHAR(10),        -- CHK flag

    -- =====================================================
    -- FUND INFORMATION (กองทุน)
    -- =====================================================
    main_fund               VARCHAR(100),       -- กองทุนหลัก (e.g., 'HC02,IP01,DRUG')
    sub_fund                VARCHAR(200),       -- กองทุนย่อย (e.g., 'IPHC,IPINRGR,NHSO-DRUG')

    -- =====================================================
    -- SERVICE INFORMATION
    -- =====================================================
    service_type            VARCHAR(50),        -- ประเภทบริการ
    refer_type              VARCHAR(10),        -- การรับส่งต่อ (0,1,2,...)
    has_right               VARCHAR(10),        -- การมีสิทธิ
    use_right               VARCHAR(10),        -- การใช้สิทธิ

    -- =====================================================
    -- PATIENT RIGHTS (สิทธิ)
    -- =====================================================
    main_right              VARCHAR(20),        -- สิทธิหลัก: UCS, WEL, SSS, LGO, PUC, etc.
    sub_right               VARCHAR(20),        -- สิทธิย่อย

    -- =====================================================
    -- HOSPITAL CODES
    -- =====================================================
    href                    VARCHAR(20),        -- HREF - Refer hospital
    hcode                   VARCHAR(10),        -- HCODE - Hospital code
    hmain                   VARCHAR(10),        -- HMAIN - Main hospital
    prov1                   VARCHAR(10),        -- PROV1 - Province code 1
    rg1                     VARCHAR(5),         -- RG1 - Region 1
    hmain2                  VARCHAR(10),        -- HMAIN2 - Hospital 2
    prov2                   VARCHAR(10),        -- PROV2 - Province code 2
    rg2                     VARCHAR(5),         -- RG2 - Region 2
    hmain3                  VARCHAR(20),        -- DMIS/HMAIN3

    -- =====================================================
    -- DRG INFORMATION (for IP)
    -- =====================================================
    da                      VARCHAR(20),        -- DA
    proj                    VARCHAR(20),        -- PROJ
    pa                      VARCHAR(20),        -- PA
    drg                     VARCHAR(20),        -- DRG code
    rw                      DECIMAL(10,4),      -- Relative Weight
    ca_type                 VARCHAR(10),        -- CA_TYPE

    -- =====================================================
    -- BILLING AMOUNTS
    -- =====================================================
    claim_amount            DECIMAL(12,2),      -- เรียกเก็บ (1)
    claim_non_car           DECIMAL(12,2),      -- กลุ่มที่ไม่ใช่กลุ่มค่ารถ+ค่ายา+ค่าอุปกรณ์ (1.1)
    claim_car               DECIMAL(12,2),      -- กลุ่มที่เป็น ค่ารถ+ค่ายา+ค่าอุปกรณ์ (1.2)
    claim_total             DECIMAL(12,2),      -- รวมยอดเรียกเก็บ (1.3)
    claim_central           DECIMAL(12,2),      -- เรียกเก็บ central reimburse (2)
    self_pay                DECIMAL(12,2),      -- ชำระเอง (3)
    point_rate              DECIMAL(10,4),      -- อัตราจ่าย/Point (4)
    late_penalty            DECIMAL(12,2),      -- ล่าช้า PS (5)

    -- =====================================================
    -- ADJUSTMENT FACTORS
    -- =====================================================
    ccuf                    DECIMAL(10,4),      -- CCUF (6)
    adj_rw_nhso             DECIMAL(10,4),      -- AdjRW_NHSO (7)
    adj_rw2                 DECIMAL(10,4),      -- AdjRW2 (8)

    -- =====================================================
    -- CALCULATED PAYMENTS
    -- =====================================================
    compensation            DECIMAL(12,2),      -- จ่ายชดเชย (9)
    prb_amount              DECIMAL(12,2),      -- ค่าพรบ. (10)
    salary_percent          DECIMAL(6,2),       -- เงินเดือน %
    salary_amount           DECIMAL(12,2),      -- จำนวนเงินเงินเดือน (11)
    net_after_salary        DECIMAL(12,2),      -- ยอดชดเชยหลังหักเงินเดือน (12)

    -- =====================================================
    -- HIGH COST (HC) - ค่าใช้จ่ายสูง
    -- =====================================================
    hc_iphc                 DECIMAL(12,2),      -- IPHC
    hc_ophc                 DECIMAL(12,2),      -- OPHC

    -- =====================================================
    -- ACCIDENT & EMERGENCY (AE) - อุบัติเหตุฉุกเฉิน
    -- =====================================================
    ae_opae                 DECIMAL(12,2),      -- OPAE
    ae_ipnb                 DECIMAL(12,2),      -- IPNB
    ae_ipuc                 DECIMAL(12,2),      -- IPUC
    ae_ip3sss               DECIMAL(12,2),      -- IP3SSS
    ae_ip7sss               DECIMAL(12,2),      -- IP7SSS
    ae_carae                DECIMAL(12,2),      -- CARAE
    ae_caref                DECIMAL(12,2),      -- CAREF
    ae_caref_puc            DECIMAL(12,2),      -- CAREF-PUC

    -- =====================================================
    -- PROSTHETICS/EQUIPMENT (INST) - อวัยวะเทียม/อุปกรณ์
    -- =====================================================
    inst_opinst             DECIMAL(12,2),      -- OPINST
    inst_inst               DECIMAL(12,2),      -- INST

    -- =====================================================
    -- INPATIENT (IP) - ผู้ป่วยใน
    -- =====================================================
    ip_ipaec                DECIMAL(12,2),      -- IPAEC
    ip_ipaer                DECIMAL(12,2),      -- IPAER
    ip_ipinrgc              DECIMAL(12,2),      -- IPINRGC
    ip_ipinrgr              DECIMAL(12,2),      -- IPINRGR
    ip_ipinspsn             DECIMAL(12,2),      -- IPINSPSN
    ip_ipprcc               DECIMAL(12,2),      -- IPPRCC
    ip_ipprcc_puc           DECIMAL(12,2),      -- IPPRCC-PUC
    ip_ipbkk_inst           DECIMAL(12,2),      -- IPBKK-INST
    ip_ip_ontop             DECIMAL(12,2),      -- IP-ONTOP

    -- =====================================================
    -- SPECIFIC DISEASES (DMIS) - โรคเฉพาะ
    -- =====================================================
    dmis_cataract           DECIMAL(12,2),      -- CATARACT
    dmis_burden_pho         DECIMAL(12,2),      -- ค่าภาระงาน(สสจ.)
    dmis_burden_hosp        DECIMAL(12,2),      -- ค่าภาระงาน(รพ.)
    dmis_catinst            DECIMAL(12,2),      -- CATINST
    dmis_dmisrc             DECIMAL(12,2),      -- DMISRC
    dmis_rcuhosc            DECIMAL(12,2),      -- RCUHOSC
    dmis_rcuhosr            DECIMAL(12,2),      -- RCUHOSR
    dmis_llop               DECIMAL(12,2),      -- LLOP
    dmis_llrgc              DECIMAL(12,2),      -- LLRGC
    dmis_llrgr              DECIMAL(12,2),      -- LLRGR
    dmis_lp                 DECIMAL(12,2),      -- LP
    dmis_stroke_drug        DECIMAL(12,2),      -- STROKE-STEMI DRUG
    dmis_dmidml             DECIMAL(12,2),      -- DMIDML
    dmis_pp                 DECIMAL(12,2),      -- PP
    dmis_dmishd             DECIMAL(12,2),      -- DMISHD
    dmis_dmicnt             DECIMAL(12,2),      -- DMICNT
    dmis_palliative         DECIMAL(12,2),      -- Palliative Care
    dmis_dm                 DECIMAL(12,2),      -- DM

    -- =====================================================
    -- DRUG - ยา
    -- =====================================================
    drug_amount             DECIMAL(12,2),      -- DRUG

    -- =====================================================
    -- OP BANGKOK SPECIFIC
    -- =====================================================
    opbkk_hc                DECIMAL(12,2),      -- OPBKK HC
    opbkk_dent              DECIMAL(12,2),      -- DENT
    opbkk_drug              DECIMAL(12,2),      -- DRUG (OPBKK)
    opbkk_fs                DECIMAL(12,2),      -- FS
    opbkk_others            DECIMAL(12,2),      -- OTHERS
    opbkk_hsub              DECIMAL(12,2),      -- HSUB
    opbkk_nhso              DECIMAL(12,2),      -- NHSO

    -- =====================================================
    -- DENIAL AMOUNTS (Deny)
    -- =====================================================
    deny_hc                 DECIMAL(12,2),      -- Deny HC
    deny_ae                 DECIMAL(12,2),      -- Deny AE
    deny_inst               DECIMAL(12,2),      -- Deny INST
    deny_ip                 DECIMAL(12,2),      -- Deny IP
    deny_dmis               DECIMAL(12,2),      -- Deny DMIS

    -- =====================================================
    -- BASE RATE
    -- =====================================================
    base_rate_original      DECIMAL(10,4),      -- base rate เดิม
    base_rate_additional    DECIMAL(10,4),      -- base rate ที่ได้รับเพิ่ม
    base_rate_net           DECIMAL(10,4),      -- base rate สุทธิ

    -- =====================================================
    -- OTHER FIELDS
    -- =====================================================
    fs                      VARCHAR(50),        -- FS
    va                      VARCHAR(50),        -- VA
    remark                  TEXT,               -- Remark
    audit_results           TEXT,               -- AUDIT RESULTS
    payment_format          VARCHAR(50),        -- รูปแบบการจ่าย
    seq_no                  VARCHAR(50),        -- SEQ NO
    invoice_no              VARCHAR(50),        -- INVOICE NO
    invoice_lt              VARCHAR(50),        -- INVOICE LT

    -- =====================================================
    -- AUDIT & METADATA
    -- =====================================================
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- =====================================================
    -- HIS RECONCILIATION FIELDS
    -- =====================================================
    his_matched             BOOLEAN DEFAULT FALSE,  -- Matched with HIS data
    his_matched_at          TIMESTAMP,              -- When matched
    his_hn                  VARCHAR(20),            -- HN from HIS
    his_an                  VARCHAR(20),            -- AN from HIS
    his_vn                  VARCHAR(20),            -- VN from HIS
    his_amount_diff         DECIMAL(12,2),          -- Difference in amount
    reconcile_status        VARCHAR(20),            -- 'pending', 'matched', 'mismatched', 'manual'
    reconcile_note          TEXT,

    -- =====================================================
    -- CONSTRAINTS
    -- =====================================================
    CONSTRAINT uq_claim_tran_file UNIQUE (tran_id, file_id)
);

-- Indexes for performance
CREATE INDEX idx_claims_file_id ON eclaim_claims(file_id);
CREATE INDEX idx_claims_tran_id ON eclaim_claims(tran_id);
CREATE INDEX idx_claims_hn ON eclaim_claims(hn);
CREATE INDEX idx_claims_an ON eclaim_claims(an);
CREATE INDEX idx_claims_pid ON eclaim_claims(pid);
CREATE INDEX idx_claims_admission_date ON eclaim_claims(admission_date);
CREATE INDEX idx_claims_discharge_date ON eclaim_claims(discharge_date);
CREATE INDEX idx_claims_patient_type ON eclaim_claims(patient_type);
CREATE INDEX idx_claims_main_right ON eclaim_claims(main_right);
CREATE INDEX idx_claims_reimburse_from ON eclaim_claims(reimburse_from);
CREATE INDEX idx_claims_error_code ON eclaim_claims(error_code);
CREATE INDEX idx_claims_reconcile ON eclaim_claims(his_matched, reconcile_status);
CREATE INDEX idx_claims_drg ON eclaim_claims(drg);

-- Composite indexes for common queries
CREATE INDEX idx_claims_hn_admission ON eclaim_claims(hn, admission_date);
CREATE INDEX idx_claims_pid_admission ON eclaim_claims(pid, admission_date);

COMMENT ON TABLE eclaim_claims IS 'Unified table for OP and IP claims from NHSO E-Claim system';

-- ============================================================================
-- 3. OP REFER (ORF) TABLE - Special structure for OP Refer data
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_op_refer (
    id                      BIGSERIAL PRIMARY KEY,

    -- Source file reference
    file_id                 INTEGER NOT NULL REFERENCES eclaim_imported_files(id),
    row_number              INTEGER NOT NULL,

    -- =====================================================
    -- CORE IDENTIFIERS
    -- =====================================================
    rep                     VARCHAR(20),        -- REP
    tran_id                 VARCHAR(20) NOT NULL,   -- TRAN_ID
    hn                      VARCHAR(20),        -- HN
    pid                     VARCHAR(20),        -- PID
    patient_name            VARCHAR(255),       -- ชื่อ

    -- =====================================================
    -- SERVICE INFORMATION
    -- =====================================================
    service_date            TIMESTAMP,          -- ว/ด/ป ที่รับบริการ
    refer_doc_no            VARCHAR(50),        -- เลขที่ใบส่งต่อ

    -- =====================================================
    -- HOSPITAL CODES
    -- =====================================================
    hospital_type1          VARCHAR(10),        -- รักษา(Htype1)
    prov1                   VARCHAR(10),        -- รักษา(Prov1)
    hcode                   VARCHAR(10),        -- รักษา(Hcode)
    hospital_type2          VARCHAR(10),        -- รักษา(Htype2)
    prov2                   VARCHAR(10),        -- รักษา(Prov2)
    hmain2                  VARCHAR(10),        -- ประจำ(Hmain2)
    href                    VARCHAR(20),        -- รับส่งต่อ(Href)

    -- =====================================================
    -- DIAGNOSIS & PROCEDURE
    -- =====================================================
    dx                      VARCHAR(100),       -- DX (Diagnosis code)
    proc_code               VARCHAR(50),        -- Proc. (Procedure code)
    dmis                    VARCHAR(20),        -- DMIS
    hmain3                  VARCHAR(20),        -- HMAIN3
    dar                     VARCHAR(20),        -- DAR
    ca_type                 VARCHAR(10),        -- CA_TYPE

    -- =====================================================
    -- BILLING AMOUNTS
    -- =====================================================
    total_claimable         DECIMAL(12,2),      -- ยอดรวมค่าใช้จ่าย(เฉพาะเบิกได้) (1)
    central_reimburse_case  VARCHAR(20),        -- กรณี central reimburse
    central_reimburse_amt   DECIMAL(12,2),      -- จำนวนเงิน central reimburse
    self_pay                DECIMAL(12,2),      -- ชำระเอง (3)
    prb_amount              DECIMAL(12,2),      -- พรบ. (4)

    -- =====================================================
    -- OP REFER AMOUNTS
    -- =====================================================
    opref_amount            DECIMAL(12,2),      -- รายการ OPREF (5)
    other_treatment         DECIMAL(12,2),      -- ค่ารักษาอื่นๆ
    before_adjust           DECIMAL(12,2),      -- ก่อนปรับลด (6)
    after_adjust            DECIMAL(12,2),      -- หลังปรับลด (7)
    total_case              DECIMAL(12,2),      -- ผลรวมทั้ง Case (8)

    -- =====================================================
    -- RESPONSIBLE PARTIES
    -- =====================================================
    responsible_cup_lte1600 DECIMAL(12,2),      -- CUP/จังหวัด <=1600
    responsible_nhso_gt1600 DECIMAL(12,2),      -- สปสช >1600

    -- =====================================================
    -- NET REIMBURSEMENT
    -- =====================================================
    net_reimbursement       DECIMAL(12,2),      -- ชดเชยสุทธิ (บาท) (10=8)
    payment_by              VARCHAR(20),        -- ชำระบัญชีโดย
    ps                      VARCHAR(10),        -- PS

    -- =====================================================
    -- CENTRAL REIMBURSE DETAIL - OPHC (HC01-HC08)
    -- =====================================================
    ophc_hc01               DECIMAL(12,2),      -- HC01
    ophc_hc02               DECIMAL(12,2),      -- HC02
    ophc_hc03               DECIMAL(12,2),      -- HC03
    ophc_hc04               DECIMAL(12,2),      -- HC04
    ophc_hc05               DECIMAL(12,2),      -- HC05
    ophc_hc06               DECIMAL(12,2),      -- HC06
    ophc_hc07               DECIMAL(12,2),      -- HC07
    ophc_hc08               DECIMAL(12,2),      -- HC08

    -- =====================================================
    -- OTHER FUNDS
    -- =====================================================
    ae_accident             DECIMAL(12,2),      -- อุบัติเหตุฉุกเฉิน (AE04)
    carae_amount            DECIMAL(12,2),      -- CARAE (AE08)
    opinst_amount           DECIMAL(12,2),      -- OPINST (HC09)
    dmisrc_amount           DECIMAL(12,2),      -- DMISRC
    rcuhosc_amount          DECIMAL(12,2),      -- RCUHOSC
    rcuhosr_amount          DECIMAL(12,2),      -- RCUHOSR
    llop_amount             DECIMAL(12,2),      -- LLOP
    lp_amount               DECIMAL(12,2),      -- LP
    stroke_drug_amount      DECIMAL(12,2),      -- STROKE-STEMI DRUG
    dmidml_amount           DECIMAL(12,2),      -- DMIDML
    pp_amount               DECIMAL(12,2),      -- PP
    dmishd_amount           DECIMAL(12,2),      -- DMISHD
    palliative_amount       DECIMAL(12,2),      -- Paliative Care
    drug_amount             DECIMAL(12,2),      -- DRUG
    ontop_amount            DECIMAL(12,2),      -- ONTOP

    -- =====================================================
    -- DETAILED EXPENSES (16 Categories)
    -- =====================================================
    -- Room & Food
    room_food_claimable     DECIMAL(12,2),      -- ค่าห้อง/ค่าอาหาร - เบิกได้
    room_food_not_claim     DECIMAL(12,2),      -- ค่าห้อง/ค่าอาหาร - เบิกไม่ได้

    -- Prosthetics
    prosthetics_claimable   DECIMAL(12,2),      -- อวัยวะเทียม - เบิกได้
    prosthetics_not_claim   DECIMAL(12,2),      -- อวัยวะเทียม - เบิกไม่ได้

    -- IV Drugs
    iv_drugs_claimable      DECIMAL(12,2),      -- ยาและสารอาหารทางเส้นเลือด - เบิกได้
    iv_drugs_not_claim      DECIMAL(12,2),      -- ยาและสารอาหารทางเส้นเลือด - เบิกไม่ได้

    -- Take-home drugs
    home_drugs_claimable    DECIMAL(12,2),      -- ยาที่นำไปใช้ต่อที่บ้าน - เบิกได้
    home_drugs_not_claim    DECIMAL(12,2),      -- ยาที่นำไปใช้ต่อที่บ้าน - เบิกไม่ได้

    -- Medical supplies
    supplies_claimable      DECIMAL(12,2),      -- เวชภัณฑ์ที่ไม่ใช่ยา - เบิกได้
    supplies_not_claim      DECIMAL(12,2),      -- เวชภัณฑ์ที่ไม่ใช่ยา - เบิกไม่ได้

    -- Blood services
    blood_claimable         DECIMAL(12,2),      -- บริการโลหิต - เบิกได้
    blood_not_claim         DECIMAL(12,2),      -- บริการโลหิต - เบิกไม่ได้

    -- Lab
    lab_claimable           DECIMAL(12,2),      -- ตรวจวินิจฉัยทางเทคนิคการแพทย์ - เบิกได้
    lab_not_claim           DECIMAL(12,2),      -- ตรวจวินิจฉัยทางเทคนิคการแพทย์ - เบิกไม่ได้

    -- Radiology
    radiology_claimable     DECIMAL(12,2),      -- ตรวจวินิจฉัยและรักษาทางรังสี - เบิกได้
    radiology_not_claim     DECIMAL(12,2),      -- ตรวจวินิจฉัยและรักษาทางรังสี - เบิกไม่ได้

    -- Special diagnostics
    special_dx_claimable    DECIMAL(12,2),      -- ตรวจวินิจฉัยโดยวิธีพิเศษ - เบิกได้
    special_dx_not_claim    DECIMAL(12,2),      -- ตรวจวินิจฉัยโดยวิธีพิเศษ - เบิกไม่ได้

    -- Equipment
    equipment_claimable     DECIMAL(12,2),      -- อุปกรณ์และเครื่องมือทางการแพทย์ - เบิกได้
    equipment_not_claim     DECIMAL(12,2),      -- อุปกรณ์และเครื่องมือทางการแพทย์ - เบิกไม่ได้

    -- Procedures & Anesthesia
    procedure_claimable     DECIMAL(12,2),      -- ทำหัตถการและบริการวิสัญญี - เบิกได้
    procedure_not_claim     DECIMAL(12,2),      -- ทำหัตถการและบริการวิสัญญี - เบิกไม่ได้

    -- Nursing services
    nursing_claimable       DECIMAL(12,2),      -- ค่าบริการทางพยาบาล - เบิกได้
    nursing_not_claim       DECIMAL(12,2),      -- ค่าบริการทางพยาบาล - เบิกไม่ได้

    -- Dental
    dental_claimable        DECIMAL(12,2),      -- ค่าบริการทางทันตกรรม - เบิกได้
    dental_not_claim        DECIMAL(12,2),      -- ค่าบริการทางทันตกรรม - เบิกไม่ได้

    -- Physical therapy
    physio_claimable        DECIMAL(12,2),      -- ค่ากายภาพบำบัด - เบิกได้
    physio_not_claim        DECIMAL(12,2),      -- ค่ากายภาพบำบัด - เบิกไม่ได้

    -- Acupuncture
    acupuncture_claimable   DECIMAL(12,2),      -- ค่าบริการฝังเข็ม - เบิกได้
    acupuncture_not_claim   DECIMAL(12,2),      -- ค่าบริการฝังเข็ม - เบิกไม่ได้

    -- OR & Delivery room
    or_delivery_claimable   DECIMAL(12,2),      -- ค่าห้องผ่าตัดและห้องคลอด - เบิกได้
    or_delivery_not_claim   DECIMAL(12,2),      -- ค่าห้องผ่าตัดและห้องคลอด - เบิกไม่ได้

    -- Professional fees
    prof_fee_claimable      DECIMAL(12,2),      -- ค่าธรรมเนียมบุคลากร - เบิกได้
    prof_fee_not_claim      DECIMAL(12,2),      -- ค่าธรรมเนียมบุคลากร - เบิกไม่ได้

    -- Other services
    other_service_claimable DECIMAL(12,2),      -- บริการอื่นๆ และส่งเสริมป้องกัน - เบิกได้
    other_service_not_claim DECIMAL(12,2),      -- บริการอื่นๆ และส่งเสริมป้องกัน - เบิกไม่ได้

    -- Uncategorized
    uncategorized_claimable DECIMAL(12,2),      -- บริการอื่นๆ ที่ยังไม่ได้จัดหมวด - เบิกได้
    uncategorized_not_claim DECIMAL(12,2),      -- บริการอื่นๆ ที่ยังไม่ได้จัดหมวด - เบิกไม่ได้

    -- =====================================================
    -- ERROR & STATUS
    -- =====================================================
    error_code              VARCHAR(50),        -- Error Code
    deny_hc                 DECIMAL(12,2),      -- Deny HC
    deny_ae                 DECIMAL(12,2),      -- Deny AE
    deny_inst               DECIMAL(12,2),      -- Deny INST
    deny_dmis               DECIMAL(12,2),      -- Deny DMIS

    -- =====================================================
    -- OTHER FIELDS
    -- =====================================================
    va                      VARCHAR(50),        -- VA
    remark                  TEXT,               -- Remark
    audit_results           TEXT,               -- AUDIT RESULTS
    payment_format          VARCHAR(50),        -- รูปแบบการจ่าย
    seq_no                  VARCHAR(50),        -- SEQ NO
    invoice_no              VARCHAR(50),        -- INVOICE NO
    invoice_lt              VARCHAR(50),        -- INVOICE LT

    -- =====================================================
    -- AUDIT & METADATA
    -- =====================================================
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- =====================================================
    -- HIS RECONCILIATION FIELDS
    -- =====================================================
    his_matched             BOOLEAN DEFAULT FALSE,
    his_matched_at          TIMESTAMP,
    his_hn                  VARCHAR(20),
    his_vn                  VARCHAR(20),
    his_amount_diff         DECIMAL(12,2),
    reconcile_status        VARCHAR(20),
    reconcile_note          TEXT,

    -- =====================================================
    -- CONSTRAINTS
    -- =====================================================
    CONSTRAINT uq_opref_tran_file UNIQUE (tran_id, file_id)
);

-- Indexes
CREATE INDEX idx_opref_file_id ON eclaim_op_refer(file_id);
CREATE INDEX idx_opref_tran_id ON eclaim_op_refer(tran_id);
CREATE INDEX idx_opref_hn ON eclaim_op_refer(hn);
CREATE INDEX idx_opref_pid ON eclaim_op_refer(pid);
CREATE INDEX idx_opref_service_date ON eclaim_op_refer(service_date);
CREATE INDEX idx_opref_refer_doc ON eclaim_op_refer(refer_doc_no);
CREATE INDEX idx_opref_reconcile ON eclaim_op_refer(his_matched, reconcile_status);

COMMENT ON TABLE eclaim_op_refer IS 'OP Refer (ORF) claims from NHSO E-Claim system';

-- ============================================================================
-- 4. SUMMARY/RECONCILIATION VIEWS
-- ============================================================================

-- Daily summary view
CREATE OR REPLACE VIEW v_daily_claim_summary AS
SELECT
    DATE(c.admission_date) as service_date,
    c.patient_type,
    c.main_right,
    COUNT(*) as claim_count,
    SUM(c.net_reimbursement) as total_reimbursement,
    SUM(CASE WHEN c.error_code IS NOT NULL AND c.error_code != '-' THEN 1 ELSE 0 END) as error_count,
    SUM(CASE WHEN c.his_matched THEN 1 ELSE 0 END) as matched_count
FROM eclaim_claims c
GROUP BY DATE(c.admission_date), c.patient_type, c.main_right
ORDER BY service_date DESC, patient_type, main_right;

-- Unmatched claims for reconciliation
CREATE OR REPLACE VIEW v_unmatched_claims AS
SELECT
    c.id,
    c.tran_id,
    c.hn,
    c.an,
    c.pid,
    c.patient_name,
    c.patient_type,
    c.admission_date,
    c.discharge_date,
    c.net_reimbursement,
    c.error_code,
    f.filename,
    f.file_date
FROM eclaim_claims c
JOIN eclaim_imported_files f ON c.file_id = f.id
WHERE c.his_matched = FALSE
ORDER BY c.admission_date DESC;

-- Fund distribution view
CREATE OR REPLACE VIEW v_fund_distribution AS
SELECT
    DATE(c.admission_date) as service_date,
    c.patient_type,
    c.main_fund,
    c.reimburse_from,
    COUNT(*) as claim_count,
    SUM(c.net_reimbursement) as total_amount
FROM eclaim_claims c
WHERE c.admission_date IS NOT NULL
GROUP BY DATE(c.admission_date), c.patient_type, c.main_fund, c.reimburse_from
ORDER BY service_date DESC;

-- Import status summary
CREATE OR REPLACE VIEW v_import_status AS
SELECT
    f.file_type,
    f.status,
    COUNT(*) as file_count,
    SUM(f.total_records) as total_records,
    SUM(f.imported_records) as imported_records,
    SUM(f.failed_records) as failed_records,
    MIN(f.file_date) as earliest_file,
    MAX(f.file_date) as latest_file
FROM eclaim_imported_files f
GROUP BY f.file_type, f.status
ORDER BY f.file_type, f.status;

-- ============================================================================
-- 5. HELPER FUNCTIONS
-- ============================================================================

-- Function to parse Thai Buddhist date from filename (25680123 -> 2025-01-23)
CREATE OR REPLACE FUNCTION parse_be_date(date_str VARCHAR)
RETURNS DATE AS $$
DECLARE
    be_year INTEGER;
    ce_year INTEGER;
    month_day VARCHAR(4);
BEGIN
    IF date_str IS NULL OR LENGTH(date_str) != 8 THEN
        RETURN NULL;
    END IF;

    be_year := CAST(SUBSTRING(date_str, 1, 4) AS INTEGER);
    ce_year := be_year - 543;
    month_day := SUBSTRING(date_str, 5, 4);

    RETURN TO_DATE(ce_year || month_day, 'YYYYMMDD');
EXCEPTION
    WHEN OTHERS THEN
        RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Function to update reconciliation status
CREATE OR REPLACE FUNCTION update_reconcile_status()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at := CURRENT_TIMESTAMP;
    IF NEW.his_matched = TRUE AND OLD.his_matched = FALSE THEN
        NEW.his_matched_at := CURRENT_TIMESTAMP;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers for updated_at
CREATE TRIGGER tr_claims_updated
    BEFORE UPDATE ON eclaim_claims
    FOR EACH ROW
    EXECUTE FUNCTION update_reconcile_status();

CREATE TRIGGER tr_opref_updated
    BEFORE UPDATE ON eclaim_op_refer
    FOR EACH ROW
    EXECUTE FUNCTION update_reconcile_status();

CREATE TRIGGER tr_files_updated
    BEFORE UPDATE ON eclaim_imported_files
    FOR EACH ROW
    EXECUTE FUNCTION update_reconcile_status();

-- ============================================================================
-- 6. SAMPLE DATA VALIDATION CONSTRAINTS
-- ============================================================================

-- Add validation for common data issues
ALTER TABLE eclaim_claims ADD CONSTRAINT chk_patient_type
    CHECK (patient_type IN ('OP', 'IP', NULL));

ALTER TABLE eclaim_claims ADD CONSTRAINT chk_main_right
    CHECK (main_right IN ('UCS', 'WEL', 'SSS', 'LGO', 'PUC', 'OFC', 'SSO', NULL) OR main_right IS NULL);

-- ============================================================================
-- 7. GRANT PERMISSIONS (adjust as needed)
-- ============================================================================
-- GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA public TO eclaim_app;
-- GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO eclaim_app;
-- GRANT SELECT ON ALL TABLES IN SCHEMA public TO eclaim_readonly;

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
