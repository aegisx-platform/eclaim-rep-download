-- Migration: Add download_status column to support retry for failed downloads
-- Date: 2026-01-13
-- Purpose: Track download status (pending, downloading, success, failed) for retry functionality

-- =====================================================
-- MySQL Version
-- =====================================================

-- Add download_status column with default 'success' for existing records
ALTER TABLE download_history
ADD COLUMN download_status VARCHAR(20) DEFAULT 'success' AFTER file_exists;

-- Add retry_count to track how many times we've retried
ALTER TABLE download_history
ADD COLUMN retry_count INT DEFAULT 0 AFTER download_status;

-- Add last_attempt_at to track when the last download attempt was made
ALTER TABLE download_history
ADD COLUMN last_attempt_at TIMESTAMP NULL AFTER retry_count;

-- Update existing records to have 'success' status (they were successful)
UPDATE download_history
SET download_status = 'success'
WHERE download_status IS NULL;

-- Modify to NOT NULL after setting defaults
ALTER TABLE download_history
MODIFY COLUMN download_status VARCHAR(20) NOT NULL DEFAULT 'success';

-- Add index for querying failed downloads
CREATE INDEX idx_download_history_status ON download_history(download_status);
