-- Migration: Add missing columns for SSS, LGO, and other fund type files
-- These columns are required for OPSSS, IPSSS, OPLGO, IPLGO, OPBMT, IPBMT, OPBKK, IPBKK, etc.

-- SSS (Social Security Scheme) specific columns
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS claim_case VARCHAR(50) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS htype VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS ae_status VARCHAR(50) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS iptype VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS hsend VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS claim_request DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS total_service_amt DECIMAL(12,2) DEFAULT NULL;

-- SSS Amount breakdown columns
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS ip_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS op_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS ae_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS hc_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS int_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS on_top_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS pp_amt DECIMAL(12,2) DEFAULT NULL;

-- LGO (Local Government Organizations) specific columns
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS org_code VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS org_name VARCHAR(255) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS claim_able DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS claim_unable DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS case_type VARCHAR(50) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS ors VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS ps_percent2 VARCHAR(20) DEFAULT NULL;

-- Common columns used in various file types
-- Note: deny_count is VARCHAR to handle values like 'C' in some file types
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS deny_count VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN IF NOT EXISTS audit_result VARCHAR(100) DEFAULT NULL;

-- Add indexes for commonly queried columns
CREATE INDEX IF NOT EXISTS idx_claim_case ON claim_rep_opip_nhso_item(claim_case);
CREATE INDEX IF NOT EXISTS idx_org_code ON claim_rep_opip_nhso_item(org_code);

-- Update file_type check constraint to include new fund types
-- First drop the old constraint if it exists
ALTER TABLE eclaim_imported_files DROP CONSTRAINT IF EXISTS chk_file_type;
ALTER TABLE eclaim_imported_files ADD CONSTRAINT chk_file_type CHECK (file_type IN (
    'OP', 'IP',
    'OPLGO', 'IPLGO',
    'OPSSS', 'IPSSS',
    'ORF', 'ORFLGO', 'ORFSSS',
    'IP_APPEAL', 'IP_APPEAL_NHSO',
    'OP_APPEAL', 'OP_APPEAL_CD',
    'OPBMT', 'IPBMT',
    'OPBKK', 'IPBKK',
    'OPNHS', 'IPNHS',
    'OPOFC', 'IPOFC'
));
