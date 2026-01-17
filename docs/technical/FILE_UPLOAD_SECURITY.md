# File Upload Security Guide

> Comprehensive file upload validation and security

**Security Level:** 🛡️ Enhanced Security (Phase 2)
**Protection:** Path traversal, file type spoofing, DoS, malware
**Date:** 2026-01-17

---

## Why File Upload Security?

File uploads are a common attack vector:

**Risks without validation:**
- 🔴 **Path Traversal:** `../../etc/passwd` → System file access
- 🔴 **File Type Spoofing:** `virus.exe` renamed to `document.xls`
- 🔴 **DoS:** 10GB file upload → Server crash
- 🔴 **Malware:** Infected files uploaded to server
- 🔴 **Code Execution:** PHP/JSP files executed on server

---

## Quick Start

### Basic Validation

```python
from utils.file_upload_security import FileUploadValidator

# Create validator
validator = FileUploadValidator(
    allowed_extensions=['.xls', '.xlsx'],
    max_size_mb=10
)

# Validate file
@app.route('/upload', methods=['POST'])
def upload_file():
    file = request.files.get('file')

    # Validate
    result = validator.validate(file)
    if not result.is_valid:
        return jsonify({'error': result.error_message}), 400

    # Save securely
    safe_path = validator.save_securely(file, 'downloads/rep/')

    return jsonify({'success': True, 'path': safe_path})
```

### Convenience Validators

```python
from utils.file_upload_security import (
    validate_excel_file,
    validate_csv_file,
    validate_image_file
)

# Excel files (.xls, .xlsx)
result = validate_excel_file(file, max_size_mb=10)

# CSV files
result = validate_csv_file(file, max_size_mb=5)

# Images
result = validate_image_file(file, max_size_mb=5)
```

---

## Security Features

### 1. Filename Sanitization

**Problem:** Malicious filenames can cause path traversal

**Examples:**
```python
# Path traversal attempts
"../../etc/passwd"           → "etc_passwd"
"../../../Windows/System32"  → "Windows_System32"

# Special characters
"file<script>.xls"          → "file_script_.xls"
"document|rm -rf /.xls"     → "document_rm_-rf_.xls"

# Hidden files
".hidden.xls"               → "_hidden.xls"

# Long filenames
"very" * 200 + ".xls"       → Truncated to 250 chars
```

**Implementation:**
```python
safe_name = validator.sanitize_filename(filename)
```

### 2. File Extension Whitelist

**Problem:** Executable files disguised as documents

**Implementation:**
```python
validator = FileUploadValidator(
    allowed_extensions=['.xls', '.xlsx', '.csv']  # Whitelist only
)
```

**Blocked extensions:**
- `.exe`, `.bat`, `.sh`, `.cmd` (executables)
- `.php`, `.jsp`, `.asp` (server scripts)
- `.js`, `.vbs` (scripts)
- Any extension not in whitelist

### 3. File Size Limits

**Problem:** Large files cause DoS (Denial of Service)

**Implementation:**
```python
validator = FileUploadValidator(
    allowed_extensions=['.xls'],
    max_size_mb=10  # Limit to 10 MB
)
```

**Prevents:**
- Memory exhaustion
- Disk space exhaustion
- Network bandwidth abuse

### 4. Magic Number Verification

**Problem:** File type spoofing (rename `virus.exe` to `document.xls`)

**How it works:**
```python
# File signature verification
File says: "document.xls"
Magic number: b'\xD0\xCF\x11\xE0'  # Real .xls signature
✓ Accepted

File says: "document.xls"
Magic number: b'MZ\x90\x00'        # .exe signature!
✗ Rejected (file type spoofing detected)
```

**Supported file types:**
| Extension | Magic Number | Description |
|-----------|--------------|-------------|
| .xls | `D0 CF 11 E0` | OLE2 (Office 97-2003) |
| .xlsx | `50 4B 03 04` | ZIP (Office 2007+) |
| .pdf | `25 50 44 46` | PDF signature |
| .jpg | `FF D8 FF` | JPEG image |
| .png | `89 50 4E 47` | PNG image |
| .zip | `50 4B` | ZIP archive |

