"""
API Keys Management Routes
Routes for managing API keys in settings
"""

from flask import Blueprint, jsonify, request
from flask_login import login_required
from utils.api_key_manager import APIKeyManager
from utils.auth import require_admin
import logging

# Create blueprint
api_keys_mgmt_bp = Blueprint('api_keys_mgmt', __name__, url_prefix='/api/settings')

logger = logging.getLogger(__name__)


@api_keys_mgmt_bp.route('/api-keys', methods=['GET', 'POST'])
@login_required
@require_admin
def manage_api_keys():
    """
    GET: List all API keys
    POST: Create new API key
    """
    if request.method == 'GET':
        try:
            keys = APIKeyManager.get_all_keys()

            # Mask API keys for security (show only last 8 characters)
            for key in keys:
                if key.get('api_key'):
                    key['api_key_masked'] = '••••••••' + key['api_key'][-8:]
                    key['api_key'] = None  # Don't send full key

            return jsonify({
                'success': True,
                'keys': keys
            })

        except Exception as e:
            logger.error(f"Error getting API keys: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    elif request.method == 'POST':
        try:
            data = request.get_json()

            key_name = data.get('key_name')
            hospital_code = data.get('hospital_code')
            description = data.get('description')
            rate_limit = int(data.get('rate_limit', 100))
            allowed_ips = data.get('allowed_ips', [])
            expires_in_days = data.get('expires_in_days')

            if not key_name:
                return jsonify({
                    'success': False,
                    'error': 'Key name is required'
                }), 400

            # Convert expires_in_days to int if provided
            if expires_in_days:
                try:
                    expires_in_days = int(expires_in_days)
                except ValueError:
                    expires_in_days = None

            # Get current user (from Flask-Login)
            from flask_login import current_user
            created_by = current_user.username if hasattr(current_user, 'username') else None

            # Create API key
            success, api_key, error = APIKeyManager.create_api_key(
                key_name=key_name,
                hospital_code=hospital_code,
                description=description,
                rate_limit=rate_limit,
                allowed_ips=allowed_ips if allowed_ips else None,
                expires_in_days=expires_in_days,
                created_by=created_by
            )

            if not success:
                return jsonify({
                    'success': False,
                    'error': error
                }), 500

            return jsonify({
                'success': True,
                'api_key': api_key,
                'message': 'API key created successfully'
            })

        except Exception as e:
            logger.error(f"Error creating API key: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@api_keys_mgmt_bp.route('/api-keys/<int:key_id>', methods=['PUT', 'DELETE'])
@login_required
@require_admin
def manage_api_key(key_id):
    """
    PUT: Update API key (toggle active status)
    DELETE: Delete API key
    """
    if request.method == 'PUT':
        try:
            data = request.get_json()
            is_active = data.get('is_active')

            if is_active is False:
                # Revoke the key
                success, error = APIKeyManager.revoke_api_key(key_id)

                if not success:
                    return jsonify({
                        'success': False,
                        'error': error
                    }), 500

                return jsonify({
                    'success': True,
                    'message': 'API key revoked successfully'
                })
            else:
                # TODO: Implement re-enable if needed
                return jsonify({
                    'success': False,
                    'error': 'Re-enabling keys not yet supported'
                }), 400

        except Exception as e:
            logger.error(f"Error updating API key: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    elif request.method == 'DELETE':
        try:
            success, error = APIKeyManager.delete_api_key(key_id)

            if not success:
                return jsonify({
                    'success': False,
                    'error': error
                }), 500

            return jsonify({
                'success': True,
                'message': 'API key deleted successfully'
            })

        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


@api_keys_mgmt_bp.route('/api-keys/usage/<int:key_id>', methods=['GET'])
@login_required
@require_admin
def get_api_key_usage(key_id):
    """Get usage statistics for an API key"""
    try:
        # TODO: Implement usage statistics query
        return jsonify({
            'success': True,
            'usage': {
                'total_requests': 0,
                'last_7_days': 0,
                'last_24_hours': 0
            }
        })

    except Exception as e:
        logger.error(f"Error getting API key usage: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
