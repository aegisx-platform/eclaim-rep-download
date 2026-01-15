-- Migration: Create alerts table for system notifications
-- MySQL version

CREATE TABLE IF NOT EXISTS system_alerts (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- Alert identification
    alert_type VARCHAR(50) NOT NULL,      -- job_failed, disk_warning, memory_warning, stale_process, db_error
    severity VARCHAR(20) NOT NULL,         -- info, warning, critical

    -- Alert content
    title VARCHAR(255) NOT NULL,
    message TEXT,

    -- Related entity
    related_type VARCHAR(50),              -- job, process, system
    related_id VARCHAR(100),               -- job_id or process name

    -- Status
    is_read BOOLEAN DEFAULT FALSE,
    is_dismissed BOOLEAN DEFAULT FALSE,

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    read_at TIMESTAMP NULL,
    dismissed_at TIMESTAMP NULL,

    -- Indexes
    INDEX idx_alerts_type (alert_type),
    INDEX idx_alerts_severity (severity),
    INDEX idx_alerts_unread (is_read, is_dismissed),
    INDEX idx_alerts_created (created_at DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='System alerts and notifications';
