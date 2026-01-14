-- =============================================================================
-- E-Claim Database Schema - PostgreSQL Merged Version
-- Based on hospital's existing schema with tracking capabilities
-- Created: 2026-01-08
-- =============================================================================

-- ============================================================================
-- 1. IMPORT TRACKING TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_imported_files (
    id                  SERIAL PRIMARY KEY,
    filename            VARCHAR(255) NOT NULL UNIQUE,
    file_type           VARCHAR(20) NOT NULL,
    hospital_code       VARCHAR(10) NOT NULL,
    file_date           DATE,
    file_sequence       VARCHAR(20),
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    total_records       INTEGER DEFAULT 0,
    imported_records    INTEGER DEFAULT 0,
    failed_records      INTEGER DEFAULT 0,
    file_created_at     TIMESTAMP,
    import_started_at   TIMESTAMP,
    import_completed_at TIMESTAMP,
    error_message       TEXT,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT chk_file_type CHECK (file_type IN ('OP', 'IP', 'OPLGO', 'IPLGO', 'OPSSS', 'IPSSS', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO', 'OP_APPEAL')),
    CONSTRAINT chk_status CHECK (status IN ('pending', 'processing', 'completed', 'failed', 'partial'))
);

CREATE INDEX idx_imported_files_type ON eclaim_imported_files(file_type);
CREATE INDEX idx_imported_files_status ON eclaim_imported_files(status);
CREATE INDEX idx_imported_files_date ON eclaim_imported_files(file_date);

-- Trigger for updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER tr_imported_files_updated
    BEFORE UPDATE ON eclaim_imported_files
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 2. OP/IP CLAIMS TABLE
-- ============================================================================
CREATE TABLE claim_rep_opip_nhso_item (
  id SERIAL PRIMARY KEY,
  file_id INTEGER,
  row_number INTEGER,
  rep_no VARCHAR(15),
  seq INTEGER,
  tran_id VARCHAR(15),
  hn VARCHAR(15),
  an VARCHAR(15),
  pid VARCHAR(20),
  name VARCHAR(100),
  ptype VARCHAR(5),
  dateadm TIMESTAMP,
  datedsc TIMESTAMP,
  reimb_nhso DECIMAL(10,2),
  reimb_agency DECIMAL(10,2),
  claim_from VARCHAR(50),
  error_code VARCHAR(100),
  main_fund VARCHAR(100),
  sub_fund VARCHAR(100),
  service_type VARCHAR(2),
  chk_refer VARCHAR(1),
  chk_right VARCHAR(1),
  chk_use_right VARCHAR(1),
  chk VARCHAR(1),
  main_inscl VARCHAR(5),
  sub_inscl VARCHAR(5),
  href VARCHAR(10),
  hcode VARCHAR(10),
  hmain VARCHAR(10),
  prov1 VARCHAR(5),
  rg1 VARCHAR(5),
  hmain2 VARCHAR(10),
  prov2 VARCHAR(5),
  rg2 VARCHAR(5),
  hmain3 VARCHAR(10),
  da VARCHAR(1),
  projcode VARCHAR(100),
  pa VARCHAR(1),
  drg VARCHAR(10),
  rw DECIMAL(7,4),
  ca_type VARCHAR(5),
  claim_drg DECIMAL(10,2),
  claim_xdrg DECIMAL(10,2),
  claim_net DECIMAL(10,2),
  claim_central_reimb DECIMAL(10,2),
  paid DECIMAL(10,2),
  pay_point DECIMAL(10,2),
  ps_chk VARCHAR(1),
  ps_percent VARCHAR(5),
  ccuf DECIMAL(7,4),
  adjrw_nhso DECIMAL(7,4),
  adjrw2 DECIMAL(7,4),
  reimb_amt DECIMAL(10,2),
  act_amt DECIMAL(10,2),
  salary_rate VARCHAR(5),
  salary_amt DECIMAL(10,2),
  reimb_diff_salary DECIMAL(10,2),
  iphc DECIMAL(10,2),
  ophc DECIMAL(10,2),
  ae_opae DECIMAL(10,2),
  ae_ipnb DECIMAL(10,2),
  ae_ipuc DECIMAL(10,2),
  ae_ip3sss DECIMAL(10,2),
  ae_ip7sss DECIMAL(10,2),
  ae_carae DECIMAL(10,2),
  ae_caref DECIMAL(10,2),
  ae_caref_puc DECIMAL(10,2),
  opinst DECIMAL(10,2),
  inst DECIMAL(10,2),
  ipaec DECIMAL(10,2),
  ipaer DECIMAL(10,2),
  ipinrgc DECIMAL(10,2),
  ipinrgr DECIMAL(10,2),
  ipinspsn DECIMAL(10,2),
  ipprcc DECIMAL(10,2),
  ipprcc_puc DECIMAL(10,2),
  ipbkk_inst DECIMAL(10,2),
  ip_ontop DECIMAL(10,2),
  cataract_amt DECIMAL(10,2),
  cataract_oth DECIMAL(10,2),
  cataract_hosp DECIMAL(10,2),
  dmis_catinst DECIMAL(10,2),
  dmisrc_amt DECIMAL(10,2),
  dmisrc_workload DECIMAL(10,2),
  rcuhosc_amt DECIMAL(10,2),
  rcuhosc_workload DECIMAL(10,2),
  rcuhosr_amt DECIMAL(10,2),
  rcuhosr_workload DECIMAL(10,2),
  dmis_llop DECIMAL(10,2),
  dmis_llrgc DECIMAL(10,2),
  dmis_llrgr DECIMAL(10,2),
  dmis_lp DECIMAL(10,2),
  dmis_stroke_drug DECIMAL(10,2),
  dmis_dmidml DECIMAL(10,2),
  dmis_pp DECIMAL(10,2),
  dmis_dmishd DECIMAL(10,2),
  dmis_dmicnt DECIMAL(10,2),
  dmis_paliative DECIMAL(10,2),
  dmis_dm DECIMAL(10,2),
  drug DECIMAL(10,2),
  opbkk_hc DECIMAL(10,2),
  opbkk_dent DECIMAL(10,2),
  opbkk_drug DECIMAL(10,2),
  opbkk_fs DECIMAL(10,2),
  opbkk_others DECIMAL(10,2),
  opbkk_hsub VARCHAR(100),
  opbkk_nhso VARCHAR(100),
  deny_hc VARCHAR(10),
  deny_ae VARCHAR(10),
  deny_inst VARCHAR(10),
  deny_ip VARCHAR(10),
  deny_dmis VARCHAR(10),
  baserate_old DECIMAL(10,2),
  baserate_add DECIMAL(10,2),
  baserate_total DECIMAL(10,2),
  fs DECIMAL(10,2),
  va DECIMAL(10,2),
  remark VARCHAR(100),
  audit_results VARCHAR(255),
  payment_type VARCHAR(255),
  seq_no VARCHAR(15),
  invoice_no VARCHAR(20),
  invoice_lt VARCHAR(20),
  inp_id INTEGER,
  inp_date TIMESTAMP,
  lastupdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  his_matched BOOLEAN DEFAULT FALSE,
  his_matched_at TIMESTAMP,
  his_vn VARCHAR(20),
  his_amount_diff DECIMAL(10,2),
  reconcile_status VARCHAR(20),
  reconcile_note TEXT,
  CONSTRAINT uq_opip_tran_file UNIQUE (tran_id, file_id),
  CONSTRAINT fk_opip_file FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);

CREATE INDEX idx_opip_file_id ON claim_rep_opip_nhso_item(file_id);
CREATE INDEX idx_opip_rep_no ON claim_rep_opip_nhso_item(rep_no, tran_id);
CREATE INDEX idx_opip_hn ON claim_rep_opip_nhso_item(hn);
CREATE INDEX idx_opip_pid ON claim_rep_opip_nhso_item(pid);
CREATE INDEX idx_opip_dateadm ON claim_rep_opip_nhso_item(dateadm);
CREATE INDEX idx_opip_an ON claim_rep_opip_nhso_item(an);
CREATE INDEX idx_opip_tran_id ON claim_rep_opip_nhso_item(tran_id);
CREATE INDEX idx_opip_error_code ON claim_rep_opip_nhso_item(error_code);
CREATE INDEX idx_opip_reconcile ON claim_rep_opip_nhso_item(his_matched, reconcile_status);

-- Trigger for updated_at
CREATE TRIGGER tr_opip_updated
    BEFORE UPDATE ON claim_rep_opip_nhso_item
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 3. OP REFER TABLE
-- ============================================================================
CREATE TABLE claim_rep_orf_nhso_item (
  id SERIAL PRIMARY KEY,
  file_id INTEGER,
  row_number INTEGER,
  rep_no VARCHAR(15),
  no INTEGER,
  tran_id VARCHAR(15),
  hn VARCHAR(15),
  pid VARCHAR(20),
  name VARCHAR(100),
  service_date TIMESTAMP,
  refer_no VARCHAR(20),
  htype1 VARCHAR(5),
  prov1 VARCHAR(5),
  hcode VARCHAR(100),
  htype2 VARCHAR(5),
  prov2 VARCHAR(5),
  hmain2 VARCHAR(100),
  href VARCHAR(100),
  dx VARCHAR(10),
  proc VARCHAR(10),
  dmis VARCHAR(100),
  hmain3 VARCHAR(100),
  dar VARCHAR(100),
  ca_type VARCHAR(5),
  claim_amt DECIMAL(10,2),
  central_reimb_case VARCHAR(20),
  central_reimb_amt DECIMAL(10,2),
  paid DECIMAL(10,2),
  act_amt DECIMAL(10,2),
  opref_list DECIMAL(10,2),
  opref_bef_adj DECIMAL(10,2),
  opref_aft_adj DECIMAL(10,2),
  total DECIMAL(10,2),
  respon_cup DECIMAL(10,2),
  respon_nhso DECIMAL(10,2),
  reimb_total DECIMAL(10,2),
  pay_by VARCHAR(50),
  ps VARCHAR(1),
  cr_ophc_hc01 DECIMAL(10,2),
  cr_ophc_hc02 DECIMAL(10,2),
  cr_ophc_hc03 DECIMAL(10,2),
  cr_ophc_hc04 DECIMAL(10,2),
  cr_ophc_hc05 DECIMAL(10,2),
  cr_ophc_hc06 DECIMAL(10,2),
  cr_ophc_hc07 DECIMAL(10,2),
  cr_ophc_hc08 DECIMAL(10,2),
  cr_ae04 DECIMAL(10,2),
  cr_carae_ae08 DECIMAL(10,2),
  cr_opinst_hc09 DECIMAL(10,2),
  cr_dmisrc_amt DECIMAL(10,2),
  cr_dmisrc_workload DECIMAL(10,2),
  cr_rcuhosc_amt DECIMAL(10,2),
  cr_rcuhosc_workload DECIMAL(10,2),
  cr_rcuhosr_amt DECIMAL(10,2),
  cr_rcuhosr_workload DECIMAL(10,2),
  cr_llop DECIMAL(10,2),
  cr_lp DECIMAL(10,2),
  cr_stroke_drug DECIMAL(10,2),
  cr_dmidml DECIMAL(10,2),
  cr_pp DECIMAL(10,2),
  cr_dmishd DECIMAL(10,2),
  cr_paliative DECIMAL(10,2),
  cr_drug DECIMAL(10,2),
  cr_ontop DECIMAL(10,2),
  cr_total DECIMAL(10,2),
  cr_by VARCHAR(100),
  oprefer_md01_claim DECIMAL(10,2),
  oprefer_md01_free DECIMAL(10,2),
  oprefer_md02_claim DECIMAL(10,2),
  oprefer_md02_free DECIMAL(10,2),
  oprefer_md03_claim DECIMAL(10,2),
  oprefer_md03_free DECIMAL(10,2),
  oprefer_md04_claim DECIMAL(10,2),
  oprefer_md04_free DECIMAL(10,2),
  oprefer_md05_claim DECIMAL(10,2),
  oprefer_md05_free DECIMAL(10,2),
  oprefer_md06_claim DECIMAL(10,2),
  oprefer_md06_free DECIMAL(10,2),
  oprefer_md07_claim DECIMAL(10,2),
  oprefer_md07_free DECIMAL(10,2),
  oprefer_md08_claim DECIMAL(10,2),
  oprefer_md08_free DECIMAL(10,2),
  oprefer_md09_claim DECIMAL(10,2),
  oprefer_md09_free DECIMAL(10,2),
  oprefer_md10_claim DECIMAL(10,2),
  oprefer_md10_free DECIMAL(10,2),
  oprefer_md11_claim DECIMAL(10,2),
  oprefer_md11_free DECIMAL(10,2),
  oprefer_md12_claim DECIMAL(10,2),
  oprefer_md12_free DECIMAL(10,2),
  oprefer_md13_claim DECIMAL(10,2),
  oprefer_md13_free DECIMAL(10,2),
  oprefer_md14_claim DECIMAL(10,2),
  oprefer_md14_free DECIMAL(10,2),
  oprefer_md15_claim DECIMAL(10,2),
  oprefer_md15_free DECIMAL(10,2),
  oprefer_md16_claim DECIMAL(10,2),
  oprefer_md16_free DECIMAL(10,2),
  oprefer_md17_claim DECIMAL(10,2),
  oprefer_md17_free DECIMAL(10,2),
  oprefer_md18_claim DECIMAL(10,2),
  oprefer_md18_free DECIMAL(10,2),
  oprefer_md19_claim DECIMAL(10,2),
  oprefer_md19_free DECIMAL(10,2),
  error_code VARCHAR(100),
  va DECIMAL(10,2),
  remark VARCHAR(100),
  audit_results VARCHAR(255),
  payment_type VARCHAR(255),
  seq_no VARCHAR(15),
  invoice_no VARCHAR(20),
  invoice_lt VARCHAR(20),
  inp_id INTEGER,
  inp_date TIMESTAMP,
  lastupdate TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  scheme VARCHAR(10),
  his_matched BOOLEAN DEFAULT FALSE,
  his_matched_at TIMESTAMP,
  his_vn VARCHAR(20),
  his_amount_diff DECIMAL(10,2),
  reconcile_status VARCHAR(20),
  reconcile_note TEXT,
  CONSTRAINT uq_orf_tran_file UNIQUE (tran_id, file_id),
  CONSTRAINT fk_orf_file FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);

CREATE INDEX idx_orf_file_id ON claim_rep_orf_nhso_item(file_id);
CREATE INDEX idx_orf_rep_no ON claim_rep_orf_nhso_item(rep_no, tran_id);
CREATE INDEX idx_orf_hn ON claim_rep_orf_nhso_item(hn);
CREATE INDEX idx_orf_pid ON claim_rep_orf_nhso_item(pid);
CREATE INDEX idx_orf_service_date ON claim_rep_orf_nhso_item(service_date);
CREATE INDEX idx_orf_scheme ON claim_rep_orf_nhso_item(scheme);
CREATE INDEX idx_orf_reconcile ON claim_rep_orf_nhso_item(his_matched, reconcile_status);

-- Trigger for updated_at
CREATE TRIGGER tr_orf_updated
    BEFORE UPDATE ON claim_rep_orf_nhso_item
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- 4. VIEWS
-- ============================================================================

CREATE OR REPLACE VIEW v_daily_claim_summary AS
SELECT
    DATE(c.dateadm) as service_date,
    c.ptype,
    c.main_inscl,
    COUNT(*) as claim_count,
    SUM(c.reimb_nhso) as total_reimbursement,
    SUM(CASE WHEN c.error_code IS NOT NULL AND c.error_code != '-' THEN 1 ELSE 0 END) as error_count,
    SUM(CASE WHEN c.his_matched THEN 1 ELSE 0 END) as matched_count
FROM claim_rep_opip_nhso_item c
GROUP BY DATE(c.dateadm), c.ptype, c.main_inscl
ORDER BY service_date DESC, ptype, main_inscl;

CREATE OR REPLACE VIEW v_unmatched_claims AS
SELECT
    c.id,
    c.tran_id,
    c.hn,
    c.an,
    c.pid,
    c.name,
    c.ptype,
    c.dateadm,
    c.datedsc,
    c.reimb_nhso,
    c.error_code,
    f.filename,
    f.file_date
FROM claim_rep_opip_nhso_item c
LEFT JOIN eclaim_imported_files f ON c.file_id = f.id
WHERE c.his_matched = FALSE
ORDER BY c.dateadm DESC;

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
-- 5. SUMMARY TABLE (from Summary sheet)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_summary (
    id SERIAL PRIMARY KEY,
    file_id INTEGER,
    rep_period VARCHAR(20),
    hcode VARCHAR(10),
    rep_no VARCHAR(20),
    file_type VARCHAR(10),

    -- จำนวนราย (ข้อมูลปกติ)
    total_cases INTEGER DEFAULT 0,
    passed_cases INTEGER DEFAULT 0,
    failed_cases INTEGER DEFAULT 0,

    -- HC (Health Center)
    hc_claim DECIMAL(15,2) DEFAULT 0,
    hc_reimb DECIMAL(15,2) DEFAULT 0,

    -- AE (Accident & Emergency)
    ae_claim DECIMAL(15,2) DEFAULT 0,
    ae_reimb DECIMAL(15,2) DEFAULT 0,

    -- INST (Instrument)
    inst_claim DECIMAL(15,2) DEFAULT 0,
    inst_reimb DECIMAL(15,2) DEFAULT 0,

    -- IP (Inpatient)
    ip_claim DECIMAL(15,2) DEFAULT 0,
    ip_reimb DECIMAL(15,2) DEFAULT 0,

    -- DMIS (Disease Management)
    dmis_claim DECIMAL(15,2) DEFAULT 0,
    dmis_reimb DECIMAL(15,2) DEFAULT 0,

    -- PP (Prevention & Promotion)
    pp_claim DECIMAL(15,2) DEFAULT 0,
    pp_reimb DECIMAL(15,2) DEFAULT 0,

    -- DRUG
    drug_claim DECIMAL(15,2) DEFAULT 0,
    drug_reimb DECIMAL(15,2) DEFAULT 0,

    -- Totals
    reimb_agency DECIMAL(15,2) DEFAULT 0,
    reimb_total DECIMAL(15,2) DEFAULT 0,

    -- อุทธรณ์
    appeal_reimb DECIMAL(15,2) DEFAULT 0,
    appeal_add DECIMAL(15,2) DEFAULT 0,
    appeal_refund DECIMAL(15,2) DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_summary_file FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);

CREATE INDEX idx_summary_file_id ON eclaim_summary(file_id);
CREATE INDEX idx_summary_rep_period ON eclaim_summary(rep_period);
CREATE INDEX idx_summary_hcode ON eclaim_summary(hcode);

-- ============================================================================
-- 6. DRUG ITEMS TABLE (from Data Drug sheet)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_drug (
    id SERIAL PRIMARY KEY,
    file_id INTEGER,
    row_number INTEGER,

    -- ข้อมูลผู้ป่วย
    tran_id VARCHAR(20),
    hn VARCHAR(15),
    an VARCHAR(20),
    dateadm DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),

    -- ข้อมูลยา
    drug_seq INTEGER,
    drug_code VARCHAR(20),
    tmt_code VARCHAR(10),
    generic_name VARCHAR(200),
    trade_name VARCHAR(100),
    drug_type VARCHAR(10),
    drug_category VARCHAR(50),
    dosage_form VARCHAR(50),

    -- ข้อมูลการเงิน
    quantity DECIMAL(10,2) DEFAULT 0,
    unit_price DECIMAL(15,2) DEFAULT 0,
    claim_amount DECIMAL(15,2) DEFAULT 0,
    ceiling_price DECIMAL(15,2) DEFAULT 0,
    reimb_amount DECIMAL(15,2) DEFAULT 0,
    reimb_agency DECIMAL(15,2) DEFAULT 0,

    error_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_drug_file FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);

CREATE INDEX idx_drug_file_id ON eclaim_drug(file_id);
CREATE INDEX idx_drug_tran_id ON eclaim_drug(tran_id);
CREATE INDEX idx_drug_hn ON eclaim_drug(hn);
CREATE INDEX idx_drug_tmt ON eclaim_drug(tmt_code);
CREATE INDEX idx_drug_dateadm ON eclaim_drug(dateadm);

-- ============================================================================
-- 7. INSTRUMENT ITEMS TABLE (from Data Instrument sheet - IP only)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_instrument (
    id SERIAL PRIMARY KEY,
    file_id INTEGER,
    row_number INTEGER,

    -- ข้อมูลผู้ป่วย
    tran_id VARCHAR(20),
    hn VARCHAR(15),
    an VARCHAR(20),
    dateadm DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),

    -- ข้อมูลอุปกรณ์
    inst_seq INTEGER,
    inst_code VARCHAR(10),
    inst_name VARCHAR(200),

    -- เรียกเก็บ
    claim_qty INTEGER DEFAULT 0,
    claim_amount DECIMAL(15,2) DEFAULT 0,

    -- จ่ายชดเชย
    reimb_qty INTEGER DEFAULT 0,
    reimb_amount DECIMAL(15,2) DEFAULT 0,

    deny_flag VARCHAR(10),
    error_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_instrument_file FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);