**Implementation:**
```python
validator = FileUploadValidator(
    allowed_extensions=['.xls'],
    check_magic_numbers=True  # Enable verification
)
```

### 5. Secure Storage

**Problem:** Files saved with unsafe permissions or paths

**Implementation:**
```python
# Save with secure permissions (600 - owner read/write only)
safe_path = validator.save_securely(
    file,
    upload_dir='downloads/rep/',
    use_hash_naming=False  # Use original filename
)

# Or use hash-based naming (prevents conflicts)
safe_path = validator.save_securely(
    file,
    upload_dir='downloads/rep/',
    use_hash_naming=True  # → "a3f5b8c2d1e4.xls"
)
```

**Security features:**
- Creates directory if not exists
- Prevents path traversal in directory
- Checks for existing files (adds timestamp if conflict)
- Sets restrictive permissions (`chmod 600`)
- Logs all saves

### 6. Malware Scanning (Optional)

**Problem:** Infected files uploaded to server

**Implementation:**
```python
validator = FileUploadValidator(
    allowed_extensions=['.xls'],
    scan_malware=True  # Enable ClamAV scanning
)
```

**Requirements:**
- ClamAV installed and running
- Python package: `pip install pyclamd`

**Note:** Disabled by default (requires infrastructure setup)

---

## Usage Examples

### E-Claim File Upload

```python
from utils.file_upload_security import FileUploadValidator

@app.route('/api/files/upload', methods=['POST'])
@login_required
@limit_api  # Rate limiting
def upload_eclaim_file():
    """Upload E-Claim REP/STM file."""

    file = request.files.get('file')
    if not file:
        return jsonify({'error': 'No file provided'}), 400

    # Validate E-Claim files
    validator = FileUploadValidator(
        allowed_extensions=['.xls', '.xlsx'],
        max_size_mb=10,
        check_magic_numbers=True
    )

    result = validator.validate(file)
    if not result.is_valid:
        # Audit failed upload attempt
        audit_logger.log(
            action='FILE_UPLOAD',
            resource_type='eclaim_file',
            status='denied',
            error_message=result.error_message
        )

        return jsonify({'error': result.error_message}), 400

    # Save securely
    safe_path = validator.save_securely(file, 'downloads/rep/')

    # Audit successful upload
    audit_logger.log(
        action='FILE_UPLOAD',
        resource_type='eclaim_file',
        status='success',
        details={'filename': result.sanitized_filename}
    )

    return jsonify({
        'success': True,
        'filename': result.sanitized_filename,
        'path': safe_path
    })
```

### Batch File Upload

```python
@app.route('/api/files/upload-batch', methods=['POST'])
@login_required
@limit_download  # Stricter rate limit
def upload_batch():
    """Upload multiple files."""

    files = request.files.getlist('files')

    if len(files) > 10:
        return jsonify({'error': 'Maximum 10 files allowed'}), 400

    validator = FileUploadValidator(
        allowed_extensions=['.xls', '.xlsx'],
        max_size_mb=10
    )

    results = []
    for file in files:
        result = validator.validate(file)

        if result.is_valid:
            safe_path = validator.save_securely(file, 'downloads/rep/')
            results.append({
                'filename': result.sanitized_filename,
                'status': 'success',
                'path': safe_path
            })
        else:
            results.append({
                'filename': file.filename,
                'status': 'failed',
                'error': result.error_message
            })

    return jsonify({'results': results})
```

---

## Attack Prevention

### Path Traversal Attack

**Attack:**
```http
POST /upload HTTP/1.1
Content-Disposition: form-data; name="file"; filename="../../etc/passwd"
```

**Defense:**
```python
safe_name = validator.sanitize_filename("../../etc/passwd")
# Result: "etc_passwd"

# File saved to: downloads/rep/etc_passwd
# NOT: ../../etc/passwd (blocked!)
```

### File Type Spoofing

**Attack:**
```bash
# Attacker renames virus
mv virus.exe document.xls

# Upload document.xls (actually virus.exe)
```

**Defense:**
```python
# Magic number check
result = validator.validate(file)
# Detects: Magic number = MZ (EXE signature)
# Error: "File type mismatch: File does not appear to be .xls"
```

