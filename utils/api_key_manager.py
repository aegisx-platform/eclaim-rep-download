"""
API Key Management Utility
Handles generation, validation, and management of API keys
"""

import secrets
import hashlib
import json
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from config.database import get_db_config, DB_TYPE

if DB_TYPE == 'postgresql':
    import psycopg2
    from psycopg2.extras import RealDictCursor
else:
    import pymysql
    import pymysql.cursors


class APIKeyManager:
    """Manager for API keys"""

    @staticmethod
    def generate_api_key(prefix: str = 'eck') -> str:
        """
        Generate a secure API key

        Args:
            prefix: Prefix for the key (default: 'eck' for E-Claim Key)

        Returns:
            Generated API key string
        """
        # Generate 32 bytes (256 bits) of random data
        random_bytes = secrets.token_bytes(32)
        # Create SHA256 hash
        key_hash = hashlib.sha256(random_bytes).hexdigest()
        # Take first 48 characters and add prefix
        key = f"{prefix}_{key_hash[:48]}"
        return key

    @staticmethod
    def create_api_key(
        key_name: str,
        hospital_code: Optional[str] = None,
        description: Optional[str] = None,
        rate_limit: int = 100,
        allowed_ips: Optional[List[str]] = None,
        expires_in_days: Optional[int] = None,
        created_by: Optional[str] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Create a new API key

        Args:
            key_name: Name for this API key
            hospital_code: Hospital code (5 digits)
            description: Description of this key
            rate_limit: Requests per minute limit
            allowed_ips: List of allowed IP addresses
            expires_in_days: Days until expiration (None = never expires)
            created_by: Username who created this key

        Returns:
            (success, api_key, error_message)
        """
        try:
            # Generate API key
            api_key = APIKeyManager.generate_api_key()

            # Calculate expiration
            expires_at = None
            if expires_in_days:
                expires_at = datetime.now() + timedelta(days=expires_in_days)

            # Convert allowed_ips to JSON
            allowed_ips_json = json.dumps(allowed_ips) if allowed_ips else None

            # Insert into database
            conn = None
            cursor = None

            if DB_TYPE == 'postgresql':
                conn = psycopg2.connect(**get_db_config())
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO api_keys
                    (key_name, api_key, hospital_code, description, rate_limit,
                     allowed_ips, expires_at, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (key_name, api_key, hospital_code, description, rate_limit,
                      allowed_ips_json, expires_at, created_by))

            else:  # MySQL
                conn = pymysql.connect(**get_db_config())
                cursor = conn.cursor()

                cursor.execute("""
                    INSERT INTO api_keys
                    (key_name, api_key, hospital_code, description, rate_limit,
                     allowed_ips, expires_at, created_by)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, (key_name, api_key, hospital_code, description, rate_limit,
                      allowed_ips_json, expires_at, created_by))

            conn.commit()
            cursor.close()
            conn.close()

            return True, api_key, None

        except Exception as e:
            return False, None, str(e)

    @staticmethod
    def validate_api_key(api_key: str, ip_address: Optional[str] = None) -> Tuple[bool, Optional[Dict], Optional[str]]:
        """
        Validate an API key

        Args:
            api_key: API key to validate
            ip_address: IP address of the request

        Returns:
            (is_valid, key_data, error_message)
        """
        try:
            conn = None
            cursor = None

            if DB_TYPE == 'postgresql':
                conn = psycopg2.connect(**get_db_config())
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                conn = pymysql.connect(**get_db_config())
                cursor = conn.cursor(pymysql.cursors.DictCursor)

            # Get key details
            cursor.execute("""
                SELECT id, key_name, hospital_code, rate_limit, allowed_ips,
                       expires_at, is_active, last_used_at
                FROM api_keys
                WHERE api_key = %s
            """, (api_key,))

            key_data = cursor.fetchone()

            if not key_data:
                cursor.close()
                conn.close()
                return False, None, "Invalid API key"

            # Check if active
            if not key_data['is_active']:
                cursor.close()
                conn.close()
                return False, None, "API key is disabled"

            # Check expiration
            if key_data['expires_at']:
                if DB_TYPE == 'postgresql':
                    expires_at = key_data['expires_at']
                else:
                    expires_at = key_data['expires_at']

                if expires_at < datetime.now():
                    cursor.close()
                    conn.close()
                    return False, None, "API key has expired"

            # Check IP whitelist
            if key_data['allowed_ips'] and ip_address:
                allowed_ips = json.loads(key_data['allowed_ips'])
                if ip_address not in allowed_ips:
                    cursor.close()
                    conn.close()
                    return False, None, f"IP address {ip_address} not allowed"

            # Update last_used_at
            cursor.execute("""
                UPDATE api_keys
                SET last_used_at = %s
                WHERE id = %s
            """, (datetime.now(), key_data['id']))

            conn.commit()
            cursor.close()
            conn.close()

            return True, dict(key_data), None

        except Exception as e:
            return False, None, str(e)

    @staticmethod
    def get_all_keys() -> List[Dict]:
        """Get all API keys"""
        try:
            conn = None
            cursor = None

            if DB_TYPE == 'postgresql':
                conn = psycopg2.connect(**get_db_config())
                cursor = conn.cursor(cursor_factory=RealDictCursor)
            else:
                conn = pymysql.connect(**get_db_config())
                cursor = conn.cursor(pymysql.cursors.DictCursor)

            cursor.execute("""
                SELECT id, key_name, api_key, hospital_code, description,
                       rate_limit, is_active, last_used_at, expires_at,
                       created_at, created_by
                FROM api_keys
                ORDER BY created_at DESC
            """)

            keys = cursor.fetchall()
            cursor.close()
            conn.close()

            return [dict(k) for k in keys] if keys else []

        except Exception as e:
            print(f"Error getting API keys: {e}")
            return []

    @staticmethod
    def revoke_api_key(api_key_id: int) -> Tuple[bool, Optional[str]]:
        """
        Revoke (disable) an API key

        Args:
            api_key_id: ID of the API key

        Returns:
            (success, error_message)
        """
        try:
            conn = None
            cursor = None

            if DB_TYPE == 'postgresql':
                conn = psycopg2.connect(**get_db_config())
                cursor = conn.cursor()
            else:
                conn = pymysql.connect(**get_db_config())
                cursor = conn.cursor()

            cursor.execute("""
                UPDATE api_keys
                SET is_active = FALSE
                WHERE id = %s
            """, (api_key_id,))

            conn.commit()
            cursor.close()
            conn.close()

            return True, None

        except Exception as e:
            return False, str(e)

    @staticmethod
    def delete_api_key(api_key_id: int) -> Tuple[bool, Optional[str]]:
        """
        Permanently delete an API key

        Args:
            api_key_id: ID of the API key

        Returns:
            (success, error_message)
        """
        try:
            conn = None
            cursor = None

            if DB_TYPE == 'postgresql':
                conn = psycopg2.connect(**get_db_config())
                cursor = conn.cursor()
            else:
                conn = pymysql.connect(**get_db_config())
                cursor = conn.cursor()

            cursor.execute("DELETE FROM api_keys WHERE id = %s", (api_key_id,))

            conn.commit()
            cursor.close()
            conn.close()

            return True, None

        except Exception as e:
            return False, str(e)

    @staticmethod
    def log_api_usage(
        api_key_id: int,
        endpoint: str,
        method: str,
        ip_address: Optional[str],
        user_agent: Optional[str],
        status_code: int,
        response_time_ms: Optional[int],
        request_params: Optional[Dict] = None,
        error_message: Optional[str] = None
    ) -> bool:
        """Log API usage"""
        try:
            conn = None
            cursor = None

            request_params_json = json.dumps(request_params) if request_params else None

            if DB_TYPE == 'postgresql':
                conn = psycopg2.connect(**get_db_config())
                cursor = conn.cursor()
            else:
                conn = pymysql.connect(**get_db_config())
                cursor = conn.cursor()

            cursor.execute("""
                INSERT INTO api_usage_logs
                (api_key_id, endpoint, method, ip_address, user_agent,
                 status_code, response_time_ms, request_params, error_message)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (api_key_id, endpoint, method, ip_address, user_agent,
                  status_code, response_time_ms, request_params_json, error_message))

            conn.commit()
            cursor.close()
            conn.close()

            return True

        except Exception as e:
            print(f"Error logging API usage: {e}")
            return False
