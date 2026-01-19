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
    id BIGSERIAL PRIMARY KEY,

    -- Who (User identification)
    user_id VARCHAR(100),                    -- Username or user identifier
    user_email VARCHAR(255),                 -- User email if available
    session_id VARCHAR(255),                 -- Session identifier for correlation

    -- What (Action details)
    action VARCHAR(50) NOT NULL,             -- CREATE, READ, UPDATE, DELETE, LOGIN, LOGOUT, EXPORT, etc.
    resource_type VARCHAR(100) NOT NULL,     -- Table name or resource type (e.g., 'claim_rep_opip_nhso_item', 'settings')
    resource_id VARCHAR(255),                -- Primary key of affected record

    -- Details (Change tracking)
    old_data JSONB,                          -- Previous state (for UPDATE/DELETE)
    new_data JSONB,                          -- New state (for CREATE/UPDATE)
    changes_summary TEXT,                    -- Human-readable summary of changes

    -- Context (Request information)
    ip_address VARCHAR(45),                  -- IPv4 or IPv6 address
    user_agent TEXT,                         -- Browser/client information
    request_method VARCHAR(10),              -- GET, POST, PUT, DELETE
    request_path TEXT,                       -- API endpoint path
    request_params JSONB,                    -- Query parameters (sanitized - no passwords)

    -- Result
    status VARCHAR(20) DEFAULT 'success',    -- success, failed, denied
    error_message TEXT,                      -- Error details if failed

    -- Timing
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    duration_ms INTEGER,                     -- How long the operation took

    -- Metadata
    metadata JSONB,                          -- Additional context-specific data

    -- Indexing for performance
    CONSTRAINT audit_log_action_check CHECK (action IN (
        'CREATE', 'READ', 'UPDATE', 'DELETE',
        'LOGIN', 'LOGOUT', 'LOGIN_FAILED',
        'EXPORT', 'IMPORT', 'DOWNLOAD',
        'SETTINGS_CHANGE', 'PERMISSION_CHANGE',
        'DATA_ACCESS', 'BULK_DELETE', 'BACKUP', 'RESTORE'
    ))
);

-- =============================================================================
-- INDEXES FOR PERFORMANCE
-- =============================================================================
-- Query patterns:
-- 1. Find all actions by user
-- 2. Find all actions on specific resource
-- 3. Find actions in time range
-- 4. Find failed/denied actions for security monitoring

