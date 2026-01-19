-- Migration: Create download_history table for tracking downloaded files
-- MySQL version

CREATE TABLE IF NOT EXISTS download_history (
    id                  INT AUTO_INCREMENT PRIMARY KEY,
    download_type       VARCHAR(20) NOT NULL,           -- REP, STM, SMT
    filename            VARCHAR(255) NOT NULL,
    document_no         VARCHAR(100),                   -- e.g., 10670_IPUCS256811_01
    scheme              VARCHAR(20),                    -- UCS, OFC, SSS, LGO
    fiscal_year         INT,                            -- Buddhist Era year
    service_month       INT,                            -- 1-12
    patient_type        VARCHAR(20),                    -- IP, OP
    rep_no              VARCHAR(50),                    -- REP number if applicable
    file_size           BIGINT,                         -- File size in bytes
    file_path           VARCHAR(500),                   -- Full path to downloaded file
    file_hash           VARCHAR(64),                    -- MD5/SHA256 hash for deduplication
    downloaded_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_exists         BOOLEAN DEFAULT TRUE,           -- Whether file still exists on disk
    imported            BOOLEAN DEFAULT FALSE,          -- Whether file has been imported
    imported_at         TIMESTAMP NULL,                 -- When file was imported
    import_file_id      INT,                            -- FK to eclaim_imported_files.id
    import_table        VARCHAR(50),                    -- Which table data was imported to
    source_url          TEXT,                           -- Original download URL
    download_params     JSON,                           -- Parameters used for download
    error_message       TEXT,                           -- Any error during download
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_download_history_type (download_type),
    INDEX idx_download_history_document (document_no),
    INDEX idx_download_history_scheme (scheme),
    INDEX idx_download_history_fiscal_year (fiscal_year),
    INDEX idx_download_history_downloaded (downloaded_at),
    INDEX idx_download_history_imported (imported),
    -- Unique constraint on (download_type, filename) for UPSERT operations
    UNIQUE INDEX idx_download_history_type_filename (download_type, filename)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Track all downloaded files from NHSO systems';
