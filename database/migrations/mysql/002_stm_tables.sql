-- =============================================================================
-- STM (Statement) Database Schema - MySQL
-- For NHSO Statement Import and Reconciliation with REP data
-- Created: 2026-01-12
-- =============================================================================

-- ============================================================================
-- 1. STM IMPORT TRACKING TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS stm_imported_files (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    filename            VARCHAR(255) NOT NULL UNIQUE,
    file_type           VARCHAR(20) NOT NULL,          -- IP_STM, OP_STM
    scheme              VARCHAR(10) NOT NULL,          -- UCS, OFC, SSS, LGO
    hospital_code       VARCHAR(10) NOT NULL,
    hospital_name       VARCHAR(255),
    province_code       VARCHAR(10),
    province_name       VARCHAR(100),
    document_no         VARCHAR(50),                   -- เลขที่เอกสาร e.g., 10670_IPUCS256811_01
    statement_month     INT,                           -- เดือนที่ออก statement
    statement_year      INT,                           -- ปีที่ออก statement (Buddhist Era)
    report_date         DATETIME,                      -- วันที่ออกรายงาน
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_records       INT DEFAULT 0,
    imported_records    INT DEFAULT 0,
    failed_records      INT DEFAULT 0,
    import_started_at   DATETIME,
    import_completed_at DATETIME,
    error_message       TEXT,
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    CONSTRAINT chk_stm_file_type CHECK (file_type IN ('IP_STM', 'OP_STM')),
    CONSTRAINT chk_stm_scheme CHECK (scheme IN ('UCS', 'OFC', 'SSS', 'LGO')),
    CONSTRAINT chk_stm_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'partial')),
    INDEX idx_stm_files_type (file_type),
    INDEX idx_stm_files_scheme (scheme),
    INDEX idx_stm_files_hospital (hospital_code),
    INDEX idx_stm_files_status (status),
    INDEX idx_stm_files_document (document_no),
    INDEX idx_stm_files_month_year (statement_year, statement_month)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 2. STM RECEIVABLE SUMMARY (รายงานพึงรับ)