CREATE INDEX IF NOT EXISTS idx_audit_log_user_id
    ON audit_log(user_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp
    ON audit_log(timestamp DESC);

CREATE INDEX IF NOT EXISTS idx_audit_log_resource
    ON audit_log(resource_type, resource_id);

CREATE INDEX IF NOT EXISTS idx_audit_log_action
    ON audit_log(action);

CREATE INDEX IF NOT EXISTS idx_audit_log_status
    ON audit_log(status)
    WHERE status != 'success';  -- Partial index for failed operations

CREATE INDEX IF NOT EXISTS idx_audit_log_ip_address
    ON audit_log(ip_address);

CREATE INDEX IF NOT EXISTS idx_audit_log_session
    ON audit_log(session_id);

-- Composite index for user activity reports
CREATE INDEX IF NOT EXISTS idx_audit_log_user_time
    ON audit_log(user_id, timestamp DESC);

-- =============================================================================
-- AUDIT LOG STATISTICS VIEW
-- =============================================================================
-- Provides quick insights into audit log data

CREATE OR REPLACE VIEW audit_log_stats AS
SELECT
    COUNT(*) as total_events,
    COUNT(DISTINCT user_id) as unique_users,
    COUNT(DISTINCT DATE(timestamp)) as active_days,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_events,
    COUNT(*) FILTER (WHERE status = 'denied') as denied_events,
    COUNT(*) FILTER (WHERE action = 'LOGIN') as total_logins,
    COUNT(*) FILTER (WHERE action = 'LOGIN_FAILED') as failed_logins,
    COUNT(*) FILTER (WHERE action IN ('CREATE', 'UPDATE', 'DELETE')) as data_changes,
    COUNT(*) FILTER (WHERE action = 'EXPORT') as data_exports,
    MIN(timestamp) as first_event,
    MAX(timestamp) as last_event,
    NOW() - MAX(timestamp) as time_since_last_event
FROM audit_log;

-- =============================================================================
-- USER ACTIVITY SUMMARY VIEW
-- =============================================================================
-- Shows activity per user for compliance reports

CREATE OR REPLACE VIEW user_activity_summary AS
SELECT
    user_id,
    user_email,
    COUNT(*) as total_actions,
    COUNT(DISTINCT DATE(timestamp)) as active_days,
    COUNT(*) FILTER (WHERE action IN ('CREATE', 'UPDATE', 'DELETE')) as data_modifications,
    COUNT(*) FILTER (WHERE action = 'READ') as data_reads,
    COUNT(*) FILTER (WHERE action = 'EXPORT') as data_exports,
    COUNT(*) FILTER (WHERE status = 'failed') as failed_actions,
    MIN(timestamp) as first_activity,
    MAX(timestamp) as last_activity,
    ARRAY_AGG(DISTINCT ip_address) as ip_addresses
FROM audit_log
WHERE user_id IS NOT NULL
GROUP BY user_id, user_email
ORDER BY last_activity DESC;

-- =============================================================================
-- DATA ACCESS LOG VIEW
-- =============================================================================
-- Tracks who accessed what data (for PDPA right to know)

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
-- Failed logins, denied access, suspicious activity

CREATE OR REPLACE VIEW security_events AS
SELECT
    id,
    user_id,
    action,
    status,
    ip_address,
    timestamp,
    error_message,
    user_agent,
    CASE
        WHEN action = 'LOGIN_FAILED' AND
             (SELECT COUNT(*)
              FROM audit_log a2
              WHERE a2.user_id = audit_log.user_id
                AND a2.action = 'LOGIN_FAILED'
                AND a2.timestamp > audit_log.timestamp - INTERVAL '15 minutes'
                AND a2.timestamp <= audit_log.timestamp
             ) >= 3
        THEN 'BRUTE_FORCE_ATTEMPT'
        WHEN status = 'denied' THEN 'UNAUTHORIZED_ACCESS'
        WHEN status = 'failed' THEN 'OPERATION_FAILED'
        ELSE 'OTHER'
    END as threat_level
FROM audit_log
WHERE status IN ('failed', 'denied')
   OR action = 'LOGIN_FAILED'
ORDER BY timestamp DESC;

-- =============================================================================
-- TRIGGER TO PREVENT AUDIT LOG MODIFICATION
-- =============================================================================
-- Audit logs must be immutable for compliance

CREATE OR REPLACE FUNCTION prevent_audit_log_modification()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' THEN
        RAISE EXCEPTION 'Audit log records cannot be modified';
    ELSIF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Audit log records cannot be deleted';
    END IF;
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW
    EXECUTE FUNCTION prevent_audit_log_modification();

-- =============================================================================
-- FUNCTION: Log Audit Event
-- =============================================================================
-- Helper function to easily insert audit events

CREATE OR REPLACE FUNCTION log_audit_event(
    p_user_id VARCHAR(100),
    p_action VARCHAR(50),
    p_resource_type VARCHAR(100),
    p_resource_id VARCHAR(255) DEFAULT NULL,
    p_old_data JSONB DEFAULT NULL,
    p_new_data JSONB DEFAULT NULL,
    p_ip_address VARCHAR(45) DEFAULT NULL,
    p_user_agent TEXT DEFAULT NULL,
    p_metadata JSONB DEFAULT NULL
) RETURNS BIGINT AS $$
DECLARE
    v_audit_id BIGINT;
BEGIN
    INSERT INTO audit_log (
        user_id, action, resource_type, resource_id,
        old_data, new_data, ip_address, user_agent, metadata
    ) VALUES (
        p_user_id, p_action, p_resource_type, p_resource_id,
        p_old_data, p_new_data, p_ip_address, p_user_agent, p_metadata
    ) RETURNING id INTO v_audit_id;

    RETURN v_audit_id;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- RETENTION POLICY FUNCTION
-- =============================================================================
-- Archive old audit logs (run monthly)
-- Keep 1 year online, move older to archive table

CREATE TABLE IF NOT EXISTS audit_log_archive (
    LIKE audit_log INCLUDING ALL
);

CREATE OR REPLACE FUNCTION archive_old_audit_logs(retention_days INTEGER DEFAULT 365)
RETURNS INTEGER AS $$
DECLARE
    archived_count INTEGER;
BEGIN
    -- Move old records to archive
    WITH moved_rows AS (
        DELETE FROM audit_log
        WHERE timestamp < CURRENT_DATE - retention_days * INTERVAL '1 day'
        RETURNING *
    )
    INSERT INTO audit_log_archive
    SELECT * FROM moved_rows;

    GET DIAGNOSTICS archived_count = ROW_COUNT;

    RETURN archived_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE audit_log IS 'Immutable audit trail of all system actions for PDPA compliance and security monitoring';
COMMENT ON COLUMN audit_log.user_id IS 'User identifier who performed the action';
COMMENT ON COLUMN audit_log.action IS 'Type of action: CREATE, READ, UPDATE, DELETE, LOGIN, EXPORT, etc.';
COMMENT ON COLUMN audit_log.resource_type IS 'Type of resource affected (table name or resource type)';
COMMENT ON COLUMN audit_log.resource_id IS 'Primary key of the affected record';
COMMENT ON COLUMN audit_log.old_data IS 'JSON snapshot of data before change (UPDATE/DELETE)';
COMMENT ON COLUMN audit_log.new_data IS 'JSON snapshot of data after change (CREATE/UPDATE)';
COMMENT ON COLUMN audit_log.ip_address IS 'IP address of the user';
COMMENT ON COLUMN audit_log.status IS 'success, failed, or denied';
COMMENT ON COLUMN audit_log.timestamp IS 'When the action occurred';

COMMENT ON VIEW audit_log_stats IS 'Summary statistics of audit log activity';
COMMENT ON VIEW user_activity_summary IS 'Per-user activity summary for compliance reports';
COMMENT ON VIEW data_access_log IS 'Who accessed what data (PDPA right to know)';
COMMENT ON VIEW security_events IS 'Failed logins and unauthorized access attempts';

COMMENT ON FUNCTION log_audit_event IS 'Helper function to insert audit log entries';
COMMENT ON FUNCTION archive_old_audit_logs IS 'Move old audit logs to archive table (run monthly)';
