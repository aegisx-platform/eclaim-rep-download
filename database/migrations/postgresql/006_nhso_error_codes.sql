-- NHSO Error Codes Master Data
-- Reference table for error codes from NHSO e-claim system
-- NOTE: Drop and recreate to ensure correct structure for seed data importer

DROP TABLE IF EXISTS nhso_error_codes CASCADE;

CREATE TABLE nhso_error_codes (
    id SERIAL PRIMARY KEY,
    code VARCHAR(20) NOT NULL,
    type VARCHAR(30) NOT NULL DEFAULT '',
    description VARCHAR(500),
    guide TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_nhso_error_code UNIQUE (code)
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_nhso_error_code ON nhso_error_codes(code);
CREATE INDEX IF NOT EXISTS idx_nhso_error_type ON nhso_error_codes(type);
CREATE INDEX IF NOT EXISTS idx_nhso_error_active ON nhso_error_codes(is_active);

-- Trigger for updated_at
DROP TRIGGER IF EXISTS tr_nhso_error_codes_updated ON nhso_error_codes;
CREATE TRIGGER tr_nhso_error_codes_updated
    BEFORE UPDATE ON nhso_error_codes
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

COMMENT ON TABLE nhso_error_codes IS 'NHSO Error Codes - Master data for e-claim error codes';
COMMENT ON COLUMN nhso_error_codes.code IS 'Error code from NHSO';
COMMENT ON COLUMN nhso_error_codes.type IS 'Error type (e.g., Corrective, Warning)';
COMMENT ON COLUMN nhso_error_codes.description IS 'Error description in Thai';
COMMENT ON COLUMN nhso_error_codes.guide IS 'Resolution guide in Thai';
