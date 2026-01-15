-- Additional tables for PostgreSQL (summary, drug, instrument, deny, zero_paid)

CREATE TABLE IF NOT EXISTS eclaim_summary (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id) ON DELETE SET NULL,
    rep_period VARCHAR(20),
    hcode VARCHAR(10),
    rep_no VARCHAR(20),
    file_type VARCHAR(10),
    total_cases INTEGER DEFAULT 0,
    passed_cases INTEGER DEFAULT 0,
    failed_cases INTEGER DEFAULT 0,
    hc_claim DECIMAL(15,2) DEFAULT 0,
    hc_reimb DECIMAL(15,2) DEFAULT 0,
    ae_claim DECIMAL(15,2) DEFAULT 0,
    ae_reimb DECIMAL(15,2) DEFAULT 0,
    inst_claim DECIMAL(15,2) DEFAULT 0,
    inst_reimb DECIMAL(15,2) DEFAULT 0,
    ip_claim DECIMAL(15,2) DEFAULT 0,
    ip_reimb DECIMAL(15,2) DEFAULT 0,
    dmis_claim DECIMAL(15,2) DEFAULT 0,
    dmis_reimb DECIMAL(15,2) DEFAULT 0,
    pp_claim DECIMAL(15,2) DEFAULT 0,
    pp_reimb DECIMAL(15,2) DEFAULT 0,
    drug_claim DECIMAL(15,2) DEFAULT 0,
    drug_reimb DECIMAL(15,2) DEFAULT 0,
    reimb_agency DECIMAL(15,2) DEFAULT 0,
    reimb_total DECIMAL(15,2) DEFAULT 0,
    appeal_reimb DECIMAL(15,2) DEFAULT 0,
    appeal_add DECIMAL(15,2) DEFAULT 0,
    appeal_refund DECIMAL(15,2) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eclaim_drug (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id) ON DELETE SET NULL,
    row_number INTEGER,
    tran_id VARCHAR(20),
    hn VARCHAR(15),
    an VARCHAR(20),
    dateadm DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),
    drug_seq INTEGER,
    drug_code VARCHAR(20),
    tmt_code VARCHAR(10),
    generic_name VARCHAR(200),
    trade_name VARCHAR(100),
    drug_type VARCHAR(10),
    drug_category VARCHAR(50),
    dosage_form VARCHAR(50),
    quantity DECIMAL(10,2) DEFAULT 0,
    unit_price DECIMAL(15,2) DEFAULT 0,
    claim_amount DECIMAL(15,2) DEFAULT 0,
    ceiling_price DECIMAL(15,2) DEFAULT 0,
    reimb_amount DECIMAL(15,2) DEFAULT 0,
    reimb_agency DECIMAL(15,2) DEFAULT 0,
    error_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eclaim_instrument (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id) ON DELETE SET NULL,
    row_number INTEGER,
    tran_id VARCHAR(20),
    hn VARCHAR(15),
    an VARCHAR(20),
    dateadm DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),
    inst_seq INTEGER,
    inst_code VARCHAR(10),
    inst_name VARCHAR(200),
    claim_qty INTEGER DEFAULT 0,
    claim_amount DECIMAL(15,2) DEFAULT 0,
    reimb_qty INTEGER DEFAULT 0,
    reimb_amount DECIMAL(15,2) DEFAULT 0,
    deny_flag VARCHAR(10),
    error_code VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eclaim_deny (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id) ON DELETE SET NULL,
    row_number INTEGER,
    tran_id VARCHAR(20),
    hcode VARCHAR(10),
    hn VARCHAR(15),
    an VARCHAR(20),
    dateadm DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),
    fund_code VARCHAR(20),
    claim_code VARCHAR(20),
    expense_category INTEGER,
    claim_amount DECIMAL(15,2) DEFAULT 0,
    deny_code VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS eclaim_zero_paid (
    id SERIAL PRIMARY KEY,
    file_id INTEGER REFERENCES eclaim_imported_files(id) ON DELETE SET NULL,
    row_number INTEGER,
    tran_id VARCHAR(20),
    hcode VARCHAR(10),
    hn VARCHAR(15),
    an VARCHAR(20),
    dateadm DATE,
    pid VARCHAR(13),
    patient_name VARCHAR(100),
    fund_code VARCHAR(20),
    claim_code VARCHAR(20),
    tmt_code VARCHAR(10),
    expense_category INTEGER,
    claim_qty INTEGER DEFAULT 0,
    paid_qty INTEGER DEFAULT 0,
    claim_amount DECIMAL(15,2) DEFAULT 0,
    paid_amount DECIMAL(15,2) DEFAULT 0,
    reason VARCHAR(200),
    error_code VARCHAR(50),
    deny_code VARCHAR(20),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_eclaim_summary_file_id ON eclaim_summary(file_id);
CREATE INDEX IF NOT EXISTS idx_eclaim_drug_file_id ON eclaim_drug(file_id);
CREATE INDEX IF NOT EXISTS idx_eclaim_drug_tran_id ON eclaim_drug(tran_id);
CREATE INDEX IF NOT EXISTS idx_eclaim_instrument_file_id ON eclaim_instrument(file_id);
CREATE INDEX IF NOT EXISTS idx_eclaim_instrument_tran_id ON eclaim_instrument(tran_id);
CREATE INDEX IF NOT EXISTS idx_eclaim_deny_file_id ON eclaim_deny(file_id);
CREATE INDEX IF NOT EXISTS idx_eclaim_deny_tran_id ON eclaim_deny(tran_id);
CREATE INDEX IF NOT EXISTS idx_eclaim_zero_paid_file_id ON eclaim_zero_paid(file_id);
CREATE INDEX IF NOT EXISTS idx_eclaim_zero_paid_tran_id ON eclaim_zero_paid(tran_id);