CREATE INDEX idx_instrument_file_id ON eclaim_instrument(file_id);
CREATE INDEX idx_instrument_tran_id ON eclaim_instrument(tran_id);
CREATE INDEX idx_instrument_hn ON eclaim_instrument(hn);
CREATE INDEX idx_instrument_code ON eclaim_instrument(inst_code);
CREATE INDEX idx_instrument_dateadm ON eclaim_instrument(dateadm);

-- ============================================================================
-- 8. DENY ITEMS TABLE (from Data DENY sheet - IP only)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_deny (
    id SERIAL PRIMARY KEY,
    file_id INTEGER,
    row_number INTEGER,

    -- ข้อมูลผู้ป่วย
    tran_id VARCHAR(20),
    hcode VARCHAR(10),
    hn VARCHAR(15),
    an VARCHAR(20),
    dateadm DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),

    -- ข้อมูลการปฏิเสธ
    fund_code VARCHAR(20),
    claim_code VARCHAR(20),
    expense_category INTEGER,
    claim_amount DECIMAL(15,2) DEFAULT 0,
    deny_code VARCHAR(20),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_deny_file FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);

CREATE INDEX idx_deny_file_id ON eclaim_deny(file_id);
CREATE INDEX idx_deny_tran_id ON eclaim_deny(tran_id);
CREATE INDEX idx_deny_hn ON eclaim_deny(hn);
CREATE INDEX idx_deny_code ON eclaim_deny(deny_code);
CREATE INDEX idx_deny_fund ON eclaim_deny(fund_code);
CREATE INDEX idx_deny_dateadm ON eclaim_deny(dateadm);

