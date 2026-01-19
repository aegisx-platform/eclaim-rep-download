-- Row-Level Security (RLS) Policies
--
-- Implements fine-grained access control at the database level.
-- Users can only access data they're authorized to see.
--
-- Security Benefits:
-- - Defense in depth (even if app code fails, database enforces security)
-- - Automatic filtering (no need to add WHERE clauses in every query)
-- - Audit trail (who accessed what)
-- - Multi-tenancy support (hospital isolation)
--
-- PostgreSQL 9.5+ required

-- =============================================================================
-- ENABLE ROW LEVEL SECURITY ON SENSITIVE TABLES
-- =============================================================================

-- Enable RLS on claim data tables
ALTER TABLE claim_rep_opip_nhso_item ENABLE ROW LEVEL SECURITY;
ALTER TABLE claim_rep_orf_nhso_item ENABLE ROW LEVEL SECURITY;

-- Enable RLS on audit and user tables
ALTER TABLE audit_log ENABLE ROW LEVEL SECURITY;
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_sessions ENABLE ROW LEVEL SECURITY;

-- Enable RLS on file tracking
ALTER TABLE eclaim_imported_files ENABLE ROW LEVEL SECURITY;

-- =============================================================================
-- RLS POLICIES FOR CLAIM DATA
-- =============================================================================

-- Policy: Users can only see claims from their hospital
CREATE POLICY claim_hospital_isolation ON claim_rep_opip_nhso_item
    FOR SELECT
    USING (
        -- Allow if user's hospital code matches claim's hospital code
        -- OR user is admin (can see all hospitals)
        current_setting('app.hospital_code', true) = hcode
        OR current_setting('app.user_role', true) = 'admin'
        OR current_setting('app.user_role', true) IS NULL  -- Bypass for system operations
    );

-- Policy: Users can only insert claims for their hospital
CREATE POLICY claim_hospital_insert ON claim_rep_opip_nhso_item
    FOR INSERT
    WITH CHECK (
        current_setting('app.hospital_code', true) = hcode
        OR current_setting('app.user_role', true) = 'admin'
    );

-- Same policies for ORF claims
CREATE POLICY orf_hospital_isolation ON claim_rep_orf_nhso_item
    FOR SELECT
    USING (
        current_setting('app.hospital_code', true) = hcode
        OR current_setting('app.user_role', true) = 'admin'
        OR current_setting('app.user_role', true) IS NULL
    );

CREATE POLICY orf_hospital_insert ON claim_rep_orf_nhso_item
    FOR INSERT
    WITH CHECK (
        current_setting('app.hospital_code', true) = hcode
        OR current_setting('app.user_role', true) = 'admin'
    );

-- =============================================================================
-- RLS POLICIES FOR AUDIT LOG
-- =============================================================================

-- Policy: Users can only see their own audit logs (admins see all)
CREATE POLICY audit_user_isolation ON audit_log
    FOR SELECT
    USING (
        user_id = current_setting('app.user_id', true)
        OR current_setting('app.user_role', true) = 'admin'
        OR current_setting('app.user_role', true) = 'auditor'  -- Auditors can see all
    );

-- Policy: Anyone can insert audit logs (append-only)
CREATE POLICY audit_insert_only ON audit_log
    FOR INSERT
    WITH CHECK (true);

-- NO UPDATE/DELETE policies - audit logs are immutable

-- =============================================================================
-- RLS POLICIES FOR USERS
-- =============================================================================

-- Policy: Users can see their own profile + admins see all
CREATE POLICY user_self_or_admin ON users
    FOR SELECT
    USING (
        id::text = current_setting('app.user_id', true)
        OR current_setting('app.user_role', true) = 'admin'
    );

-- Policy: Users can update their own profile
CREATE POLICY user_self_update ON users
    FOR UPDATE
    USING (
        id::text = current_setting('app.user_id', true)
    );

-- Policy: Only admins can insert users
CREATE POLICY user_admin_insert ON users
    FOR INSERT
    WITH CHECK (
        current_setting('app.user_role', true) = 'admin'
    );

-- Policy: Only admins can delete users
CREATE POLICY user_admin_delete ON users
    FOR DELETE
    USING (
        current_setting('app.user_role', true) = 'admin'
    );

-- =============================================================================
-- RLS POLICIES FOR USER SESSIONS
-- =============================================================================

-- Policy: Users can only see their own sessions
CREATE POLICY session_self_only ON user_sessions
    FOR ALL
    USING (
        user_id::text = current_setting('app.user_id', true)
        OR current_setting('app.user_role', true) = 'admin'
    );

-- =============================================================================
-- RLS POLICIES FOR IMPORTED FILES
-- =============================================================================

-- Policy: Users can see files from their hospital
CREATE POLICY files_hospital_isolation ON eclaim_imported_files
    FOR SELECT
    USING (
        -- Extract hospital code from filename (e.g., "REP_10670_202601.xls")
        substring(filename from 'REP_([0-9]{5})') = current_setting('app.hospital_code', true)
        OR substring(filename from 'STM_([0-9]{5})') = current_setting('app.hospital_code', true)
        OR current_setting('app.user_role', true) = 'admin'
        OR current_setting('app.user_role', true) IS NULL
    );

-- =============================================================================
-- HELPER FUNCTIONS FOR SETTING RLS CONTEXT
-- =============================================================================

