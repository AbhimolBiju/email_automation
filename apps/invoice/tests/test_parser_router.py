"""Tests for insurer-specific parser routing."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.invoice.services.parser.router import (
    detect_insurer,
    is_credit_note,
    normalize_parser_output,
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

    def test_detect_alliance(self) -> None:
        text = "ALLIANCE INSURANCE\nCREDIT NOTE"
        self.assertEqual(detect_insurer(text), "alliance")

    def test_detect_arabia(self) -> None:
        text = "ARABIA INSURANCE CO. S.A.L."
        self.assertEqual(detect_insurer(text), "arabia")

    def test_detect_dni(self) -> None:
        text = "DUBAI NATIONAL INSURANCE\nTAX INVOICE"
        self.assertEqual(detect_insurer(text), "dni")

    def test_detect_fidelity(self) -> None:
        text = "UNITED FIDELITY INSURANCE COMPANY"
        self.assertEqual(detect_insurer(text), "fidelity")

    def test_detect_methaq(self) -> None:
        text = "METHAQ TAKAFUL INSURANCE COMPANY"
        self.assertEqual(detect_insurer(text), "methaq")

    def test_detect_nia(self) -> None:
        text = "THE NEW INDIA ASSURANCE CO. LTD"
        self.assertEqual(detect_insurer(text), "nia")

    def test_detect_rak(self) -> None:
        text = "RAK INSURANCE\nCREDIT NOTE"
        self.assertEqual(detect_insurer(text), "rak")

    def test_detect_sharjah(self) -> None:
        text = "SHARJAH INSURANCE COMPANY PSC"
        self.assertEqual(detect_insurer(text), "sharjah")

    def test_detect_watania(self) -> None:
        text = "WATANIA TAKAFUL GENERAL P.J.S.C."
        self.assertEqual(detect_insurer(text), "watania")

    def test_credit_note_detection_from_document_type(self) -> None:
        self.assertTrue(is_credit_note("", "tax_invoice"))
        self.assertFalse(is_credit_note("", "invoice"))

    def test_normalize_maps_company_name_to_insurer_name(self) -> None:
        normalized = normalize_parser_output(
            {"company_name": "ALLIANCE INSURANCE", "invoice_number": "CN-1"}
        )
        self.assertEqual(normalized.get("insurer_name"), "ALLIANCE INSURANCE")
        self.assertEqual(normalized.get("invoice_no"), "CN-1")

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

    def test_alliance_credit_routes_to_alliance_parser(self) -> None:
        text = (
            "ALLIANCE INSURANCE\n"
            "CREDIT NOTE\n"
            "Invoice No: CN-2024-001\n"
            "Date: 15/03/2024\n"
        )
        parsed = parse_insurance_document(text, document_type="tax_invoice")

        self.assertEqual(parsed.get("_parser_meta", {}).get("insurer"), "alliance")
        self.assertTrue(parsed.get("_parser_meta", {}).get("is_credit_note"))

    def test_watania_debit_routes_to_watania_parser(self) -> None:
        text = (
            "WATANIA TAKAFUL\n"
            "TAX INVOICE\n"
            "Invoice No: INV-100\n"
        )
        parsed = parse_insurance_document(text, document_type="invoice")

        self.assertEqual(parsed.get("_parser_meta", {}).get("insurer"), "watania")
        self.assertFalse(parsed.get("_parser_meta", {}).get("is_credit_note"))
