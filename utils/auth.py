"""
User Authentication System

Provides user management and authentication using Flask-Login and bcrypt.
Integrates with audit logging for security tracking.

Usage:
    from utils.auth import auth_manager, User

    # Login user
    user = auth_manager.authenticate('admin', 'password')
    if user:
        login_user(user)

    # Check permissions
    @login_required
    @require_role('admin')
    def admin_only_route():
        pass
"""

import bcrypt
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from functools import wraps

from flask import request, g, abort, redirect, url_for, session
from flask_login import UserMixin, current_user

from config.database import get_db_config, DB_TYPE
from config.db_pool import get_connection, return_connection
from utils.audit_logger import audit_logger


class User(UserMixin):
    """
    User model for Flask-Login.

    Implements UserMixin for Flask-Login integration.
    """

    def __init__(
        self,
        id: int,
        username: str,
        email: str,
        full_name: Optional[str] = None,
        role: str = 'user',
        hospital_code: Optional[str] = None,
        is_active: bool = True,
        must_change_password: bool = False
    ):
        self.id = id
        self.username = username
        self.email = email
        self.full_name = full_name
        self.role = role
        self.hospital_code = hospital_code
        self._is_active = is_active
        self.must_change_password = must_change_password

    def get_id(self):
        """Return user ID as string (required by Flask-Login)."""
        return str(self.id)

    @property
    def is_active(self):
        """Check if user is active (required by Flask-Login)."""
        return self._is_active

    @property
    def is_authenticated(self):
        """User is authenticated (required by Flask-Login)."""
        return True

    @property
    def is_anonymous(self):
        """User is not anonymous (required by Flask-Login)."""
        return False

    def has_role(self, *roles):
        """Check if user has any of the specified roles."""
        return self.role in roles

    def is_admin(self):
        """Check if user is admin."""
        return self.role == 'admin'

    def can_edit(self):
        """Check if user can edit data."""
        return self.role in ('admin', 'user')

    def can_delete(self):
        """Check if user can delete data."""
        return self.role == 'admin'

    def can_export(self):
        """Check if user can export data."""
        return self.role in ('admin', 'user', 'analyst')

    def to_dict(self):
        """Convert user to dictionary."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'full_name': self.full_name,
            'role': self.role,
            'hospital_code': self.hospital_code,
            'is_active': self._is_active
        }


class AuthManager:
    """
    Manages user authentication and authorization.

    Handles:
    - User creation and updates
    - Password hashing and verification
    - Login/logout with audit logging
    - Account lockout after failed attempts
    - Session management
    """

    def __init__(self):
        """Initialize auth manager."""
        self.db_type = DB_TYPE

    def hash_password(self, password: str) -> str:
        """
        Hash a password using bcrypt.

        Args:
            password: Plain text password

        Returns:
            Bcrypt hashed password
        """
        return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    def verify_password(self, password: str, password_hash: str) -> bool:
        """
        Verify a password against its hash.

        Args:
            password: Plain text password
            password_hash: Bcrypt hash

        Returns:
            True if password matches
        """
        try:
            return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))
        except Exception:
            return False

    def get_user_by_id(self, user_id: int) -> Optional[User]:
        """
        Get user by ID (for Flask-Login user_loader).

        Args:
            user_id: User ID

        Returns:
            User object or None
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            query = """
                SELECT id, username, email, full_name, role, hospital_code,
                       is_active, must_change_password
                FROM users
                WHERE id = %s
                  AND deleted_at IS NULL
            """
            cursor.execute(query, (user_id,))
            row = cursor.fetchone()

            if row:
                return User(
                    id=row[0],
                    username=row[1],
                    email=row[2],
                    full_name=row[3],
                    role=row[4],
                    hospital_code=row[5],
                    is_active=row[6],
                    must_change_password=row[7]
                )

            return None

        except Exception as e:
            print(f"Error getting user by ID: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def get_user_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        """
        Get user details by username.

        Args:
            username: Username

        Returns:
            User dict with password_hash or None
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            query = """
                SELECT id, username, email, password_hash, full_name, role,
                       hospital_code, is_active, must_change_password,
                       failed_login_attempts, locked_until
                FROM users
                WHERE username = %s
                  AND deleted_at IS NULL
            """
            cursor.execute(query, (username,))
            row = cursor.fetchone()

            if row:
                return {
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'password_hash': row[3],
                    'full_name': row[4],
                    'role': row[5],
                    'hospital_code': row[6],
                    'is_active': row[7],
                    'must_change_password': row[8],
                    'failed_login_attempts': row[9],
                    'locked_until': row[10]
                }

            return None

        except Exception as e:
            print(f"Error getting user by username: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def is_account_locked(self, user_data: Dict[str, Any]) -> bool:
        """
        Check if account is locked.

        Args:
            user_data: User data dict

        Returns:
            True if account is locked
        """
        locked_until = user_data.get('locked_until')
        if not locked_until:
            return False

        # Check if lock has expired
        if isinstance(locked_until, str):
            from datetime import datetime
            locked_until = datetime.fromisoformat(locked_until)

        return locked_until > datetime.now()

    def authenticate(self, username: str, password: str, ip_address: Optional[str] = None) -> Optional[User]:
        """
        Authenticate user with username and password.

        Args:
            username: Username
            password: Plain text password
            ip_address: User's IP address

        Returns:
            User object if authenticated, None otherwise
        """
        user_data = self.get_user_by_username(username)

        if not user_data:
            # Log failed login
            audit_logger.log_login(
                user_id=username,
                success=False,
                ip_address=ip_address,
                error_message='User not found'
            )
            return None

        # Check if account is locked
        if self.is_account_locked(user_data):
            audit_logger.log_login(
                user_id=username,
                success=False,
                ip_address=ip_address,
                error_message='Account locked due to too many failed attempts'
            )
            return None

        # Check if account is active
        if not user_data['is_active']:
            audit_logger.log_login(
                user_id=username,
                success=False,
                ip_address=ip_address,
                error_message='Account disabled'
            )
            return None

        # Verify password
        if not self.verify_password(password, user_data['password_hash']):
            # Record failed login
            self._record_failed_login(username)

            audit_logger.log_login(
                user_id=username,
                success=False,
                ip_address=ip_address,
                error_message='Invalid password'
            )
            return None

        # Successful login
        self._reset_failed_login_attempts(user_data['id'], ip_address)

        audit_logger.log_login(
            user_id=username,
            success=True,
            ip_address=ip_address
        )

        return User(
            id=user_data['id'],
            username=user_data['username'],
            email=user_data['email'],
            full_name=user_data['full_name'],
            role=user_data['role'],
            hospital_code=user_data['hospital_code'],
            is_active=user_data['is_active'],
            must_change_password=user_data['must_change_password']
        )

    def create_user(
        self,
        username: str,
        email: str,
        password: str,
        full_name: Optional[str] = None,
        role: str = 'user',
        hospital_code: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> Optional[int]:
        """
        Create a new user.

        Args:
            username: Username (unique)
            email: Email (unique)
            password: Plain text password (will be hashed)
            full_name: Full name
            role: User role
            hospital_code: Hospital code
            created_by: Username of creator

        Returns:
            User ID if created, None otherwise
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            password_hash = self.hash_password(password)

            if self.db_type == 'postgresql':
                query = """
                    INSERT INTO users (
                        username, email, password_hash, full_name, role,
                        hospital_code, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """
            else:  # MySQL
                query = """
                    INSERT INTO users (
                        username, email, password_hash, full_name, role,
                        hospital_code, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """

            cursor.execute(query, (
                username, email, password_hash, full_name, role,
                hospital_code, created_by
            ))

            conn.commit()

            if self.db_type == 'postgresql':
                user_id = cursor.fetchone()[0]
            else:
                user_id = cursor.lastrowid

            # Log user creation
            audit_logger.log(
                action='CREATE',
                resource_type='users',
                resource_id=str(user_id),
                user_id=created_by or 'system',
                new_data={'username': username, 'role': role}
            )

            return user_id

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error creating user: {e}")
            return None

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def change_password(
        self,
        user_id: int,
        new_password: str,
        changed_by: Optional[str] = None
    ) -> bool:
        """
        Change user password.

        Args:
            user_id: User ID
            new_password: New plain text password
            changed_by: Username of who changed it

        Returns:
            True if successful
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            password_hash = self.hash_password(new_password)

            query = """
                UPDATE users
                SET password_hash = %s,
                    must_change_password = FALSE,
                    updated_by = %s
                WHERE id = %s
            """
            cursor.execute(query, (password_hash, changed_by, user_id))
            conn.commit()

            # Log password change
            audit_logger.log(
                action='UPDATE',
                resource_type='users',
                resource_id=str(user_id),
                user_id=changed_by or str(user_id),
                changes_summary='Password changed'
            )

            return True

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error changing password: {e}")
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def _record_failed_login(self, username: str):
        """Record failed login attempt."""
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            if self.db_type == 'postgresql':
                cursor.execute("SELECT record_failed_login(%s)", (username,))
            else:  # MySQL
                cursor.execute("CALL record_failed_login(%s)", (username,))

            conn.commit()

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error recording failed login: {e}")

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def _reset_failed_login_attempts(self, user_id: int, ip_address: Optional[str]):
        """Reset failed login attempts."""
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            if self.db_type == 'postgresql':
                cursor.execute("SELECT reset_failed_login_attempts(%s, %s)", (user_id, ip_address))
            else:  # MySQL
                cursor.execute("CALL reset_failed_login_attempts(%s, %s)", (user_id, ip_address))

            conn.commit()

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error resetting failed login attempts: {e}")

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def get_all_users(self) -> list:
        """
        Get all active users.

        Returns:
            List of user dicts
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            query = """
                SELECT id, username, email, full_name, role, hospital_code,
                       is_active, must_change_password, created_at, updated_at,
                       created_by, updated_by, last_login_at
                FROM users
                WHERE deleted_at IS NULL
                ORDER BY created_at DESC
            """
            cursor.execute(query)
            rows = cursor.fetchall()

            users = []
            for row in rows:
                users.append({
                    'id': row[0],
                    'username': row[1],
                    'email': row[2],
                    'full_name': row[3],
                    'role': row[4],
                    'hospital_code': row[5],
                    'is_active': row[6],
                    'must_change_password': row[7],
                    'created_at': row[8],
                    'updated_at': row[9],
                    'created_by': row[10],
                    'updated_by': row[11],
                    'last_login_at': row[12]
                })

            return users

        except Exception as e:
            print(f"Error getting all users: {e}")
            return []

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def update_user(
        self,
        user_id: int,
        email: Optional[str] = None,
        full_name: Optional[str] = None,
        role: Optional[str] = None,
        hospital_code: Optional[str] = None,
        updated_by: Optional[str] = None
    ) -> bool:
        """
        Update user information.

        Args:
            user_id: User ID
            email: New email
            full_name: New full name
            role: New role
            hospital_code: New hospital code
            updated_by: Username of updater

        Returns:
            True if successful
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            # Build update query dynamically
            updates = []
            params = []

            if email is not None:
                updates.append("email = %s")
                params.append(email)

            if full_name is not None:
                updates.append("full_name = %s")
                params.append(full_name)

            if role is not None:
                updates.append("role = %s")
                params.append(role)

            if hospital_code is not None:
                updates.append("hospital_code = %s")
                params.append(hospital_code)

            if not updates:
                return True  # Nothing to update

            updates.append("updated_by = %s")
            params.append(updated_by)
            params.append(user_id)

            query = f"""
                UPDATE users
                SET {', '.join(updates)}
                WHERE id = %s
            """

            cursor.execute(query, tuple(params))
            conn.commit()

            # Log user update
            audit_logger.log(
                action='UPDATE',
                resource_type='users',
                resource_id=str(user_id),
                user_id=updated_by or 'system',
                changes_summary=f"Updated: {', '.join([u.split('=')[0].strip() for u in updates[:-1]])}"
            )

            return True

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error updating user: {e}")
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def toggle_user_status(self, user_id: int, updated_by: Optional[str] = None) -> bool:
        """
        Toggle user active/inactive status.

        Args:
            user_id: User ID
            updated_by: Username of updater

        Returns:
            True if successful
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            query = """
                UPDATE users
                SET is_active = NOT is_active,
                    updated_by = %s
                WHERE id = %s
            """
            cursor.execute(query, (updated_by, user_id))
            conn.commit()

            # Log status change
            audit_logger.log(
                action='UPDATE',
                resource_type='users',
                resource_id=str(user_id),
                user_id=updated_by or 'system',
                changes_summary='Status toggled'
            )

            return True

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error toggling user status: {e}")
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def delete_user(self, user_id: int, deleted_by: Optional[str] = None) -> bool:
        """
        Soft delete user.

        Args:
            user_id: User ID
            deleted_by: Username of deleter

        Returns:
            True if successful
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            query = """
                UPDATE users
                SET deleted_at = NOW(),
                    is_active = FALSE,
                    updated_by = %s
                WHERE id = %s
            """
            cursor.execute(query, (deleted_by, user_id))
            conn.commit()

            # Log user deletion
            audit_logger.log(
                action='DELETE',
                resource_type='users',
                resource_id=str(user_id),
                user_id=deleted_by or 'system',
                changes_summary='User deleted (soft)'
            )

            return True

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error deleting user: {e}")
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)

    def reset_user_password(
        self,
        user_id: int,
        new_password: str,
        require_change: bool = True,
        reset_by: Optional[str] = None
    ) -> bool:
        """
        Reset user password (admin function).

        Args:
            user_id: User ID
            new_password: New plain text password
            require_change: Require password change on next login
            reset_by: Username of admin who reset it

        Returns:
            True if successful
        """
        conn = None
        cursor = None

        try:
            conn = get_connection()
            cursor = conn.cursor()

            password_hash = self.hash_password(new_password)

            query = """
                UPDATE users
                SET password_hash = %s,
                    must_change_password = %s,
                    updated_by = %s
                WHERE id = %s
            """
            cursor.execute(query, (password_hash, require_change, reset_by, user_id))
            conn.commit()

            # Log password reset
            audit_logger.log(
                action='UPDATE',
                resource_type='users',
                resource_id=str(user_id),
                user_id=reset_by or 'admin',
                changes_summary='Password reset by admin'
            )

            return True

        except Exception as e:
            if conn:
                conn.rollback()
            print(f"Error resetting password: {e}")
            return False

        finally:
            if cursor:
                cursor.close()
            if conn:
                return_connection(conn)


# Global instance
auth_manager = AuthManager()


# =============================================================================
# DECORATORS
# =============================================================================

def require_role(*roles):
    """
    Decorator to require specific role(s).

    Usage:
        @app.route('/admin')
        @login_required
        @require_role('admin')
        def admin_page():
            pass

        @require_role('admin', 'analyst')  # Allow multiple roles
        def analytics_page():
            pass
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)

            if not current_user.has_role(*roles):
                # Log unauthorized access attempt
                audit_logger.log(
                    action='DATA_ACCESS',
                    resource_type=request.endpoint or 'unknown',
                    user_id=current_user.username,
                    ip_address=request.remote_addr,
                    status='denied',
                    error_message=f'Insufficient permissions. Required: {roles}, Has: {current_user.role}'
                )
                abort(403)  # Forbidden

            return f(*args, **kwargs)

        return decorated_function
    return decorator


def require_admin(f):
    """Decorator to require admin role."""
    return require_role('admin')(f)
