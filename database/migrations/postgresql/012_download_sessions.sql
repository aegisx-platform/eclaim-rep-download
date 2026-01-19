-- =============================================================================
-- Migration: 012_download_sessions
-- Description: Download Manager - Session tracking tables
-- Date: 2026-01-18
-- =============================================================================

-- Download Sessions: Track each download run
CREATE TABLE IF NOT EXISTS download_sessions (
    id              VARCHAR(36) PRIMARY KEY,      -- UUID
    source_type     VARCHAR(20) NOT NULL,         -- rep, stm, smt
    status          VARCHAR(20) NOT NULL,         -- pending, discovering, downloading,
                                                  -- completed, failed, cancelled

    -- Parameters
    fiscal_year     INTEGER,
    service_month   INTEGER,
    scheme          VARCHAR(20),
    params          JSONB,                        -- Additional source-specific params

    -- Discovery Results
    total_discovered    INTEGER DEFAULT 0,
    already_downloaded  INTEGER DEFAULT 0,
    to_download         INTEGER DEFAULT 0,
    retry_failed        INTEGER DEFAULT 0,

    -- Execution Results
    processed       INTEGER DEFAULT 0,
    downloaded      INTEGER DEFAULT 0,
    skipped         INTEGER DEFAULT 0,
    failed          INTEGER DEFAULT 0,

    -- Worker Info
    max_workers     INTEGER DEFAULT 1,
    worker_info     JSONB,                        -- Worker status array

    -- Timing
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,
    updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    -- Control
    cancellable     BOOLEAN DEFAULT TRUE,
    resumable       BOOLEAN DEFAULT TRUE,
    cancelled_at    TIMESTAMP,
    resume_count    INTEGER DEFAULT 0,

    -- Error Info
    error_message   TEXT,
    error_details   JSONB,

    -- Metadata
    triggered_by    VARCHAR(50),                  -- manual, scheduler, api
    notes           TEXT
);

-- Indexes for download_sessions
CREATE INDEX IF NOT EXISTS idx_ds_source_type ON download_sessions(source_type);
CREATE INDEX IF NOT EXISTS idx_ds_status ON download_sessions(status);
CREATE INDEX IF NOT EXISTS idx_ds_created ON download_sessions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_ds_fiscal_year ON download_sessions(fiscal_year);

-- Download Files: Track individual files in a session
CREATE TABLE IF NOT EXISTS download_session_files (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES download_sessions(id) ON DELETE CASCADE,

    -- File Info
    filename        VARCHAR(255) NOT NULL,
    file_url        TEXT,
    file_type       VARCHAR(20),                  -- OP, IP, ORF, etc.

    -- Status
    status          VARCHAR(20) NOT NULL,         -- pending, downloading, completed,
                                                  -- skipped, failed
    skip_reason     VARCHAR(50),                  -- already_exists, duplicate, etc.

    -- Result
    file_size       BIGINT,
    file_path       VARCHAR(500),
    file_hash       VARCHAR(64),

    -- Timing
    queued_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    started_at      TIMESTAMP,
    completed_at    TIMESTAMP,

    -- Worker
    worker_id       INTEGER,
    worker_name     VARCHAR(50),

    -- Retry
    retry_count     INTEGER DEFAULT 0,
    error_message   TEXT,

    -- Metadata
    source_metadata JSONB                         -- Original file info from source
);

-- Indexes for download_session_files
CREATE INDEX IF NOT EXISTS idx_dsf_session ON download_session_files(session_id);
CREATE INDEX IF NOT EXISTS idx_dsf_status ON download_session_files(status);
CREATE INDEX IF NOT EXISTS idx_dsf_filename ON download_session_files(filename);
CREATE UNIQUE INDEX IF NOT EXISTS idx_dsf_session_file ON download_session_files(session_id, filename);

-- Session Events: Audit trail for debugging
CREATE TABLE IF NOT EXISTS download_session_events (
    id              BIGSERIAL PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL REFERENCES download_sessions(id) ON DELETE CASCADE,

    event_type      VARCHAR(50) NOT NULL,
    event_data      JSONB,

    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_dse_session ON download_session_events(session_id);
CREATE INDEX IF NOT EXISTS idx_dse_type ON download_session_events(event_type);

-- Update updated_at trigger
CREATE OR REPLACE FUNCTION update_download_session_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_download_session_updated_at
    BEFORE UPDATE ON download_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_download_session_updated_at();
