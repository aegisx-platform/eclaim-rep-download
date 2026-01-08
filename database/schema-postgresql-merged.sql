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
    CONSTRAINT chk_file_type CHECK (file_type IN ('OP', 'IP', 'ORF', 'IP_APPEAL', 'IP_APPEAL_NHSO')),
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
-- END OF SCHEMA
-- ============================================================================
