"""
Input Validation Schemas

Provides Pydantic schemas for validating API inputs.
Prevents injection attacks, invalid data, and DoS via malformed inputs.

Usage:
    from utils.validation import validate_request

    @app.route('/api/endpoint', methods=['POST'])
    @validate_request(MySchema)
    def my_endpoint(validated_data):
        # validated_data is guaranteed to match MySchema
        return jsonify({'success': True})
"""

from typing import Optional, List, Any
from datetime import date, datetime
from pydantic import (
    BaseModel,
    Field,
    validator,
    field_validator,
    ConfigDict
)
from functools import wraps
from flask import request, jsonify


# =============================================================================
# BASE SCHEMAS
# =============================================================================

class BaseSchema(BaseModel):
    """Base schema with common configuration."""
    model_config = ConfigDict(
        str_strip_whitespace=True,  # Auto-trim strings
        validate_assignment=True,    # Validate on assignment
        extra='forbid'               # Reject unknown fields
    )


# =============================================================================
# DOWNLOAD SCHEMAS
# =============================================================================

class DownloadMonthSchema(BaseSchema):
    """Schema for downloading specific month."""
    month: int = Field(..., ge=1, le=12, description="Month (1-12)")
    year: int = Field(..., ge=2560, le=2600, description="Buddhist year (2560-2600)")
    schemes: Optional[List[str]] = Field(
        default=None,
        max_length=20,
        description="Insurance schemes to download"
    )

    @field_validator('schemes')
    @classmethod
    def validate_schemes(cls, v):
        if v is not None:
            # Limit scheme name length
            for scheme in v:
                if len(scheme) > 50:
                    raise ValueError('Scheme name too long')
        return v


class BulkDownloadSchema(BaseSchema):
    """Schema for bulk download."""
    start_month: int = Field(..., ge=1, le=12)
    start_year: int = Field(..., ge=2560, le=2600)
    end_month: int = Field(..., ge=1, le=12)
    end_year: int = Field(..., ge=2560, le=2600)
    schemes: Optional[List[str]] = Field(default=None, max_length=20)
    auto_import: bool = Field(default=False)

    @field_validator('end_year')
    @classmethod
    def validate_date_range(cls, v, info):
        """Ensure end date is after start date."""
        if 'start_year' in info.data and 'start_month' in info.data and 'end_month' in info.data:
            start_year = info.data['start_year']
            start_month = info.data['start_month']
            end_month = info.data['end_month']

            start = start_year * 12 + start_month
            end = v * 12 + end_month

            if end < start:
                raise ValueError('End date must be after start date')
            if end - start > 120:  # Max 10 years
                raise ValueError('Date range too large (max 10 years)')

        return v


# =============================================================================
# FILE SCHEMAS
# =============================================================================

class FileFilterSchema(BaseSchema):
    """Schema for file listing with filters."""
    page: int = Field(default=1, ge=1, le=10000, description="Page number")
    per_page: int = Field(default=50, ge=1, le=500, description="Items per page")
    file_type: Optional[str] = Field(
        default=None,
        max_length=10,
        description="File type filter (rep, stm, smt)"
    )
    month: Optional[int] = Field(default=None, ge=1, le=12)
    year: Optional[int] = Field(default=None, ge=2560, le=2600)
    import_status: Optional[str] = Field(
        default=None,
        max_length=20,
        description="Import status filter"
    )

    @field_validator('file_type')
    @classmethod
    def validate_file_type(cls, v):
        if v is not None and v not in ['rep', 'stm', 'smt', 'all']:
            raise ValueError("file_type must be 'rep', 'stm', 'smt', or 'all'")
        return v


