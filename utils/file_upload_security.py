"""
File Upload Security

Provides comprehensive security validation for file uploads.
Prevents malicious file uploads, path traversal, and file type spoofing.

Security Features:
- File type validation (whitelist)
- File size limits (DoS prevention)
- Filename sanitization (path traversal prevention)
- MIME type verification
- Magic number checking (detect spoofed files)
- Malware scanning integration (optional)
- Secure storage path generation

Usage:
    from utils.file_upload_security import FileUploadValidator

    validator = FileUploadValidator(
        allowed_extensions=['.xls', '.xlsx'],
        max_size_mb=10
    )

    # Validate file
    result = validator.validate(file)
    if not result.is_valid:
        return jsonify({'error': result.error_message}), 400

    # Save securely
    safe_path = validator.save_securely(file, upload_dir)
"""

import os
import hashlib
import mimetypes
from pathlib import Path
from typing import List, Optional, Tuple
from dataclasses import dataclass
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from utils.logging_config import setup_logger

logger = setup_logger('file_upload_security')


# Magic numbers (file signatures) for common file types
MAGIC_NUMBERS = {
    # Excel files
    '.xls': [
        b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1',  # OLE2 (MS Office 97-2003)
    ],
    '.xlsx': [
        b'PK\x03\x04',  # ZIP (Office 2007+)
    ],

    # CSV/Text
    '.csv': [
        # CSV has no magic number (plain text)
    ],
    '.txt': [
        # Plain text has no magic number
    ],

    # PDF
    '.pdf': [
        b'%PDF-',
    ],

    # Images
    '.jpg': [
        b'\xFF\xD8\xFF',
    ],
    '.jpeg': [
        b'\xFF\xD8\xFF',
    ],
    '.png': [
        b'\x89PNG\r\n\x1a\n',
    ],

    # Archives
    '.zip': [
        b'PK\x03\x04',
        b'PK\x05\x06',  # Empty archive
        b'PK\x07\x08',  # Spanned archive
    ],
}


@dataclass
class ValidationResult:
    """Result of file validation."""
    is_valid: bool
    error_message: Optional[str] = None
    sanitized_filename: Optional[str] = None
    detected_type: Optional[str] = None


