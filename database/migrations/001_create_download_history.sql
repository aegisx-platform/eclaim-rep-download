-- Migration: Create download_history table
-- Purpose: Move download tracking from JSON files to database
-- Date: 2026-01-13

-- =====================================================
-- PostgreSQL Version
-- =====================================================

-- Drop if exists (for clean migration)
DROP TABLE IF EXISTS download_history CASCADE;

-- Create download_history table
CREATE TABLE download_history (
    id SERIAL PRIMARY KEY,

    -- Download identification
    download_type VARCHAR(20) NOT NULL,      -- 'rep', 'stm', 'smt'
    filename VARCHAR(255) NOT NULL,
    document_no VARCHAR(100),                -- e.g., '10670_IPUCS256810_01'

    -- Classification
    scheme VARCHAR(20),                      -- 'ucs', 'ofc', 'sss', 'lgo'
    fiscal_year INTEGER,                     -- Thai Buddhist year (e.g., 2569)
    service_month INTEGER,                   -- 1-12
    patient_type VARCHAR(20),                -- 'ip', 'op', 'all'
    rep_no VARCHAR(50),                      -- REP number if applicable

    -- File info
    file_size BIGINT,
    file_path VARCHAR(500),
    file_hash VARCHAR(64),                   -- SHA256 hash for integrity check

    -- Status tracking
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_exists BOOLEAN DEFAULT TRUE,
    download_status VARCHAR(20) DEFAULT 'success',  -- 'pending', 'downloading', 'success', 'failed'
    retry_count INTEGER DEFAULT 0,
    last_attempt_at TIMESTAMP,

    -- Import tracking (link to imported_files tables)
    imported BOOLEAN DEFAULT FALSE,
    imported_at TIMESTAMP,
    import_file_id INTEGER,                  -- FK to eclaim_imported_files or stm_imported_files
    import_table VARCHAR(50),                -- 'eclaim_imported_files' or 'stm_imported_files'

    -- Metadata
    source_url TEXT,
    download_params JSONB,                   -- Store original download parameters
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE(download_type, filename)
);

-- Indexes for common queries
CREATE INDEX idx_download_history_type ON download_history(download_type);
CREATE INDEX idx_download_history_fiscal_year ON download_history(fiscal_year);
CREATE INDEX idx_download_history_scheme ON download_history(scheme);
CREATE INDEX idx_download_history_downloaded_at ON download_history(downloaded_at);
CREATE INDEX idx_download_history_imported ON download_history(imported);
CREATE INDEX idx_download_history_document_no ON download_history(document_no);
CREATE INDEX idx_download_history_status ON download_history(download_status);

-- Trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_download_history_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_download_history_updated_at
    BEFORE UPDATE ON download_history
    FOR EACH ROW
    EXECUTE FUNCTION update_download_history_updated_at();

-- Comments
COMMENT ON TABLE download_history IS 'Track all downloaded files (REP, STM, SMT) - replaces JSON files';
COMMENT ON COLUMN download_history.download_type IS 'Type of download: rep, stm, smt';
COMMENT ON COLUMN download_history.document_no IS 'Document number from NHSO (e.g., 10670_IPUCS256810_01)';
COMMENT ON COLUMN download_history.fiscal_year IS 'Thai Buddhist fiscal year (e.g., 2569)';
COMMENT ON COLUMN download_history.file_exists IS 'Whether the physical file still exists on disk';
COMMENT ON COLUMN download_history.import_file_id IS 'Foreign key to imported_files table (polymorphic)';
COMMENT ON COLUMN download_history.import_table IS 'Name of import tracking table (eclaim_imported_files or stm_imported_files)';
