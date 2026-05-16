"""Unit tests for OCR service layer."""

from __future__ import annotations

from decimal import Decimal

from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from apps.ocr.field_transformers import normalize_text, parse_currency, parse_date
from apps.ocr.serialization import to_json_safe, to_json_safe_dict
from apps.ocr.services.azure_ocr_service import OCRResult
from apps.ocr.services.confidence_filter import filter_by_confidence
from apps.ocr.services.field_mapper import map_ocr_fields, transform_field_value
from apps.ocr.field_mappings import resolve_model_id


class JsonSerializationTests(SimpleTestCase):
    """Tests for JSON-safe OCR payload conversion."""

    def test_serializes_date_and_decimal(self) -> None:
        """Azure date/decimal values must be JSON-safe before DB save."""
        payload = {
            "DateOfBirth": date(1990, 3, 15),
            "InvoiceTotal": Decimal("1250.50"),
        }
        safe = to_json_safe_dict(payload)
        self.assertEqual(safe["DateOfBirth"], "1990-03-15")
        self.assertEqual(safe["InvoiceTotal"], "1250.50")
        self.assertEqual(to_json_safe(date(2000, 1, 1)), "2000-01-01")


class FieldTransformerTests(SimpleTestCase):
    """Tests for post-extraction field transformers."""

    def test_parse_date_returns_iso_format(self) -> None:
        """Date strings should normalize to YYYY-MM-DD."""
        self.assertEqual(parse_date("15/03/1990"), "1990-03-15")

    def test_parse_currency_strips_symbols(self) -> None:
        """Currency strings should parse to Decimal amounts."""
        self.assertEqual(parse_currency("AED 1,250.50"), Decimal("1250.50"))

    def test_normalize_text_collapses_whitespace(self) -> None:
        """Text values should be trimmed and collapsed."""
        self.assertEqual(normalize_text("  hello   world  "), "hello world")


class FieldMapperTests(SimpleTestCase):
    """Tests for Azure-to-CRM field mapping."""

    def test_maps_deal_create_id_document_fields(self) -> None:
        """Known Azure keys should map to CRM fields for deal_create."""
        ocr_result = OCRResult(
            raw_fields={
                "DocumentNumber": "784-1990-1234567-1",
                "DateOfBirth": "1990-01-01",
            },
            confidence_scores={
                "DocumentNumber": 0.95,
                "DateOfBirth": 0.80,
            },
            model_used="prebuilt-idDocument",
            page_count=1,
        )

        mapped = map_ocr_fields(ocr_result, "deal_create")

        extracted = {field.crm_field: field.value for field in mapped.extracted}
        self.assertEqual(extracted["emirates_id"], "784-1990-1234567-1")
        self.assertEqual(extracted["date_of_birth"], "1990-01-01")
        self.assertEqual(mapped.unmapped, [])

    def test_maps_invoice_fields_for_deal_create(self) -> None:
        """Invoice model fields should map when model_used is prebuilt-invoice."""
        ocr_result = OCRResult(
            raw_fields={
                "VendorName": "Example Insurance",
                "InvoiceTotal": "AED 500.00",
            },
            confidence_scores={
                "VendorName": 0.9,
                "InvoiceTotal": 0.88,
            },
            model_used="prebuilt-invoice",
            page_count=1,
        )

        mapped = map_ocr_fields(ocr_result, "deal_create")
        extracted = {field.crm_field: field.value for field in mapped.extracted}

        self.assertEqual(extracted["insurer_name"], "Example Insurance")
        self.assertEqual(extracted["premium_amount"], Decimal("500.00"))

    def test_unmapped_azure_fields_are_reported(self) -> None:
        """Azure keys without schema mapping should appear in unmapped."""
        ocr_result = OCRResult(
            raw_fields={"UnknownField": "value"},
            confidence_scores={"UnknownField": 0.99},
            model_used="prebuilt-document",
            page_count=1,
        )

        mapped = map_ocr_fields(ocr_result, "deal_create")

        self.assertEqual(mapped.unmapped, ["UnknownField"])
        self.assertEqual(mapped.extracted, [])

    def test_transform_field_value_applies_date_and_currency_sets(self) -> None:
        """Mapper transformers should respect DATE_FIELDS and CURRENCY_FIELDS."""
        self.assertEqual(
            transform_field_value("date_of_birth", "01/02/2000"),
            "2000-02-01",
        )
        self.assertEqual(transform_field_value("gender", "M"), "Male")
        self.assertEqual(
            transform_field_value("premium_amount", "$1,000"),
            Decimal("1000"),
        )


class ConfidenceFilterTests(SimpleTestCase):
    """Tests for confidence threshold filtering."""

    @override_settings(OCR_CONFIDENCE_THRESHOLD=0.75)
    def test_splits_fields_by_threshold(self) -> None:
        """Fields below threshold should be flagged for review."""
        ocr_result = OCRResult(
            raw_fields={
                "DocumentNumber": "784-1990-1234567-1",
                "Sex": "F",
            },
            confidence_scores={
                "DocumentNumber": 0.95,
                "Sex": 0.50,
            },
            model_used="prebuilt-idDocument",
            page_count=1,
        )
        mapped = map_ocr_fields(ocr_result, "deal_create")
        filtered = filter_by_confidence(mapped)

        self.assertIn("emirates_id", filtered.high_confidence)
        self.assertIn("gender", filtered.needs_review)
        self.assertEqual(len(mapped.low_confidence), 1)


class ModelRoutingTests(SimpleTestCase):
    """Tests for document_type to Azure model routing."""

    def test_id_card_uses_id_document_model(self) -> None:
        """ID document types should route to prebuilt-idDocument."""
        self.assertEqual(resolve_model_id("emirates_id"), "prebuilt-idDocument")

    def test_invoice_uses_invoice_model(self) -> None:
        """Invoice document type should route to prebuilt-invoice."""
        self.assertEqual(resolve_model_id("invoice"), "prebuilt-invoice")
