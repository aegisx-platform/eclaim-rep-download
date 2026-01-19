-- =============================================================================
-- Migration: 012_download_sessions
-- Description: Download Manager - Session tracking tables (MySQL version)
-- Date: 2026-01-18
-- =============================================================================

-- Download Sessions: Track each download run
CREATE TABLE IF NOT EXISTS download_sessions (
    id              VARCHAR(36) PRIMARY KEY,
    source_type     VARCHAR(20) NOT NULL,
    status          VARCHAR(20) NOT NULL,

    fiscal_year     INT,
    service_month   INT,
    scheme          VARCHAR(20),
    params          JSON,

    total_discovered    INT DEFAULT 0,
    already_downloaded  INT DEFAULT 0,
    to_download         INT DEFAULT 0,
    retry_failed        INT DEFAULT 0,

    processed       INT DEFAULT 0,
    downloaded      INT DEFAULT 0,
    skipped         INT DEFAULT 0,
    failed          INT DEFAULT 0,

    max_workers     INT DEFAULT 1,
    worker_info     JSON,

    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at      DATETIME,
    completed_at    DATETIME,
    updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    cancellable     BOOLEAN DEFAULT TRUE,
    resumable       BOOLEAN DEFAULT TRUE,
    cancelled_at    DATETIME,
    resume_count    INT DEFAULT 0,

    error_message   TEXT,
    error_details   JSON,

    triggered_by    VARCHAR(50),
    notes           TEXT,

    INDEX idx_ds_source_type (source_type),
    INDEX idx_ds_status (status),
    INDEX idx_ds_created (created_at DESC),
    INDEX idx_ds_fiscal_year (fiscal_year)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Download Files: Track individual files in a session
CREATE TABLE IF NOT EXISTS download_session_files (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL,

    filename        VARCHAR(255) NOT NULL,
    file_url        TEXT,
    file_type       VARCHAR(20),

    status          VARCHAR(20) NOT NULL,
    skip_reason     VARCHAR(50),

    file_size       BIGINT,
    file_path       VARCHAR(500),
    file_hash       VARCHAR(64),

    queued_at       DATETIME DEFAULT CURRENT_TIMESTAMP,
    started_at      DATETIME,
    completed_at    DATETIME,

    worker_id       INT,
    worker_name     VARCHAR(50),

    retry_count     INT DEFAULT 0,
    error_message   TEXT,

    source_metadata JSON,

    FOREIGN KEY (session_id) REFERENCES download_sessions(id) ON DELETE CASCADE,
    INDEX idx_dsf_session (session_id),
    INDEX idx_dsf_status (status),
    INDEX idx_dsf_filename (filename),
    UNIQUE INDEX idx_dsf_session_file (session_id, filename)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Session Events: Audit trail for debugging
CREATE TABLE IF NOT EXISTS download_session_events (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id      VARCHAR(36) NOT NULL,

    event_type      VARCHAR(50) NOT NULL,
    event_data      JSON,

    created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (session_id) REFERENCES download_sessions(id) ON DELETE CASCADE,
    INDEX idx_dse_session (session_id),
    INDEX idx_dse_type (event_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