### DoS via Large Files

**Attack:**
```http
POST /upload HTTP/1.1
Content-Length: 10737418240

[10 GB of data]
```

**Defense:**
```python
# File size limit
validator = FileUploadValidator(max_size_mb=10)

result = validator.validate(large_file)
# Error: "File too large: 10240.0MB (max: 10.0MB)"
```

### Malicious Filenames

**Attack:**
```
file<script>alert('XSS')</script>.xls
file; rm -rf /.xls
$(whoami).xls
```

**Defense:**
```python
safe_name = validator.sanitize_filename(malicious_name)
# Result: "file_script_alert_XSS_script_.xls"
# All dangerous characters removed
```

---

## Testing

### Run Tests

```bash
# Unit tests
python test_file_upload_security.py

# Integration tests (requires Docker)
docker-compose exec web python test_file_upload_security.py
```

**Expected output:**
```
================================
FILE UPLOAD SECURITY TEST
================================

Testing: Filename Sanitization...
✓ Filename sanitized: 'normal_file.xls' → 'normal_file.xls'
✓ Filename sanitized: '../../etc/passwd' → 'etc_passwd'
✓ Path traversal blocked: '../../../etc/passwd'

Testing: Magic Number Validation...
✓ Real .xls file accepted (correct magic number)
✓ Fake .xls file rejected (wrong magic number)

...

Result: 7/7 tests passed

🎉 All file upload security tests passed!
```

### Manual Testing

```python
# Test valid file
from werkzeug.datastructures import FileStorage
import io

file = FileStorage(
    stream=io.BytesIO(b'\xD0\xCF\x11\xE0' + b'x' * 100),
    filename='test.xls'
)

result = validate_excel_file(file)
print(result.is_valid)  # True

# Test invalid file
fake_file = FileStorage(
    stream=io.BytesIO(b'MZ\x90\x00' + b'x' * 100),  # EXE signature
    filename='virus.xls'
)

result = validate_excel_file(fake_file)
print(result.is_valid)  # False
print(result.error_message)  # "File type mismatch..."
```

---

## Best Practices

1. **Always validate:** Never trust user uploads
2. **Use whitelists:** Don't blacklist, whitelist allowed types
3. **Check magic numbers:** Prevent file type spoofing
4. **Limit file sizes:** Prevent DoS
5. **Sanitize filenames:** Prevent path traversal
6. **Use secure storage:** Restrictive permissions (600)
7. **Audit uploads:** Log all upload attempts
8. **Rate limit:** Prevent upload spam

---

## Configuration

### Production Settings

```python
# Strict validation for production
validator = FileUploadValidator(
    allowed_extensions=['.xls', '.xlsx'],
    max_size_mb=10,
    check_magic_numbers=True,  # Enable
    scan_malware=True          # Enable if ClamAV available
)
```

### Development Settings

```python
# Relaxed validation for development
validator = FileUploadValidator(
    allowed_extensions=['.xls', '.xlsx', '.csv'],
    max_size_mb=50,            # Larger limit
    check_magic_numbers=False,  # Faster
    scan_malware=False         # Not required
)
```

---

## Troubleshooting

### Issue: Valid files rejected

**Cause:** Magic number mismatch

**Solution:** Check file is not corrupted
```bash
# Check file signature
hexdump -C file.xls | head -n 1
# Should start with: d0 cf 11 e0 (OLE2)
```

### Issue: Malware scan fails

**Cause:** ClamAV not running

**Solution:**
```bash
# Install ClamAV
apt-get install clamav clamav-daemon

# Start daemon
systemctl start clamav-daemon

# Test
clamdscan --version
```

---

## Resources

- **File Signatures:** https://en.wikipedia.org/wiki/List_of_file_signatures
- **OWASP File Upload:** https://owasp.org/www-community/vulnerabilities/Unrestricted_File_Upload
- **ClamAV:** https://www.clamav.net/

---

**Last Updated:** 2026-01-17
**Maintainer:** Security Team

**Next:** [Dependency Scanning](DEPENDENCY_SECURITY.md) | [Phase 2 Complete](PHASE2_COMPLETE.md)
