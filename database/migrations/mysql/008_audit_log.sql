-- Migration 008: Audit Log System
-- Purpose: Track all data access and modifications for PDPA compliance
-- Date: 2026-01-17
-- CRITICAL SECURITY: Required for PDPA compliance and incident investigation

-- =============================================================================
-- AUDIT LOG TABLE
-- =============================================================================
-- Tracks all user actions for security and compliance
-- Immutable log (no updates/deletes allowed - enforced by triggers)

CREATE TABLE IF NOT EXISTS audit_log (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,

    -- Who (User identification)
    user_id VARCHAR(100),
    user_email VARCHAR(255),
    session_id VARCHAR(255),

    -- What (Action details)
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255),

    -- Details (Change tracking)
    old_data JSON,
    new_data JSON,
    changes_summary TEXT,

    -- Context (Request information)
    ip_address VARCHAR(45),
    user_agent TEXT,
    request_method VARCHAR(10),
    request_path TEXT,
    request_params JSON,

    -- Result
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,

    -- Timing
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    duration_ms INTEGER,

    -- Metadata
    metadata JSON,

    -- Constraints
    CONSTRAINT audit_log_action_check CHECK (action IN (
        'CREATE', 'READ', 'UPDATE', 'DELETE',
        'LOGIN', 'LOGOUT', 'LOGIN_FAILED',
        'EXPORT', 'IMPORT', 'DOWNLOAD',
        'SETTINGS_CHANGE', 'PERMISSION_CHANGE',
        'DATA_ACCESS', 'BULK_DELETE', 'BACKUP', 'RESTORE'
    )),

    -- Indexes
    INDEX idx_audit_log_user_id (user_id),
    INDEX idx_audit_log_timestamp (timestamp DESC),
    INDEX idx_audit_log_resource (resource_type, resource_id),
    INDEX idx_audit_log_action (action),
    INDEX idx_audit_log_status (status),
    INDEX idx_audit_log_ip_address (ip_address),
    INDEX idx_audit_log_session (session_id),
    INDEX idx_audit_log_user_time (user_id, timestamp DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- AUDIT LOG STATISTICS VIEW
-- =============================================================================

CREATE OR REPLACE VIEW audit_log_stats AS
SELECT
    COUNT(*) as total_events,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT DATE(timestamp)) as active_days,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_events,
    SUM(CASE WHEN status = 'denied' THEN 1 ELSE 0 END) as denied_events,
    SUM(CASE WHEN action = 'LOGIN' THEN 1 ELSE 0 END) as total_logins,
    SUM(CASE WHEN action = 'LOGIN_FAILED' THEN 1 ELSE 0 END) as failed_logins,
    SUM(CASE WHEN action IN ('CREATE', 'UPDATE', 'DELETE') THEN 1 ELSE 0 END) as data_changes,
    SUM(CASE WHEN action = 'EXPORT' THEN 1 ELSE 0 END) as data_exports,
    MIN(timestamp) as first_event,
    MAX(timestamp) as last_event,
    TIMESTAMPDIFF(SECOND, MAX(timestamp), NOW()) as seconds_since_last_event
FROM audit_log;

-- =============================================================================
-- USER ACTIVITY SUMMARY VIEW
-- =============================================================================

CREATE OR REPLACE VIEW user_activity_summary AS
SELECT
    user_id,
    user_email,
    COUNT(*) as total_actions,
    COUNT(DISTINCT DATE(timestamp)) as active_days,
    SUM(CASE WHEN action IN ('CREATE', 'UPDATE', 'DELETE') THEN 1 ELSE 0 END) as data_modifications,
    SUM(CASE WHEN action = 'READ' THEN 1 ELSE 0 END) as data_reads,
    SUM(CASE WHEN action = 'EXPORT' THEN 1 ELSE 0 END) as data_exports,
    SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed_actions,
    MIN(timestamp) as first_activity,
    MAX(timestamp) as last_activity
FROM audit_log
WHERE user_id IS NOT NULL
GROUP BY user_id, user_email
ORDER BY last_activity DESC;

-- =============================================================================
-- DATA ACCESS LOG VIEW
-- =============================================================================

