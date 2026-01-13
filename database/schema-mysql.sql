-- =============================================================================
-- E-Claim Database Schema for NHSO (สปสช.) Data - MySQL Version
-- Hospital: 10670 (Khon Kaen Hospital)
-- Created: 2026-01-08
-- =============================================================================

-- ============================================================================
-- 1. IMPORT TRACKING TABLE - Track imported files and their status
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_imported_files (
    id                  INT AUTO_INCREMENT PRIMARY KEY,

    -- File identification
    filename            VARCHAR(255) NOT NULL UNIQUE,
    file_type           VARCHAR(20) NOT NULL,  -- 'OP', 'IP', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO'
    hospital_code       VARCHAR(10) NOT NULL,  -- e.g., '10670'

    -- File metadata from filename
    file_date           DATE,                  -- Date extracted from filename (25680123 -> 2025-01-23)
    file_sequence       VARCHAR(20),           -- Sequence number from filename

    -- Import status
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',  -- pending, processing, completed, failed
    total_records       INT DEFAULT 0,
    imported_records    INT DEFAULT 0,
    failed_records      INT DEFAULT 0,

    -- Timestamps
    file_created_at     TIMESTAMP NULL,        -- When file was created/downloaded
    import_started_at   TIMESTAMP NULL,
    import_completed_at TIMESTAMP NULL,

    -- Error tracking
    error_message       TEXT,

    -- Audit
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    CONSTRAINT chk_file_type CHECK (file_type IN ('OP', 'IP', 'OPLGO', 'IPLGO', 'OPSSS', 'IPSSS', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO', 'OP_APPEAL')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'partial')),

    INDEX idx_imported_files_type (file_type),
    INDEX idx_imported_files_status (status),
    INDEX idx_imported_files_date (file_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Track all imported E-Claim files from NHSO';

-- ============================================================================
-- 2. COMMON CLAIM DATA TABLE - Unified table for OP and IP claims
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_claims (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Source file reference
    file_id                 INT NOT NULL,
    row_number              INT NOT NULL,

    -- =====================================================
    -- CORE IDENTIFIERS
    -- =====================================================
    rep_no                  VARCHAR(20),
    tran_id                 VARCHAR(20) NOT NULL,
    hn                      VARCHAR(20),
    an                      VARCHAR(20),
    pid                     VARCHAR(20),

    -- =====================================================
    -- PATIENT INFORMATION
    -- =====================================================
    patient_name            VARCHAR(255),
    patient_type            VARCHAR(5),

    -- =====================================================
    -- VISIT DATES
    -- =====================================================
    admission_date          TIMESTAMP NULL,
    discharge_date          TIMESTAMP NULL,

    -- =====================================================
    -- REIMBURSEMENT AMOUNTS
    -- =====================================================
    net_reimbursement       DECIMAL(12,2),
    net_reimbursement_org   DECIMAL(12,2),
    reimburse_from          VARCHAR(20),

    -- =====================================================
    -- CLAIM STATUS & ERRORS
    -- =====================================================
    error_code              VARCHAR(50),
    chk                     VARCHAR(10),

    -- =====================================================
    -- FUND INFORMATION
    -- =====================================================
    main_fund               VARCHAR(100),
    sub_fund                VARCHAR(200),

    -- =====================================================
    -- SERVICE INFORMATION
    -- =====================================================
    service_type            VARCHAR(50),
    refer_type              VARCHAR(10),
    has_right               VARCHAR(10),
    use_right               VARCHAR(10),

    -- =====================================================
    -- PATIENT RIGHTS
    -- =====================================================
    main_right              VARCHAR(20),
    sub_right               VARCHAR(20),

    -- =====================================================
    -- HOSPITAL CODES
    -- =====================================================
    href                    VARCHAR(20),
    hcode                   VARCHAR(10),
    hmain                   VARCHAR(10),
    prov1                   VARCHAR(10),
    rg1                     VARCHAR(5),
    hmain2                  VARCHAR(10),
    prov2                   VARCHAR(10),
    rg2                     VARCHAR(5),
    hmain3                  VARCHAR(20),

    -- =====================================================
    -- DRG INFORMATION (for IP)
    -- =====================================================
    da                      VARCHAR(20),
    proj                    VARCHAR(20),
    pa                      VARCHAR(20),
    drg                     VARCHAR(20),
    rw                      DECIMAL(10,4),
    ca_type                 VARCHAR(10),

    -- =====================================================
    -- BILLING AMOUNTS
    -- =====================================================
    claim_amount            DECIMAL(12,2),
    claim_non_car           DECIMAL(12,2),
    claim_car               DECIMAL(12,2),
    claim_total             DECIMAL(12,2),
    claim_central           DECIMAL(12,2),
    self_pay                DECIMAL(12,2),
    point_rate              DECIMAL(10,4),
    late_penalty            DECIMAL(12,2),

    -- =====================================================
    -- ADJUSTMENT FACTORS
    -- =====================================================
    ccuf                    DECIMAL(10,4),
    adj_rw_nhso             DECIMAL(10,4),
    adj_rw2                 DECIMAL(10,4),

    -- =====================================================
    -- CALCULATED PAYMENTS
    -- =====================================================
    compensation            DECIMAL(12,2),
    prb_amount              DECIMAL(12,2),
    salary_percent          DECIMAL(6,2),
    salary_amount           DECIMAL(12,2),
    net_after_salary        DECIMAL(12,2),

    -- =====================================================
    -- HIGH COST (HC)
    -- =====================================================
    hc_iphc                 DECIMAL(12,2),
    hc_ophc                 DECIMAL(12,2),

    -- =====================================================
    -- ACCIDENT & EMERGENCY (AE)
    -- =====================================================
    ae_opae                 DECIMAL(12,2),
    ae_ipnb                 DECIMAL(12,2),
    ae_ipuc                 DECIMAL(12,2),
    ae_ip3sss               DECIMAL(12,2),
    ae_ip7sss               DECIMAL(12,2),
    ae_carae                DECIMAL(12,2),
    ae_caref                DECIMAL(12,2),
    ae_caref_puc            DECIMAL(12,2),

    -- =====================================================
    -- PROSTHETICS/EQUIPMENT (INST)
    -- =====================================================
    inst_opinst             DECIMAL(12,2),
    inst_inst               DECIMAL(12,2),

    -- =====================================================
    -- INPATIENT (IP)
    -- =====================================================
    ip_ipaec                DECIMAL(12,2),
    ip_ipaer                DECIMAL(12,2),
    ip_ipinrgc              DECIMAL(12,2),
    ip_ipinrgr              DECIMAL(12,2),
    ip_ipinspsn             DECIMAL(12,2),
    ip_ipprcc               DECIMAL(12,2),
    ip_ipprcc_puc           DECIMAL(12,2),
    ip_ipbkk_inst           DECIMAL(12,2),
    ip_ip_ontop             DECIMAL(12,2),

    -- =====================================================
    -- SPECIFIC DISEASES (DMIS)
    -- =====================================================
    dmis_cataract           DECIMAL(12,2),
    dmis_burden_pho         DECIMAL(12,2),
    dmis_burden_hosp        DECIMAL(12,2),
    dmis_catinst            DECIMAL(12,2),
    dmis_dmisrc             DECIMAL(12,2),
    dmis_rcuhosc            DECIMAL(12,2),
    dmis_rcuhosr            DECIMAL(12,2),
    dmis_llop               DECIMAL(12,2),
    dmis_llrgc              DECIMAL(12,2),
    dmis_llrgr              DECIMAL(12,2),
    dmis_lp                 DECIMAL(12,2),
    dmis_stroke_drug        DECIMAL(12,2),
    dmis_dmidml             DECIMAL(12,2),
    dmis_pp                 DECIMAL(12,2),
    dmis_dmishd             DECIMAL(12,2),
    dmis_dmicnt             DECIMAL(12,2),
    dmis_palliative         DECIMAL(12,2),
    dmis_dm                 DECIMAL(12,2),

    -- =====================================================
    -- DRUG
    -- =====================================================
    drug_amount             DECIMAL(12,2),

    -- =====================================================
    -- OP BANGKOK SPECIFIC
    -- =====================================================
    opbkk_hc                DECIMAL(12,2),
    opbkk_dent              DECIMAL(12,2),
    opbkk_drug              DECIMAL(12,2),
    opbkk_fs                DECIMAL(12,2),
    opbkk_others            DECIMAL(12,2),
    opbkk_hsub              DECIMAL(12,2),
    opbkk_nhso              DECIMAL(12,2),

    -- =====================================================
    -- DENIAL AMOUNTS
    -- =====================================================
    deny_hc                 DECIMAL(12,2),
    deny_ae                 DECIMAL(12,2),
    deny_inst               DECIMAL(12,2),
    deny_ip                 DECIMAL(12,2),
    deny_dmis               DECIMAL(12,2),

    -- =====================================================
    -- BASE RATE
    -- =====================================================
    base_rate_original      DECIMAL(10,4),
    base_rate_additional    DECIMAL(10,4),
    base_rate_net           DECIMAL(10,4),

    -- =====================================================
    -- OTHER FIELDS
    -- =====================================================
    fs                      VARCHAR(50),
    va                      VARCHAR(50),
    remark                  TEXT,
    audit_results           TEXT,
    payment_format          VARCHAR(50),
    seq_no                  VARCHAR(50),
    invoice_no              VARCHAR(50),
    invoice_lt              VARCHAR(50),

    -- =====================================================
    -- AUDIT & METADATA
    -- =====================================================
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- =====================================================
    -- HIS RECONCILIATION FIELDS
    -- =====================================================
    his_matched             BOOLEAN DEFAULT FALSE,
    his_matched_at          TIMESTAMP NULL,
    his_hn                  VARCHAR(20),
    his_an                  VARCHAR(20),
    his_vn                  VARCHAR(20),
    his_amount_diff         DECIMAL(12,2),
    reconcile_status        VARCHAR(20),
    reconcile_note          TEXT,

    -- =====================================================
    -- CONSTRAINTS
    -- =====================================================
    UNIQUE KEY uq_claim_tran_file (tran_id, file_id),
    FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id),

    -- Indexes
    INDEX idx_claims_file_id (file_id),
    INDEX idx_claims_tran_id (tran_id),
    INDEX idx_claims_hn (hn),
    INDEX idx_claims_an (an),
    INDEX idx_claims_pid (pid),
    INDEX idx_claims_admission_date (admission_date),
    INDEX idx_claims_discharge_date (discharge_date),
    INDEX idx_claims_patient_type (patient_type),
    INDEX idx_claims_main_right (main_right),
    INDEX idx_claims_reimburse_from (reimburse_from),
    INDEX idx_claims_error_code (error_code),
    INDEX idx_claims_reconcile (his_matched, reconcile_status),
    INDEX idx_claims_drg (drg),
    INDEX idx_claims_hn_admission (hn, admission_date),
    INDEX idx_claims_pid_admission (pid, admission_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Unified table for OP and IP claims from NHSO E-Claim system';

-- ============================================================================
-- 3. OP REFER (ORF) TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_op_refer (
    id                      BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Source file reference
    file_id                 INT NOT NULL,
    row_number              INT NOT NULL,

    -- =====================================================
    -- CORE IDENTIFIERS
    -- =====================================================
    rep                     VARCHAR(20),
    tran_id                 VARCHAR(20) NOT NULL,
    hn                      VARCHAR(20),
    pid                     VARCHAR(20),
    patient_name            VARCHAR(255),

    -- =====================================================
    -- SERVICE INFORMATION
    -- =====================================================
    service_date            TIMESTAMP NULL,
    refer_doc_no            VARCHAR(50),

    -- =====================================================
    -- HOSPITAL CODES
    -- =====================================================
    hospital_type1          VARCHAR(10),
    prov1                   VARCHAR(10),
    hcode                   VARCHAR(10),
    hospital_type2          VARCHAR(10),
    prov2                   VARCHAR(10),
    hmain2                  VARCHAR(10),
    href                    VARCHAR(20),

    -- =====================================================
    -- DIAGNOSIS & PROCEDURE
    -- =====================================================
    dx                      VARCHAR(100),
    proc_code               VARCHAR(50),
    dmis                    VARCHAR(20),
    hmain3                  VARCHAR(20),
    dar                     VARCHAR(20),
    ca_type                 VARCHAR(10),

    -- =====================================================
    -- BILLING AMOUNTS
    -- =====================================================
    total_claimable         DECIMAL(12,2),
    central_reimburse_case  VARCHAR(20),
    central_reimburse_amt   DECIMAL(12,2),
    self_pay                DECIMAL(12,2),
    prb_amount              DECIMAL(12,2),

    -- =====================================================
    -- OP REFER AMOUNTS
    -- =====================================================
    opref_amount            DECIMAL(12,2),
    other_treatment         DECIMAL(12,2),
    before_adjust           DECIMAL(12,2),
    after_adjust            DECIMAL(12,2),
    total_case              DECIMAL(12,2),

    -- =====================================================
    -- RESPONSIBLE PARTIES
    -- =====================================================
    responsible_cup_lte1600 DECIMAL(12,2),
    responsible_nhso_gt1600 DECIMAL(12,2),

    -- =====================================================
    -- NET REIMBURSEMENT
    -- =====================================================
    net_reimbursement       DECIMAL(12,2),
    payment_by              VARCHAR(20),
    ps                      VARCHAR(10),

    -- =====================================================
    -- CENTRAL REIMBURSE DETAIL - OPHC (HC01-HC08)
    -- =====================================================
    ophc_hc01               DECIMAL(12,2),
    ophc_hc02               DECIMAL(12,2),
    ophc_hc03               DECIMAL(12,2),
    ophc_hc04               DECIMAL(12,2),
    ophc_hc05               DECIMAL(12,2),
    ophc_hc06               DECIMAL(12,2),
    ophc_hc07               DECIMAL(12,2),
    ophc_hc08               DECIMAL(12,2),

    -- =====================================================
    -- OTHER FUNDS
    -- =====================================================
    ae_accident             DECIMAL(12,2),
    carae_amount            DECIMAL(12,2),
    opinst_amount           DECIMAL(12,2),
    dmisrc_amount           DECIMAL(12,2),
    rcuhosc_amount          DECIMAL(12,2),
    rcuhosr_amount          DECIMAL(12,2),
    llop_amount             DECIMAL(12,2),
    lp_amount               DECIMAL(12,2),
    stroke_drug_amount      DECIMAL(12,2),
    dmidml_amount           DECIMAL(12,2),
    pp_amount               DECIMAL(12,2),
    dmishd_amount           DECIMAL(12,2),
    palliative_amount       DECIMAL(12,2),
    drug_amount             DECIMAL(12,2),
    ontop_amount            DECIMAL(12,2),

    -- =====================================================
    -- DETAILED EXPENSES (16 Categories)
    -- =====================================================
    room_food_claimable     DECIMAL(12,2),
    room_food_not_claim     DECIMAL(12,2),
    prosthetics_claimable   DECIMAL(12,2),
    prosthetics_not_claim   DECIMAL(12,2),
    iv_drugs_claimable      DECIMAL(12,2),
    iv_drugs_not_claim      DECIMAL(12,2),
    home_drugs_claimable    DECIMAL(12,2),
    home_drugs_not_claim    DECIMAL(12,2),
    supplies_claimable      DECIMAL(12,2),
    supplies_not_claim      DECIMAL(12,2),
    blood_claimable         DECIMAL(12,2),
    blood_not_claim         DECIMAL(12,2),
    lab_claimable           DECIMAL(12,2),
    lab_not_claim           DECIMAL(12,2),
    radiology_claimable     DECIMAL(12,2),
    radiology_not_claim     DECIMAL(12,2),
    special_dx_claimable    DECIMAL(12,2),
    special_dx_not_claim    DECIMAL(12,2),
    equipment_claimable     DECIMAL(12,2),
    equipment_not_claim     DECIMAL(12,2),
    procedure_claimable     DECIMAL(12,2),
    procedure_not_claim     DECIMAL(12,2),
    nursing_claimable       DECIMAL(12,2),
    nursing_not_claim       DECIMAL(12,2),
    dental_claimable        DECIMAL(12,2),
    dental_not_claim        DECIMAL(12,2),
    physio_claimable        DECIMAL(12,2),
    physio_not_claim        DECIMAL(12,2),
    acupuncture_claimable   DECIMAL(12,2),
    acupuncture_not_claim   DECIMAL(12,2),
    or_delivery_claimable   DECIMAL(12,2),
    or_delivery_not_claim   DECIMAL(12,2),
    prof_fee_claimable      DECIMAL(12,2),
    prof_fee_not_claim      DECIMAL(12,2),
    other_service_claimable DECIMAL(12,2),
    other_service_not_claim DECIMAL(12,2),
    uncategorized_claimable DECIMAL(12,2),
    uncategorized_not_claim DECIMAL(12,2),

    -- =====================================================
    -- ERROR & STATUS
    -- =====================================================
    error_code              VARCHAR(50),
    deny_hc                 DECIMAL(12,2),
    deny_ae                 DECIMAL(12,2),
    deny_inst               DECIMAL(12,2),
    deny_dmis               DECIMAL(12,2),

    -- =====================================================
    -- OTHER FIELDS
    -- =====================================================
    va                      VARCHAR(50),
    remark                  TEXT,
    audit_results           TEXT,
    payment_format          VARCHAR(50),
    seq_no                  VARCHAR(50),
    invoice_no              VARCHAR(50),
    invoice_lt              VARCHAR(50),

    -- =====================================================
    -- AUDIT & METADATA
    -- =====================================================
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- =====================================================
    -- HIS RECONCILIATION FIELDS
    -- =====================================================
    his_matched             BOOLEAN DEFAULT FALSE,
    his_matched_at          TIMESTAMP NULL,
    his_hn                  VARCHAR(20),
    his_vn                  VARCHAR(20),
    his_amount_diff         DECIMAL(12,2),
    reconcile_status        VARCHAR(20),
    reconcile_note          TEXT,

    -- =====================================================
    -- CONSTRAINTS
    -- =====================================================
    UNIQUE KEY uq_opref_tran_file (tran_id, file_id),
    FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id),

    -- Indexes
    INDEX idx_opref_file_id (file_id),
    INDEX idx_opref_tran_id (tran_id),
    INDEX idx_opref_hn (hn),
    INDEX idx_opref_pid (pid),
    INDEX idx_opref_service_date (service_date),
    INDEX idx_opref_refer_doc (refer_doc_no),
    INDEX idx_opref_reconcile (his_matched, reconcile_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='OP Refer (ORF) claims from NHSO E-Claim system';

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
-- END OF SCHEMA
-- ============================================================================
