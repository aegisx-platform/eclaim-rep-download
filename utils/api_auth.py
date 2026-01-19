"""
API Authentication Middleware
Handles API key authentication for external API endpoints
"""

from functools import wraps
from flask import request, jsonify
from utils.api_key_manager import APIKeyManager
import time


def require_api_key(f):
    """
    Decorator to require API key authentication

    Usage:
        @app.route('/api/v1/endpoint')
        @require_api_key
        def endpoint():
            # Access validated key data
            api_key_data = request.api_key_data
            return jsonify({'success': True})
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        start_time = time.time()

        # Get API key from headers
        api_key = None

        # Try X-API-Key header first
        if 'X-API-Key' in request.headers:
            api_key = request.headers.get('X-API-Key')
        # Try Authorization: Bearer <key> format
        elif 'Authorization' in request.headers:
            auth_header = request.headers.get('Authorization')
            if auth_header and auth_header.startswith('Bearer '):
                api_key = auth_header.replace('Bearer ', '', 1)

        if not api_key:
            return jsonify({
                'success': False,
                'error': 'API key is required',
                'code': 'MISSING_API_KEY'
            }), 401

        # Get client IP
        ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
        if ',' in ip_address:
            ip_address = ip_address.split(',')[0].strip()

        # Validate API key
        is_valid, key_data, error = APIKeyManager.validate_api_key(api_key, ip_address)

        if not is_valid:
            # Log failed attempt
            response_time = int((time.time() - start_time) * 1000)
            # We can't log without key_id, but we could log to a separate table for security
            return jsonify({
                'success': False,
                'error': error or 'Invalid API key',
                'code': 'INVALID_API_KEY'
            }), 401

        # Store key data in request context
        request.api_key_data = key_data
        request.api_key_id = key_data['id']
        request.api_start_time = start_time

        # Call the actual endpoint
        response = f(*args, **kwargs)

        # Log API usage (async would be better for production)
        response_time = int((time.time() - start_time) * 1000)
        status_code = response[1] if isinstance(response, tuple) else 200

        APIKeyManager.log_api_usage(
            api_key_id=key_data['id'],
            endpoint=request.path,
            method=request.method,
            ip_address=ip_address,
            user_agent=request.headers.get('User-Agent'),
            status_code=status_code,
            response_time_ms=response_time,
            request_params={
                'query': dict(request.args),
                'body': request.get_json(silent=True) if request.is_json else None
            }
        )

        return response

    return decorated_function


def get_client_ip() -> str:
    """Get client IP address from request"""
    ip_address = request.headers.get('X-Forwarded-For', request.remote_addr)
    if ',' in ip_address:
        ip_address = ip_address.split(',')[0].strip()
    return ip_address