CREATE OR REPLACE VIEW data_access_log AS
SELECT
    id,
    user_id,
    user_email,
    action,
    resource_type,
    resource_id,
    timestamp,
    ip_address,
    CASE
        WHEN action = 'READ' THEN 'Viewed'
        WHEN action = 'EXPORT' THEN 'Exported'
        WHEN action = 'UPDATE' THEN 'Modified'
        WHEN action = 'DELETE' THEN 'Deleted'
        ELSE action
    END as access_type
FROM audit_log
WHERE action IN ('READ', 'EXPORT', 'UPDATE', 'DELETE')
ORDER BY timestamp DESC;

-- =============================================================================
-- SECURITY EVENTS VIEW
-- =============================================================================

CREATE OR REPLACE VIEW security_events AS
SELECT
    al.id,
    al.user_id,
    al.action,
    al.status,
    al.ip_address,
    al.timestamp,
    al.error_message,
    al.user_agent,
    CASE
        WHEN al.action = 'LOGIN_FAILED' AND
             (SELECT COUNT(*)
              FROM audit_log a2
              WHERE a2.user_id = al.user_id
                AND a2.action = 'LOGIN_FAILED'
                AND a2.timestamp > DATE_SUB(al.timestamp, INTERVAL 15 MINUTE)
                AND a2.timestamp <= al.timestamp
             ) >= 3
        THEN 'BRUTE_FORCE_ATTEMPT'
        WHEN al.status = 'denied' THEN 'UNAUTHORIZED_ACCESS'
        WHEN al.status = 'failed' THEN 'OPERATION_FAILED'
        ELSE 'OTHER'
    END as threat_level
FROM audit_log al
WHERE al.status IN ('failed', 'denied')
   OR al.action = 'LOGIN_FAILED'
ORDER BY al.timestamp DESC;

-- =============================================================================
-- TRIGGER TO PREVENT AUDIT LOG MODIFICATION
-- =============================================================================

DELIMITER //

CREATE TRIGGER audit_log_prevent_update
BEFORE UPDATE ON audit_log
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Audit log records cannot be modified';
END//

CREATE TRIGGER audit_log_prevent_delete
BEFORE DELETE ON audit_log
FOR EACH ROW
BEGIN
    SIGNAL SQLSTATE '45000'
    SET MESSAGE_TEXT = 'Audit log records cannot be deleted';
END//

DELIMITER ;

-- =============================================================================
-- AUDIT LOG ARCHIVE TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS audit_log_archive (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(100),
    user_email VARCHAR(255),
    session_id VARCHAR(255),
    action VARCHAR(50) NOT NULL,
    resource_type VARCHAR(100) NOT NULL,
    resource_id VARCHAR(255),
    old_data JSON,
    new_data JSON,
    changes_summary TEXT,
    ip_address VARCHAR(45),
    user_agent TEXT,
    request_method VARCHAR(10),
    request_path TEXT,
    request_params JSON,
    status VARCHAR(20) DEFAULT 'success',
    error_message TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    duration_ms INTEGER,
    metadata JSON,
    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_archive_user_id (user_id),
    INDEX idx_archive_timestamp (timestamp DESC),
    INDEX idx_archive_resource (resource_type, resource_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- STORED PROCEDURE: Archive Old Audit Logs
-- =============================================================================

DELIMITER //

CREATE PROCEDURE archive_old_audit_logs(IN retention_days INTEGER)
BEGIN
    DECLARE archived_count INTEGER;

    -- Move old records to archive
    INSERT INTO audit_log_archive (
        id, user_id, user_email, session_id, action, resource_type, resource_id,
        old_data, new_data, changes_summary, ip_address, user_agent,
        request_method, request_path, request_params, status, error_message,
        timestamp, duration_ms, metadata
    )
    SELECT
        id, user_id, user_email, session_id, action, resource_type, resource_id,
        old_data, new_data, changes_summary, ip_address, user_agent,
        request_method, request_path, request_params, status, error_message,
        timestamp, duration_ms, metadata
    FROM audit_log
    WHERE timestamp < DATE_SUB(CURRENT_DATE, INTERVAL retention_days DAY);

    -- Get count
    SET archived_count = ROW_COUNT();

    -- Delete from main table
    DELETE FROM audit_log
    WHERE timestamp < DATE_SUB(CURRENT_DATE, INTERVAL retention_days DAY);

    SELECT archived_count as records_archived;
END//

DELIMITER ;
