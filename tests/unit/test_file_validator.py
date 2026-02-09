"""
Unit tests for the FileValidator module.

Tests cover:
- Magic bytes detection for various file types
- Extension validation
- File size limits
- PDF structure validation
- Error handling
"""

import pytest
from src.infrastructure.security.file_validator import (
    FileValidator,
    FileValidationError,
    ValidationResult
)


class TestFileValidatorMagicBytes:
    """Tests for magic bytes detection."""

    def test_detect_valid_pdf(self):
        """Should detect valid PDF from magic bytes."""
        # Minimal valid PDF structure
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF'
        validator = FileValidator(allowed_types=['pdf'])

        result = validator.validate(pdf_content, 'test.pdf')

        assert result.is_valid is True
        assert result.file_type == 'pdf'

    def test_detect_valid_png(self):
        """Should detect valid PNG from magic bytes."""
        # PNG magic bytes (minimal, won't be a valid image but valid signature)
        png_header = b'\x89PNG\r\n\x1a\n'
        png_content = png_header + b'\x00' * 100

        validator = FileValidator(allowed_types=['png'])
        result = validator.validate(png_content, 'test.png')

        assert result.is_valid is True
        assert result.file_type == 'png'

    def test_detect_valid_jpg_jfif(self):
        """Should detect JPEG JFIF format."""
        jpg_content = b'\xff\xd8\xff\xe0' + b'\x00' * 100

        validator = FileValidator(allowed_types=['jpg'])
        result = validator.validate(jpg_content, 'test.jpg')

        assert result.is_valid is True
        assert result.file_type == 'jpg'

    def test_detect_valid_jpg_exif(self):
        """Should detect JPEG Exif format."""
        jpg_content = b'\xff\xd8\xff\xe1' + b'\x00' * 100

        validator = FileValidator(allowed_types=['jpg'])
        result = validator.validate(jpg_content, 'test.jpeg')

        assert result.is_valid is True
        assert result.file_type == 'jpg'

    def test_detect_valid_gif87a(self):
        """Should detect GIF 87a format."""
        gif_content = b'GIF87a' + b'\x00' * 100

        validator = FileValidator(allowed_types=['gif'])
        result = validator.validate(gif_content, 'test.gif')

        assert result.is_valid is True
        assert result.file_type == 'gif'

    def test_detect_valid_gif89a(self):
        """Should detect GIF 89a format."""
        gif_content = b'GIF89a' + b'\x00' * 100

        validator = FileValidator(allowed_types=['gif'])
        result = validator.validate(gif_content, 'test.gif')

        assert result.is_valid is True
        assert result.file_type == 'gif'

    def test_detect_valid_webp(self):
        """Should detect WEBP format."""
        webp_content = b'RIFF\x00\x00\x00\x00WEBP' + b'\x00' * 100

        validator = FileValidator(allowed_types=['webp'])
        result = validator.validate(webp_content, 'test.webp')

        assert result.is_valid is True
        assert result.file_type == 'webp'

    def test_reject_unknown_file_type(self):
        """Should reject files with unknown magic bytes."""
        unknown_content = b'UNKNOWN_MAGIC_BYTES' + b'\x00' * 100

        validator = FileValidator(allowed_types=['pdf'])
        result = validator.validate(unknown_content, 'test.pdf')

        assert result.is_valid is False
        assert result.error_code == 'UNKNOWN_FILE_TYPE'

    def test_reject_empty_file(self):
        """Should reject empty files."""
        validator = FileValidator(allowed_types=['pdf'])
        result = validator.validate(b'', 'test.pdf')

        assert result.is_valid is False
        assert result.error_code == 'EMPTY_FILE'


class TestFileValidatorAllowedTypes:
    """Tests for file type restrictions."""

    def test_reject_pdf_when_only_images_allowed(self):
        """Should reject PDF when only images are allowed."""
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF'

        validator = FileValidator(allowed_types=['png', 'jpg'])
        result = validator.validate(pdf_content, 'test.pdf')

        assert result.is_valid is False
        assert result.error_code == 'FILE_TYPE_NOT_ALLOWED'
        assert result.file_type == 'pdf'

    def test_reject_image_when_only_pdf_allowed(self):
        """Should reject images when only PDF is allowed."""
        png_content = b'\x89PNG\r\n\x1a\n' + b'\x00' * 100

        validator = FileValidator(allowed_types=['pdf'])
        result = validator.validate(png_content, 'test.png')

        assert result.is_valid is False
        assert result.error_code == 'FILE_TYPE_NOT_ALLOWED'


