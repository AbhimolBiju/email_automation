"""Tests for invoice OCR text parser enrichment."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.invoice.services.invoice_parser import (
    extract_branch,
    extract_insurer_name,
    extract_invoice_number,
    extract_policy_period,
    extract_policy_type,
    extract_purchase_order,
    extract_total_premium,
    parse_invoice_document,
)


class InvoiceParserTests(SimpleTestCase):
    """Label-based extraction from invoice OCR content."""

    def test_extract_invoice_number_from_label(self) -> None:
        """Invoice number should be parsed from common label patterns."""
        text = "Tax Invoice No: INV-2024-99\nTotal: AED 100"
        self.assertEqual(extract_invoice_number(text), "INV-2024-99")

    def test_extract_purchase_order_from_label(self) -> None:
        """Purchase order should be parsed from PO label patterns."""
        text = "Purchase Order: PO-12345\nVendor: Acme"
        self.assertEqual(extract_purchase_order(text), "PO-12345")

    def test_parse_invoice_document_returns_crm_keys(self) -> None:
        """parse_invoice_document should return both Azure and CRM key aliases."""
        text = "Invoice No: ABC-001\nP.O. PO-99"
        parsed = parse_invoice_document(text)

        self.assertEqual(parsed["invoice_no"], "ABC-001")
        self.assertEqual(parsed["InvoiceId"], "ABC-001")
        self.assertEqual(parsed["purchase_order"], "PO-99")
        self.assertEqual(parsed["PurchaseOrder"], "PO-99")

    def test_extract_branch_from_label(self) -> None:
        """Branch should be parsed from BRANCH label on debit note OCR text."""
        text = "BRANCH\nDubai Main\nTotal: AED 100"
        self.assertEqual(extract_branch(text), "Dubai Main")

    def test_extract_branch_from_layout_table_row(self) -> None:
        """Branch should be parsed from the cell to the right of BRANCH in a table row."""
        layout = {
            "lines": [],
            "words": [
                {
                    "content": "BRANCH",
                    "box": {
                        "x_min": 10,
                        "x_max": 70,
                        "x_center": 40,
                        "y_center": 120,
                        "height": 12,
                    },
                },
                {
                    "content": "Dubai",
                    "box": {
                        "x_min": 200,
                        "x_max": 250,
                        "x_center": 225,
                        "y_center": 121,
                        "height": 12,
                    },
                },
                {
                    "content": "Main",
                    "box": {
                        "x_min": 260,
                        "x_max": 310,
                        "x_center": 285,
                        "y_center": 121,
                        "height": 12,
                    },
                },
            ],
        }
        self.assertEqual(extract_branch("", layout=layout), "Dubai Main")

    def test_extract_policy_type_from_layout_split_label(self) -> None:
        """Policy type should be parsed when POLICY and TYPE are separate OCR words."""
        layout = {
            "lines": [],
            "words": [
                {
                    "content": "POLICY",
                    "box": {
                        "x_min": 10,
                        "x_max": 70,
                        "x_center": 40,
                        "y_center": 150,
                        "height": 12,
                    },
                },
                {
                    "content": "TYPE",
                    "box": {
                        "x_min": 80,
                        "x_max": 130,
                        "x_center": 105,
                        "y_center": 150,
                        "height": 12,
                    },
                },
                {
                    "content": "Motor",
                    "box": {
                        "x_min": 220,
                        "x_max": 280,
                        "x_center": 250,
                        "y_center": 151,
                        "height": 12,
                    },
                },
                {
                    "content": "Comprehensive",
                    "box": {
                        "x_min": 290,
                        "x_max": 420,
                        "x_center": 355,
                        "y_center": 151,
                        "height": 12,
                    },
                },
            ],
        }
        self.assertEqual(
            extract_policy_type("", layout=layout),
            "Motor Comprehensive",
        )

    def test_extract_policy_period_from_label(self) -> None:
        """Policy dates should be parsed from PERIOD label on credit note OCR text."""
        text = "PERIOD: 01/01/2024 - 31/12/2024"
        parsed = extract_policy_period(text)

        self.assertEqual(parsed["policy_start_date"], "2024-01-01")
        self.assertEqual(parsed["policy_end_date"], "2024-12-31")

    def test_extract_insurer_name_from_label(self) -> None:
        """Insurer name should be parsed from INSURER label on debit note OCR text."""
        text = "INSURER NAME: Oman Insurance Company\nBRANCH: Dubai"
        self.assertEqual(extract_insurer_name(text), "Oman Insurance Company")

    def test_extract_total_premium_from_total_row(self) -> None:
        """Premium should be parsed from the bottom TOTAL row (rightmost amount)."""
        text = (
            "Line items\n"
            "SUB TOTAL 1,000.00\n"
            "VAT 50.00\n"
            "TOTAL AED 3,800.00"
        )
        self.assertEqual(extract_total_premium(text), "3800.00")

    def test_extract_total_premium_from_layout_geometry(self) -> None:
        """Layout geometry should pick the amount to the right of TOTAL on the same row."""
        layout = {
            "lines": [
                {
                    "content": "TOTAL",
                    "box": {
                        "x_min": 10,
                        "x_max": 60,
                        "y_center": 200,
                        "height": 12,
                    },
                }
            ],
            "words": [
                {
                    "content": "TOTAL",
                    "box": {
                        "x_min": 10,
                        "x_max": 60,
                        "x_center": 35,
                        "y_center": 200,
                        "height": 12,
                    },
                },
                {
                    "content": "3,800.00",
                    "box": {
                        "x_min": 300,
                        "x_max": 380,
                        "x_center": 340,
                        "y_center": 201,
                        "height": 12,
                    },
                },
            ],
        }
        self.assertEqual(extract_total_premium("", layout=layout), "3800.00")

    def test_extract_policy_type_from_label(self) -> None:
        """Policy type should be parsed from POLICY TYPE label."""
        text = "POLICY TYPE: Motor Comprehensive\nPremium: AED 100"
        self.assertEqual(extract_policy_type(text), "Motor Comprehensive")

    def test_parse_invoice_document_includes_branch_and_period(self) -> None:
        """parse_invoice_document should enrich branch and policy period keys."""
        text = (
            "BRANCH: Abu Dhabi\n"
            "POLICY TYPE: Motor Comprehensive\n"
            "PERIOD 15/03/2024 to 14/03/2025"
        )
        parsed = parse_invoice_document(text)

        self.assertEqual(parsed["branch"], "Abu Dhabi")
        self.assertEqual(parsed["policy_type"], "Motor Comprehensive")
        self.assertEqual(parsed["policy_start_date"], "2024-03-15")
        self.assertEqual(parsed["policy_end_date"], "2025-03-14")
