# Input Validation Guide

> Complete guide to input validation with Pydantic in E-Claim System

**Status:** ✅ Input Validation Enabled
**Framework:** Pydantic 2.5.3
**Date:** 2026-01-17

---

## Why Input Validation?

Input validation prevents:
- **Injection Attacks:** SQL injection, command injection, XSS
- **DoS Attacks:** Malformed inputs causing crashes or resource exhaustion
- **Logic Errors:** Invalid data types, out-of-range values
- **Data Corruption:** Bad data entering the database

**Without validation:**
```python
# ❌ DANGEROUS - No validation
page = request.args.get('page', 1, type=int)  # What if page = -1000000?
per_page = request.args.get('per_page', 50, type=int)  # What if per_page = 999999999?
# Could cause memory exhaustion!
```

**With validation:**
```python
# ✅ SAFE - Pydantic validates everything
@validate_query_params(FileFilterSchema)
def get_files(validated_data):
    # validated_data.page is guaranteed to be 1-10000
    # validated_data.per_page is guaranteed to be 1-500
```

---

## Quick Start

### 1. Define Schema

```python
from utils.validation import BaseSchema
from pydantic import Field

class MyRequestSchema(BaseSchema):
    """Schema for my API request."""
    username: str = Field(..., min_length=3, max_length=100)
    age: int = Field(..., ge=0, le=150)
    email: str = Field(..., max_length=255)

    @field_validator('email')
    @classmethod
    def validate_email(cls, v):
        if '@' not in v:
            raise ValueError('Invalid email')
        return v.lower()
```

### 2. Apply to Route

```python
from utils.validation import validate_request

@app.route('/api/users', methods=['POST'])
@validate_request(MyRequestSchema)
def create_user(validated_data):
    # validated_data is a MyRequestSchema instance
    # All fields are validated and type-safe

    username = validated_data.username  # str, length 3-100
    age = validated_data.age            # int, 0-150
    email = validated_data.email        # str, valid email

    return jsonify({'success': True})
```

### 3. Handle Errors Automatically

If validation fails, Pydantic returns a clear error:

**Request:**
```json
{
    "username": "ab",
    "age": 200,
    "email": "invalid"
}
```

**Response (400 Bad Request):**
```json
{
    "success": false,
    "error": "Validation failed",
    "validation_errors": [
        {
            "field": "username",
            "message": "String should have at least 3 characters",
            "type": "string_too_short"
        },
        {
            "field": "age",
            "message": "Input should be less than or equal to 150",
            "type": "less_than_equal"
        },
        {
            "field": "email",
            "message": "Invalid email",
            "type": "value_error"
        }
    ]
}
```

---

## Available Schemas

See `utils/validation.py` for all schemas. Key schemas include:

- `DownloadMonthSchema` - Download specific month
- `BulkDownloadSchema` - Bulk download with date range
- `FileFilterSchema` - File listing with pagination
- `FileDeleteSchema` - Secure file deletion
- `ImportFileSchema` - File import validation
- `CredentialsSchema` - E-Claim credentials
- `ScheduleSettingsSchema` - Scheduler configuration
- `HospitalSettingsSchema` - Hospital settings
- `AnalyticsFilterSchema` - Analytics filters
- `ExportSchema` - Data export
- `UserCreateSchema` - User creation
- `PasswordChangeSchema` - Password change with strength requirements

---

## Usage Patterns

### JSON Request Body

```python
from utils.validation import validate_request, DownloadMonthSchema

@app.route('/api/downloads/month', methods=['POST'])
@login_required
@validate_request(DownloadMonthSchema)
def download_month(validated_data):
    """Download specific month."""
    month = validated_data.month    # int, 1-12
    year = validated_data.year      # int, 2560-2600
    schemes = validated_data.schemes or []

    # Use validated data safely
    downloader.download(month, year, schemes)

    return jsonify({'success': True})
```

### Query Parameters

```python
from utils.validation import validate_query_params, FileFilterSchema

@app.route('/api/files', methods=['GET'])
@login_required
@validate_query_params(FileFilterSchema)
def list_files(validated_data):
    """List files with pagination."""
    page = validated_data.page          # int, 1-10000
    per_page = validated_data.per_page  # int, 1-500
    file_type = validated_data.file_type

    files = file_manager.list_files(
        page=page,
        per_page=per_page,
        file_type=file_type
    )

    return jsonify({'success': True, 'files': files})
```

### Form Data

```python
from utils.validation import validate_form_data, CredentialsSchema

@app.route('/api/settings/credentials', methods=['POST'])
@login_required
@require_admin
@validate_form_data(CredentialsSchema)
def update_credentials(validated_data):
    """Update E-Claim credentials."""
    username = validated_data.username
    password = validated_data.password

    settings_manager.update_credentials(username, password)

    return jsonify({'success': True})
```

---

## Security Benefits

### Prevents Injection Attacks

**SQL Injection:**
```python
# ❌ Without validation
user_id = request.args.get('id')
query = f"SELECT * FROM users WHERE id = {user_id}"  # DANGEROUS!
# Attacker: /api/users?id=1 OR 1=1

# ✅ With validation
class UserIdSchema(BaseSchema):
    id: int = Field(..., ge=1, le=1000000)

@validate_query_params(UserIdSchema)
def get_user(validated_data):
    # validated_data.id is guaranteed to be an integer
    query = "SELECT * FROM users WHERE id = %s"
    cursor.execute(query, (validated_data.id,))
```

**Path Traversal:**
```python
# ❌ Without validation
filename = request.args.get('file')
with open(f'/downloads/{filename}') as f:
    content = f.read()
# Attacker: file=../../../etc/passwd → SECURITY BREACH!

# ✅ With validation
class FileSchema(BaseSchema):
    filename: str = Field(..., max_length=255)

    @field_validator('filename')
    @classmethod
    def no_path_traversal(cls, v):
        if '..' in v or '/' in v or '\\' in v:
            raise ValueError('Invalid filename')
        return v
```

### Prevents DoS Attacks

**Memory Exhaustion:**
```python
# ❌ Without validation
per_page = request.args.get('per_page', type=int)
files = file_manager.list_files(per_page=per_page)
# Attacker: per_page=999999999 → OutOfMemory

# ✅ With validation
class PaginationSchema(BaseSchema):
    per_page: int = Field(..., ge=1, le=500)  # Max 500
```

**Large Input Attacks:**
```python
# ❌ Without validation
username = request.form.get('username')
# Attacker sends 10MB username → DoS

# ✅ With validation
class UserSchema(BaseSchema):
    username: str = Field(..., max_length=100)  # Limit size
```

---

## Best Practices

### ✅ DO

1. **Validate ALL user inputs** (JSON, forms, query params)
2. **Use strict limits** (min, max, ge, le)
3. **Whitelist allowed values** (enums, choices)
4. **Normalize data** (trim, lowercase)
5. **Provide clear error messages**
6. **Log validation failures** for security monitoring

### ❌ DON'T

1. **Don't trust user input** - always validate
2. **Don't use blacklists** - use whitelists instead
3. **Don't allow unlimited sizes** - always set max lengths
4. **Don't expose internal errors** to users
5. **Don't skip validation** for "trusted" inputs

---

## Testing

Run validation tests:
```bash
python test_validation.py
```

---

## Resources

- **Pydantic Documentation:** https://docs.pydantic.dev/
- **OWASP Input Validation:** https://owasp.org/www-project-proactive-controls/
- **Code:** `utils/validation.py`

---

**Last Updated:** 2026-01-17
**Maintainer:** Security Team
