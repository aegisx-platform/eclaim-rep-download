-- Health Offices table for MySQL
-- Master data for healthcare facilities

CREATE TABLE IF NOT EXISTS health_offices (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(500) NOT NULL,
    hcode9_new VARCHAR(20),
    hcode9 VARCHAR(20),
    hcode5 VARCHAR(10),
    license_no VARCHAR(20),
    org_type VARCHAR(100),
    service_type VARCHAR(200),
    affiliation VARCHAR(200),
    department VARCHAR(200),
    hospital_level VARCHAR(100),
    actual_beds INTEGER DEFAULT 0,
    status VARCHAR(50),
    health_region VARCHAR(50),
    address TEXT,
    province_code VARCHAR(10),
    province VARCHAR(100),
    district_code VARCHAR(10),
    district VARCHAR(100),
    subdistrict_code VARCHAR(10),
    subdistrict VARCHAR(100),
    moo VARCHAR(10),
    postal_code VARCHAR(10),
    parent_code VARCHAR(100),
    established_date DATE,
    closed_date DATE,
    source_updated_at DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    UNIQUE KEY uq_health_offices_hcode5 (hcode5),
    INDEX idx_health_offices_hcode5 (hcode5),
    INDEX idx_health_offices_hcode9 (hcode9),
    INDEX idx_health_offices_province (province_code),
    INDEX idx_health_offices_status (status),
    INDEX idx_health_offices_level (hospital_level),
    INDEX idx_health_offices_region (health_region),
    INDEX idx_health_offices_name (name(100))
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='Master data for healthcare facilities';

-- Import tracking for health offices
CREATE TABLE IF NOT EXISTS health_offices_import_log (
    id INT AUTO_INCREMENT PRIMARY KEY,
    import_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    filename VARCHAR(255),
    total_records INTEGER DEFAULT 0,
    imported INTEGER DEFAULT 0,
    updated INTEGER DEFAULT 0,
    skipped INTEGER DEFAULT 0,
    errors INTEGER DEFAULT 0,
    import_mode VARCHAR(20) DEFAULT 'upsert',
    status VARCHAR(20) DEFAULT 'completed',
    error_message TEXT,
    duration_seconds DECIMAL(10,2)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
COMMENT='Import log for health offices data';
