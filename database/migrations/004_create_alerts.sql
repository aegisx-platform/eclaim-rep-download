-- Migration: Create alerts table for system notifications
-- PostgreSQL version

CREATE TABLE IF NOT EXISTS system_alerts (
    id SERIAL PRIMARY KEY,

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
    read_at TIMESTAMP,
    dismissed_at TIMESTAMP
);

-- Indexes
CREATE INDEX IF NOT EXISTS idx_alerts_type ON system_alerts(alert_type);
CREATE INDEX IF NOT EXISTS idx_alerts_severity ON system_alerts(severity);
CREATE INDEX IF NOT EXISTS idx_alerts_unread ON system_alerts(is_read, is_dismissed);
CREATE INDEX IF NOT EXISTS idx_alerts_created ON system_alerts(created_at DESC);

-- Comments
COMMENT ON TABLE system_alerts IS 'System alerts and notifications';
COMMENT ON COLUMN system_alerts.alert_type IS 'Type: job_failed, disk_warning, memory_warning, stale_process, db_error';
COMMENT ON COLUMN system_alerts.severity IS 'Severity: info, warning, critical';
