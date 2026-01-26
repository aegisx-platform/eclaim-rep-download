-- Migration 011: Add download_status column to download_history table
-- MySQL version

-- Add download_status column if not exists
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'download_history' AND COLUMN_NAME = 'download_status') > 0,
    'SELECT 1',
    'ALTER TABLE download_history ADD COLUMN download_status VARCHAR(20) DEFAULT ''success'''
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add retry_count column if not exists
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'download_history' AND COLUMN_NAME = 'retry_count') > 0,
    'SELECT 1',
    'ALTER TABLE download_history ADD COLUMN retry_count INTEGER DEFAULT 0'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Add last_attempt_at column if not exists
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'download_history' AND COLUMN_NAME = 'last_attempt_at') > 0,
    'SELECT 1',
    'ALTER TABLE download_history ADD COLUMN last_attempt_at TIMESTAMP NULL'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

-- Update existing records: set status based on error_message
UPDATE download_history
SET download_status = CASE
    WHEN error_message IS NOT NULL AND error_message != '' THEN 'failed'
    WHEN imported = TRUE THEN 'success'
    ELSE 'success'
END
WHERE download_status = 'success';

-- Create index if not exists (using procedure)
SET @sql = (SELECT IF(
    (SELECT COUNT(*) FROM INFORMATION_SCHEMA.STATISTICS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'download_history' AND INDEX_NAME = 'idx_download_history_status') > 0,
    'SELECT 1',
    'CREATE INDEX idx_download_history_status ON download_history (download_status)'
));
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;
