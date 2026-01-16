-- NHSO Error Codes Master Data
-- Reference table for error codes from NHSO e-claim system
-- NOTE: Drop and recreate to ensure correct structure for seed data importer

DROP TABLE IF EXISTS nhso_error_codes;

CREATE TABLE nhso_error_codes (
    id INT UNSIGNED NOT NULL AUTO_INCREMENT,
    code VARCHAR(20) NOT NULL,
    type VARCHAR(30) NOT NULL DEFAULT '',
    description VARCHAR(500) DEFAULT NULL,
    guide TEXT,
    is_active TINYINT UNSIGNED DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    PRIMARY KEY (id),
    UNIQUE KEY uq_nhso_error_code (code),
    KEY idx_nhso_error_type (type),
    KEY idx_nhso_error_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
