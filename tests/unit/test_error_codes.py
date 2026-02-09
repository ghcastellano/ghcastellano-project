"""Unit tests for ErrorCode.get_error() static method."""

import pytest

from src.error_codes import ErrorCode


class TestErrorCodeGetError:
    """Tests for ErrorCode.get_error() static method."""

    # ── String code lookup ───────────────────────────────────────────────

    def test_get_error_by_valid_code(self):
        """Should return the matching error dict for a valid code string."""
        result = ErrorCode.get_error("ERR_1001")
        assert result == ErrorCode.ERR_1001
        assert result["code"] == "ERR_1001"

    def test_get_error_by_another_valid_code(self):
        """Should return the matching error dict for another valid code string."""
        result = ErrorCode.get_error("ERR_9002")
        assert result == ErrorCode.ERR_9002
        assert result["code"] == "ERR_9002"

    def test_get_error_by_invalid_code_returns_default(self):
        """Should fall back to ERR_9001 for an unrecognised code string."""
        result = ErrorCode.get_error("ERR_INVALID")
        assert result == ErrorCode.ERR_9001

    # ── Exception analysis – PDF / Upload (1xxx) ────────────────────────

    def test_get_error_empty_keyword(self):
        """Exception containing 'empty' should map to ERR_1002."""
        result = ErrorCode.get_error(Exception("PDF is empty"))
        assert result == ErrorCode.ERR_1002

    def test_get_error_no_text_keyword(self):
        """Exception containing 'no text' should map to ERR_1002."""
        result = ErrorCode.get_error(Exception("no text found in document"))
        assert result == ErrorCode.ERR_1002

    def test_get_error_corrupt_keyword(self):
        """Exception containing 'corrupt' should map to ERR_1001."""
        result = ErrorCode.get_error(Exception("File is corrupt"))
        assert result == ErrorCode.ERR_1001

    def test_get_error_invalid_pdf_keyword(self):
        """Exception containing 'invalid pdf' should map to ERR_1001."""
        result = ErrorCode.get_error(Exception("invalid pdf format"))
        assert result == ErrorCode.ERR_1001

    def test_get_error_file_size_keyword(self):
        """Exception containing 'file size' should map to ERR_1003."""
        result = ErrorCode.get_error(Exception("file size exceeds limit"))
        assert result == ErrorCode.ERR_1003

    def test_get_error_too_large_keyword(self):
        """Exception containing 'too large' should map to ERR_1003."""
        result = ErrorCode.get_error(Exception("File too large to process"))
        assert result == ErrorCode.ERR_1003

    # ── Exception analysis – OpenAI / IA (2xxx) ─────────────────────────

    def test_get_error_openai_timeout(self):
        """Exception containing both 'timeout' and 'openai' should map to ERR_2001."""
        result = ErrorCode.get_error(Exception("OpenAI API timeout after 30s"))
        assert result == ErrorCode.ERR_2001

    def test_get_error_quota_keyword(self):
        """Exception containing 'quota' (without 'drive') should map to ERR_2002."""
        result = ErrorCode.get_error(Exception("Quota exceeded for this month"))
        assert result == ErrorCode.ERR_2002

    def test_get_error_rate_limit_keyword(self):
        """Exception containing 'rate limit' should map to ERR_2002."""
        result = ErrorCode.get_error(Exception("Rate limit reached, retry later"))
        assert result == ErrorCode.ERR_2002

    def test_get_error_api_key_keyword(self):
        """Exception containing 'api key' should map to ERR_2004."""
        result = ErrorCode.get_error(Exception("API key is invalid or revoked"))
        assert result == ErrorCode.ERR_2004

    def test_get_error_authentication_keyword(self):
        """Exception containing 'authentication' should map to ERR_2004."""
        result = ErrorCode.get_error(Exception("Authentication failed for request"))
        assert result == ErrorCode.ERR_2004

    def test_get_error_validation_keyword(self):
        """Exception containing 'validation' should map to ERR_2003."""
        result = ErrorCode.get_error(Exception("Validation error in response"))
        assert result == ErrorCode.ERR_2003

    def test_get_error_parsing_keyword(self):
        """Exception containing 'parsing' should map to ERR_2003."""
        result = ErrorCode.get_error(Exception("JSON parsing failed"))
        assert result == ErrorCode.ERR_2003

    # ── Exception analysis – Database (3xxx) ────────────────────────────

    def test_get_error_database_keyword(self):
        """Exception containing 'database' should map to ERR_3003."""
        result = ErrorCode.get_error(Exception("Database write error"))
        assert result == ErrorCode.ERR_3003

    def test_get_error_connection_keyword(self):
        """Exception containing 'connection' should map to ERR_3003."""
        result = ErrorCode.get_error(Exception("Connection refused by host"))
        assert result == ErrorCode.ERR_3003

    def test_get_error_duplicate_keyword(self):
        """Exception containing 'duplicate' should map to ERR_3004."""
        result = ErrorCode.get_error(Exception("Duplicate entry for primary key"))
        assert result == ErrorCode.ERR_3004

    def test_get_error_unique_constraint_keyword(self):
        """Exception containing 'unique constraint' should map to ERR_3004."""
        result = ErrorCode.get_error(Exception("Unique constraint violation on column x"))
        assert result == ErrorCode.ERR_3004

    def test_get_error_establishment_not_found(self):
        """Exception containing 'establishment' AND 'not found' should map to ERR_3002."""
        result = ErrorCode.get_error(Exception("Establishment not found"))
        assert result == ErrorCode.ERR_3002

    # ── Exception analysis – Drive / Storage (4xxx) ─────────────────────

    def test_get_error_drive_quota_hits_openai_quota_first(self):
        """'Drive quota' contains 'quota' which is caught by ERR_2002 before ERR_4002.

        Note: the ERR_4002 branch (line 173) is unreachable because the earlier
        'quota' check at line 157 always matches first. This test documents the
        actual runtime behaviour.
        """
        result = ErrorCode.get_error(Exception("Drive quota exceeded"))
        # Due to branch ordering, 'quota' matches ERR_2002 before 'drive'+'quota' matches ERR_4002
        assert result == ErrorCode.ERR_2002

    def test_get_error_drive_generic(self):
        """Exception containing 'drive' (without 'quota') should map to ERR_4001."""
        result = ErrorCode.get_error(Exception("Drive API returned error 500"))
        assert result == ErrorCode.ERR_4001

    def test_get_error_upload_keyword(self):
        """Exception containing 'upload' should map to ERR_4001."""
        result = ErrorCode.get_error(Exception("Upload failed after retry"))
        assert result == ErrorCode.ERR_4001

    def test_get_error_storage_keyword(self):
        """Exception containing 'storage' should map to ERR_4004."""
        result = ErrorCode.get_error(Exception("Storage service unavailable"))
        assert result == ErrorCode.ERR_4004

    # ── Default fallback ────────────────────────────────────────────────

    def test_get_error_unknown_exception_returns_default(self):
        """Exception with no recognised keywords should fall back to ERR_9001."""
        result = ErrorCode.get_error(Exception("Something completely unknown happened"))
        assert result == ErrorCode.ERR_9001

    # ── Edge-case / case-insensitivity checks ───────────────────────────

    def test_get_error_case_insensitive_matching(self):
        """Keywords should be matched case-insensitively."""
        result = ErrorCode.get_error(Exception("FILE IS EMPTY"))
        assert result == ErrorCode.ERR_1002

    def test_get_error_mixed_case_openai_timeout(self):
        """Mixed-case 'OpenAI' and 'Timeout' should still match ERR_2001."""
        result = ErrorCode.get_error(Exception("OPENAI request TIMEOUT"))
        assert result == ErrorCode.ERR_2001

    def test_get_error_timeout_without_openai_is_not_err_2001(self):
        """A timeout exception that does NOT mention 'openai' should NOT map to ERR_2001."""
        result = ErrorCode.get_error(Exception("Request timeout"))
        # 'timeout' alone does not match any specific branch, so it falls through to default
        assert result == ErrorCode.ERR_9001

    def test_get_error_result_has_required_keys(self):
        """Every returned error dict must contain code, admin_msg, and user_msg."""
        result = ErrorCode.get_error(Exception("Something random"))
        assert "code" in result
        assert "admin_msg" in result
        assert "user_msg" in result
