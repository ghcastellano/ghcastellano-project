"""Unit tests for log sanitization."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# We need to import the function directly since it's defined in app.py
# which has side effects. Let's test the regex patterns instead.
import re


# Copy of the patterns from app.py for testing
SENSITIVE_PATTERNS = [
    (re.compile(r'(sk-[a-zA-Z0-9]{20,})'), r'sk-***REDACTED***'),  # OpenAI API keys
    (re.compile(r'(password["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', re.I), r'\1***REDACTED***'),  # Passwords
    (re.compile(r'(api[_-]?key["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', re.I), r'\1***REDACTED***'),  # API keys
    (re.compile(r'(token["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', re.I), r'\1***REDACTED***'),  # Tokens
    (re.compile(r'(secret["\']?\s*[:=]\s*["\']?)([^"\'&\s]+)', re.I), r'\1***REDACTED***'),  # Secrets
    (re.compile(r'(Bearer\s+)([a-zA-Z0-9._-]+)', re.I), r'\1***REDACTED***'),  # Bearer tokens
]


def sanitize_log_message(message: str) -> str:
    """Remove sensitive data patterns from log messages."""
    for pattern, replacement in SENSITIVE_PATTERNS:
        message = pattern.sub(replacement, message)
    return message


class TestLogSanitizer:
    """Tests for log sanitization function."""

    def test_sanitize_openai_api_key(self):
        """Should mask OpenAI API keys."""
        message = "Using API key: sk-abcdefghij1234567890abcdefghij"
        result = sanitize_log_message(message)
        assert "sk-abcdefghij1234567890" not in result
        assert "***REDACTED***" in result

    def test_sanitize_password_in_json(self):
        """Should mask passwords in JSON-like strings."""
        message = '{"password": "mysecretpass123"}'
        result = sanitize_log_message(message)
        assert "mysecretpass123" not in result
        assert "***REDACTED***" in result

    def test_sanitize_api_key_equals(self):
        """Should mask api_key assignments."""
        message = "api_key=very_secret_key_here"
        result = sanitize_log_message(message)
        assert "very_secret_key_here" not in result
        assert "***REDACTED***" in result

    def test_sanitize_bearer_token(self):
        """Should mask Bearer tokens."""
        message = "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xxx"
        result = sanitize_log_message(message)
        assert "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9" not in result
        assert "***REDACTED***" in result

    def test_sanitize_secret_colon(self):
        """Should mask secret values."""
        message = "secret: my_super_secret_value"
        result = sanitize_log_message(message)
        assert "my_super_secret_value" not in result
        assert "***REDACTED***" in result

    def test_preserve_normal_messages(self):
        """Should not modify messages without sensitive data."""
        message = "User logged in successfully"
        result = sanitize_log_message(message)
        assert result == message

    def test_preserve_timestamps(self):
        """Should not modify timestamp patterns."""
        message = "2026-02-09 12:00:00 - Request processed"
        result = sanitize_log_message(message)
        assert result == message

    def test_multiple_sensitive_values(self):
        """Should mask multiple sensitive values in one message."""
        message = "api_key=secret123 password=pass456"
        result = sanitize_log_message(message)
        assert "secret123" not in result
        assert "pass456" not in result
        assert result.count("***REDACTED***") == 2