-- ============================================================================
-- 9. ZERO PAID ITEMS TABLE (from Data sheet 0)
-- ============================================================================
CREATE TABLE IF NOT EXISTS eclaim_zero_paid (
    id SERIAL PRIMARY KEY,
    file_id INTEGER,
    row_number INTEGER,

    -- ข้อมูลผู้ป่วย
    tran_id VARCHAR(20),
    hcode VARCHAR(10),
    hn VARCHAR(15),
    an VARCHAR(20),
    dateadm DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),

    -- ข้อมูลรายการ
    fund_code VARCHAR(20),
    claim_code VARCHAR(20),
    tmt_code VARCHAR(10),
    expense_category INTEGER,
    claim_qty INTEGER DEFAULT 0,
    paid_qty INTEGER DEFAULT 0,
    paid_amount DECIMAL(15,2) DEFAULT 0,
    reason VARCHAR(200),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_zero_paid_file FOREIGN KEY (file_id) REFERENCES eclaim_imported_files(id) ON DELETE SET NULL
);

CREATE INDEX idx_zero_paid_file_id ON eclaim_zero_paid(file_id);
CREATE INDEX idx_zero_paid_tran_id ON eclaim_zero_paid(tran_id);
CREATE INDEX idx_zero_paid_hn ON eclaim_zero_paid(hn);
CREATE INDEX idx_zero_paid_fund ON eclaim_zero_paid(fund_code);
CREATE INDEX idx_zero_paid_dateadm ON eclaim_zero_paid(dateadm);

