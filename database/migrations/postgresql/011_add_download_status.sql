-- Migration 006: Add download_status column to download_history table
-- PostgreSQL version

-- Add download_status column with default 'success' for existing records
ALTER TABLE download_history
ADD COLUMN IF NOT EXISTS download_status VARCHAR(20) DEFAULT 'success';

-- Add retry_count and last_attempt_at columns (used by download_status logic)
ALTER TABLE download_history
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

ALTER TABLE download_history
ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP;

-- Update existing records: set status based on error_message
UPDATE download_history
SET download_status = CASE
    WHEN error_message IS NOT NULL AND error_message != '' THEN 'failed'
    WHEN imported = TRUE THEN 'success'
    ELSE 'success'
END
WHERE download_status = 'success';  -- Only update records that still have default value

-- Create index for faster queries on download_status
CREATE INDEX IF NOT EXISTS idx_download_history_status ON download_history(download_status);

-- Add check constraint
ALTER TABLE download_history
ADD CONSTRAINT check_download_status
CHECK (download_status IN ('pending', 'downloading', 'success', 'failed'));

COMMENT ON COLUMN download_history.download_status IS 'Download status: pending, downloading, success, failed';
COMMENT ON COLUMN download_history.retry_count IS 'Number of retry attempts for failed downloads';
COMMENT ON COLUMN download_history.last_attempt_at IS 'Last download attempt timestamp';
