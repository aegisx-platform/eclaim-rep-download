"""
Audit Logging Utility for PDPA Compliance

Provides centralized audit logging for all data access and modifications.
Automatically captures user context, IP address, and request details.

Usage:
    from utils.audit_logger import audit_logger

    # Simple usage
    audit_logger.log('CREATE', 'settings', user_id='admin')

    # With details
    audit_logger.log(
        action='UPDATE',
        resource_type='claim_rep_opip_nhso_item',
        resource_id='12345',
        user_id='user@hospital.local',
        old_data={'status': 'pending'},
        new_data={'status': 'approved'},
        ip_address=request.remote_addr
    )

CRITICAL SECURITY: Required for PDPA compliance and incident investigation
"""

import json
import time
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager

from config.database import get_db_config, DB_TYPE
from config.db_pool import get_connection, return_connection


class AuditLogger:
    """
    Centralized audit logging for PDPA compliance.

    Tracks all data access and modifications with:
    - User identification
    - Action details
    - Before/after state
    - Request context (IP, user agent, etc.)
    - Timing information
    """

    # Action types (matches database constraint)
    ACTION_CREATE = 'CREATE'
    ACTION_READ = 'READ'
    ACTION_UPDATE = 'UPDATE'
    ACTION_DELETE = 'DELETE'
    ACTION_LOGIN = 'LOGIN'
    ACTION_LOGOUT = 'LOGOUT'
    ACTION_LOGIN_FAILED = 'LOGIN_FAILED'
    ACTION_EXPORT = 'EXPORT'
    ACTION_IMPORT = 'IMPORT'
    ACTION_DOWNLOAD = 'DOWNLOAD'
    ACTION_SETTINGS_CHANGE = 'SETTINGS_CHANGE'
    ACTION_PERMISSION_CHANGE = 'PERMISSION_CHANGE'
    ACTION_DATA_ACCESS = 'DATA_ACCESS'
    ACTION_BULK_DELETE = 'BULK_DELETE'
    ACTION_BACKUP = 'BACKUP'
    ACTION_RESTORE = 'RESTORE'

    # Status types
    STATUS_SUCCESS = 'success'
    STATUS_FAILED = 'failed'
    STATUS_DENIED = 'denied'

    def __init__(self):
        """Initialize audit logger."""
        self.db_type = DB_TYPE

    def log(
        self,
        action: str,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        user_email: Optional[str] = None,
        session_id: Optional[str] = None,
        old_data: Optional[Dict[str, Any]] = None,
        new_data: Optional[Dict[str, Any]] = None,
        changes_summary: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        request_method: Optional[str] = None,
        request_path: Optional[str] = None,
        request_params: Optional[Dict[str, Any]] = None,
        status: str = STATUS_SUCCESS,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Optional[int]:
        """
        Log an audit event to the database.

        Args:
            action: Action type (CREATE, READ, UPDATE, DELETE, etc.)
            resource_type: Type of resource (table name or resource type)
            resource_id: Primary key of affected record
            user_id: User identifier
            user_email: User email
            session_id: Session identifier
            old_data: Previous state (for UPDATE/DELETE)
            new_data: New state (for CREATE/UPDATE)
            changes_summary: Human-readable summary
            ip_address: User's IP address
            user_agent: Browser/client info
            request_method: HTTP method (GET, POST, etc.)
            request_path: API endpoint path
            request_params: Query parameters (sanitized)
            status: success, failed, or denied
            error_message: Error details if failed
            duration_ms: Operation duration in milliseconds
            metadata: Additional context

        Returns:
            Audit log ID if successful, None if failed
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Sanitize request params to remove sensitive data
            if request_params:
                request_params = self._sanitize_params(request_params)

            # Convert dicts to JSON strings
            old_data_json = json.dumps(old_data) if old_data else None
            new_data_json = json.dumps(new_data) if new_data else None
            request_params_json = json.dumps(request_params) if request_params else None
            metadata_json = json.dumps(metadata) if metadata else None

            if self.db_type == 'postgresql':
                query = """
                    INSERT INTO audit_log (
                        user_id, user_email, session_id,
                        action, resource_type, resource_id,
                        old_data, new_data, changes_summary,
                        ip_address, user_agent, request_method, request_path, request_params,
                        status, error_message, duration_ms, metadata
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s::jsonb, %s::jsonb, %s,
                        %s, %s, %s, %s, %s::jsonb,
                        %s, %s, %s, %s::jsonb
                    ) RETURNING id
                """
            else:  # MySQL
                query = """
                    INSERT INTO audit_log (
                        user_id, user_email, session_id,
                        action, resource_type, resource_id,
                        old_data, new_data, changes_summary,
                        ip_address, user_agent, request_method, request_path, request_params,
                        status, error_message, duration_ms, metadata
                    ) VALUES (
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s,
                        %s, %s, %s, %s, %s,
                        %s, %s, %s, %s
                    )
                """

            cursor.execute(query, (
                user_id, user_email, session_id,
                action, resource_type, resource_id,
                old_data_json, new_data_json, changes_summary,
                ip_address, user_agent, request_method, request_path, request_params_json,
                status, error_message, duration_ms, metadata_json
            ))

            conn.commit()

            # Get inserted ID
            if self.db_type == 'postgresql':
                audit_id = cursor.fetchone()[0]
            else:  # MySQL
                audit_id = cursor.lastrowid

            return audit_id

        except Exception as e:
            if conn:
                conn.rollback()
            # Don't raise - audit logging should never break the application
            print(f"Warning: Audit log failed: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def log_login(
        self,
        user_id: str,
        success: bool = True,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> Optional[int]:
        """
        Log a login attempt.

        Args:
            user_id: User identifier
            success: Whether login succeeded
            ip_address: User's IP address
            user_agent: Browser/client info
            error_message: Error message if failed

        Returns:
            Audit log ID
        """
        return self.log(
            action=self.ACTION_LOGIN if success else self.ACTION_LOGIN_FAILED,
            resource_type='authentication',
            user_id=user_id,
            ip_address=ip_address,
            user_agent=user_agent,
            status=self.STATUS_SUCCESS if success else self.STATUS_FAILED,
            error_message=error_message
        )

    def log_logout(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Optional[int]:
        """Log a logout event."""
        return self.log(
            action=self.ACTION_LOGOUT,
            resource_type='authentication',
            user_id=user_id,
            session_id=session_id,
            ip_address=ip_address
        )

    def log_data_access(
        self,
        resource_type: str,
        resource_id: Optional[str] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        count: Optional[int] = None
    ) -> Optional[int]:
        """
        Log data access (read operation).

        Args:
            resource_type: Type of data accessed
            resource_id: Specific record ID (if applicable)
            user_id: User who accessed the data
            ip_address: User's IP address
            count: Number of records accessed (for bulk reads)

        Returns:
            Audit log ID
        """
        metadata = {'count': count} if count else None
        return self.log(
            action=self.ACTION_READ,
            resource_type=resource_type,
            resource_id=resource_id,
            user_id=user_id,
            ip_address=ip_address,
            metadata=metadata
        )

    def log_data_export(
        self,
        resource_type: str,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
        record_count: Optional[int] = None,
        export_format: Optional[str] = None,
        filename: Optional[str] = None
    ) -> Optional[int]:
        """
        Log data export (critical for PDPA compliance).

        Args:
            resource_type: Type of data exported
            user_id: User who exported the data
            ip_address: User's IP address
            record_count: Number of records exported
            export_format: Export format (excel, csv, json)
            filename: Export filename

        Returns:
            Audit log ID
        """
        return self.log(
            action=self.ACTION_EXPORT,
            resource_type=resource_type,
            user_id=user_id,
            ip_address=ip_address,
            metadata={
                'record_count': record_count,
                'export_format': export_format,
                'filename': filename
            }
        )

    def log_settings_change(
        self,
        setting_name: str,
        old_value: Any,
        new_value: Any,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> Optional[int]:
        """Log a settings change."""
        return self.log(
            action=self.ACTION_SETTINGS_CHANGE,
            resource_type='settings',
            resource_id=setting_name,
            user_id=user_id,
            ip_address=ip_address,
            old_data={'value': old_value},
            new_data={'value': new_value},
            changes_summary=f"Changed {setting_name} from {old_value} to {new_value}"
        )

    @contextmanager
    def timed_operation(
        self,
        action: str,
        resource_type: str,
        user_id: Optional[str] = None,
        **kwargs
    ):
        """
        Context manager for timing operations and auto-logging.

        Usage:
            with audit_logger.timed_operation('IMPORT', 'claims', user_id='admin'):
                # ... perform import ...
                pass
        """
        start_time = time.time()
        error = None

        try:
            yield
        except Exception as e:
            error = e
            raise
        finally:
            duration_ms = int((time.time() - start_time) * 1000)
            self.log(
                action=action,
                resource_type=resource_type,
                user_id=user_id,
                duration_ms=duration_ms,
                status=self.STATUS_FAILED if error else self.STATUS_SUCCESS,
                error_message=str(error) if error else None,
                **kwargs
            )

    def _sanitize_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remove sensitive data from request parameters.

        Args:
            params: Request parameters

        Returns:
            Sanitized parameters
        """
        # List of parameter names to redact
        sensitive_keys = {
            'password', 'passwd', 'pwd', 'pass',
            'secret', 'token', 'api_key', 'apikey',
            'auth', 'authorization', 'session',
            'credit_card', 'ssn', 'social_security'
        }

        sanitized = {}
        for key, value in params.items():
            # Check if key contains sensitive keyword
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                sanitized[key] = '***REDACTED***'
            else:
                sanitized[key] = value

        return sanitized

    def get_user_activity(
        self,
        user_id: str,
        days: int = 30
    ) -> list:
        """
        Get recent activity for a user (PDPA right to access).

        Args:
            user_id: User identifier
            days: Number of days to look back

        Returns:
            List of activity records
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            if self.db_type == 'postgresql':
                query = """
                    SELECT
                        action, resource_type, resource_id,
                        timestamp, ip_address, status
                    FROM audit_log
                    WHERE user_id = %s
                      AND timestamp > CURRENT_TIMESTAMP - INTERVAL '%s days'
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """
            else:  # MySQL
                query = """
                    SELECT
                        action, resource_type, resource_id,
                        timestamp, ip_address, status
                    FROM audit_log
                    WHERE user_id = %s
                      AND timestamp > DATE_SUB(NOW(), INTERVAL %s DAY)
                    ORDER BY timestamp DESC
                    LIMIT 1000
                """

            cursor.execute(query, (user_id, days))
            columns = [desc[0] for desc in cursor.description]
            return [dict(zip(columns, row)) for row in cursor.fetchall()]

        except Exception as e:
            print(f"Warning: Failed to get user activity: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)


# Global instance
audit_logger = AuditLogger()
