"""Tests for insurer-specific parser routing."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.invoice.services.parser.router import (
    detect_insurer,
    is_credit_note,
    parse_insurance_document,
)


class ParserRouterTests(SimpleTestCase):
    """Ensure OCR routes to the correct insurer parser."""

    def test_detect_qic(self) -> None:
        text = "QATAR INSURANCE COMPANY\nCREDIT NOTE"
        self.assertEqual(detect_insurer(text), "qic")

    def test_detect_al_sagr(self) -> None:
        text = "AL SAGR NATIONAL INSURANCE CO.(PSC)"
        self.assertEqual(detect_insurer(text), "al_sagr")

    def test_detect_adamjee(self) -> None:
        text = "ADAMJEE INSURANCE CO. LTD"
        self.assertEqual(detect_insurer(text), "adamjee")

    def test_credit_note_detection_from_document_type(self) -> None:
        self.assertTrue(is_credit_note("", "tax_invoice"))
        self.assertFalse(is_credit_note("", "invoice"))

    def test_qic_debit_parses_branch_and_policy_type(self) -> None:
        text = (
            "QATAR INSURANCE COMPANY\n"
            "Branch : Dubai Branch\n"
            "Product : Motor Comprehensive\n"
            "TOTAL 100.00 50.00 5.00 105.00"
        )
        parsed = parse_insurance_document(text, document_type="invoice")

        self.assertEqual(parsed.get("_parser_meta", {}).get("insurer"), "qic")
        self.assertEqual(parsed.get("branch"), "Dubai Branch")
        self.assertEqual(parsed.get("policy_type"), "Motor Comprehensive")

    def test_adamjee_debit_parses_branch_and_policy_type(self) -> None:
        text = (
            "ADAMJEE INSURANCE CO. LTD\n"
            "BRANCH: Abu Dhabi\n"
            "POLICY TYPE: Third Party Liability\n"
            "TOTAL PREMIUM: AED 1,250.00"
        )
        parsed = parse_insurance_document(text, document_type="invoice")

        self.assertEqual(parsed.get("_parser_meta", {}).get("insurer"), "adamjee")
        self.assertEqual(parsed.get("branch"), "Abu Dhabi")
        self.assertEqual(parsed.get("policy_type"), "Third Party Liability")
