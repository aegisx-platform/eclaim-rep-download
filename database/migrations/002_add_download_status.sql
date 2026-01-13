-- Migration: Add download_status column to support retry for failed downloads
-- Date: 2026-01-13
-- Purpose: Track download status (pending, downloading, success, failed) for retry functionality

-- =====================================================
-- PostgreSQL Version
-- =====================================================

-- Add download_status column with default 'success' for existing records
ALTER TABLE download_history
ADD COLUMN IF NOT EXISTS download_status VARCHAR(20) DEFAULT 'success';

-- Add retry_count to track how many times we've retried
ALTER TABLE download_history
ADD COLUMN IF NOT EXISTS retry_count INTEGER DEFAULT 0;

-- Add last_attempt_at to track when the last download attempt was made
ALTER TABLE download_history
ADD COLUMN IF NOT EXISTS last_attempt_at TIMESTAMP;

-- Update existing records to have 'success' status (they were successful)
UPDATE download_history
SET download_status = 'success'
WHERE download_status IS NULL;

-- Make download_status NOT NULL after setting defaults
ALTER TABLE download_history
ALTER COLUMN download_status SET NOT NULL;

-- Add index for querying failed downloads
CREATE INDEX IF NOT EXISTS idx_download_history_status ON download_history(download_status);

-- Add comments
COMMENT ON COLUMN download_history.download_status IS 'Download status: pending, downloading, success, failed';
COMMENT ON COLUMN download_history.retry_count IS 'Number of retry attempts';
COMMENT ON COLUMN download_history.last_attempt_at IS 'Timestamp of last download attempt';
