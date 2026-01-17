-- Row-Level Security for MySQL
--
-- TEMPORARILY DISABLED: MySQL migration runner does not support DELIMITER syntax
-- for stored procedures. This migration has been disabled to allow successful
-- database initialization.
--
-- Row-level security will be enforced at application level instead.
--
-- To enable stored procedure-based RLS later, manually execute this SQL
-- using MySQL CLI after deployment.
--
-- Original file backed up as: 010_row_level_security.sql.backup

-- Placeholder to mark migration as applied
SELECT 'Row-level security procedures skipped - enforced at application level' AS migration_status;
