"""Tests for shared nationality OCR extraction."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.ocr.nationality import (
    extract_nationality_from_ocr,
    normalize_nationality,
)


class NationalityExtractionTests(SimpleTestCase):
    def test_extracts_latin_inline_nationality(self) -> None:
        text = """
        Nationality: IND
        الجنسية: الهند
        """
        self.assertEqual(extract_nationality_from_ocr(text), "Indian")

    def test_skips_arabic_line_after_english_label(self) -> None:
        text = """
        Nationality
        IND
        الهند
        """
        self.assertEqual(extract_nationality_from_ocr(text), "Indian")

    def test_uses_azure_code_over_arabic_name(self) -> None:
        value = extract_nationality_from_ocr(
            "",
            existing_fields={
                "Nationality": {"code": "IND", "name": "الهند"},
            },
        )
        self.assertEqual(value, "Indian")

    def test_translates_arabic_when_only_arabic_available(self) -> None:
        self.assertEqual(normalize_nationality("الهند"), "Indian")

    def test_maps_india_country_name_to_indian(self) -> None:
        value = extract_nationality_from_ocr(
            "",
            existing_fields={"Nationality": "India"},
        )
        self.assertEqual(value, "Indian")
