"""API tests for OCR extraction endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.ocr.services.azure_ocr_service import OCRResult

User = get_user_model()


@override_settings(
    AZURE_FORM_RECOGNIZER_ENDPOINT="https://example.cognitiveservices.azure.com",
    AZURE_FORM_RECOGNIZER_KEY="test-key",
)
class OCRExtractViewTests(TestCase):
    """Stub tests for POST /api/ocr/extract/."""

    def setUp(self) -> None:
        """Create an authenticated API client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="ocr-tester",
            email="ocr-tester@example.com",
            password="test-pass-123",
        )
        self.client.force_authenticate(user=self.user)

    def _sample_file(self) -> SimpleUploadedFile:
        """Return a minimal valid PNG upload."""
        return SimpleUploadedFile(
            "id.png",
            b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
        )

    @patch("deals.services.ocr.pipeline.AzureOCRService.analyze_document")
    def test_extract_returns_mapped_fields(self, analyze_document: MagicMock) -> None:
        """Successful OCR should return job_id and extracted field payloads."""
        analyze_document.return_value = OCRResult(
            raw_fields={"DocumentNumber": "784-1990-1234567-1"},
            confidence_scores={"DocumentNumber": 0.92},
            model_used="prebuilt-idDocument",
            page_count=1,
        )

        response = self.client.post(
            "/api/ocr/extract/",
            {
                "file": self._sample_file(),
                "document_type": "emirates_id",
                "target_schema": "deal_create",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("job_id", response.data)
        self.assertIn("extracted_fields", response.data)
        self.assertIn("needs_review_fields", response.data)
        self.assertIn("confidence_scores", response.data)
        self.assertEqual(
            response.data["extracted_fields"].get("emirates_id"),
            "784-1990-1234567-1",
        )

    def test_rejects_unsupported_file_type(self) -> None:
        """Non-PDF/image uploads should return validation errors."""
        bad_file = SimpleUploadedFile(
            "notes.txt",
            b"plain text",
            content_type="text/plain",
        )
        response = self.client.post(
            "/api/ocr/extract/",
            {
                "file": bad_file,
                "document_type": "other",
                "target_schema": "deal_create",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)

    @patch("deals.services.ocr.pipeline.AzureOCRService.analyze_document")
    def test_azure_failure_returns_error_payload(
        self, analyze_document: MagicMock
    ) -> None:
        """Azure failures should return error_code and user_message."""
        from apps.ocr.exceptions import AzureOCRError

        analyze_document.side_effect = AzureOCRError("Service unavailable")

        response = self.client.post(
            "/api/ocr/extract/",
            {
                "file": self._sample_file(),
                "document_type": "emirates_id",
                "target_schema": "deal_create",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["error_code"], "azure_ocr_failed")
        self.assertIn("user_message", response.data)
