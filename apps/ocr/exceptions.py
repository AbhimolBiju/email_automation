"""Custom exceptions for the OCR microservice."""

from __future__ import annotations


class OCRServiceError(Exception):
    """Base exception for OCR service failures."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = "ocr_error",
        user_message: str | None = None,
    ) -> None:
        """Initialize with a technical message and optional user-facing text."""
        super().__init__(message)
        self.error_code = error_code
        self.user_message = user_message or message

    def as_response_dict(self) -> dict[str, str]:
        """Return a JSON-serializable error payload for API responses."""
        return {
            "error_code": self.error_code,
            "user_message": self.user_message,
        }


class OCRConfigurationError(OCRServiceError):
    """Raised when Azure credentials or SDK configuration is missing."""

    def __init__(self, message: str) -> None:
        """Initialize a configuration error with a stable error code."""
        super().__init__(
            message,
            error_code="ocr_not_configured",
            user_message="Document scanning is not available. Please contact support.",
        )


class OCRValidationError(OCRServiceError):
    """Raised when uploaded files or request parameters are invalid."""

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        """Initialize a validation error."""
        super().__init__(
            message,
            error_code="ocr_validation_error",
            user_message=user_message or message,
        )


class AzureOCRError(OCRServiceError):
    """Raised when Azure Document Intelligence returns an error."""

    def __init__(self, message: str, *, user_message: str | None = None) -> None:
        """Initialize an Azure provider error."""
        super().__init__(
            message,
            error_code="azure_ocr_failed",
            user_message=user_message
            or "We could not read this document. Try a clearer scan or enter details manually.",
        )
