-- Migration 009: User Authentication System
-- Purpose: User management and authentication for Flask-Login
-- Date: 2026-01-17
-- CRITICAL SECURITY: Required for access control and authentication

-- =============================================================================
-- USERS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY,

    -- User credentials
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    -- User profile
    full_name VARCHAR(255),
    hospital_code VARCHAR(10),
    department VARCHAR(100),
    position VARCHAR(100),

    -- Access control
    role VARCHAR(50) NOT NULL DEFAULT 'user',
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,

    -- Security
    failed_login_attempts INT DEFAULT 0,
    last_failed_login TIMESTAMP NULL,
    locked_until TIMESTAMP NULL,
    must_change_password BOOLEAN DEFAULT FALSE,

    -- Session management
    last_login_at TIMESTAMP NULL,
    last_login_ip VARCHAR(45),
    current_session_id VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP NULL,

    -- Metadata
    created_by VARCHAR(100),
    updated_by VARCHAR(100),

    -- Constraints
    CONSTRAINT users_role_check CHECK (role IN ('admin', 'user', 'readonly', 'analyst', 'auditor')),

    -- Indexes
    INDEX idx_users_username (username),
    INDEX idx_users_email (email),
    INDEX idx_users_hospital_code (hospital_code),
    INDEX idx_users_role (role),
    INDEX idx_users_is_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- USER SESSIONS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS user_sessions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,

    session_id VARCHAR(255) UNIQUE NOT NULL,

    -- Session info
    ip_address VARCHAR(45),
    user_agent TEXT,
    device_type VARCHAR(50),
    browser VARCHAR(100),

    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NULL,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Foreign keys
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    -- Indexes
    INDEX idx_user_sessions_user_id (user_id),
    INDEX idx_user_sessions_session_id (session_id),
    INDEX idx_user_sessions_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- PASSWORD RESET TOKENS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id INT NOT NULL,

    token VARCHAR(255) UNIQUE NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP NULL,

    ip_address VARCHAR(45),

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,

    INDEX idx_password_reset_tokens_token (token),
    INDEX idx_password_reset_tokens_user_id (user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- =============================================================================
-- VIEWS
-- =============================================================================

CREATE OR REPLACE VIEW active_users_summary AS
SELECT
    u.id,
    u.username,
    u.email,
    u.full_name,
    u.role,
    u.hospital_code,
    u.last_login_at,
    u.created_at,
    (SELECT COUNT(*) FROM user_sessions WHERE user_id = u.id AND is_active = TRUE) as active_sessions
FROM users u
WHERE u.is_active = TRUE
  AND u.deleted_at IS NULL
ORDER BY u.last_login_at DESC;

CREATE OR REPLACE VIEW user_login_history AS
SELECT
    u.id as user_id,
    u.username,
    u.email,
    a.timestamp as login_time,
    a.ip_address,
    a.status,
    a.error_message
FROM users u
LEFT JOIN audit_log a ON a.user_id = u.username
    AND a.action IN ('LOGIN', 'LOGIN_FAILED')
    AND a.timestamp > DATE_SUB(NOW(), INTERVAL 90 DAY)
WHERE u.deleted_at IS NULL
ORDER BY a.timestamp DESC;

-- =============================================================================
-- STORED PROCEDURES
-- =============================================================================

DELIMITER //

-- Check if user is locked
CREATE PROCEDURE is_user_locked(IN p_user_id INT, OUT p_is_locked BOOLEAN)
BEGIN
    DECLARE v_locked_until TIMESTAMP;

    SELECT locked_until INTO v_locked_until
    FROM users
    WHERE id = p_user_id;

    IF v_locked_until IS NULL THEN
        SET p_is_locked = FALSE;
    ELSEIF v_locked_until > NOW() THEN
        SET p_is_locked = TRUE;
    ELSE
        -- Unlock if lock period has passed
        UPDATE users
        SET locked_until = NULL,
            failed_login_attempts = 0
        WHERE id = p_user_id;
        SET p_is_locked = FALSE;
    END IF;
END//

-- Record failed login attempt
CREATE PROCEDURE record_failed_login(IN p_username VARCHAR(100))
BEGIN
    DECLARE v_attempts INT;
    DECLARE v_max_attempts INT DEFAULT 5;
    DECLARE v_lockout_minutes INT DEFAULT 30;

    -- Increment failed attempts
    UPDATE users
    SET failed_login_attempts = failed_login_attempts + 1,
        last_failed_login = NOW()
    WHERE username = p_username;

    SELECT failed_login_attempts INTO v_attempts
    FROM users
    WHERE username = p_username;

    -- Lock account if too many failed attempts
    IF v_attempts >= v_max_attempts THEN
        UPDATE users
        SET locked_until = DATE_ADD(NOW(), INTERVAL v_lockout_minutes MINUTE)
        WHERE username = p_username;
    END IF;
END//

-- Reset failed login attempts on successful login
CREATE PROCEDURE reset_failed_login_attempts(IN p_user_id INT, IN p_ip_address VARCHAR(45))
BEGIN
    UPDATE users
    SET failed_login_attempts = 0,
        last_failed_login = NULL,
        locked_until = NULL,
        last_login_at = NOW(),
        last_login_ip = p_ip_address
    WHERE id = p_user_id;
END//

-- Clean expired sessions
CREATE PROCEDURE clean_expired_sessions()
BEGIN
    DELETE FROM user_sessions
    WHERE expires_at < NOW()
       OR (last_activity < DATE_SUB(NOW(), INTERVAL 24 HOUR) AND is_active = FALSE);

    SELECT ROW_COUNT() as deleted_count;
END//

DELIMITER ;

-- =============================================================================
-- DEFAULT ADMIN USER
-- =============================================================================
-- Create default admin user (password: admin - MUST BE CHANGED)
-- Password hash is bcrypt of 'admin'

INSERT INTO users (username, email, password_hash, full_name, role, must_change_password)
VALUES (
    'admin',
    'admin@eclaim.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqXfj0cG1i',
    'System Administrator',
    'admin',
    TRUE
)
ON DUPLICATE KEY UPDATE id=id;