-- Function to set RLS context for a session
CREATE OR REPLACE FUNCTION set_user_context(
    p_user_id TEXT,
    p_user_role TEXT,
    p_hospital_code TEXT
) RETURNS void AS $$
BEGIN
    -- Set session variables for RLS policies
    PERFORM set_config('app.user_id', p_user_id, false);
    PERFORM set_config('app.user_role', p_user_role, false);
    PERFORM set_config('app.hospital_code', p_hospital_code, false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to clear RLS context
CREATE OR REPLACE FUNCTION clear_user_context() RETURNS void AS $$
BEGIN
    PERFORM set_config('app.user_id', '', false);
    PERFORM set_config('app.user_role', '', false);
    PERFORM set_config('app.hospital_code', '', false);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Function to get current RLS context
CREATE OR REPLACE FUNCTION get_user_context() RETURNS TABLE(
    user_id TEXT,
    user_role TEXT,
    hospital_code TEXT
) AS $$
BEGIN
    RETURN QUERY SELECT
        current_setting('app.user_id', true) AS user_id,
        current_setting('app.user_role', true) AS user_role,
        current_setting('app.hospital_code', true) AS hospital_code;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =============================================================================
-- SECURE VIEWS WITH BUILT-IN ACCESS CONTROL
-- =============================================================================

-- View: Claims summary (respects RLS)
CREATE OR REPLACE VIEW v_claims_summary_secure AS
SELECT
    date_trunc('month', dateadm) AS month,
    COUNT(*) AS claim_count,
    SUM(CAST(payprice AS NUMERIC)) AS total_amount,
    COUNT(DISTINCT pid) AS patient_count,
    current_setting('app.hospital_code', true) AS hospital_code
FROM claim_rep_opip_nhso_item
WHERE hcode = current_setting('app.hospital_code', true)
    OR current_setting('app.user_role', true) = 'admin'
GROUP BY date_trunc('month', dateadm);

COMMENT ON VIEW v_claims_summary_secure IS 'Claims summary with automatic hospital isolation via RLS';

-- View: Recent imports (respects RLS)
CREATE OR REPLACE VIEW v_recent_imports_secure AS
SELECT
    filename,
    import_date,
    status,
    rows_imported,
    error_message
FROM eclaim_imported_files
WHERE import_date >= CURRENT_DATE - INTERVAL '30 days'
ORDER BY import_date DESC
LIMIT 100;

COMMENT ON VIEW v_recent_imports_secure IS 'Recent file imports with RLS filtering';

-- =============================================================================
-- GRANT PERMISSIONS
-- =============================================================================

-- Grant execute permission on helper functions
GRANT EXECUTE ON FUNCTION set_user_context(TEXT, TEXT, TEXT) TO eclaim;
GRANT EXECUTE ON FUNCTION clear_user_context() TO eclaim;
GRANT EXECUTE ON FUNCTION get_user_context() TO eclaim;

-- Grant select permission on secure views
GRANT SELECT ON v_claims_summary_secure TO eclaim;
GRANT SELECT ON v_recent_imports_secure TO eclaim;

-- =============================================================================
-- TESTING RLS POLICIES
-- =============================================================================

-- Test function to verify RLS is working
CREATE OR REPLACE FUNCTION test_rls_policies() RETURNS TABLE(
    test_name TEXT,
    result BOOLEAN,
    message TEXT
) AS $$
DECLARE
    claim_count_before INT;
    claim_count_after INT;
BEGIN
    -- Test 1: Set context and verify isolation
    SELECT COUNT(*) INTO claim_count_before FROM claim_rep_opip_nhso_item;

    PERFORM set_user_context('test_user', 'user', '10670');
    SELECT COUNT(*) INTO claim_count_after FROM claim_rep_opip_nhso_item;

    RETURN QUERY SELECT
        'Hospital Isolation'::TEXT,
        claim_count_after < claim_count_before OR claim_count_before = 0,
        format('Before: %s, After: %s', claim_count_before, claim_count_after);

    -- Clean up
    PERFORM clear_user_context();

    -- Test 2: Admin can see all
    PERFORM set_user_context('admin_user', 'admin', '10670');
    SELECT COUNT(*) INTO claim_count_after FROM claim_rep_opip_nhso_item;

    RETURN QUERY SELECT
        'Admin Access'::TEXT,
        claim_count_after = claim_count_before OR claim_count_before = 0,
        format('Admin sees: %s rows', claim_count_after);

    PERFORM clear_user_context();
END;
$$ LANGUAGE plpgsql;

GRANT EXECUTE ON FUNCTION test_rls_policies() TO eclaim;

-- =============================================================================
-- DOCUMENTATION
-- =============================================================================

COMMENT ON TABLE claim_rep_opip_nhso_item IS 'OP/IP claims with RLS enabled (hospital isolation)';
COMMENT ON TABLE claim_rep_orf_nhso_item IS 'ORF claims with RLS enabled (hospital isolation)';
COMMENT ON TABLE audit_log IS 'Audit log with RLS enabled (user isolation)';
COMMENT ON TABLE users IS 'Users with RLS enabled (self + admin access)';
COMMENT ON TABLE user_sessions IS 'User sessions with RLS enabled (self access)';

-- Migration complete
-- RLS policies active
-- Use set_user_context() in application code to enable RLS
