-- Migration: Create download_history table for tracking downloaded files
-- PostgreSQL version

CREATE TABLE IF NOT EXISTS download_history (
    id                  SERIAL PRIMARY KEY,
    download_type       VARCHAR(20) NOT NULL,           -- REP, STM, SMT
    filename            VARCHAR(255) NOT NULL,
    document_no         VARCHAR(100),                   -- e.g., 10670_IPUCS256811_01
    scheme              VARCHAR(20),                    -- UCS, OFC, SSS, LGO
    fiscal_year         INTEGER,                        -- Buddhist Era year
    service_month       INTEGER,                        -- 1-12
    patient_type        VARCHAR(20),                    -- IP, OP
    rep_no              VARCHAR(50),                    -- REP number if applicable
    file_size           BIGINT,                         -- File size in bytes
    file_path           VARCHAR(500),                   -- Full path to downloaded file
    file_hash           VARCHAR(64),                    -- MD5/SHA256 hash for deduplication
    downloaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_exists         BOOLEAN DEFAULT TRUE,           -- Whether file still exists on disk
    imported            BOOLEAN DEFAULT FALSE,          -- Whether file has been imported
    imported_at         TIMESTAMP,                      -- When file was imported
    import_file_id      INTEGER,                        -- FK to eclaim_imported_files.id
    import_table        VARCHAR(50),                    -- Which table data was imported to
    source_url          TEXT,                           -- Original download URL
    download_params     JSONB,                          -- Parameters used for download
    error_message       TEXT,                           -- Any error during download
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_download_history_type ON download_history(download_type);
CREATE INDEX IF NOT EXISTS idx_download_history_document ON download_history(document_no);
CREATE INDEX IF NOT EXISTS idx_download_history_scheme ON download_history(scheme);
CREATE INDEX IF NOT EXISTS idx_download_history_fiscal_year ON download_history(fiscal_year);
CREATE INDEX IF NOT EXISTS idx_download_history_downloaded ON download_history(downloaded_at);
CREATE INDEX IF NOT EXISTS idx_download_history_imported ON download_history(imported);
-- Unique constraint on (download_type, filename) for UPSERT operations
CREATE UNIQUE INDEX IF NOT EXISTS idx_download_history_type_filename ON download_history(download_type, filename);

COMMENT ON TABLE download_history IS 'Track all downloaded files from NHSO systems';