class FileDeleteSchema(BaseSchema):
    """Schema for file deletion."""
    filename: str = Field(..., min_length=1, max_length=255)
    confirm: bool = Field(..., description="Must be true to confirm deletion")

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        """Ensure filename is safe (no path traversal)."""
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid filename (path traversal detected)')
        if not v.endswith(('.xls', '.xlsx', '.txt', '.csv')):
            raise ValueError('Invalid file extension')
        return v

    @field_validator('confirm')
    @classmethod
    def validate_confirm(cls, v):
        if not v:
            raise ValueError('Deletion must be confirmed')
        return v


# =============================================================================
# IMPORT SCHEMAS
# =============================================================================

class ImportFileSchema(BaseSchema):
    """Schema for importing a single file."""
    filename: str = Field(..., min_length=1, max_length=255)
    force: bool = Field(default=False, description="Force re-import")

    @field_validator('filename')
    @classmethod
    def validate_filename(cls, v):
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid filename')
        return v


class ImportBulkSchema(BaseSchema):
    """Schema for bulk import."""
    file_pattern: Optional[str] = Field(default=None, max_length=100)
    month: Optional[int] = Field(default=None, ge=1, le=12)
    year: Optional[int] = Field(default=None, ge=2560, le=2600)
    force: bool = Field(default=False)


# =============================================================================
# SETTINGS SCHEMAS
# =============================================================================

class CredentialsSchema(BaseSchema):
    """Schema for E-Claim credentials."""
    username: str = Field(..., min_length=1, max_length=100)
    password: str = Field(..., min_length=1, max_length=255)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        """Ensure username contains only safe characters."""
        if not v.replace('_', '').replace('-', '').replace('.', '').isalnum():
            raise ValueError('Username contains invalid characters')
        return v


class ScheduleSettingsSchema(BaseSchema):
    """Schema for schedule settings."""
    enabled: bool = Field(...)
    hour: int = Field(..., ge=0, le=23, description="Hour (0-23)")
    minute: int = Field(..., ge=0, le=59, description="Minute (0-59)")
    auto_import: bool = Field(default=False)


class HospitalSettingsSchema(BaseSchema):
    """Schema for hospital settings."""
    hospital_code: str = Field(..., min_length=5, max_length=5, pattern=r'^\d{5}$')
    total_beds: Optional[int] = Field(default=None, ge=1, le=10000)

    @field_validator('hospital_code')
    @classmethod
    def validate_hospital_code(cls, v):
        """Ensure hospital code is 5 digits."""
        if not v.isdigit() or len(v) != 5:
            raise ValueError('Hospital code must be exactly 5 digits')
        return v


# =============================================================================
# ANALYTICS SCHEMAS
# =============================================================================

class AnalyticsFilterSchema(BaseSchema):
    """Schema for analytics filters."""
    start_date: Optional[str] = Field(default=None, max_length=10)
    end_date: Optional[str] = Field(default=None, max_length=10)
    fund_type: Optional[str] = Field(default=None, max_length=50)
    service_type: Optional[str] = Field(default=None, max_length=50)
    limit: int = Field(default=1000, ge=1, le=10000)

    @field_validator('start_date', 'end_date')
    @classmethod
    def validate_date_format(cls, v):
        """Validate date format (YYYY-MM-DD)."""
        if v is not None:
            try:
                datetime.strptime(v, '%Y-%m-%d')
            except ValueError:
                raise ValueError('Invalid date format (use YYYY-MM-DD)')
        return v


class ExportSchema(BaseSchema):
    """Schema for data export."""
    format: str = Field(..., max_length=10)
    start_date: Optional[str] = Field(default=None, max_length=10)
    end_date: Optional[str] = Field(default=None, max_length=10)
    filters: Optional[dict] = Field(default=None)

    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        if v not in ['excel', 'csv', 'json']:
            raise ValueError("format must be 'excel', 'csv', or 'json'")
        return v


# =============================================================================
# USER SCHEMAS
# =============================================================================

