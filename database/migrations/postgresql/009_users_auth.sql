-- Migration 009: User Authentication System
-- Purpose: User management and authentication for Flask-Login
-- Date: 2026-01-17
-- CRITICAL SECURITY: Required for access control and authentication

-- =============================================================================
-- USERS TABLE
-- =============================================================================
-- Stores user accounts with password hashing and role-based access

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,

    -- User credentials
    username VARCHAR(100) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,  -- bcrypt hash

    -- User profile
    full_name VARCHAR(255),
    hospital_code VARCHAR(10),            -- Hospital this user belongs to
    department VARCHAR(100),
    position VARCHAR(100),

    -- Access control
    role VARCHAR(50) NOT NULL DEFAULT 'user',  -- admin, user, readonly, analyst
    is_active BOOLEAN DEFAULT TRUE,
    is_verified BOOLEAN DEFAULT FALSE,    -- Email verification

    -- Security
    failed_login_attempts INTEGER DEFAULT 0,
    last_failed_login TIMESTAMP,
    locked_until TIMESTAMP,               -- Account lockout (after too many failed attempts)
    must_change_password BOOLEAN DEFAULT FALSE,

    -- Session management
    last_login_at TIMESTAMP,
    last_login_ip VARCHAR(45),
    current_session_id VARCHAR(255),

    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    deleted_at TIMESTAMP,                 -- Soft delete

    -- Metadata
    created_by VARCHAR(100),
    updated_by VARCHAR(100),

    -- Constraints
    CONSTRAINT users_role_check CHECK (role IN ('admin', 'user', 'readonly', 'analyst', 'auditor'))
);

-- =============================================================================
-- INDEXES
-- =============================================================================

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email) WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_users_hospital_code ON users(hospital_code);
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active) WHERE is_active = TRUE;

-- =============================================================================
-- USER SESSIONS TABLE
-- =============================================================================
-- Track active sessions for multi-device management and force logout

CREATE TABLE IF NOT EXISTS user_sessions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    session_id VARCHAR(255) UNIQUE NOT NULL,

    -- Session info
    ip_address VARCHAR(45),
    user_agent TEXT,
    device_type VARCHAR(50),              -- desktop, mobile, tablet
    browser VARCHAR(100),

    -- Timing
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,

    -- Status
    is_active BOOLEAN DEFAULT TRUE,

    -- Indexes
    CONSTRAINT user_sessions_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_user_sessions_user_id ON user_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_session_id ON user_sessions(session_id);
CREATE INDEX IF NOT EXISTS idx_user_sessions_active ON user_sessions(is_active) WHERE is_active = TRUE;

-- =============================================================================
-- PASSWORD RESET TOKENS TABLE
-- =============================================================================

CREATE TABLE IF NOT EXISTS password_reset_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,

    token VARCHAR(255) UNIQUE NOT NULL,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,

    ip_address VARCHAR(45),

    CONSTRAINT password_reset_tokens_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_token ON password_reset_tokens(token);
CREATE INDEX IF NOT EXISTS idx_password_reset_tokens_user_id ON password_reset_tokens(user_id);

-- =============================================================================
-- VIEWS
-- =============================================================================

-- Active users summary
CREATE OR REPLACE VIEW active_users_summary AS
SELECT
    id,
    username,
    email,
    full_name,
    role,
    hospital_code,
    last_login_at,
    created_at,
    (SELECT COUNT(*) FROM user_sessions WHERE user_id = users.id AND is_active = TRUE) as active_sessions
FROM users
WHERE is_active = TRUE
  AND deleted_at IS NULL
ORDER BY last_login_at DESC NULLS LAST;

-- User login history (last 90 days)
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
    AND a.timestamp > CURRENT_TIMESTAMP - INTERVAL '90 days'
WHERE u.deleted_at IS NULL
ORDER BY a.timestamp DESC;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_users_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER users_update_timestamp
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_users_updated_at();

-- Update last_activity on user_sessions
CREATE OR REPLACE FUNCTION update_session_last_activity()
RETURNS TRIGGER AS $$
BEGIN
    NEW.last_activity = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER user_sessions_update_activity
    BEFORE UPDATE ON user_sessions
    FOR EACH ROW
    EXECUTE FUNCTION update_session_last_activity();

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Check if user is locked
CREATE OR REPLACE FUNCTION is_user_locked(p_user_id INTEGER)
RETURNS BOOLEAN AS $$
DECLARE
    v_locked_until TIMESTAMP;
