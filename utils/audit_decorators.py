"""
Flask Decorators for Automatic Audit Logging

Provides decorators to automatically log API requests and data access.
Captures user context from Flask request object.

Usage:
    from utils.audit_decorators import audit_action

    @app.route('/api/settings', methods=['POST'])
    @audit_action('SETTINGS_CHANGE', 'settings')
    def update_settings():
        # ... your code ...
        return jsonify({'success': True})

    # The decorator automatically logs:
    # - User ID (from session when auth is implemented)
    # - IP address
    # - User agent
    # - Request method and path
    # - Response status
"""

from functools import wraps
from flask import request, g
from typing import Optional, Callable
import time

from utils.audit_logger import audit_logger


def audit_action(
    action: str,
    resource_type: str,
    resource_id_param: Optional[str] = None,
    include_request_body: bool = False
):
    """
    Decorator to automatically audit log an API endpoint.

    Args:
        action: Action type (CREATE, READ, UPDATE, DELETE, etc.)
        resource_type: Resource type (table name or resource type)
        resource_id_param: Name of parameter containing resource ID (e.g., 'filename', 'id')
        include_request_body: Whether to log request body as new_data

    Example:
        @app.route('/api/files/<filename>', methods=['DELETE'])
        @audit_action('DELETE', 'files', resource_id_param='filename')
        def delete_file(filename):
            # filename is automatically captured as resource_id
            pass

        @app.route('/api/settings', methods=['POST'])
        @audit_action('SETTINGS_CHANGE', 'settings', include_request_body=True)
        def update_settings():
            # Request JSON is captured as new_data
            pass
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            error = None
            status = audit_logger.STATUS_SUCCESS

            try:
                # Execute the route function
                response = f(*args, **kwargs)
                return response

            except Exception as e:
                error = e
                status = audit_logger.STATUS_FAILED
                raise

            finally:
                # Calculate duration
                duration_ms = int((time.time() - start_time) * 1000)

                # Get resource ID from kwargs if specified
                resource_id = None
                if resource_id_param and resource_id_param in kwargs:
                    resource_id = str(kwargs[resource_id_param])

                # Get user info (will be populated when auth is implemented)
                user_id = getattr(g, 'user_id', None) or 'anonymous'
                user_email = getattr(g, 'user_email', None)
                session_id = getattr(g, 'session_id', None)

                # Get request body if requested
                new_data = None
                if include_request_body and request.is_json:
                    new_data = request.get_json(silent=True)

                # Log the audit event
                audit_logger.log(
                    action=action,
                    resource_type=resource_type,
                    resource_id=resource_id,
                    user_id=user_id,
                    user_email=user_email,
                    session_id=session_id,
                    new_data=new_data,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    request_method=request.method,
                    request_path=request.path,
                    request_params=dict(request.args) if request.args else None,
                    status=status,
                    error_message=str(error) if error else None,
                    duration_ms=duration_ms
                )

        return decorated_function
    return decorator


def audit_data_access(resource_type: str, resource_id_param: Optional[str] = None):
    """
    Decorator specifically for data read/access operations.

    Args:
        resource_type: Resource type being accessed
        resource_id_param: Parameter containing resource ID

    Example:
        @app.route('/api/claims/<claim_id>')
        @audit_data_access('claims', resource_id_param='claim_id')
        def get_claim(claim_id):
            pass
    """
    return audit_action(
        action=audit_logger.ACTION_READ,
        resource_type=resource_type,
        resource_id_param=resource_id_param
    )


def audit_data_export(resource_type: str, format_param: str = 'format'):
    """
    Decorator specifically for data export operations (CRITICAL for PDPA).

    Args:
        resource_type: Type of data being exported
        format_param: Parameter name containing export format

    Example:
        @app.route('/api/analytics/export')
        @audit_data_export('analytics_claims')
        def export_claims():
            pass
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()

            try:
                response = f(*args, **kwargs)
                return response

            finally:
                duration_ms = int((time.time() - start_time) * 1000)

                # Get export details
                export_format = request.args.get(format_param, 'unknown')

                # Get user info
                user_id = getattr(g, 'user_id', None) or 'anonymous'

                # Log export
                audit_logger.log_data_export(
                    resource_type=resource_type,
                    user_id=user_id,
                    ip_address=request.remote_addr,
                    export_format=export_format,
                    metadata={
                        'duration_ms': duration_ms,
                        'user_agent': request.headers.get('User-Agent'),
                        'filters': dict(request.args)
                    }
                )

        return decorated_function
    return decorator


def audit_bulk_operation(action: str, resource_type: str):
    """
    Decorator for bulk operations (import, delete, etc.).

    Automatically tracks count of affected records.

    Args:
        action: Action type (IMPORT, BULK_DELETE, etc.)
        resource_type: Resource type

    Example:
        @app.route('/api/imports/bulk', methods=['POST'])
        @audit_bulk_operation('IMPORT', 'claims')
        def bulk_import_claims():
            # Return response with 'count' key
            return jsonify({'success': True, 'count': 1000})
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args, **kwargs):
            start_time = time.time()
            error = None
            status = audit_logger.STATUS_SUCCESS
            count = None

            try:
                response = f(*args, **kwargs)

                # Try to extract count from response
                if hasattr(response, 'json') and response.json:
                    count = response.json.get('count') or response.json.get('total')

                return response

            except Exception as e:
                error = e
                status = audit_logger.STATUS_FAILED
                raise

            finally:
                duration_ms = int((time.time() - start_time) * 1000)

                user_id = getattr(g, 'user_id', None) or 'anonymous'

                audit_logger.log(
                    action=action,
                    resource_type=resource_type,
                    user_id=user_id,
                    ip_address=request.remote_addr,
                    user_agent=request.headers.get('User-Agent'),
                    request_method=request.method,
                    request_path=request.path,
                    status=status,
                    error_message=str(error) if error else None,
                    duration_ms=duration_ms,
                    metadata={'affected_count': count}
                )

        return decorated_function
    return decorator


# Example usage in app.py:
"""
from utils.audit_decorators import audit_action, audit_data_access, audit_data_export

# Simple CRUD operations
@app.route('/api/settings', methods=['POST'])
@audit_action('SETTINGS_CHANGE', 'settings', include_request_body=True)
def update_settings():
    pass

# Data access
@app.route('/api/claims/<claim_id>')
@audit_data_access('claims', resource_id_param='claim_id')
def get_claim(claim_id):
    pass

# Data export (CRITICAL for PDPA)
@app.route('/api/analytics/export')
@audit_data_export('analytics_claims')
def export_claims():
    pass

# Bulk operations
@app.route('/api/imports/bulk', methods=['POST'])
@audit_bulk_operation('IMPORT', 'claims')
def bulk_import():
    return jsonify({'success': True, 'count': 1000})

# File deletion
@app.route('/api/files/<filename>', methods=['DELETE'])
@audit_action('DELETE', 'files', resource_id_param='filename')
def delete_file(filename):
    pass
"""
