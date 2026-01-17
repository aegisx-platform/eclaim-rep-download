-- Row-Level Security for MySQL
--
-- MySQL does not have native Row-Level Security like PostgreSQL.
-- This implementation uses:
-- - Secure views with built-in WHERE clauses
-- - User variables for context
-- - Stored procedures for access control
--
-- Security Benefits:
-- - Application-enforced multi-tenancy
-- - Defense in depth
-- - Audit trail
--
-- Note: Not as secure as PostgreSQL RLS, but provides similar functionality

-- =============================================================================
-- USER VARIABLES FOR SECURITY CONTEXT
-- =============================================================================

-- Set user context variables
-- Call this after authentication in application code
DELIMITER $$

CREATE PROCEDURE set_user_context(
    IN p_user_id VARCHAR(100),
    IN p_user_role VARCHAR(50),
    IN p_hospital_code VARCHAR(10)
)
BEGIN
    SET @app_user_id = p_user_id;
    SET @app_user_role = p_user_role;
    SET @app_hospital_code = p_hospital_code;
END$$

DELIMITER ;

-- Clear user context
DELIMITER $$

CREATE PROCEDURE clear_user_context()
BEGIN
    SET @app_user_id = NULL;
    SET @app_user_role = NULL;
    SET @app_hospital_code = NULL;
END$$

DELIMITER ;

-- Get current context
DELIMITER $$

CREATE PROCEDURE get_user_context()
BEGIN
    SELECT
        @app_user_id AS user_id,
        @app_user_role AS user_role,
        @app_hospital_code AS hospital_code;
END$$

DELIMITER ;

-- =============================================================================
-- SECURE VIEWS WITH BUILT-IN ACCESS CONTROL
-- =============================================================================

-- View: Claims for current hospital only
CREATE OR REPLACE VIEW v_claims_hospital_secure AS
SELECT *
FROM claim_rep_opip_nhso_item
WHERE
    hcode = @app_hospital_code
    OR @app_user_role = 'admin'
    OR @app_user_role IS NULL;  -- Bypass for system operations

-- View: ORF claims for current hospital only
CREATE OR REPLACE VIEW v_orf_hospital_secure AS
SELECT *
FROM claim_rep_orf_nhso_item
WHERE
    hcode = @app_hospital_code
    OR @app_user_role = 'admin'
    OR @app_user_role IS NULL;

-- View: Audit logs for current user
CREATE OR REPLACE VIEW v_audit_user_secure AS
SELECT *
FROM audit_log
WHERE
    user_id = @app_user_id
    OR @app_user_role = 'admin'
    OR @app_user_role = 'auditor';

-- View: User profile (self or admin)
CREATE OR REPLACE VIEW v_user_profile_secure AS
SELECT
    id,
    username,
    email,
    full_name,
    role,
    hospital_code,
    created_at,
    last_login,
    is_active,
    must_change_password
FROM users
WHERE
    CAST(id AS CHAR) = @app_user_id
    OR @app_user_role = 'admin';

-- View: User sessions (self only)
CREATE OR REPLACE VIEW v_user_sessions_secure AS
SELECT *
FROM user_sessions
WHERE
    CAST(user_id AS CHAR) = @app_user_id
    OR @app_user_role = 'admin';

-- View: Imported files for hospital
CREATE OR REPLACE VIEW v_files_hospital_secure AS
SELECT *
FROM eclaim_imported_files
WHERE
    -- Extract hospital code from filename
    SUBSTRING(filename, LOCATE('_', filename) + 1, 5) = @app_hospital_code
    OR @app_user_role = 'admin'
    OR @app_user_role IS NULL;

-- =============================================================================
-- SECURE AGGREGATE VIEWS
-- =============================================================================

-- View: Claims summary (hospital isolated)
CREATE OR REPLACE VIEW v_claims_summary_secure AS
SELECT
    DATE_FORMAT(dateadm, '%Y-%m-01') AS month,
    COUNT(*) AS claim_count,
    CAST(SUM(CAST(payprice AS DECIMAL(15,2))) AS DECIMAL(15,2)) AS total_amount,
    COUNT(DISTINCT pid) AS patient_count,
    @app_hospital_code AS hospital_code
FROM claim_rep_opip_nhso_item
WHERE
    hcode = @app_hospital_code
    OR @app_user_role = 'admin'
GROUP BY DATE_FORMAT(dateadm, '%Y-%m-01');

-- View: Recent imports (last 30 days)
CREATE OR REPLACE VIEW v_recent_imports_secure AS
SELECT
    filename,
    import_date,
    status,
    rows_imported,
    error_message
FROM eclaim_imported_files
WHERE
    import_date >= DATE_SUB(CURDATE(), INTERVAL 30 DAY)
    AND (
        SUBSTRING(filename, LOCATE('_', filename) + 1, 5) = @app_hospital_code
        OR @app_user_role = 'admin'
        OR @app_user_role IS NULL
    )
ORDER BY import_date DESC
LIMIT 100;

-- =============================================================================
-- STORED PROCEDURES WITH ACCESS CONTROL
-- =============================================================================

-- Procedure: Get claims for current user's hospital
DELIMITER $$

CREATE PROCEDURE get_claims_secure(
    IN p_limit INT,
    IN p_offset INT
)
BEGIN
    SELECT *
    FROM v_claims_hospital_secure
    ORDER BY dateadm DESC
    LIMIT p_limit OFFSET p_offset;
END$$

