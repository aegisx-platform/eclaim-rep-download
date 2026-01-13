-- Migration: Create download_history table (MySQL Version)
-- Purpose: Move download tracking from JSON files to database
-- Date: 2026-01-13

-- =====================================================
-- MySQL Version
-- =====================================================

-- Drop if exists (for clean migration)
DROP TABLE IF EXISTS download_history;

-- Create download_history table
CREATE TABLE download_history (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Download identification
    download_type VARCHAR(20) NOT NULL,      -- 'rep', 'stm', 'smt'
    filename VARCHAR(255) NOT NULL,
    document_no VARCHAR(100),                -- e.g., '10670_IPUCS256810_01'

    -- Classification
    scheme VARCHAR(20),                      -- 'ucs', 'ofc', 'sss', 'lgo'
    fiscal_year INT,                         -- Thai Buddhist year (e.g., 2569)
    service_month INT,                       -- 1-12
    patient_type VARCHAR(20),                -- 'ip', 'op', 'all'
    rep_no VARCHAR(50),                      -- REP number if applicable

    -- File info
    file_size BIGINT,
    file_path VARCHAR(500),
    file_hash VARCHAR(64),                   -- SHA256 hash for integrity check

    -- Status tracking
    downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    file_exists BOOLEAN DEFAULT TRUE,

    -- Import tracking (link to imported_files tables)
    imported BOOLEAN DEFAULT FALSE,
    imported_at TIMESTAMP NULL,
    import_file_id INT,                      -- FK to eclaim_imported_files or stm_imported_files
    import_table VARCHAR(50),                -- 'eclaim_imported_files' or 'stm_imported_files'

    -- Metadata
    source_url TEXT,
    download_params JSON,                    -- Store original download parameters
    error_message TEXT,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Constraints
    UNIQUE KEY uk_download_type_filename (download_type, filename)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Indexes for common queries
CREATE INDEX idx_download_history_type ON download_history(download_type);
CREATE INDEX idx_download_history_fiscal_year ON download_history(fiscal_year);
CREATE INDEX idx_download_history_scheme ON download_history(scheme);
CREATE INDEX idx_download_history_downloaded_at ON download_history(downloaded_at);
CREATE INDEX idx_download_history_imported ON download_history(imported);
CREATE INDEX idx_download_history_document_no ON download_history(document_no);
