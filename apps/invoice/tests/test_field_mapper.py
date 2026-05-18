"""Tests for invoice field mapper."""

from __future__ import annotations

from decimal import Decimal

from django.test import SimpleTestCase

from apps.invoice.services.azure_invoice_service import InvoiceResult
from apps.invoice.services.field_mapper import map_invoice_fields


class InvoiceFieldMapperTests(SimpleTestCase):
    """Ensure Azure invoice keys map to CRM fields for invoice_create."""

    def test_maps_invoice_create_fields(self) -> None:
        """Known Azure keys should map to CRM fields for invoice_create."""
        invoice_result = InvoiceResult(
            raw_fields={
                "InvoiceId": "INV-100",
                "InvoiceDate": "2024-01-15",
                "InvoiceTotal": "AED 500.00",
            },
            confidence_scores={
                "InvoiceId": 0.95,
                "InvoiceDate": 0.85,
                "InvoiceTotal": 0.90,
            },
            model_used="prebuilt-invoice",
            page_count=1,
        )

        mapped = map_invoice_fields(invoice_result, "invoice_create")
        extracted = {field.crm_field: field.value for field in mapped.extracted}

        self.assertEqual(extracted["invoice_no"], "INV-100")
        self.assertEqual(extracted["invoice_date"], "2024-01-15")
        self.assertEqual(extracted["total_amount"], Decimal("500.00"))

    def test_passes_through_enriched_crm_keys(self) -> None:
        """Parser-enriched CRM keys should be included in mapped output."""
        invoice_result = InvoiceResult(
            raw_fields={"purchase_order": "PO-7788"},
            confidence_scores={"purchase_order": 0.9},
            model_used="prebuilt-invoice",
            page_count=1,
        )

        mapped = map_invoice_fields(invoice_result, "invoice_create")
        extracted = {field.crm_field: field.value for field in mapped.extracted}

        self.assertEqual(extracted.get("purchase_order"), "PO-7788")
