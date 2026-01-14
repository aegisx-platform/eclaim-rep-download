-- Migration: Create job_history table for tracking all system jobs
-- PostgreSQL version

CREATE TABLE IF NOT EXISTS job_history (
    id SERIAL PRIMARY KEY,

    -- Job identification
    job_id VARCHAR(100) NOT NULL UNIQUE,  -- e.g., "download_20260114_103000"
    job_type VARCHAR(50) NOT NULL,         -- download, import, schedule
    job_subtype VARCHAR(50),               -- single, bulk, parallel, scheduled

    -- Status tracking
    status VARCHAR(20) NOT NULL DEFAULT 'running',  -- running, completed, failed, cancelled

    -- Timing
    started_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds INTEGER,

    -- Parameters (JSON)
    parameters JSONB,  -- {month, year, schemes, auto_import, etc}

    -- Results (JSON)
    results JSONB,     -- {total_files, success, failed, records, etc}

    -- Error info
    error_message TEXT,

    -- Source info
    triggered_by VARCHAR(50) DEFAULT 'manual',  -- manual, schedule, api

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_job_history_type ON job_history(job_type);
CREATE INDEX IF NOT EXISTS idx_job_history_status ON job_history(status);
CREATE INDEX IF NOT EXISTS idx_job_history_started ON job_history(started_at DESC);
CREATE INDEX IF NOT EXISTS idx_job_history_type_status ON job_history(job_type, status);

-- Comments
COMMENT ON TABLE job_history IS 'Tracks all download, import, and scheduled job executions';
COMMENT ON COLUMN job_history.job_type IS 'Type: download, import, schedule';
COMMENT ON COLUMN job_history.job_subtype IS 'Subtype: single, bulk, parallel, scheduled';
COMMENT ON COLUMN job_history.parameters IS 'Job parameters as JSON';
COMMENT ON COLUMN job_history.results IS 'Job results as JSON';
