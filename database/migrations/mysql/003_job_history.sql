-- Migration: Create job_history table for tracking all system jobs
-- MySQL version

CREATE TABLE IF NOT EXISTS job_history (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Job identification
    job_id VARCHAR(100) NOT NULL UNIQUE,  -- e.g., "download_20260114_103000"
    job_type VARCHAR(50) NOT NULL,         -- download, import, schedule
    job_subtype VARCHAR(50),               -- single, bulk, parallel, scheduled

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, completed, failed, cancelled

    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP NULL,
    duration_seconds INTEGER,

    -- Parameters (JSON)
    parameters JSON,  -- {month, year, schemes, auto_import, etc}

    -- Results (JSON)
    results JSON,     -- {total_files, success, failed, records, etc}

    -- Error info
    error_message TEXT,

    -- Source info
    triggered_by VARCHAR(50) DEFAULT 'manual',  -- manual, schedule, api

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    -- Indexes
    INDEX idx_job_history_type (job_type),
    INDEX idx_job_history_status (status),
    INDEX idx_job_history_started (started_at DESC),
    INDEX idx_job_history_type_status (job_type, status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Tracks all download, import, and scheduled job executions';