class FileUploadValidator:
    """
    Comprehensive file upload security validator.

    Example:
        validator = FileUploadValidator(
            allowed_extensions=['.xls', '.xlsx', '.csv'],
            max_size_mb=10
        )

        result = validator.validate(uploaded_file)
        if result.is_valid:
            safe_path = validator.save_securely(uploaded_file, 'uploads/')
    """

    def __init__(
        self,
        allowed_extensions: List[str],
        max_size_mb: float = 10.0,
        check_magic_numbers: bool = True,
        scan_malware: bool = False
    ):
        """
        Initialize file upload validator.

        Args:
            allowed_extensions: List of allowed file extensions (e.g., ['.xls', '.xlsx'])
            max_size_mb: Maximum file size in megabytes
            check_magic_numbers: Verify file type by magic number
            scan_malware: Enable malware scanning (requires ClamAV)
        """
        self.allowed_extensions = [ext.lower() for ext in allowed_extensions]
        self.max_size_bytes = int(max_size_mb * 1024 * 1024)
        self.check_magic_numbers = check_magic_numbers
        self.scan_malware = scan_malware

    def validate(self, file: FileStorage) -> ValidationResult:
        """
        Validate uploaded file.

        Args:
            file: Werkzeug FileStorage object

        Returns:
            ValidationResult with validation status
        """
        # Check if file exists
        if not file or not file.filename:
            return ValidationResult(
                is_valid=False,
                error_message="No file provided"
            )

        # Sanitize filename
        sanitized_filename = self.sanitize_filename(file.filename)

        # Check filename
        result = self._validate_filename(sanitized_filename)
        if not result.is_valid:
            return result

        # Check file extension
        result = self._validate_extension(sanitized_filename)
        if not result.is_valid:
            return result

        # Check file size
        result = self._validate_size(file)
        if not result.is_valid:
            return result

        # Check magic number (file type spoofing)
        if self.check_magic_numbers:
            result = self._validate_magic_number(file, sanitized_filename)
            if not result.is_valid:
                return result

        # Malware scan (optional)
        if self.scan_malware:
            result = self._scan_malware(file)
            if not result.is_valid:
                return result

        # All validations passed
        return ValidationResult(
            is_valid=True,
            sanitized_filename=sanitized_filename
        )

    def sanitize_filename(self, filename: str) -> str:
        """
        Sanitize filename to prevent path traversal and other attacks.

        Args:
            filename: Original filename

        Returns:
            Sanitized filename

        Example:
            >>> sanitize_filename("../../etc/passwd")
            'etc_passwd'
            >>> sanitize_filename("file<script>.xls")
            'file_script_.xls'
        """
        # Remove path traversal patterns first (before checking for hidden files)
        filename = filename.replace('..', '')

        # Check if hidden file (starts with '.')
        is_hidden = filename.startswith('.')
        if is_hidden:
            filename = filename[1:]  # Remove dot temporarily

        # Replace ALL dangerous characters and patterns
        dangerous_chars = ['<', '>', ':', '"', '|', '?', '*']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')

        # Use Werkzeug's secure_filename (handles path separators and Unicode)
        safe_name = secure_filename(filename)

        # Restore underscore prefix if was hidden file
        if is_hidden:
            safe_name = '_' + safe_name

        # Limit filename length (prevents filesystem issues)
        name, ext = os.path.splitext(safe_name)
        if len(name) > 200:
            name = name[:200]

        safe_name = name + ext

        return safe_name

    def _validate_filename(self, filename: str) -> ValidationResult:
        """Validate filename is not empty and not dangerous."""
        if not filename:
            return ValidationResult(
                is_valid=False,
                error_message="Invalid filename"
            )

        # Check for path traversal attempts
        if '..' in filename or '/' in filename or '\\' in filename:
            logger.warning(f"Path traversal attempt detected: {filename}")
            return ValidationResult(
                is_valid=False,
                error_message="Invalid filename (contains path separators)"
            )

        return ValidationResult(is_valid=True)

    def _validate_extension(self, filename: str) -> ValidationResult:
        """Validate file extension is in allowed list."""
        ext = os.path.splitext(filename)[1].lower()

        if not ext:
            return ValidationResult(
                is_valid=False,
                error_message="File has no extension"
            )

        if ext not in self.allowed_extensions:
            return ValidationResult(
                is_valid=False,
                error_message=f"File type not allowed: {ext}. "
                             f"Allowed types: {', '.join(self.allowed_extensions)}"
            )

        return ValidationResult(is_valid=True)

    def _validate_size(self, file: FileStorage) -> ValidationResult:
        """Validate file size is within limits."""
        # Seek to end to get size
        file.seek(0, os.SEEK_END)
        size = file.tell()
        file.seek(0)  # Reset to beginning

        if size == 0:
            return ValidationResult(
                is_valid=False,
                error_message="File is empty"
            )

        if size > self.max_size_bytes:
            max_mb = self.max_size_bytes / (1024 * 1024)
            actual_mb = size / (1024 * 1024)
            return ValidationResult(
                is_valid=False,
                error_message=f"File too large: {actual_mb:.1f}MB (max: {max_mb:.1f}MB)"
            )

        return ValidationResult(is_valid=True)

    def _validate_magic_number(
        self,
        file: FileStorage,
        filename: str
    ) -> ValidationResult:
        """
        Validate file type by checking magic number (file signature).

        Prevents file type spoofing (e.g., renaming virus.exe to virus.xls).
        """
        ext = os.path.splitext(filename)[1].lower()

        # Skip for file types without magic numbers
        if ext in ['.csv', '.txt']:
            return ValidationResult(is_valid=True)

        # Get expected magic numbers
        expected_magic = MAGIC_NUMBERS.get(ext)
        if not expected_magic:
            logger.warning(f"No magic number defined for extension: {ext}")
            return ValidationResult(is_valid=True)  # Allow (can't verify)

        # Read first 8 bytes
        file.seek(0)
        header = file.read(8)
        file.seek(0)  # Reset

        if len(header) < 4:
            return ValidationResult(
                is_valid=False,
                error_message="File too small to determine type"
            )

        # Check if header matches any expected magic number
        for magic in expected_magic:
            if header.startswith(magic):
                return ValidationResult(
                    is_valid=True,
                    detected_type=ext
                )

        # Magic number mismatch - possible file type spoofing
        logger.warning(
            f"Magic number mismatch for {filename}: "
            f"Expected {ext}, got {header[:8].hex()}"
        )

        return ValidationResult(
            is_valid=False,
            error_message=f"File type mismatch: File does not appear to be {ext}"
        )

    def _scan_malware(self, file: FileStorage) -> ValidationResult:
        """
        Scan file for malware using ClamAV.

        Note: Requires ClamAV to be installed and running.
        """
        try:
            import pyclamd

            # Connect to ClamAV daemon
            cd = pyclamd.ClamdUnixSocket()

            if not cd.ping():
                logger.warning("ClamAV not available - skipping malware scan")
                return ValidationResult(is_valid=True)

            # Scan file
            file.seek(0)
            scan_result = cd.scan_stream(file.read())
            file.seek(0)  # Reset

            if scan_result is None:
                # Clean file
                return ValidationResult(is_valid=True)
            else:
                # Malware detected
                virus_name = scan_result.get('stream', ['Unknown'])[1]
                logger.error(f"Malware detected: {virus_name}")

                return ValidationResult(
                    is_valid=False,
                    error_message=f"Malware detected: {virus_name}"
                )

        except ImportError:
            logger.warning("pyclamd not installed - skipping malware scan")
            return ValidationResult(is_valid=True)
        except Exception as e:
            logger.error(f"Malware scan error: {e}")
            # Don't block upload if scan fails (availability over security)
            return ValidationResult(is_valid=True)

    def save_securely(
        self,
        file: FileStorage,
        upload_dir: str,
        use_hash_naming: bool = False
    ) -> str:
        """
        Save file securely with proper permissions.

        Args:
            file: Werkzeug FileStorage object
            upload_dir: Directory to save file
            use_hash_naming: Use hash-based filename (prevents conflicts)

        Returns:
            Path to saved file

        Example:
            safe_path = validator.save_securely(file, 'downloads/rep/')
        """
        # Ensure upload directory exists
        Path(upload_dir).mkdir(parents=True, exist_ok=True)

        # Get sanitized filename
        sanitized_filename = self.sanitize_filename(file.filename)

        # Generate secure filename
        if use_hash_naming:
            # Hash-based naming (prevents conflicts, hides original name)
            file_hash = hashlib.sha256(file.read()).hexdigest()[:16]
            file.seek(0)  # Reset

            ext = os.path.splitext(sanitized_filename)[1]
            secure_name = f"{file_hash}{ext}"
        else:
            secure_name = sanitized_filename

        # Build full path
        file_path = os.path.join(upload_dir, secure_name)

        # Check if file already exists
        if os.path.exists(file_path):
            # Add timestamp to make unique
            import time
            name, ext = os.path.splitext(secure_name)
            timestamp = int(time.time())
            secure_name = f"{name}_{timestamp}{ext}"
            file_path = os.path.join(upload_dir, secure_name)

        # Save file
        file.save(file_path)

        # Set restrictive permissions (owner read/write only)
        os.chmod(file_path, 0o600)

        logger.info(f"File saved securely: {file_path}")

        return file_path


# Convenience validators for common file types
def validate_excel_file(file: FileStorage, max_size_mb: float = 10.0) -> ValidationResult:
    """Validate Excel file (.xls, .xlsx)."""
    validator = FileUploadValidator(
        allowed_extensions=['.xls', '.xlsx'],
        max_size_mb=max_size_mb
    )
    return validator.validate(file)


def validate_csv_file(file: FileStorage, max_size_mb: float = 5.0) -> ValidationResult:
    """Validate CSV file."""
    validator = FileUploadValidator(
        allowed_extensions=['.csv', '.txt'],
        max_size_mb=max_size_mb,
        check_magic_numbers=False  # CSV has no magic number
    )
    return validator.validate(file)


def validate_image_file(file: FileStorage, max_size_mb: float = 5.0) -> ValidationResult:
    """Validate image file (.jpg, .jpeg, .png)."""
    validator = FileUploadValidator(
        allowed_extensions=['.jpg', '.jpeg', '.png'],
        max_size_mb=max_size_mb
    )
    return validator.validate(file)
