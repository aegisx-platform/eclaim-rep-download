"""
Secure logging configuration with credential masking.

This module provides logging utilities that automatically mask sensitive information
such as passwords, API keys, tokens, and other credentials from log output.

Addresses Security Issue #4: Credentials in Logs (CRITICAL)
"""

import logging
import re
import sys
import traceback
from typing import Optional
from io import StringIO


class CredentialMaskingFormatter(logging.Formatter):
    """
    Custom logging formatter that masks sensitive credential data.

    Automatically redacts:
    - Passwords (password=, pwd=, passwd=, etc.)
    - API keys and tokens
    - Session IDs
    - Authorization headers
    - Database connection strings
    - Any field containing 'secret', 'key', 'token'

    Usage:
        handler = logging.StreamHandler()
        handler.setFormatter(CredentialMaskingFormatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        ))
    """

    # Patterns to match and mask (case-insensitive)
    SENSITIVE_PATTERNS = [
        # Password fields
        (r'password["\']?\s*[:=]\s*["\']?[^\s"\']+', 'password=***MASKED***'),
        (r'pwd["\']?\s*[:=]\s*["\']?[^\s"\']+', 'pwd=***MASKED***'),
        (r'passwd["\']?\s*[:=]\s*["\']?[^\s"\']+', 'passwd=***MASKED***'),
        (r'pass["\']?\s*[:=]\s*["\']?[^\s"\']+', 'pass=***MASKED***'),

        # API keys and tokens
        (r'api[_-]?key["\']?\s*[:=]\s*["\']?[^\s"\']+', 'api_key=***MASKED***'),
        (r'token["\']?\s*[:=]\s*["\']?[^\s"\']+', 'token=***MASKED***'),
        (r'access[_-]?token["\']?\s*[:=]\s*["\']?[^\s"\']+', 'access_token=***MASKED***'),
        (r'refresh[_-]?token["\']?\s*[:=]\s*["\']?[^\s"\']+', 'refresh_token=***MASKED***'),
        (r'bearer\s+[a-zA-Z0-9\-._~+/]+=*', 'bearer ***MASKED***'),

        # Secret keys
        (r'secret[_-]?key["\']?\s*[:=]\s*["\']?[^\s"\']+', 'secret_key=***MASKED***'),
        (r'secret["\']?\s*[:=]\s*["\']?[^\s"\']+', 'secret=***MASKED***'),

        # Session IDs
        (r'session[_-]?id["\']?\s*[:=]\s*["\']?[^\s"\']+', 'session_id=***MASKED***'),
        (r'sid["\']?\s*[:=]\s*["\']?[^\s"\']+', 'sid=***MASKED***'),

        # Authorization headers
        (r'authorization["\']?\s*[:=]\s*["\']?[^\s"\']+', 'authorization=***MASKED***'),
        (r'auth["\']?\s*[:=]\s*["\']?[^\s"\']+', 'auth=***MASKED***'),

        # Database connection strings
        (r'postgresql://[^:]+:[^@]+@', 'postgresql://***:***@'),
        (r'mysql://[^:]+:[^@]+@', 'mysql://***:***@'),
        (r'mongodb://[^:]+:[^@]+@', 'mongodb://***:***@'),

        # Generic credential patterns (key=value where key contains 'credential')
        (r'credential[s]?["\']?\s*[:=]\s*["\']?[^\s"\']+', 'credentials=***MASKED***'),
    ]

    def format(self, record: logging.LogRecord) -> str:
        """
        Format the log record and mask any sensitive information.

        Args:
            record: The log record to format

        Returns:
            Formatted log message with credentials masked
        """
        # Format the record using parent formatter
        msg = super().format(record)

        # Apply all masking patterns
        for pattern, replacement in self.SENSITIVE_PATTERNS:
            msg = re.sub(pattern, replacement, msg, flags=re.IGNORECASE)

        return msg


def mask_sensitive_data(text: str) -> str:
    """
    Mask sensitive data in any text string.

    Useful for masking credentials in exception messages, stack traces,
    or any other text that might contain sensitive information.

    Args:
        text: Text that may contain sensitive data

    Returns:
        Text with sensitive data masked

    Example:
        >>> error_msg = "Login failed with password=secret123"
        >>> mask_sensitive_data(error_msg)
        'Login failed with password=***MASKED***'
    """
    result = text
    for pattern, replacement in CredentialMaskingFormatter.SENSITIVE_PATTERNS:
        result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    return result


def safe_format_exception(exc_info=None) -> str:
    """
    Format exception information with credential masking.

    Replacement for traceback.print_exc() that masks sensitive data
    before logging exception details.

    Args:
        exc_info: Exception info tuple (type, value, traceback) or None for sys.exc_info()

    Returns:
        Formatted exception string with credentials masked

    Example:
        >>> try:
        ...     login(password="secret123")
        ... except Exception:
        ...     logger.error(safe_format_exception())
    """
    if exc_info is None:
        exc_info = sys.exc_info()

    # Format the traceback
    output = StringIO()
    traceback.print_exception(*exc_info, file=output)
    tb_text = output.getvalue()
    output.close()

    # Mask sensitive data
    return mask_sensitive_data(tb_text)


def setup_logger(
    name: str,
    level: int = logging.INFO,
    log_file: Optional[str] = None,
    enable_masking: bool = True
) -> logging.Logger:
    """
    Set up a logger with credential masking.

    Args:
        name: Logger name
        level: Logging level (default: INFO)
        log_file: Optional log file path
        enable_masking: Whether to enable credential masking (default: True)

    Returns:
        Configured logger instance

    Example:
        >>> logger = setup_logger('my_app', level=logging.DEBUG)
        >>> logger.info("Password: secret123")  # Will be masked
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers = []

    # Create formatter
    fmt = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    if enable_masking:
        formatter = CredentialMaskingFormatter(fmt)
    else:
        formatter = logging.Formatter(fmt)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    # Prevent propagation to avoid duplicate logs
    logger.propagate = False

    return logger


# Example usage
if __name__ == '__main__':
    # Test the credential masking
    logger = setup_logger('test', level=logging.DEBUG)

    # These should all be masked
    logger.info("User login: password=secret123")
    logger.info("API request with token=abc123def456")
    logger.info("DB connection: postgresql://user:mypassword@localhost/db")
    logger.info("Auth header: Authorization=Bearer eyJhbGc...")
    logger.info('Config: {"api_key": "sk-1234567890", "secret": "mysecret"}')

    # Test safe exception formatting
    try:
        # Simulate error with sensitive data
        raise ValueError("Login failed with credentials={'password': 'secret123', 'username': 'admin'}")
    except Exception:
        logger.error("Exception occurred:\n%s", safe_format_exception())

    print("\n✓ All sensitive data should be masked above")