class TestFileValidatorExtensionMismatch:
    """Tests for extension vs content mismatch detection."""

    def test_reject_pdf_content_with_jpg_extension(self):
        """Should reject when PDF content has .jpg extension."""
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF'

        validator = FileValidator(allowed_types=['pdf', 'jpg'])
        result = validator.validate(pdf_content, 'malicious.jpg')

        assert result.is_valid is False
        assert result.error_code == 'EXTENSION_MISMATCH'

    def test_reject_jpg_content_with_pdf_extension(self):
        """Should reject when JPEG content has .pdf extension."""
        jpg_content = b'\xff\xd8\xff\xe0' + b'\x00' * 100

        validator = FileValidator(allowed_types=['pdf', 'jpg'])
        result = validator.validate(jpg_content, 'malicious.pdf')

        assert result.is_valid is False
        assert result.error_code == 'EXTENSION_MISMATCH'

    def test_skip_extension_check_when_disabled(self):
        """Should skip extension check when disabled."""
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF'

        validator = FileValidator(allowed_types=['pdf'])
        result = validator.validate(pdf_content, 'test.jpg', check_extension=False)

        assert result.is_valid is True
        assert result.file_type == 'pdf'


class TestFileValidatorSizeLimit:
    """Tests for file size validation."""

    def test_reject_file_exceeding_global_limit(self):
        """Should reject files exceeding the global size limit."""
        pdf_content = b'%PDF-1.4\n' + b'x' * 1024 * 1024  # ~1MB content
        # Append valid PDF structure
        pdf_content += b'\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF'

        validator = FileValidator(
            allowed_types=['pdf'],
            max_size_bytes=500 * 1024  # 500 KB limit
        )
        result = validator.validate(pdf_content, 'large.pdf')

        assert result.is_valid is False
        assert result.error_code == 'FILE_TOO_LARGE'

    def test_accept_file_within_limit(self):
        """Should accept files within size limit."""
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\n0000000000 65535 f \ntrailer\n<<>>\nstartxref\n9\n%%EOF'

        validator = FileValidator(
            allowed_types=['pdf'],
            max_size_bytes=50 * 1024 * 1024  # 50 MB
        )
        result = validator.validate(pdf_content, 'small.pdf')

        assert result.is_valid is True


class TestFileValidatorPDFStructure:
    """Tests for PDF structure validation."""

    def test_reject_pdf_without_eof(self):
        """Should reject PDF without EOF marker."""
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\nxref\n0 1\nstartxref\n9\n'

        validator = FileValidator(allowed_types=['pdf'])
        result = validator.validate(pdf_content, 'no_eof.pdf')

        assert result.is_valid is False
        assert result.error_code == 'INVALID_PDF_STRUCTURE'

    def test_reject_pdf_without_xref(self):
        """Should reject PDF without xref/startxref."""
        pdf_content = b'%PDF-1.4\n1 0 obj\n<<>>\nendobj\n%%EOF'

        validator = FileValidator(allowed_types=['pdf'])
        result = validator.validate(pdf_content, 'no_xref.pdf')

        assert result.is_valid is False
        assert result.error_code == 'INVALID_PDF_STRUCTURE'


class TestFileValidatorFactoryMethods:
    """Tests for factory methods."""

    def test_create_pdf_validator(self):
        """Should create a PDF-only validator."""
        validator = FileValidator.create_pdf_validator(max_size_mb=30)

        assert validator.allowed_types == ['pdf']
        assert validator.max_size_bytes == 30 * 1024 * 1024

    def test_create_image_validator(self):
        """Should create an image validator."""
        validator = FileValidator.create_image_validator(max_size_mb=5)

        assert 'png' in validator.allowed_types
        assert 'jpg' in validator.allowed_types
        assert 'gif' in validator.allowed_types
        assert 'webp' in validator.allowed_types
        assert validator.max_size_bytes == 5 * 1024 * 1024


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_valid_result(self):
        """Should create valid result correctly."""
        result = ValidationResult(is_valid=True, file_type='pdf')

        assert result.is_valid is True
        assert result.file_type == 'pdf'
        assert result.error_message is None
        assert result.error_code is None

    def test_invalid_result(self):
        """Should create invalid result correctly."""
        result = ValidationResult(
            is_valid=False,
            file_type='pdf',
            error_message='File too large',
            error_code='FILE_TOO_LARGE'
        )

        assert result.is_valid is False
        assert result.file_type == 'pdf'
        assert result.error_message == 'File too large'
        assert result.error_code == 'FILE_TOO_LARGE'


class TestFileValidationError:
    """Tests for FileValidationError exception."""

    def test_exception_attributes(self):
        """Should store message and error code."""
        error = FileValidationError("Test error", "TEST_CODE")

        assert error.message == "Test error"
        assert error.error_code == "TEST_CODE"
        assert str(error) == "Test error"

    def test_exception_default_code(self):
        """Should use default error code."""
        error = FileValidationError("Test error")

        assert error.error_code == "INVALID_FILE"
