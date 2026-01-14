-- Migration: Add scheme column to claim_rep_orf_nhso_item
-- Purpose: Enable filtering ORF data by insurance scheme (UCS, OFC, SSS, LGO)
-- Date: 2026-01-14

-- =====================================================
-- PostgreSQL Version
-- =====================================================

-- Add scheme column to ORF table
ALTER TABLE claim_rep_orf_nhso_item
ADD COLUMN IF NOT EXISTS scheme VARCHAR(10);

-- Add index for efficient filtering
CREATE INDEX IF NOT EXISTS idx_orf_scheme ON claim_rep_orf_nhso_item(scheme);

-- Add comment
COMMENT ON COLUMN claim_rep_orf_nhso_item.scheme IS 'Insurance scheme: UCS, OFC, SSS, LGO (derived from file_type or filename)';

-- =====================================================
-- Update existing records based on file_type
-- =====================================================

-- Update scheme based on eclaim_imported_files.file_type
UPDATE claim_rep_orf_nhso_item orf
SET scheme = CASE
    WHEN f.file_type IN ('ORF', 'OP', 'IP') THEN 'UCS'
    WHEN f.file_type LIKE '%LGO%' THEN 'LGO'
    WHEN f.file_type LIKE '%SSS%' THEN 'SSS'
    WHEN f.file_type LIKE '%OFC%' THEN 'OFC'
    ELSE 'UCS'
END
FROM eclaim_imported_files f
WHERE orf.file_id = f.id
AND orf.scheme IS NULL;

-- =====================================================
-- MySQL Version (for reference)
-- =====================================================
--
-- ALTER TABLE claim_rep_orf_nhso_item
-- ADD COLUMN scheme VARCHAR(10) DEFAULT NULL;
--
-- CREATE INDEX idx_orf_scheme ON claim_rep_orf_nhso_item(scheme);
--
-- UPDATE claim_rep_orf_nhso_item orf
-- JOIN eclaim_imported_files f ON orf.file_id = f.id
-- SET orf.scheme = CASE
--     WHEN f.file_type IN ('ORF', 'OP', 'IP') THEN 'UCS'
--     WHEN f.file_type LIKE '%LGO%' THEN 'LGO'
--     WHEN f.file_type LIKE '%SSS%' THEN 'SSS'
--     WHEN f.file_type LIKE '%OFC%' THEN 'OFC'
--     ELSE 'UCS'
-- END
-- WHERE orf.scheme IS NULL;
