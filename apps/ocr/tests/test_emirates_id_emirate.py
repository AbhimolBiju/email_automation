"""Tests for emirate extraction from Emirates ID back."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.ocr.services.emirates_id_parser import (
    extract_emirate_from_emirates_id_back,
    normalize_emirate,
    parse_emirates_id_document,
)


class EmiratesIdEmirateTests(SimpleTestCase):
    """Tests for Issuing Place -> emirate parsing."""

    def test_extracts_from_azure_issuing_place(self) -> None:
        """IssuingPlace field should map to emirate."""
        value = extract_emirate_from_emirates_id_back(
            "",
            existing_fields={"IssuingPlace": "Dubai"},
        )
        self.assertEqual(value, "DUBAI")

    def test_strips_embedded_issuing_place_label(self) -> None:
        """Values like 'Issuing Place. Dubai' should drop the label."""
        value = extract_emirate_from_emirates_id_back(
            "",
            existing_fields={"IssuingPlace": "Issuing Place. Dubai"},
        )
        self.assertEqual(value, "DUBAI")

    def test_extracts_from_ocr_text_label(self) -> None:
        """Free-text OCR should read the line after Issuing Place."""
        text = """
        Issuing Place
        Abu Dhabi
        """
        self.assertEqual(extract_emirate_from_emirates_id_back(text), "ABU DHABI")

    def test_maps_sharjah_to_crm_label(self) -> None:
        """Sharjah should use the CRM dropdown label."""
        self.assertEqual(normalize_emirate("Sharjah"), "SHARJAH.  U.A.E")

    def test_parse_document_back_only_sets_emirate(self) -> None:
        """Emirate is added only for emirates_id_back document type."""
        back = parse_emirates_id_document(
            "",
            existing_fields={"IssuingPlace": "Ajman"},
            document_type="emirates_id_back",
        )
        front = parse_emirates_id_document(
            "",
            existing_fields={"IssuingPlace": "Ajman"},
            document_type="emirates_id_front",
        )
        self.assertEqual(back.get("emirate"), "AJMAN")
        self.assertNotIn("emirate", front)
