-- Migration: Add scheme column to claim_rep_opip_nhso_item
-- Date: 2026-01-15
-- Description: Add scheme column to track insurance scheme (UCS, LGO, SSS, OFC)

-- ============================================================================
-- PostgreSQL Migration
-- ============================================================================

-- Add scheme column if not exists
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_name = 'claim_rep_opip_nhso_item'
        AND column_name = 'scheme'
    ) THEN
        ALTER TABLE claim_rep_opip_nhso_item ADD COLUMN scheme VARCHAR(10);
        CREATE INDEX idx_opip_scheme ON claim_rep_opip_nhso_item(scheme);
        RAISE NOTICE 'Added scheme column to claim_rep_opip_nhso_item';
    ELSE
        RAISE NOTICE 'scheme column already exists in claim_rep_opip_nhso_item';
    END IF;
END $$;

-- Update existing records with default scheme based on main_inscl
UPDATE claim_rep_opip_nhso_item
SET scheme = CASE
    WHEN main_inscl IN ('LGO', 'อปท') THEN 'LGO'
    WHEN main_inscl IN ('SSS', 'ประกันสังคม') THEN 'SSS'
    WHEN main_inscl IN ('OFC', 'ข้าราชการ') THEN 'OFC'
    ELSE 'UCS'
END
WHERE scheme IS NULL;

-- ============================================================================
-- MySQL Migration (run separately)
-- ============================================================================
/*
-- Check if column exists and add if not
SET @dbname = DATABASE();
SET @tablename = 'claim_rep_opip_nhso_item';
SET @columnname = 'scheme';
SET @preparedStatement = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS
     WHERE TABLE_SCHEMA = @dbname AND TABLE_NAME = @tablename AND COLUMN_NAME = @columnname) > 0,
    'SELECT 1',
    CONCAT('ALTER TABLE ', @tablename, ' ADD COLUMN ', @columnname, ' VARCHAR(10) DEFAULT NULL COMMENT ''Insurance scheme: UCS, LGO, SSS, OFC''')
));
PREPARE alterIfNotExists FROM @preparedStatement;
EXECUTE alterIfNotExists;
DEALLOCATE PREPARE alterIfNotExists;

-- Add index
CREATE INDEX idx_scheme ON claim_rep_opip_nhso_item(scheme);

-- Update existing records
UPDATE claim_rep_opip_nhso_item
SET scheme = CASE
    WHEN main_inscl IN ('LGO', 'อปท') THEN 'LGO'
    WHEN main_inscl IN ('SSS', 'ประกันสังคม') THEN 'SSS'
    WHEN main_inscl IN ('OFC', 'ข้าราชการ') THEN 'OFC'
    ELSE 'UCS'
END
WHERE scheme IS NULL;
*/
