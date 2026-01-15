-- =============================================================================
-- STM (Statement) Database Schema - PostgreSQL
-- For NHSO Statement Import and Reconciliation with REP data
-- Created: 2026-01-12
-- =============================================================================

-- ============================================================================
-- 1. STM IMPORT TRACKING TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS stm_imported_files (
    id                  SERIAL PRIMARY KEY,
    filename            VARCHAR(255) NOT NULL UNIQUE,
    file_type           VARCHAR(20) NOT NULL,          -- IP_STM, OP_STM
    scheme              VARCHAR(10) NOT NULL,          -- UCS, OFC, SSS, LGO
    hospital_code       VARCHAR(10) NOT NULL,
    hospital_name       VARCHAR(255),
    province_code       VARCHAR(10),
    province_name       VARCHAR(100),
    document_no         VARCHAR(50),                   -- เลขที่เอกสาร e.g., 10670_IPUCS256811_01
    statement_month     INTEGER,                       -- เดือนที่ออก statement
    statement_year      INTEGER,                       -- ปีที่ออก statement (Buddhist Era)
    report_date         TIMESTAMP,                     -- วันที่ออกรายงาน
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_records       INTEGER DEFAULT 0,
    imported_records    INTEGER DEFAULT 0,
    failed_records      INTEGER DEFAULT 0,
    import_started_at   TIMESTAMP,
    import_completed_at TIMESTAMP,
    error_message       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_stm_file_type CHECK (file_type IN ('IP_STM', 'OP_STM')),
    CONSTRAINT chk_stm_scheme CHECK (scheme IN ('UCS', 'OFC', 'SSS', 'LGO')),
    CONSTRAINT chk_stm_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'partial'))
);

CREATE INDEX idx_stm_files_type ON stm_imported_files(file_type);
CREATE INDEX idx_stm_files_scheme ON stm_imported_files(scheme);
CREATE INDEX idx_stm_files_hospital ON stm_imported_files(hospital_code);
CREATE INDEX idx_stm_files_status ON stm_imported_files(status);
CREATE INDEX idx_stm_files_document ON stm_imported_files(document_no);
CREATE INDEX idx_stm_files_month_year ON stm_imported_files(statement_year, statement_month);

-- Trigger for updated_at (reuse existing function if exists)
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_proc WHERE proname = 'update_updated_at_column') THEN
        CREATE FUNCTION update_updated_at_column()
        RETURNS TRIGGER AS $func$
        BEGIN
            NEW.updated_at = CURRENT_TIMESTAMP;
            RETURN NEW;
        END;
        $func$ LANGUAGE plpgsql;
    END IF;
END;
$$;

CREATE TRIGGER tr_stm_files_updated
    BEFORE UPDATE ON stm_imported_files
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 2. STM RECEIVABLE SUMMARY (รายงานพึงรับ)
-- High-level totals per statement file
-- ============================================================================
CREATE TABLE IF NOT EXISTS stm_receivable_summary (
    id                  SERIAL PRIMARY KEY,
    file_id             INTEGER NOT NULL REFERENCES stm_imported_files(id) ON DELETE CASCADE,
    data_type           VARCHAR(20) NOT NULL,         -- normal, appeal, disabled_d1
    patient_type        VARCHAR(20) NOT NULL,         -- inpatient (ผู้ป่วยใน), outpatient (ผู้ป่วยนอก)
    rep_count           INTEGER DEFAULT 0,            -- จำนวน REP ที่ส่ง
    patient_count       INTEGER DEFAULT 0,            -- จำนวนราย (ผ่าน A)
    total_adjrw         DECIMAL(15,4) DEFAULT 0,      -- ผลรวม ADJRW
    total_paid          DECIMAL(15,2) DEFAULT 0,      -- จ่ายชดเชย
    salary_deduction    DECIMAL(15,2) DEFAULT 0,      -- ยอดหักเงินเดือน สป.
    adjrw_paid_deduction DECIMAL(15,2) DEFAULT 0,     -- ยอดหักเงินเดือน adjrw paid*380
    net_receivable      DECIMAL(15,2) DEFAULT 0,      -- รวม (พึงรับสุทธิ)
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_stm_data_type CHECK (data_type IN ('normal', 'appeal', 'disabled_d1')),
    CONSTRAINT chk_stm_patient_type CHECK (patient_type IN ('inpatient', 'outpatient'))
);

CREATE INDEX idx_stm_receivable_file ON stm_receivable_summary(file_id);
CREATE INDEX idx_stm_receivable_type ON stm_receivable_summary(data_type, patient_type);

-- ============================================================================
-- 3. STM REP SUMMARY (รายงานสรุป)
-- Summary by REP number - bridges Statement and REP files
-- ============================================================================
CREATE TABLE IF NOT EXISTS stm_rep_summary (
    id                  SERIAL PRIMARY KEY,
    file_id             INTEGER NOT NULL REFERENCES stm_imported_files(id) ON DELETE CASCADE,
    data_type           VARCHAR(20) NOT NULL,         -- normal, appeal, disabled_d1
    period              VARCHAR(20),                  -- งวด e.g., 6811_IP_01, 6811_OP_01
    hcode               VARCHAR(10),                  -- HCODE
    rep_no              VARCHAR(20),                  -- REP NO.
    claim_type          VARCHAR(20),                  -- ประเภท (ข้อมูลปกติ/ข้อมูลอุทธรณ์)
    total_passed        INTEGER DEFAULT 0,            -- ทั้งหมดที่ผ่าน
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

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_stm_rep_data_type CHECK (data_type IN ('normal', 'appeal', 'disabled_d1'))
);

