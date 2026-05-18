"""API tests for invoice extraction endpoint."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.invoice.models import InvoiceJob
from apps.invoice.services.azure_invoice_service import InvoiceResult

User = get_user_model()


@override_settings(
    AZURE_FORM_RECOGNIZER_ENDPOINT="https://example.cognitiveservices.azure.com",
    AZURE_FORM_RECOGNIZER_KEY="test-key",
)
class InvoiceExtractViewTests(TestCase):
    """Tests for POST /api/invoice/extract/."""

    def setUp(self) -> None:
        """Create an authenticated API client."""
        self.client = APIClient()
        self.user = User.objects.create_user(
            username="invoice-tester",
            email="invoice-tester@example.com",
            password="test-pass-123",
        )
        self.client.force_authenticate(user=self.user)

    def _sample_file(self) -> SimpleUploadedFile:
        """Return a minimal valid PNG upload."""
        return SimpleUploadedFile(
            "invoice.png",
            b"\x89PNG\r\n\x1a\n",
            content_type="image/png",
        )

    @patch("apps.invoice.views.AzureInvoiceService.analyze_document")
    def test_extract_returns_mapped_fields(self, analyze_document: MagicMock) -> None:
        """Successful extraction should return job_id and extracted field payloads."""
        analyze_document.return_value = InvoiceResult(
            raw_fields={
                "InvoiceId": "INV-2024-001",
                "VendorName": "Example Vendor",
                "InvoiceTotal": "AED 1,250.00",
            },
            confidence_scores={
                "InvoiceId": 0.92,
                "VendorName": 0.88,
                "InvoiceTotal": 0.90,
            },
            model_used="prebuilt-invoice",
            page_count=1,
        )

        response = self.client.post(
            "/api/invoice/extract/",
            {
                "file": self._sample_file(),
                "document_type": "invoice",
                "target_schema": "invoice_create",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn("job_id", response.data)
        self.assertIn("extracted_fields", response.data)
        self.assertIn("needs_review_fields", response.data)
        self.assertIn("confidence_scores", response.data)
        self.assertEqual(
            response.data["extracted_fields"].get("invoice_no"),
            "INV-2024-001",
        )
        self.assertEqual(
            response.data["extracted_fields"].get("vendor_name"),
            "Example Vendor",
        )

    def test_rejects_unsupported_file_type(self) -> None:
        """Non-PDF/image uploads should return validation errors."""
        bad_file = SimpleUploadedFile(
            "notes.txt",
            b"plain text",
            content_type="text/plain",
        )
        response = self.client.post(
            "/api/invoice/extract/",
            {
                "file": bad_file,
                "document_type": "invoice",
                "target_schema": "invoice_create",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("file", response.data)

    @patch("apps.invoice.views.AzureInvoiceService.analyze_document")
    def test_azure_failure_returns_error_payload(
        self, analyze_document: MagicMock
    ) -> None:
        """Azure failures should return error_code and user_message."""
        from apps.invoice.exceptions import AzureInvoiceError

        analyze_document.side_effect = AzureInvoiceError("Service unavailable")

        response = self.client.post(
            "/api/invoice/extract/",
            {
                "file": self._sample_file(),
                "document_type": "invoice",
                "target_schema": "invoice_create",
            },
            format="multipart",
        )

        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.data["error_code"], "azure_invoice_failed")
        self.assertIn("user_message", response.data)

    @patch("apps.invoice.views.AzureInvoiceService.analyze_document")
    def test_get_job_returns_stored_extraction(self, analyze_document: MagicMock) -> None:
        """GET job detail should return persisted OCR fields for re-autofill."""
        analyze_document.return_value = InvoiceResult(
            raw_fields={"InvoiceId": "INV-99"},
            confidence_scores={"InvoiceId": 0.9},
            model_used="prebuilt-invoice",
            page_count=1,
        )

        create_response = self.client.post(
            "/api/invoice/extract/",
            {
                "file": self._sample_file(),
                "document_type": "invoice",
                "target_schema": "invoice_create",
            },
            format="multipart",
        )
        job_id = create_response.data["job_id"]

        detail_response = self.client.get(f"/api/invoice/jobs/{job_id}/")

        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(detail_response.data["job_id"], job_id)
        self.assertEqual(detail_response.data["status"], InvoiceJob.STATUS_COMPLETED)
        self.assertEqual(detail_response.data["extracted_fields"]["invoice_no"], "INV-99")