-- ============================================================================
-- 10. ADDITIONAL VIEWS FOR NEW TABLES
-- ============================================================================

-- Drug Analytics View
CREATE OR REPLACE VIEW v_drug_analytics AS
SELECT
    d.tmt_code,
    d.generic_name,
    d.drug_type,
    COUNT(*) as prescription_count,
    SUM(d.quantity) as total_quantity,
    SUM(d.claim_amount) as total_claim,
    SUM(d.reimb_amount) as total_reimb,
    AVG(d.unit_price) as avg_unit_price,
    COUNT(CASE WHEN d.error_code IS NOT NULL AND d.error_code != '' THEN 1 END) as error_count
FROM eclaim_drug d
GROUP BY d.tmt_code, d.generic_name, d.drug_type
ORDER BY total_claim DESC;

-- Deny Analytics View
CREATE OR REPLACE VIEW v_deny_analytics AS
SELECT
    d.deny_code,
    d.fund_code,
    COUNT(*) as deny_count,
    SUM(d.claim_amount) as total_denied_amount,
    COUNT(DISTINCT d.tran_id) as affected_cases
FROM eclaim_deny d
GROUP BY d.deny_code, d.fund_code
ORDER BY deny_count DESC;

-- Instrument Analytics View
CREATE OR REPLACE VIEW v_instrument_analytics AS
SELECT
    i.inst_code,
    i.inst_name,
    COUNT(*) as usage_count,
    SUM(i.claim_qty) as total_claim_qty,
    SUM(i.claim_amount) as total_claim,
    SUM(i.reimb_qty) as total_reimb_qty,
    SUM(i.reimb_amount) as total_reimb,
    ROUND(SUM(i.reimb_amount) * 100.0 / NULLIF(SUM(i.claim_amount), 0), 2) as approval_rate
