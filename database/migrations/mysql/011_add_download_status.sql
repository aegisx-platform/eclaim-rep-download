-- Migration 006: Add download_status column to download_history table
-- MySQL version

-- Add download_status column with default 'success' for existing records
ALTER TABLE download_history
ADD COLUMN download_status VARCHAR(20) DEFAULT 'success';

-- Add retry_count and last_attempt_at columns (used by download_status logic)
ALTER TABLE download_history
ADD COLUMN retry_count INTEGER DEFAULT 0;

ALTER TABLE download_history
ADD COLUMN last_attempt_at TIMESTAMP NULL;

-- Update existing records: set status based on error_message
UPDATE download_history
SET download_status = CASE
    WHEN error_message IS NOT NULL AND error_message != '' THEN 'failed'
    WHEN imported = TRUE THEN 'success'
    ELSE 'success'
END
WHERE download_status = 'success';  -- Only update records that still have default value

-- Create index for faster queries on download_status
-- Note: MySQL doesn't support IF NOT EXISTS for indexes in ALTER TABLE
ALTER TABLE download_history
ADD INDEX idx_download_history_status (download_status);

-- Add check constraint (MySQL 8.0+)
-- Note: Check constraints may not be supported in older MySQL versions
ALTER TABLE download_history
ADD CONSTRAINT check_download_status
CHECK (download_status IN ('pending', 'downloading', 'success', 'failed'));