class UserCreateSchema(BaseSchema):
    """Schema for creating a new user."""
    username: str = Field(..., min_length=3, max_length=100)
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    role: str = Field(default='user', max_length=50)
    hospital_code: Optional[str] = Field(default=None, max_length=10)

    @field_validator('username')
    @classmethod
    def validate_username(cls, v):
        if not v.replace('_', '').replace('-', '').replace('.', '').isalnum():
            raise ValueError('Username contains invalid characters')
        return v

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        """Basic email validation."""
        if '@' not in v or '.' not in v.split('@')[1]:
            raise ValueError('Invalid email format')
        return v.lower()

    @field_validator('role')
    @classmethod
    def validate_role(cls, v):
        valid_roles = ['admin', 'user', 'readonly', 'analyst', 'auditor']
        if v not in valid_roles:
            raise ValueError(f'Role must be one of: {", ".join(valid_roles)}')
        return v


class PasswordChangeSchema(BaseSchema):
    """Schema for password change."""
    current_password: Optional[str] = Field(default=None, min_length=1, max_length=255)
    new_password: str = Field(..., min_length=8, max_length=255)
    confirm_password: str = Field(..., min_length=8, max_length=255)

    @field_validator('confirm_password')
    @classmethod
    def passwords_match(cls, v, info):
        if 'new_password' in info.data and v != info.data['new_password']:
            raise ValueError('Passwords do not match')
        return v

    @field_validator('new_password')
    @classmethod
    def password_strength(cls, v):
        """Ensure password meets minimum requirements."""
        if len(v) < 8:
            raise ValueError('Password must be at least 8 characters')
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain at least one uppercase letter')
        if not any(c.islower() for c in v):
            raise ValueError('Password must contain at least one lowercase letter')
        if not any(c.isdigit() for c in v):
            raise ValueError('Password must contain at least one number')
        return v


# =============================================================================
# DECORATOR FOR AUTOMATIC VALIDATION
# =============================================================================

def validate_request(schema_class: type[BaseModel], source: str = 'json'):
    """
    Decorator to validate request data against a Pydantic schema.

    Args:
        schema_class: Pydantic schema class to validate against
        source: Where to get data from ('json', 'form', 'args')

    Returns:
        Decorated function that receives validated data

    Usage:
        @app.route('/api/endpoint', methods=['POST'])
        @validate_request(MySchema)
        def my_endpoint(validated_data):
            # validated_data is a Pydantic model instance
            return jsonify({'success': True})

    Error Response:
        {
            'success': False,
            'error': 'Validation failed',
            'validation_errors': [
                {
                    'field': 'email',
                    'message': 'Invalid email format',
                    'type': 'value_error'
                }
            ]
        }
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # Get data from request
            if source == 'json':
                data = request.get_json(silent=True) or {}
            elif source == 'form':
                data = request.form.to_dict()
            elif source == 'args':
                data = request.args.to_dict()
            else:
                return jsonify({
                    'success': False,
                    'error': f'Invalid validation source: {source}'
                }), 500

            # Validate data
            try:
                validated_data = schema_class(**data)
            except Exception as e:
                # Parse Pydantic validation errors
                errors = []
                if hasattr(e, 'errors'):
                    for error in e.errors():
                        errors.append({
                            'field': '.'.join(str(loc) for loc in error['loc']),
                            'message': error['msg'],
                            'type': error['type']
                        })
                else:
                    errors.append({
                        'field': 'unknown',
                        'message': str(e),
                        'type': 'validation_error'
                    })

                return jsonify({
                    'success': False,
                    'error': 'Validation failed',
                    'validation_errors': errors
                }), 400

            # Call original function with validated data
            return f(*args, validated_data=validated_data, **kwargs)

        return decorated_function
    return decorator


def validate_query_params(schema_class: type[BaseModel]):
    """Decorator to validate query parameters."""
    return validate_request(schema_class, source='args')


def validate_form_data(schema_class: type[BaseModel]):
    """Decorator to validate form data."""
    return validate_request(schema_class, source='form')