DELIMITER ;

-- Procedure: Get claim count for hospital
DELIMITER $$

CREATE PROCEDURE get_claim_count_secure()
BEGIN
    SELECT COUNT(*) AS claim_count
    FROM v_claims_hospital_secure;
END$$

DELIMITER ;

-- Procedure: Insert claim with hospital validation
DELIMITER $$

CREATE PROCEDURE insert_claim_secure(
    IN p_claim_data JSON
)
BEGIN
    DECLARE v_hcode VARCHAR(10);

    -- Extract hospital code from claim data
    SET v_hcode = JSON_UNQUOTE(JSON_EXTRACT(p_claim_data, '$.hcode'));

    -- Validate user can insert for this hospital
    IF v_hcode != @app_hospital_code AND @app_user_role != 'admin' THEN
        SIGNAL SQLSTATE '45000'
        SET MESSAGE_TEXT = 'Access denied: Cannot insert claim for different hospital';
    END IF;

    -- Insert claim (actual implementation would parse JSON and insert)
    -- This is a template - actual implementation depends on schema
END$$

DELIMITER ;

-- =============================================================================
-- ACCESS CONTROL FUNCTIONS
-- =============================================================================

-- Function: Check if user can access hospital data
DELIMITER $$

CREATE FUNCTION can_access_hospital(p_hospital_code VARCHAR(10))
RETURNS BOOLEAN
DETERMINISTIC
BEGIN
    IF @app_user_role = 'admin' THEN
        RETURN TRUE;
    END IF;

    IF @app_hospital_code = p_hospital_code THEN
        RETURN TRUE;
    END IF;

    RETURN FALSE;
END$$

DELIMITER ;

-- Function: Check if user is admin
DELIMITER $$

CREATE FUNCTION is_admin()
RETURNS BOOLEAN
DETERMINISTIC
BEGIN
    RETURN @app_user_role = 'admin';
END$$

DELIMITER ;

-- Function: Check if user is auditor
DELIMITER $$

CREATE FUNCTION is_auditor()
RETURNS BOOLEAN
DETERMINISTIC
BEGIN
    RETURN @app_user_role = 'auditor' OR @app_user_role = 'admin';
END$$

DELIMITER ;

-- =============================================================================
-- TESTING PROCEDURES
-- =============================================================================

-- Test procedure to verify security context
DELIMITER $$

CREATE PROCEDURE test_security_context()
BEGIN
    DECLARE v_claim_count_user INT;
    DECLARE v_claim_count_admin INT;

    -- Test 1: User context
    CALL set_user_context('test_user', 'user', '10670');
    SELECT COUNT(*) INTO v_claim_count_user FROM v_claims_hospital_secure;

    SELECT
        'User Context Test' AS test_name,
        v_claim_count_user AS rows_visible,
        'Should only see hospital 10670' AS expected;

    -- Test 2: Admin context
    CALL set_user_context('admin_user', 'admin', '10670');
    SELECT COUNT(*) INTO v_claim_count_admin FROM v_claims_hospital_secure;

    SELECT
        'Admin Context Test' AS test_name,
        v_claim_count_admin AS rows_visible,
        'Should see all hospitals' AS expected;

    -- Clean up
    CALL clear_user_context();
END$$

DELIMITER ;

-- =============================================================================
-- GRANTS
-- =============================================================================

-- Grant execute permissions on procedures/functions
GRANT EXECUTE ON PROCEDURE set_user_context TO 'eclaim'@'%';
GRANT EXECUTE ON PROCEDURE clear_user_context TO 'eclaim'@'%';
GRANT EXECUTE ON PROCEDURE get_user_context TO 'eclaim'@'%';
GRANT EXECUTE ON PROCEDURE get_claims_secure TO 'eclaim'@'%';
GRANT EXECUTE ON PROCEDURE get_claim_count_secure TO 'eclaim'@'%';
GRANT EXECUTE ON PROCEDURE test_security_context TO 'eclaim'@'%';

GRANT EXECUTE ON FUNCTION can_access_hospital TO 'eclaim'@'%';
GRANT EXECUTE ON FUNCTION is_admin TO 'eclaim'@'%';
GRANT EXECUTE ON FUNCTION is_auditor TO 'eclaim'@'%';

-- Grant select permissions on secure views
GRANT SELECT ON v_claims_hospital_secure TO 'eclaim'@'%';
GRANT SELECT ON v_orf_hospital_secure TO 'eclaim'@'%';
GRANT SELECT ON v_audit_user_secure TO 'eclaim'@'%';
GRANT SELECT ON v_user_profile_secure TO 'eclaim'@'%';
GRANT SELECT ON v_user_sessions_secure TO 'eclaim'@'%';
GRANT SELECT ON v_files_hospital_secure TO 'eclaim'@'%';
GRANT SELECT ON v_claims_summary_secure TO 'eclaim'@'%';
GRANT SELECT ON v_recent_imports_secure TO 'eclaim'@'%';

-- =============================================================================
-- DOCUMENTATION
-- =============================================================================

-- Add comments (MySQL 8.0+)
-- ALTER TABLE claim_rep_opip_nhso_item COMMENT = 'OP/IP claims - use v_claims_hospital_secure for access control';
-- ALTER TABLE claim_rep_orf_nhso_item COMMENT = 'ORF claims - use v_orf_hospital_secure for access control';

-- Migration complete
-- Security views and procedures created
-- Use set_user_context() in application code before queries
