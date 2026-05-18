"""Unit tests for invoice service layer."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.test import SimpleTestCase, override_settings

from apps.invoice.field_mappings import resolve_model_id
from apps.invoice.field_transformers import normalize_text, parse_currency, parse_date
from apps.invoice.serialization import to_json_safe, to_json_safe_dict
from apps.invoice.services.azure_invoice_service import InvoiceResult
from apps.invoice.services.confidence_filter import filter_by_confidence
from apps.invoice.services.field_mapper import map_invoice_fields, transform_field_value


class JsonSerializationTests(SimpleTestCase):
    """Tests for JSON-safe invoice payload conversion."""

    def test_serializes_date_and_decimal(self) -> None:
        """Azure date/decimal values must be JSON-safe before DB save."""
        payload = {
            "invoice_date": date(2024, 3, 15),
            "total_amount": Decimal("1250.50"),
        }
        safe = to_json_safe_dict(payload)
        self.assertEqual(safe["invoice_date"], "2024-03-15")
        self.assertEqual(safe["total_amount"], "1250.50")
        self.assertEqual(to_json_safe(date(2000, 1, 1)), "2000-01-01")


class FieldTransformerTests(SimpleTestCase):
    """Tests for post-extraction field transformers."""

    def test_parse_date_returns_iso_format(self) -> None:
        """Date strings should normalize to YYYY-MM-DD."""
        self.assertEqual(parse_date("15/03/2024"), "2024-03-15")

    def test_parse_currency_strips_symbols(self) -> None:
        """Currency strings should parse to Decimal amounts."""
        self.assertEqual(parse_currency("AED 1,250.50"), Decimal("1250.50"))

    def test_normalize_text_collapses_whitespace(self) -> None:
        """Text values should be trimmed and collapsed."""
        self.assertEqual(normalize_text("  hello   world  "), "hello world")


class ConfidenceFilterTests(SimpleTestCase):
    """Tests for confidence threshold filtering."""

    @override_settings(INVOICE_CONFIDENCE_THRESHOLD=0.75)
    def test_splits_fields_by_threshold(self) -> None:
        """Fields below threshold should be flagged for review."""
        invoice_result = InvoiceResult(
            raw_fields={
                "InvoiceId": "INV-1",
                "VendorName": "Low Confidence Vendor",
            },
            confidence_scores={
                "InvoiceId": 0.95,
                "VendorName": 0.50,
            },
            model_used="prebuilt-invoice",
            page_count=1,
        )
        mapped = map_invoice_fields(invoice_result, "invoice_create")
        filtered = filter_by_confidence(mapped)

        self.assertIn("invoice_no", filtered.high_confidence)
        self.assertIn("vendor_name", filtered.needs_review)
        self.assertEqual(len(mapped.low_confidence), 1)


class ModelRoutingTests(SimpleTestCase):
    """Tests for document_type to Azure model routing."""

    def test_invoice_uses_prebuilt_invoice_model(self) -> None:
        """Invoice document types should route to prebuilt-invoice."""
        self.assertEqual(resolve_model_id("invoice"), "prebuilt-invoice")

    def test_tax_invoice_uses_prebuilt_invoice_model(self) -> None:
        """Tax invoice document type should route to prebuilt-invoice."""
        self.assertEqual(resolve_model_id("tax_invoice"), "prebuilt-invoice")

    def test_transform_field_value_applies_date_and_currency_sets(self) -> None:
        """Mapper transformers should respect DATE_FIELDS and CURRENCY_FIELDS."""
        self.assertEqual(
            transform_field_value("invoice_date", "01/02/2024"),
            "2024-02-01",
        )
        self.assertEqual(
            transform_field_value("total_amount", "$1,000"),
            Decimal("1000"),
        )
