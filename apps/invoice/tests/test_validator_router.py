"""Tests for insurer-specific validator routing."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.invoice.services.validator.router import (
    apply_validation_to_review_fields,
    validate_insurance_document,
)


class ValidatorRouterTests(SimpleTestCase):
    """Ensure parsed fields route to the correct insurer validator."""

    def test_validate_alliance_credit_note_complete(self) -> None:
        parsed = {
            "invoice_number": "CN-1",
            "invoice_date": "2024-03-15",
            "insured_name": "Acme LLC",
            "policy_number": "POL-1",
            "total_amount": "100.00",
        }
        result = validate_insurance_document(
            parsed,
            raw_content="ALLIANCE INSURANCE\nCREDIT NOTE",
            document_type="tax_invoice",
            insurer="alliance",
            is_credit=True,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result["is_valid"])
        self.assertEqual(result["insurer"], "alliance")

    def test_validate_alliance_credit_note_missing_fields(self) -> None:
        parsed = {"invoice_number": "CN-1"}
        result = validate_insurance_document(
            parsed,
            insurer="alliance",
            is_credit=True,
        )

        self.assertIsNotNone(result)
        assert result is not None
        self.assertFalse(result["is_valid"])
        self.assertIn("invoice_date", result["missing_fields"])

    def test_apply_validation_merges_needs_review(self) -> None:
        validation = {
            "is_valid": False,
            "missing_fields": ["invoice_date", "policy_number"],
            "message": "Missing fields",
            "insurer": "alliance",
            "is_credit_note": True,
        }
        extracted = {"invoice_number": "CN-1"}
        needs_review: dict = {}

        enriched, review = apply_validation_to_review_fields(
            extracted,
            needs_review,
            validation,
        )

        self.assertFalse(enriched["_validation"]["is_valid"])
        self.assertIn("invoice_date", review)
        self.assertIn("policy_number", review)

    def test_unknown_insurer_returns_none(self) -> None:
        result = validate_insurance_document(
            {"invoice_number": "X"},
            raw_content="UNKNOWN INSURER BRAND",
            document_type="invoice",
        )
        self.assertIsNone(result)
