-- Migration: API Keys for External Integrations
-- Description: Add api_keys table for managing external API access

CREATE TABLE IF NOT EXISTS api_keys (
    id INT AUTO_INCREMENT PRIMARY KEY,
    key_name VARCHAR(100) NOT NULL,
    api_key VARCHAR(64) NOT NULL UNIQUE,
    hospital_code VARCHAR(5),
    description TEXT,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    rate_limit INT NOT NULL DEFAULT 100,  -- requests per minute
    allowed_ips TEXT,  -- JSON array of allowed IP addresses
    last_used_at TIMESTAMP NULL,
    expires_at TIMESTAMP NULL,
    created_by VARCHAR(50),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_api_keys_api_key (api_key, is_active),
    INDEX idx_api_keys_hospital_code (hospital_code),
    INDEX idx_api_keys_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table for tracking API usage
CREATE TABLE IF NOT EXISTS api_usage_logs (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    api_key_id INT NOT NULL,
    endpoint VARCHAR(255) NOT NULL,
    method VARCHAR(10) NOT NULL,
    ip_address VARCHAR(45),
    user_agent TEXT,
    status_code INT,
    response_time_ms INT,
    request_params TEXT,  -- JSON
    error_message TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE,
    INDEX idx_api_usage_logs_api_key_id (api_key_id),
    INDEX idx_api_usage_logs_created_at (created_at),
    INDEX idx_api_usage_logs_endpoint (endpoint)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Table for rate limiting
CREATE TABLE IF NOT EXISTS api_rate_limits (
    id INT AUTO_INCREMENT PRIMARY KEY,
    api_key_id INT NOT NULL,
    window_start TIMESTAMP NOT NULL,
    request_count INT NOT NULL DEFAULT 0,
    FOREIGN KEY (api_key_id) REFERENCES api_keys(id) ON DELETE CASCADE,
    UNIQUE KEY unique_key_window (api_key_id, window_start),
    INDEX idx_api_rate_limits_key_window (api_key_id, window_start)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Insert default API key for testing (will be regenerated on first use)
-- INSERT INTO api_keys (key_name, api_key, hospital_code, description, created_by)
-- VALUES ('Development Key', 'dev_key_will_be_regenerated', NULL, 'Default development API key', 'system')
-- ON DUPLICATE KEY UPDATE key_name = key_name;
