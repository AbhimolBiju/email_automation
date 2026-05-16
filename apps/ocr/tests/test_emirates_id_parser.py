"""Tests for Emirates ID OCR text parsing."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.ocr.services.emirates_id_parser import (
    extract_nationality_from_emirates_id,
    normalize_nationality,
    parse_emirates_id_document,
)


class EmiratesIdParserTests(SimpleTestCase):
    """Tests for nationality extraction from Emirates ID OCR text."""

    def test_extracts_latin_inline_nationality(self) -> None:
        """Nationality should use the Latin value on the Nationality label."""
        text = """
        Nationality: IND
        الجنسية: الهند
        """
        self.assertEqual(extract_nationality_from_emirates_id(text), "Indian")

    def test_skips_arabic_line_after_english_label(self) -> None:
        """Arabic line after Nationality should be skipped for Latin code."""
        text = """
        Nationality
        IND
        الهند
        """
        self.assertEqual(extract_nationality_from_emirates_id(text), "Indian")

    def test_uses_azure_code_over_arabic_name(self) -> None:
        """Azure country code should win over Arabic country name."""
        value = extract_nationality_from_emirates_id(
            "",
            existing_fields={
                "Nationality": {"code": "IND", "name": "الهند"},
            },
        )
        self.assertEqual(value, "Indian")

    def test_translates_arabic_when_only_arabic_available(self) -> None:
        """Known Arabic nationality text should map to English."""
        self.assertEqual(normalize_nationality("الهند"), "Indian")

    def test_strips_embedded_nationality_label(self) -> None:
        """Azure values like 'Nationality. Yemen' should drop the label."""
        value = extract_nationality_from_emirates_id(
            "",
            existing_fields={"Nationality": "Nationality. Yemen"},
        )
        self.assertEqual(value, "Yemen")

    def test_maps_india_country_name_to_indian(self) -> None:
        """English country name India should map to dropdown label Indian."""
        value = extract_nationality_from_emirates_id(
            "",
            existing_fields={"Nationality": "India"},
        )
        self.assertEqual(value, "Indian")

    def test_ignores_country_region(self) -> None:
        """Only the Nationality field should be used."""
        text = """
        Nationality: IND
        CountryRegion: United Arab Emirates
        """
        self.assertEqual(extract_nationality_from_emirates_id(text), "Indian")

    def test_parse_document_returns_english_nationality(self) -> None:
        """Parser output should expose English nationality."""
        data = parse_emirates_id_document(
            "Nationality\nIND\nالهند\n",
            existing_fields={},
        )
        self.assertEqual(data.get("nationality"), "Indian")
