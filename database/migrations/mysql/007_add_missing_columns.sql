-- Migration: Add missing columns for SSS, LGO, and other fund type files
-- These columns are required for OPSSS, IPSSS, OPLGO, IPLGO, OPBMT, IPBMT, OPBKK, IPBKK, etc.

-- SSS (Social Security Scheme) specific columns
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN claim_case VARCHAR(50) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN htype VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN ae_status VARCHAR(50) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN iptype VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN hsend VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN claim_request DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN total_service_amt DECIMAL(12,2) DEFAULT NULL;

-- SSS Amount breakdown columns
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN ip_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN op_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN ae_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN hc_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN int_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN on_top_amt DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN pp_amt DECIMAL(12,2) DEFAULT NULL;

-- LGO (Local Government Organizations) specific columns
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN org_code VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN org_name VARCHAR(255) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN claim_able DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN claim_unable DECIMAL(12,2) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN case_type VARCHAR(50) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN ors VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN ps_percent2 VARCHAR(20) DEFAULT NULL;

-- Common columns used in various file types
-- Note: deny_count is VARCHAR to handle values like 'C' in some file types
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN deny_count VARCHAR(20) DEFAULT NULL;
ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN audit_result VARCHAR(100) DEFAULT NULL;

-- Update file_type check constraint to include new fund types
-- Drop the old constraint if it exists
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
