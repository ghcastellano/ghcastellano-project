"""
File validation module with magic bytes verification.

This module provides secure file validation that goes beyond simple extension checks.
It validates files using magic bytes (file signatures) to prevent malicious uploads.
"""

import logging
from dataclasses import dataclass
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class FileValidationError(Exception):
    """Raised when file validation fails."""

    def __init__(self, message: str, error_code: str = "INVALID_FILE"):
        self.message = message
        self.error_code = error_code
        super().__init__(self.message)


@dataclass
class ValidationResult:
    """Result of file validation."""
    is_valid: bool
    file_type: Optional[str] = None
    error_message: Optional[str] = None
    error_code: Optional[str] = None


class FileValidator:
    """
    Validates files using magic bytes (file signatures).

    Magic bytes are the first few bytes of a file that identify its format.
    This is more secure than checking file extensions, which can be spoofed.
    """

    # Magic bytes for supported file types
    # Format: {file_type: [(magic_bytes, offset), ...]}
    MAGIC_BYTES = {
        'pdf': [
            (b'%PDF', 0),  # Standard PDF header
        ],
        'png': [
            (b'\x89PNG\r\n\x1a\n', 0),  # PNG header
        ],
        'jpg': [
            (b'\xff\xd8\xff\xe0', 0),  # JPEG JFIF
            (b'\xff\xd8\xff\xe1', 0),  # JPEG Exif
            (b'\xff\xd8\xff\xe2', 0),  # JPEG ICC
            (b'\xff\xd8\xff\xe3', 0),  # JPEG Samsung
            (b'\xff\xd8\xff\xdb', 0),  # JPEG raw
            (b'\xff\xd8\xff\xee', 0),  # JPEG Adobe
        ],
        'gif': [
            (b'GIF87a', 0),  # GIF 87a
            (b'GIF89a', 0),  # GIF 89a
        ],
        'webp': [
            (b'RIFF', 0),  # WEBP starts with RIFF (need to check WEBP at offset 8)
        ],
    }

    # File extension to type mapping
    EXTENSION_MAP = {
        '.pdf': 'pdf',
        '.png': 'png',
        '.jpg': 'jpg',
        '.jpeg': 'jpg',
        '.gif': 'gif',
        '.webp': 'webp',
    }

    # Default file size limits (in bytes)
    DEFAULT_SIZE_LIMITS = {
        'pdf': 50 * 1024 * 1024,    # 50 MB for PDFs
        'image': 10 * 1024 * 1024,   # 10 MB for images
    }

    def __init__(
        self,
        allowed_types: Optional[list] = None,
        max_size_bytes: Optional[int] = None,
        custom_size_limits: Optional[dict] = None
    ):
        """
        Initialize the file validator.

        Args:
            allowed_types: List of allowed file types (e.g., ['pdf', 'png', 'jpg'])
            max_size_bytes: Maximum file size in bytes (overrides type-specific limits)
            custom_size_limits: Custom size limits per file type
        """
        self.allowed_types = allowed_types or ['pdf']
        self.max_size_bytes = max_size_bytes
        self.size_limits = {**self.DEFAULT_SIZE_LIMITS, **(custom_size_limits or {})}

    def validate(
        self,
        file_content: bytes,
        filename: str,
        check_extension: bool = True
    ) -> ValidationResult:
        """
        Validate a file's content and optionally its extension.

        Args:
            file_content: The raw bytes of the file
            filename: The filename (used for extension validation)
            check_extension: Whether to also validate the file extension

        Returns:
            ValidationResult with validation status and details
        """
        # Check if file is empty
        if not file_content:
            return ValidationResult(
                is_valid=False,
                error_message="Arquivo vazio",
                error_code="EMPTY_FILE"
            )

        # Detect file type from magic bytes
        detected_type = self._detect_file_type(file_content)

        if not detected_type:
            logger.warning(f"Failed to detect file type for: {filename}")
            return ValidationResult(
                is_valid=False,
                error_message="Tipo de arquivo não reconhecido. Envie um PDF válido.",
                error_code="UNKNOWN_FILE_TYPE"
            )

        # Check if detected type is allowed
        if detected_type not in self.allowed_types:
            logger.warning(f"File type not allowed: {detected_type} for {filename}")
            return ValidationResult(
                is_valid=False,
                file_type=detected_type,
                error_message=f"Tipo de arquivo '{detected_type}' não é permitido. Tipos aceitos: {', '.join(self.allowed_types)}",
                error_code="FILE_TYPE_NOT_ALLOWED"
            )

        # Validate extension matches content (if enabled)
        if check_extension:
            ext_result = self._validate_extension(filename, detected_type)
            if not ext_result[0]:
                return ValidationResult(
                    is_valid=False,
                    file_type=detected_type,
                    error_message=ext_result[1],
                    error_code="EXTENSION_MISMATCH"
                )

        # Validate file size
        size_result = self._validate_size(file_content, detected_type)
        if not size_result[0]:
            return ValidationResult(
                is_valid=False,
                file_type=detected_type,
                error_message=size_result[1],
                error_code="FILE_TOO_LARGE"
            )

        # Additional PDF validation
        if detected_type == 'pdf':
            pdf_result = self._validate_pdf_structure(file_content)
            if not pdf_result[0]:
                return ValidationResult(
                    is_valid=False,
                    file_type=detected_type,
                    error_message=pdf_result[1],
                    error_code="INVALID_PDF_STRUCTURE"
                )

        logger.info(f"File validation passed: {filename} (type: {detected_type})")
        return ValidationResult(
            is_valid=True,
            file_type=detected_type
        )

    def _detect_file_type(self, content: bytes) -> Optional[str]:
        """Detect file type from magic bytes."""
        for file_type, signatures in self.MAGIC_BYTES.items():
            for magic, offset in signatures:
                if len(content) >= offset + len(magic):
                    if content[offset:offset + len(magic)] == magic:
                        # Special case for WEBP (need to check WEBP at offset 8)
                        if file_type == 'webp':
                            if len(content) >= 12 and content[8:12] == b'WEBP':
                                return 'webp'
                            continue
                        return file_type
        return None

    def _validate_extension(self, filename: str, detected_type: str) -> Tuple[bool, str]:
        """Validate that file extension matches detected type."""
        import os
        ext = os.path.splitext(filename.lower())[1]

        if not ext:
            return False, "Arquivo sem extensão"

        expected_type = self.EXTENSION_MAP.get(ext)

        if expected_type != detected_type:
            return False, f"Extensão do arquivo ({ext}) não corresponde ao conteúdo ({detected_type})"

        return True, ""

    def _validate_size(self, content: bytes, file_type: str) -> Tuple[bool, str]:
        """Validate file size against limits."""
        size = len(content)

        # Use global max if set
        if self.max_size_bytes and size > self.max_size_bytes:
            max_mb = self.max_size_bytes / (1024 * 1024)
            return False, f"Arquivo muito grande. Tamanho máximo: {max_mb:.1f} MB"

        # Use type-specific limit
        if file_type == 'pdf':
            limit = self.size_limits.get('pdf', self.DEFAULT_SIZE_LIMITS['pdf'])
        else:
            limit = self.size_limits.get('image', self.DEFAULT_SIZE_LIMITS['image'])

        if size > limit:
            limit_mb = limit / (1024 * 1024)
            return False, f"Arquivo muito grande. Tamanho máximo para {file_type}: {limit_mb:.1f} MB"

        return True, ""

    def _validate_pdf_structure(self, content: bytes) -> Tuple[bool, str]:
        """
        Perform basic PDF structure validation.

        This checks for:
        - Valid PDF header
        - EOF marker presence
        - Basic structure integrity
        """
        # Check header
        if not content.startswith(b'%PDF'):
            return False, "Cabeçalho PDF inválido"

        # Check for EOF marker (should be near the end)
        # PDF files should end with %%EOF
        tail = content[-1024:] if len(content) > 1024 else content
        if b'%%EOF' not in tail:
            return False, "Arquivo PDF corrompido (marcador EOF ausente)"

        # Check for xref or startxref (required in valid PDFs)
        if b'startxref' not in content and b'xref' not in content:
            return False, "Estrutura PDF inválida (tabela de referência ausente)"

        return True, ""

    @classmethod
    def create_pdf_validator(cls, max_size_mb: int = 50) -> 'FileValidator':
        """Factory method to create a PDF-only validator."""
        return cls(
            allowed_types=['pdf'],
            max_size_bytes=max_size_mb * 1024 * 1024
        )

    @classmethod
    def create_image_validator(cls, max_size_mb: int = 10) -> 'FileValidator':
        """Factory method to create an image validator."""
        return cls(
            allowed_types=['png', 'jpg', 'gif', 'webp'],
            max_size_bytes=max_size_mb * 1024 * 1024
        )