-- High-level totals per statement file
-- ============================================================================
CREATE TABLE IF NOT EXISTS stm_receivable_summary (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    file_id             INT NOT NULL,
    data_type           VARCHAR(20) NOT NULL,         -- normal, appeal, disabled_d1
    patient_type        VARCHAR(20) NOT NULL,         -- inpatient (ผู้ป่วยใน), outpatient (ผู้ป่วยนอก)
    rep_count           INT DEFAULT 0,                -- จำนวน REP ที่ส่ง
    patient_count       INT DEFAULT 0,                -- จำนวนราย (ผ่าน A)
    total_adjrw         DECIMAL(15,4) DEFAULT 0,      -- ผลรวม ADJRW
    total_paid          DECIMAL(15,2) DEFAULT 0,      -- จ่ายชดเชย
    salary_deduction    DECIMAL(15,2) DEFAULT 0,      -- ยอดหักเงินเดือน สป.
    adjrw_paid_deduction DECIMAL(15,2) DEFAULT 0,     -- ยอดหักเงินเดือน adjrw paid*380
    net_receivable      DECIMAL(15,2) DEFAULT 0,      -- รวม (พึงรับสุทธิ)
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_stm_data_type CHECK (data_type IN ('normal', 'appeal', 'disabled_d1')),
    CONSTRAINT chk_stm_patient_type CHECK (patient_type IN ('inpatient', 'outpatient')),
    FOREIGN KEY (file_id) REFERENCES stm_imported_files(id) ON DELETE CASCADE,
    INDEX idx_stm_receivable_file (file_id),
    INDEX idx_stm_receivable_type (data_type, patient_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 3. STM REP SUMMARY (รายงานสรุป)
-- Summary by REP number - bridges Statement and REP files
-- ============================================================================
CREATE TABLE IF NOT EXISTS stm_rep_summary (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    file_id             INT NOT NULL,
    data_type           VARCHAR(20) NOT NULL,         -- normal, appeal, disabled_d1
    period              VARCHAR(20),                  -- งวด e.g., 6811_IP_01, 6811_OP_01
    hcode               VARCHAR(10),                  -- HCODE
    rep_no              VARCHAR(20),                  -- REP NO.
    claim_type          VARCHAR(20),                  -- ประเภท (ข้อมูลปกติ/ข้อมูลอุทธรณ์)
    total_passed        INT DEFAULT 0,                -- ทั้งหมดที่ผ่าน
    amount_claimed      DECIMAL(15,2) DEFAULT 0,      -- เรียกเก็บ
    prb_amount          DECIMAL(15,2) DEFAULT 0,      -- พรบ.

    -- พึงรับ breakdown columns
    receivable_op       DECIMAL(15,2) DEFAULT 0,      -- พึงรับ OP
    receivable_ip_calc  DECIMAL(15,2) DEFAULT 0,      -- พึงรับ IP ยอดชดเชยที่คำนวณได้
    receivable_ip_paid  DECIMAL(15,2) DEFAULT 0,      -- พึงรับ IP ยอดชดเชยที่จ่ายจริง

    -- Fund breakdown columns
    hc_amount           DECIMAL(15,2) DEFAULT 0,      -- HC
    hc_drug             DECIMAL(15,2) DEFAULT 0,      -- HC_DRUG
    ae_amount           DECIMAL(15,2) DEFAULT 0,      -- AE
    ae_drug             DECIMAL(15,2) DEFAULT 0,      -- AE_DRUG
    inst_amount         DECIMAL(15,2) DEFAULT 0,      -- INST
    dmis_calc           DECIMAL(15,2) DEFAULT 0,      -- DMIS ยอดชดเชยที่คำนวณได้
    dmis_paid           DECIMAL(15,2) DEFAULT 0,      -- DMIS ยอดชดเชยที่จ่ายจริง
    dmis_drug           DECIMAL(15,2) DEFAULT 0,      -- DMIS_DRUG
    palliative_care     DECIMAL(15,2) DEFAULT 0,      -- Palliative care
    dmishd_amount       DECIMAL(15,2) DEFAULT 0,      -- DMISHD
    pp_amount           DECIMAL(15,2) DEFAULT 0,      -- PP
    fs_amount           DECIMAL(15,2) DEFAULT 0,      -- FS
    opbkk_amount        DECIMAL(15,2) DEFAULT 0,      -- OPBKK

    total_receivable    DECIMAL(15,2) DEFAULT 0,      -- พึงรับทั้งหมด
    covid_amount        DECIMAL(15,2) DEFAULT 0,      -- COVID
    data_source         VARCHAR(20),                  -- แหล่งข้อมูล (FDH, ECLAIM-ONLINE, NHSO)

    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_stm_rep_data_type CHECK (data_type IN ('normal', 'appeal', 'disabled_d1')),
    FOREIGN KEY (file_id) REFERENCES stm_imported_files(id) ON DELETE CASCADE,
    INDEX idx_stm_rep_summary_file (file_id),
    INDEX idx_stm_rep_summary_rep (rep_no),
    INDEX idx_stm_rep_summary_hcode (hcode),
    INDEX idx_stm_rep_summary_period (period),
    UNIQUE INDEX idx_stm_rep_summary_unique (file_id, rep_no, data_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 4. STM CLAIM ITEM (รายละเอียด)
-- Individual patient claim details - main reconciliation table
-- Links to REP data via tran_id
-- ============================================================================
CREATE TABLE IF NOT EXISTS stm_claim_item (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    file_id             INT NOT NULL,
    `row_number`        INT,                          -- Row in Excel file
    data_type           VARCHAR(20) NOT NULL,         -- normal, appeal, disabled_d1

    -- Identifiers
    rep_no              VARCHAR(20),                  -- REP document number
    seq                 INT,                          -- ลำดับที่
    tran_id             VARCHAR(20),                  -- TRAN_ID - KEY LINK TO REP DATA

    -- Patient info
    hn                  VARCHAR(20),                  -- HN
    an                  VARCHAR(20),                  -- AN
    pid                 VARCHAR(20),                  -- เลขประจำตัวประชาชน
    patient_name        VARCHAR(255),                 -- ชื่อ - สกุล

    -- Admission dates
    date_admit          DATETIME,                     -- วันเข้ารักษา
    date_discharge      DATETIME,                     -- วันจำหน่าย

    -- Insurance info
    main_inscl          VARCHAR(10),                  -- MAININSCL
    proj_code           VARCHAR(50),                  -- PROJCODE

    -- Claim amounts
    amount_claimed      DECIMAL(15,2) DEFAULT 0,      -- เรียกเก็บ
    fund_ip_prb         DECIMAL(15,2) DEFAULT 0,      -- กองทุน IP พรบ.
    adjrw               DECIMAL(10,4) DEFAULT 0,      -- AdjRW
    late_penalty        DECIMAL(5,2) DEFAULT 0,       -- ล่าช้า (PS)
    ccuf                DECIMAL(10,4) DEFAULT 0,      -- CCUF
    adjrw2              DECIMAL(10,4) DEFAULT 0,      -- AdjRW2
    payment_rate        DECIMAL(15,2) DEFAULT 0,      -- อัตราจ่าย
    salary_deduction    DECIMAL(15,2) DEFAULT 0,      -- เงินเดือน
    paid_after_deduction DECIMAL(15,2) DEFAULT 0,     -- จ่ายชดเชยหลังหัก พรบ.และเงินเดือน

    -- Receivable breakdown (พึงรับ)
    receivable_op       DECIMAL(15,2) DEFAULT 0,      -- พึงรับ OP
    receivable_ip_calc  DECIMAL(15,2) DEFAULT 0,      -- พึงรับ IP ยอดชดเชยที่คำนวณได้
    receivable_ip_paid  DECIMAL(15,2) DEFAULT 0,      -- พึงรับ IP ยอดชดเชยที่จ่ายจริง

    -- Fund breakdown
    hc_amount           DECIMAL(15,2) DEFAULT 0,      -- HC
    hc_drug             DECIMAL(15,2) DEFAULT 0,      -- HC_DRUG
    ae_amount           DECIMAL(15,2) DEFAULT 0,      -- AE
    ae_drug             DECIMAL(15,2) DEFAULT 0,      -- AE_DRUG
    inst_amount         DECIMAL(15,2) DEFAULT 0,      -- INST
    dmis_calc           DECIMAL(15,2) DEFAULT 0,      -- DMIS ยอดชดเชยที่คำนวณได้
    dmis_paid           DECIMAL(15,2) DEFAULT 0,      -- DMIS ยอดชดเชยที่จ่ายจริง
    dmis_drug           DECIMAL(15,2) DEFAULT 0,      -- DMIS_DRUG
    palliative_care     DECIMAL(15,2) DEFAULT 0,      -- Palliative care
    dmishd_amount       DECIMAL(15,2) DEFAULT 0,      -- DMISHD
    pp_amount           DECIMAL(15,2) DEFAULT 0,      -- PP
    fs_amount           DECIMAL(15,2) DEFAULT 0,      -- FS
    opbkk_amount        DECIMAL(15,2) DEFAULT 0,      -- OPBKK

    -- Totals
    total_compensation  DECIMAL(15,2) DEFAULT 0,      -- ยอดชดเชยทั้งสิ้น
    va_amount           DECIMAL(15,2) DEFAULT 0,      -- VA
    covid_amount        DECIMAL(15,2) DEFAULT 0,      -- COVID

    -- Metadata
    data_source         VARCHAR(20),                  -- แหล่งข้อมูล (FDH, ECLAIM-ONLINE, NHSO)
    seq_no              VARCHAR(20),                  -- SEQ NO

    -- Reconciliation fields
    rep_matched         BOOLEAN DEFAULT FALSE,        -- Whether matched with REP data
    rep_tran_id         INT,                          -- FK to claim_rep_opip_nhso_item.id
    reconcile_status    VARCHAR(20),                  -- matched, amount_diff, missing_rep, missing_stm
    reconcile_diff      DECIMAL(15,2),                -- Difference between REP and STM amounts
    reconcile_date      DATETIME,                     -- When reconciliation was done

    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    CONSTRAINT chk_stm_claim_data_type CHECK (data_type IN ('normal', 'appeal', 'disabled_d1')),
    FOREIGN KEY (file_id) REFERENCES stm_imported_files(id) ON DELETE CASCADE,
    INDEX idx_stm_claim_file (file_id),
    INDEX idx_stm_claim_tran_id (tran_id),
    INDEX idx_stm_claim_rep_no (rep_no),
    INDEX idx_stm_claim_hn (hn),
    INDEX idx_stm_claim_pid (pid),
    INDEX idx_stm_claim_date (date_admit),
    INDEX idx_stm_claim_data_type (data_type),
    INDEX idx_stm_claim_reconcile (reconcile_status),
    INDEX idx_stm_claim_rep_matched (rep_matched),
    UNIQUE INDEX idx_stm_claim_unique (file_id, tran_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- ============================================================================
-- 5. RECONCILIATION VIEW
-- Join STM with REP data for easy reconciliation analysis
-- ============================================================================
CREATE OR REPLACE VIEW v_stm_rep_reconciliation AS
SELECT
    s.id AS stm_id,
    s.tran_id,
    s.hn,
    s.an,
    s.pid,
    s.patient_name,
    s.date_admit,
    s.date_discharge,
    s.amount_claimed AS stm_claimed,
    s.total_compensation AS stm_compensation,
    s.data_source AS stm_source,

    r.id AS rep_id,
    r.rep_no AS rep_repno,
    r.claim_net AS rep_claim_net,
    r.paid AS rep_paid,
    r.reimb_nhso AS rep_reimb_nhso,

    f.document_no,
    f.scheme,
    f.file_type,
    f.statement_month,
    f.statement_year,

    -- Reconciliation calculations
    CASE
        WHEN r.id IS NULL THEN 'missing_rep'
        WHEN s.total_compensation IS NULL THEN 'missing_stm'
        WHEN ABS(COALESCE(s.total_compensation, 0) - COALESCE(r.paid, 0)) < 1 THEN 'matched'
        ELSE 'amount_diff'
    END AS reconcile_status,
    COALESCE(s.total_compensation, 0) - COALESCE(r.paid, 0) AS amount_difference

FROM stm_claim_item s
LEFT JOIN claim_rep_opip_nhso_item r ON s.tran_id = r.tran_id
LEFT JOIN stm_imported_files f ON s.file_id = f.id
WHERE s.data_type IN ('normal', 'appeal');

-- ============================================================================
-- 6. SUMMARY STATISTICS VIEW
-- Quick statistics for dashboard
-- ============================================================================
CREATE OR REPLACE VIEW v_stm_statistics AS
SELECT
    f.hospital_code,
    f.scheme,
    f.file_type,
    f.statement_year,
    f.statement_month,
    COUNT(DISTINCT f.id) AS file_count,
    SUM(r.rep_count) AS total_rep_count,
    SUM(r.patient_count) AS total_patient_count,
    SUM(r.total_paid) AS total_paid,
    SUM(r.net_receivable) AS total_net_receivable
FROM stm_imported_files f
LEFT JOIN stm_receivable_summary r ON f.id = r.file_id
WHERE f.status = 'completed'
GROUP BY f.hospital_code, f.scheme, f.file_type, f.statement_year, f.statement_month;

-- ============================================================================
-- 7. SMT BUDGET TRANSFERS TABLE
-- Stores payment data from NHSO Smart Money Transfer (SMT) system
-- ============================================================================
CREATE TABLE IF NOT EXISTS smt_budget_transfers (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    run_date            DATE,
    posting_date        VARCHAR(20),                    -- YYYYMMDD format in Buddhist Era
    batch_no            VARCHAR(20),
    ref_doc_no          VARCHAR(50),
    vendor_no           VARCHAR(20),
    fund_name           VARCHAR(100),
    fund_group          INT,
    fund_group_desc     VARCHAR(100),
    fund_desc           VARCHAR(200),
    efund_desc          VARCHAR(200),
    mou_grp_code        VARCHAR(20),
    amount              DECIMAL(15,2) DEFAULT 0,
    wait_amount         DECIMAL(15,2) DEFAULT 0,
    debt_amount         DECIMAL(15,2) DEFAULT 0,
    bond_amount         DECIMAL(15,2) DEFAULT 0,
    total_amount        DECIMAL(15,2) DEFAULT 0,
    bank_name           VARCHAR(100),
    payment_status      VARCHAR(10),
    budget_source       VARCHAR(10),
    moph_id             VARCHAR(50),
    moph_desc           VARCHAR(200),
    created_at          DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY idx_smt_budget_unique (ref_doc_no, vendor_no, posting_date, mou_grp_code),
    INDEX idx_smt_budget_posting_date (posting_date),
    INDEX idx_smt_budget_vendor (vendor_no),
    INDEX idx_smt_budget_fund_group (fund_group_desc)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
