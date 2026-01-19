-- Add ORF_APPEAL file type to check constraint
-- Migration: 013_add_orf_appeal_file_type.sql
-- Date: 2026-01-19
-- Description: Add ORF_APPEAL and missing file types to eclaim_imported_files.file_type constraint

-- Create constraint with all file types found in database
-- Note: constraint doesn't exist yet due to migration 007 MySQL syntax issue
ALTER TABLE eclaim_imported_files ADD CONSTRAINT chk_file_type CHECK (file_type IN (
    'OP', 'IP',
    'OPLGO', 'IPLGO',
    'OPSSS', 'IPSSS',
    'ORF', 'ORFLGO', 'ORFSSS',
    'ORF_APPEAL',
    'IP_APPEAL', 'IP_APPEAL_NHSO', 'IP_APPEAL_CD',
    'OP_APPEAL', 'OP_APPEAL_CD', 'OP_APPEAL_NHSO',
    'OPBMT', 'IPBMT',
    'OPBKK', 'IPBKK',
    'OPCS',
    'OPNHS', 'IPNHS',
    'OPOFC', 'IPOFC',
    'OPLGO_APPEAL'
));
