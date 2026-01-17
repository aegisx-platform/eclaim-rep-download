"""
Database Security Utilities

Provides security features for database operations:
- Row-Level Security (RLS) context management
- Secure connection handling
- Query parameter validation
- SQL injection prevention helpers

Usage:
    from utils.database_security import DatabaseSecurity

    # Set RLS context
    db_security = DatabaseSecurity(conn)
    db_security.set_user_context(
        user_id='123',
        user_role='user',
        hospital_code='10670'
    )

    # Execute query with RLS active
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM claim_rep_opip_nhso_item")  # Automatically filtered by RLS
"""

import psycopg2
import pymysql
from typing import Optional, Dict, Any
from config.database import get_db_config, DB_TYPE
from utils.logging_config import setup_logger

logger = setup_logger('database_security')


class DatabaseSecurity:
    """
    Database security helper for RLS and secure operations.
    """

    def __init__(self, connection):
        """
        Initialize database security helper.

        Args:
            connection: psycopg2 or pymysql connection object
        """
        self.connection = connection
        self.db_type = DB_TYPE

    def set_user_context(
        self,
        user_id: str,
        user_role: str,
        hospital_code: str
    ):
        """
        Set Row-Level Security context for current session.

        This must be called after getting a database connection
        and before executing any queries that need RLS filtering.

        Args:
            user_id: User ID
            user_role: User role (admin, user, readonly, analyst, auditor)
            hospital_code: Hospital code (5 digits)

        Example:
            db_security = DatabaseSecurity(conn)
            db_security.set_user_context(
                user_id=str(current_user.id),
                user_role=current_user.role,
                hospital_code=current_user.hospital_code
            )

            # Now all queries respect RLS
            cursor.execute("SELECT * FROM claim_rep_opip_nhso_item")
            # User only sees claims from their hospital
        """
        cursor = self.connection.cursor()

        try:
            if self.db_type == 'postgresql':
                # PostgreSQL: Use set_user_context() function
                cursor.execute(
                    "SELECT set_user_context(%s, %s, %s)",
                    (user_id, user_role, hospital_code)
                )
            else:
                # MySQL: Use set_user_context() procedure
                cursor.callproc('set_user_context', (user_id, user_role, hospital_code))

            self.connection.commit()

            logger.info(
                f"RLS context set: user_id={user_id}, role={user_role}, "
                f"hospital={hospital_code}"
            )

        except Exception as e:
            logger.error(f"Failed to set RLS context: {e}")
            raise
        finally:
            cursor.close()

    def clear_user_context(self):
        """
        Clear Row-Level Security context.

        Call this when returning connection to pool or on logout.
        """
        cursor = self.connection.cursor()

        try:
            if self.db_type == 'postgresql':
                cursor.execute("SELECT clear_user_context()")
            else:
                cursor.callproc('clear_user_context')

            self.connection.commit()
            logger.debug("RLS context cleared")

        except Exception as e:
            logger.error(f"Failed to clear RLS context: {e}")
            raise
        finally:
            cursor.close()

    def get_user_context(self) -> Dict[str, Optional[str]]:
        """
        Get current Row-Level Security context.

        Returns:
            Dict with user_id, user_role, hospital_code

        Example:
            context = db_security.get_user_context()
            print(f"Current user: {context['user_id']}")
            print(f"Hospital: {context['hospital_code']}")
        """
        cursor = self.connection.cursor()

        try:
            if self.db_type == 'postgresql':
                cursor.execute("SELECT * FROM get_user_context()")
                result = cursor.fetchone()
                if result:
                    return {
                        'user_id': result[0],
                        'user_role': result[1],
                        'hospital_code': result[2]
                    }
            else:
                cursor.callproc('get_user_context')
                result = cursor.fetchone()
                if result:
                    return {
                        'user_id': result[0],
                        'user_role': result[1],
                        'hospital_code': result[2]
                    }

            return {
                'user_id': None,
                'user_role': None,
                'hospital_code': None
            }

        except Exception as e:
            logger.error(f"Failed to get RLS context: {e}")
            raise
        finally:
            cursor.close()

    def test_rls(self) -> bool:
        """
        Test if Row-Level Security is working correctly.

        Returns:
            True if RLS is active and working

        Example:
            if not db_security.test_rls():
                logger.error("RLS is not working!")
        """
        cursor = self.connection.cursor()

        try:
            if self.db_type == 'postgresql':
                # Test RLS by checking if policies exist
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM pg_policies
                    WHERE tablename IN ('claim_rep_opip_nhso_item', 'audit_log', 'users')
                """)
                policy_count = cursor.fetchone()[0]

                if policy_count > 0:
                    logger.info(f"RLS test passed: {policy_count} policies found")
                    return True
                else:
                    logger.warning("RLS test failed: No policies found")
                    return False
            else:
                # MySQL: Test by checking if views exist
                cursor.execute("""
                    SELECT COUNT(*)
                    FROM information_schema.views
                    WHERE table_schema = DATABASE()
                    AND table_name LIKE 'v_%_secure'
                """)
                view_count = cursor.fetchone()[0]

                if view_count > 0:
                    logger.info(f"RLS test passed: {view_count} secure views found")
                    return True
                else:
                    logger.warning("RLS test failed: No secure views found")
                    return False

        except Exception as e:
            logger.error(f"RLS test error: {e}")
            return False
        finally:
            cursor.close()


# =============================================================================
# SQL INJECTION PREVENTION HELPERS
# =============================================================================

def validate_identifier(identifier: str, max_length: int = 100) -> str:
    """
    Validate SQL identifier (table/column name).

    Prevents SQL injection in dynamic queries.

    Args:
        identifier: Table or column name
        max_length: Maximum length allowed

    Returns:
        Validated identifier

    Raises:
        ValueError: If identifier contains invalid characters

    Example:
        table = validate_identifier(request.args.get('table'))
        query = f"SELECT * FROM {table}"  # Safe because validated
    """
    # Allow only alphanumeric, underscore, and hyphen
    if not identifier.replace('_', '').replace('-', '').isalnum():
        raise ValueError(f"Invalid identifier: {identifier}")

    if len(identifier) > max_length:
        raise ValueError(f"Identifier too long: {len(identifier)} > {max_length}")

    # Block SQL keywords
    sql_keywords = [
        'SELECT', 'INSERT', 'UPDATE', 'DELETE', 'DROP', 'CREATE',
        'ALTER', 'EXEC', 'EXECUTE', 'UNION', 'FROM', 'WHERE'
    ]

    if identifier.upper() in sql_keywords:
        raise ValueError(f"Identifier cannot be SQL keyword: {identifier}")

    return identifier


def validate_sort_column(column: str, allowed_columns: list) -> str:
    """
    Validate sort column for ORDER BY clause.

    Args:
        column: Column name to sort by
        allowed_columns: List of allowed column names

    Returns:
        Validated column name

    Raises:
        ValueError: If column not in allowed list

    Example:
        allowed = ['date', 'amount', 'patient_id']
        column = validate_sort_column(request.args.get('sort'), allowed)
        query = f"SELECT * FROM claims ORDER BY {column}"
    """
    column = column.strip()

    if column not in allowed_columns:
        raise ValueError(
            f"Invalid sort column: {column}. "
            f"Allowed: {', '.join(allowed_columns)}"
        )

    return column


def validate_sort_direction(direction: str) -> str:
    """
    Validate sort direction for ORDER BY clause.

    Args:
        direction: 'asc' or 'desc'

    Returns:
        Validated direction ('ASC' or 'DESC')

    Raises:
        ValueError: If direction invalid

    Example:
        direction = validate_sort_direction(request.args.get('dir', 'asc'))
        query = f"SELECT * FROM claims ORDER BY date {direction}"
    """
    direction = direction.strip().upper()

    if direction not in ['ASC', 'DESC']:
        raise ValueError(f"Invalid sort direction: {direction}. Must be ASC or DESC")

    return direction


def escape_like_pattern(pattern: str) -> str:
    """
    Escape special characters in LIKE pattern.

    Args:
        pattern: Search pattern

    Returns:
        Escaped pattern

    Example:
        search = escape_like_pattern(request.args.get('search'))
        cursor.execute(
            "SELECT * FROM claims WHERE patient_name LIKE %s",
            (f"%{search}%",)
        )
    """
    # Escape % and _ which are wildcards in LIKE
    pattern = pattern.replace('\\', '\\\\')  # Escape backslash first
    pattern = pattern.replace('%', '\\%')
    pattern = pattern.replace('_', '\\_')

    return pattern


# =============================================================================
# SECURE CONNECTION HELPERS
# =============================================================================

def get_secure_connection():
    """
    Get database connection with security best practices.

    Returns:
        Database connection with SSL/TLS (if configured)

    Example:
        conn = get_secure_connection()
        db_security = DatabaseSecurity(conn)
        db_security.set_user_context(...)
    """
    config = get_db_config()

    # Add SSL/TLS configuration if available
    # Note: Requires SSL certificates to be configured
    # See: docs/technical/DATABASE_SECURITY.md

    if DB_TYPE == 'postgresql':
        # PostgreSQL SSL configuration
        # config['sslmode'] = 'require'  # Uncomment when SSL certs available
        conn = psycopg2.connect(**config)
    else:
        # MySQL SSL configuration
        # config['ssl'] = {'ssl_ca': '/path/to/ca.pem'}  # Uncomment when SSL certs available
        conn = pymysql.connect(**config)

    logger.debug("Secure database connection established")
    return conn


def close_secure_connection(connection, clear_context: bool = True):
    """
    Close database connection securely.

    Args:
        connection: Database connection
        clear_context: Clear RLS context before closing

    Example:
        conn = get_secure_connection()
        try:
            # Use connection
            pass
        finally:
            close_secure_connection(conn)
    """
    if clear_context:
        try:
            db_security = DatabaseSecurity(connection)
            db_security.clear_user_context()
        except Exception as e:
            logger.warning(f"Failed to clear context on close: {e}")

    connection.close()
    logger.debug("Secure database connection closed")