BEGIN
    SELECT locked_until INTO v_locked_until
    FROM users
    WHERE id = p_user_id;

    IF v_locked_until IS NULL THEN
        RETURN FALSE;
    END IF;

    IF v_locked_until > CURRENT_TIMESTAMP THEN
        RETURN TRUE;
    ELSE
        -- Unlock if lock period has passed
        UPDATE users
        SET locked_until = NULL,
            failed_login_attempts = 0
        WHERE id = p_user_id;
        RETURN FALSE;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Record failed login attempt
CREATE OR REPLACE FUNCTION record_failed_login(p_username VARCHAR)
RETURNS VOID AS $$
DECLARE
    v_attempts INTEGER;
    v_max_attempts INTEGER := 5;
    v_lockout_minutes INTEGER := 30;
BEGIN
    -- Increment failed attempts
    UPDATE users
    SET failed_login_attempts = failed_login_attempts + 1,
        last_failed_login = CURRENT_TIMESTAMP
    WHERE username = p_username
    RETURNING failed_login_attempts INTO v_attempts;

    -- Lock account if too many failed attempts
    IF v_attempts >= v_max_attempts THEN
        UPDATE users
        SET locked_until = CURRENT_TIMESTAMP + (v_lockout_minutes || ' minutes')::INTERVAL
        WHERE username = p_username;
    END IF;
END;
$$ LANGUAGE plpgsql;

-- Reset failed login attempts on successful login
CREATE OR REPLACE FUNCTION reset_failed_login_attempts(p_user_id INTEGER, p_ip_address VARCHAR)
RETURNS VOID AS $$
BEGIN
    UPDATE users
    SET failed_login_attempts = 0,
        last_failed_login = NULL,
        locked_until = NULL,
        last_login_at = CURRENT_TIMESTAMP,
        last_login_ip = p_ip_address
    WHERE id = p_user_id;
END;
$$ LANGUAGE plpgsql;

-- Clean expired sessions
CREATE OR REPLACE FUNCTION clean_expired_sessions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM user_sessions
    WHERE expires_at < CURRENT_TIMESTAMP
       OR (last_activity < CURRENT_TIMESTAMP - INTERVAL '24 hours' AND is_active = FALSE);

    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- =============================================================================
-- DEFAULT ADMIN USER
-- =============================================================================
-- Create default admin user (password: admin - MUST BE CHANGED)
-- Password hash is bcrypt of 'admin'

INSERT INTO users (username, email, password_hash, full_name, role, must_change_password)
VALUES (
    'admin',
    'admin@eclaim.local',
    '$2b$12$LQv3c1yqBWVHxkd0LHAkCOYz6TtxMQJqhN8/LewY5GyYqXfj0cG1i',  -- bcrypt('admin')
    'System Administrator',
    'admin',
    TRUE  -- Force password change on first login
)
ON CONFLICT (username) DO NOTHING;

-- =============================================================================
-- COMMENTS
-- =============================================================================

COMMENT ON TABLE users IS 'User accounts for authentication and access control';
COMMENT ON COLUMN users.password_hash IS 'Bcrypt hashed password (NEVER store plaintext)';
COMMENT ON COLUMN users.role IS 'User role: admin (full access), user (standard), readonly (view only), analyst (analytics only), auditor (audit logs only)';
COMMENT ON COLUMN users.failed_login_attempts IS 'Number of consecutive failed login attempts';
COMMENT ON COLUMN users.locked_until IS 'Account locked until this timestamp (due to too many failed attempts)';
COMMENT ON COLUMN users.must_change_password IS 'Force user to change password on next login';

COMMENT ON TABLE user_sessions IS 'Active user sessions for multi-device tracking';
COMMENT ON TABLE password_reset_tokens IS 'Tokens for password reset functionality';

COMMENT ON VIEW active_users_summary IS 'Summary of all active users with session counts';
COMMENT ON VIEW user_login_history IS 'Login history for all users (last 90 days)';

COMMENT ON FUNCTION is_user_locked IS 'Check if user account is currently locked';
COMMENT ON FUNCTION record_failed_login IS 'Record failed login attempt and lock account if threshold reached';
COMMENT ON FUNCTION reset_failed_login_attempts IS 'Reset failed attempts counter on successful login';
COMMENT ON FUNCTION clean_expired_sessions IS 'Remove expired and inactive sessions (run daily)';
