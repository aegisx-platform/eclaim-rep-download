#!/usr/bin/env python3
"""
Database Configuration for E-Claim Import System
"""

import os
from pathlib import Path

# Database type: 'postgresql' or 'mysql'
DB_TYPE = os.getenv('DB_TYPE', 'postgresql')

# Database connection settings
DB_CONFIG = {
    'postgresql': {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 5432)),
        'database': os.getenv('DB_NAME', 'eclaim_db'),
        'user': os.getenv('DB_USER', 'postgres'),
        'password': os.getenv('DB_PASSWORD', ''),
    },
    'mysql': {
        'host': os.getenv('DB_HOST', 'localhost'),
        'port': int(os.getenv('DB_PORT', 3306)),
        'database': os.getenv('DB_NAME', 'eclaim_db'),
        'user': os.getenv('DB_USER', 'root'),
        'password': os.getenv('DB_PASSWORD', ''),
        'charset': 'utf8mb4'
    }
}

# Import settings
IMPORT_CONFIG = {
    'batch_size': 100,  # Number of records to insert per batch
    'max_retries': 3,  # Max retry attempts for failed imports
    'timeout': 30,  # Database query timeout in seconds
}

# File paths
BASE_DIR = Path(__file__).resolve().parent.parent
DOWNLOADS_DIR = BASE_DIR / 'downloads'
LOGS_DIR = BASE_DIR / 'logs'
DATABASE_DIR = BASE_DIR / 'database'

# Ensure directories exist
LOGS_DIR.mkdir(exist_ok=True)


def get_db_config(db_type: str = None) -> dict:
    """
    Get database configuration

    Args:
        db_type: 'postgresql' or 'mysql', defaults to DB_TYPE env var

    Returns:
        Database configuration dict
    """
    if db_type is None:
        db_type = DB_TYPE

    if db_type not in DB_CONFIG:
        raise ValueError(f"Invalid DB_TYPE: {db_type}. Must be 'postgresql' or 'mysql'")

    return DB_CONFIG[db_type]


def get_connection_string(db_type: str = None) -> str:
    """
    Get database connection string

    Args:
        db_type: 'postgresql' or 'mysql'

    Returns:
        Connection string (SQLAlchemy format)
    """
    if db_type is None:
        db_type = DB_TYPE

    config = get_db_config(db_type)

    if db_type == 'postgresql':
        return (f"postgresql://{config['user']}:{config['password']}@"
                f"{config['host']}:{config['port']}/{config['database']}")
    elif db_type == 'mysql':
        return (f"mysql+pymysql://{config['user']}:{config['password']}@"
                f"{config['host']}:{config['port']}/{config['database']}"
                f"?charset={config['charset']}")

    raise ValueError(f"Unsupported DB_TYPE: {db_type}")
