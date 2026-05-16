"""Tests for Emirates ID front field extraction."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.ocr.services.emirates_id_parser import (
    extract_emirates_id_number,
    extract_gender_from_emirates_id,
    parse_emirates_id_document,
)


class EmiratesIdFrontFieldsTests(SimpleTestCase):
    """Tests for ID Number and Sex extraction from Emirates ID front."""

    def test_extracts_emirates_id_from_id_number_label(self) -> None:
        """ID Number label with value on next line should extract Emirates ID."""
        text = """
        ID Number
        784-1990-1234567-1
        Nationality
        IND
        """
        self.assertEqual(
            extract_emirates_id_number(text),
            "784-1990-1234567-1",
        )

    def test_extracts_emirates_id_inline(self) -> None:
        """Inline ID Number value should extract Emirates ID."""
        text = "ID Number: 784-1990-1234567-1"
        self.assertEqual(
            extract_emirates_id_number(text),
            "784-1990-1234567-1",
        )

    def test_extracts_gender_from_sex_label(self) -> None:
        """Sex label M/F should map to Male/Female."""
        text = """
        Sex
        F
        """
        self.assertEqual(extract_gender_from_emirates_id(text), "Female")

    def test_extracts_gender_male_inline(self) -> None:
        """Inline Sex: M should map to Male."""
        self.assertEqual(extract_gender_from_emirates_id("Sex: M"), "Male")

    def test_extracts_gender_from_bottom_sex_field(self) -> None:
        """Sex label at the bottom of the card should map F/M to Female/Male."""
        text = """
        ID Number
        784-1990-1234567-1
        Nationality
        IND
        Sex
        F
        """
        self.assertEqual(extract_gender_from_emirates_id(text), "Female")

    def test_prefers_ocr_sex_over_wrong_azure_field(self) -> None:
        """OCR Sex label should win when Azure Sex field is incorrect."""
        text = "Sex\nF\n"
        self.assertEqual(
            extract_gender_from_emirates_id(
                text,
                existing_fields={"Sex": "M"},
            ),
            "Female",
        )

    def test_parse_document_front_sets_id_and_gender(self) -> None:
        """Parser should set emirates_id and gender for front document type."""
        data = parse_emirates_id_document(
            "ID Number\n784-1990-1234567-1\nSex\nM\n",
            document_type="emirates_id_front",
        )
        self.assertEqual(data.get("emirates_id"), "784-1990-1234567-1")
        self.assertEqual(data.get("gender"), "Male")