CREATE INDEX idx_stm_rep_summary_file ON stm_rep_summary(file_id);
CREATE INDEX idx_stm_rep_summary_rep ON stm_rep_summary(rep_no);
CREATE INDEX idx_stm_rep_summary_hcode ON stm_rep_summary(hcode);
CREATE INDEX idx_stm_rep_summary_period ON stm_rep_summary(period);
CREATE UNIQUE INDEX idx_stm_rep_summary_unique ON stm_rep_summary(file_id, rep_no, data_type);

-- ============================================================================
-- 4. STM CLAIM ITEM (รายละเอียด)
-- Individual patient claim details - main reconciliation table
-- Links to REP data via tran_id
-- ============================================================================
CREATE TABLE IF NOT EXISTS stm_claim_item (
    id                  SERIAL PRIMARY KEY,
    file_id             INTEGER NOT NULL REFERENCES stm_imported_files(id) ON DELETE CASCADE,
    row_number          INTEGER,                      -- Row in Excel file
    data_type           VARCHAR(20) NOT NULL,         -- normal, appeal, disabled_d1

    -- Identifiers
    rep_no              VARCHAR(20),                  -- REP document number
    seq                 INTEGER,                      -- ลำดับที่
    tran_id             VARCHAR(20),                  -- TRAN_ID - KEY LINK TO REP DATA

    -- Patient info
    hn                  VARCHAR(20),                  -- HN
    an                  VARCHAR(20),                  -- AN
    pid                 VARCHAR(20),                  -- เลขประจำตัวประชาชน
    patient_name        VARCHAR(255),                 -- ชื่อ - สกุล

    -- Admission dates
    date_admit          TIMESTAMP,                    -- วันเข้ารักษา
    date_discharge      TIMESTAMP,                    -- วันจำหน่าย

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
    rep_tran_id         INTEGER,                      -- FK to claim_rep_opip_nhso_item.id
    reconcile_status    VARCHAR(20),                  -- matched, amount_diff, missing_rep, missing_stm
    reconcile_diff      DECIMAL(15,2),                -- Difference between REP and STM amounts
    reconcile_date      TIMESTAMP,                    -- When reconciliation was done

    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT chk_stm_claim_data_type CHECK (data_type IN ('normal', 'appeal', 'disabled_d1'))
);

-- Primary indexes for queries
CREATE INDEX idx_stm_claim_file ON stm_claim_item(file_id);
CREATE INDEX idx_stm_claim_tran_id ON stm_claim_item(tran_id);
CREATE INDEX idx_stm_claim_rep_no ON stm_claim_item(rep_no);
CREATE INDEX idx_stm_claim_hn ON stm_claim_item(hn);
CREATE INDEX idx_stm_claim_pid ON stm_claim_item(pid);
CREATE INDEX idx_stm_claim_date ON stm_claim_item(date_admit);
CREATE INDEX idx_stm_claim_data_type ON stm_claim_item(data_type);

-- Reconciliation indexes
CREATE INDEX idx_stm_claim_reconcile ON stm_claim_item(reconcile_status);
CREATE INDEX idx_stm_claim_rep_matched ON stm_claim_item(rep_matched);

-- Unique constraint for UPSERT
CREATE UNIQUE INDEX idx_stm_claim_unique ON stm_claim_item(file_id, tran_id);

-- Trigger for updated_at
CREATE TRIGGER tr_stm_claim_updated
    BEFORE UPDATE ON stm_claim_item
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

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
    id                  SERIAL PRIMARY KEY,
    run_date            DATE,
    posting_date        VARCHAR(20),                    -- YYYYMMDD format in Buddhist Era
    batch_no            VARCHAR(20),
    ref_doc_no          VARCHAR(50),
    vendor_no           VARCHAR(20),
    fund_name           VARCHAR(100),
    fund_group          INTEGER,
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
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_smt_budget_unique ON smt_budget_transfers(ref_doc_no, vendor_no, posting_date, mou_grp_code);
CREATE INDEX IF NOT EXISTS idx_smt_budget_posting_date ON smt_budget_transfers(posting_date);
CREATE INDEX IF NOT EXISTS idx_smt_budget_vendor ON smt_budget_transfers(vendor_no);
CREATE INDEX IF NOT EXISTS idx_smt_budget_fund_group ON smt_budget_transfers(fund_group_desc);

-- ============================================================================
-- COMMENTS
-- ============================================================================
COMMENT ON TABLE stm_imported_files IS 'Track imported STM (Statement) files from NHSO';
COMMENT ON TABLE stm_receivable_summary IS 'High-level summary from รายงานพึงรับ sheet';
COMMENT ON TABLE stm_rep_summary IS 'Summary by REP number from รายงานสรุป sheet';
COMMENT ON TABLE stm_claim_item IS 'Individual claim details from รายละเอียด sheets, links to REP via tran_id';
COMMENT ON TABLE smt_budget_transfers IS 'Payment data from NHSO Smart Money Transfer (SMT) system for reconciliation';

COMMENT ON COLUMN stm_claim_item.tran_id IS 'Transaction ID - primary key for joining with claim_rep_opip_nhso_item';
COMMENT ON COLUMN stm_claim_item.rep_matched IS 'Whether this STM record has been matched with REP data';
COMMENT ON COLUMN stm_claim_item.reconcile_status IS 'Reconciliation status: matched, amount_diff, missing_rep, missing_stm';
COMMENT ON COLUMN stm_claim_item.reconcile_diff IS 'Amount difference between STM and REP (positive = STM higher)';