FROM eclaim_instrument i
GROUP BY i.inst_code, i.inst_name
ORDER BY total_claim DESC;

-- Monthly Summary View
CREATE OR REPLACE VIEW v_monthly_summary AS
SELECT
    s.rep_period,
    s.file_type,
    SUM(s.total_cases) as total_cases,
    SUM(s.passed_cases) as passed_cases,
    SUM(s.failed_cases) as failed_cases,
    SUM(s.hc_claim + s.ae_claim + s.inst_claim + s.ip_claim + s.dmis_claim + s.pp_claim + s.drug_claim) as total_claim,
    SUM(s.hc_reimb + s.ae_reimb + s.inst_reimb + s.ip_reimb + s.dmis_reimb + s.pp_reimb + s.drug_reimb) as total_reimb,
    SUM(s.reimb_total) as grand_total
FROM eclaim_summary s
GROUP BY s.rep_period, s.file_type
ORDER BY s.rep_period DESC;

-- ============================================================================
-- HEALTH OFFICES MASTER DATA (from hcode.moph.go.th)
-- ============================================================================
CREATE TABLE IF NOT EXISTS health_offices (
    id                      SERIAL PRIMARY KEY,
    name                    VARCHAR(500) NOT NULL,
    hcode9_new              VARCHAR(20),           -- รหัส 9 หลักใหม่
    hcode9                  VARCHAR(20),           -- รหัส 9 หลัก
    hcode5                  VARCHAR(10),           -- รหัส 5 หลัก (vendor_id)
    license_no              VARCHAR(20),           -- เลขอนุญาตให้ประกอบสถานบริการสุขภาพ 11 หลัก
    org_type                VARCHAR(100),          -- ประเภทองค์กร
    service_type            VARCHAR(200),          -- ประเภทหน่วยบริการสุขภาพ
    affiliation             VARCHAR(200),          -- สังกัด
    department              VARCHAR(200),          -- แผนก/กรม
    hospital_level          VARCHAR(100),          -- ระดับโรงพยาบาล
    actual_beds             INTEGER DEFAULT 0,     -- เตียงที่ใช้จริง
    status                  VARCHAR(50),           -- สถานะการใช้งาน
    health_region           VARCHAR(50),           -- เขตบริการ
    address                 TEXT,                  -- ที่อยู่
    province_code           VARCHAR(10),           -- รหัสจังหวัด
    province                VARCHAR(100),          -- จังหวัด
    district_code           VARCHAR(10),           -- รหัสอำเภอ
    district                VARCHAR(100),          -- อำเภอ/เขต
    subdistrict_code        VARCHAR(10),           -- รหัสตำบล
    subdistrict             VARCHAR(100),          -- ตำบล/แขวง
    moo                     VARCHAR(10),           -- หมู่
    postal_code             VARCHAR(10),           -- รหัสไปรษณีย์
    parent_code             VARCHAR(100),          -- แม่ข่าย (can be text, not just code)
    established_date        DATE,                  -- วันที่ก่อตั้ง
    closed_date             DATE,                  -- วันที่ปิดบริการ
    source_updated_at       DATE,                  -- อัพเดตล่าสุด(เริ่ม 05/09/2566)
    created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_health_offices_hcode5 UNIQUE (hcode5)
);

-- Indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_health_offices_hcode5 ON health_offices(hcode5);
CREATE INDEX IF NOT EXISTS idx_health_offices_hcode9 ON health_offices(hcode9);
CREATE INDEX IF NOT EXISTS idx_health_offices_province ON health_offices(province_code);
CREATE INDEX IF NOT EXISTS idx_health_offices_status ON health_offices(status);
CREATE INDEX IF NOT EXISTS idx_health_offices_level ON health_offices(hospital_level);
CREATE INDEX IF NOT EXISTS idx_health_offices_region ON health_offices(health_region);
CREATE INDEX IF NOT EXISTS idx_health_offices_name ON health_offices(name);

-- Trigger for updated_at
CREATE TRIGGER tr_health_offices_updated
    BEFORE UPDATE ON health_offices
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Import tracking for health offices
CREATE TABLE IF NOT EXISTS health_offices_import_log (
    id              SERIAL PRIMARY KEY,
    import_date     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filename        VARCHAR(255),
    total_records   INTEGER DEFAULT 0,
    imported        INTEGER DEFAULT 0,
    updated         INTEGER DEFAULT 0,
    skipped         INTEGER DEFAULT 0,
    errors          INTEGER DEFAULT 0,
    import_mode     VARCHAR(20) DEFAULT 'upsert',  -- 'upsert' or 'replace'
    status          VARCHAR(20) DEFAULT 'completed',
    error_message   TEXT,
    duration_seconds NUMERIC(10,2)
);

-- ============================================================================
-- END OF SCHEMA
-- ============================================================================
