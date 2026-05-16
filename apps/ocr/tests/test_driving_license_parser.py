"""Tests for driving license OCR parsing."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.ocr.services.driving_license_parser import (
    extract_license_number_from_license_front,
    normalize_license_number,
    parse_driving_license_document,
)


class DrivingLicenseParserTests(SimpleTestCase):
    """Tests for license number extraction from license front."""

    def test_extracts_from_azure_document_number(self) -> None:
        """DocumentNumber on license front should map to license_no."""
        value = extract_license_number_from_license_front(
            "",
            existing_fields={"DocumentNumber": "35372179989"},
        )
        self.assertEqual(value, "35372179989")

    def test_strips_embedded_license_label(self) -> None:
        """Values like 'License No. 35372179989' should drop the label."""
        value = extract_license_number_from_license_front(
            "",
            existing_fields={"DocumentNumber": "License No. 35372179989"},
        )
        self.assertEqual(value, "35372179989")

    def test_extracts_from_ocr_text_label(self) -> None:
        """Free-text OCR should read the line after License No."""
        text = """
        License No
        35372179989
        """
        self.assertEqual(
            extract_license_number_from_license_front(text),
            "35372179989",
        )

    def test_rejects_emirates_id_pattern(self) -> None:
        """Emirates ID numbers should not be treated as license numbers."""
        value = normalize_license_number("784-1990-1234567-1")
        self.assertEqual(value, "")

    def test_extracts_license_issue_and_expiry_dates(self) -> None:
        """Issue and expiry dates should come from driving license front."""
        text = """
        Driving License
        Issue Date
        21/05/2017
        Expiry Date
        28/11/2038
        """
        from apps.ocr.services.driving_license_parser import (
            extract_license_dates_from_license_front,
        )

        dates = extract_license_dates_from_license_front(text)
        self.assertEqual(dates.get("license_from_date"), "2017-05-21")
        self.assertEqual(dates.get("license_to_date"), "2038-11-28")

    def test_extracts_license_dates_from_azure_fields(self) -> None:
        """Azure DateOfIssue/DateOfExpiration should map to license dates."""
        from apps.ocr.services.driving_license_parser import (
            parse_driving_license_document,
        )

        data = parse_driving_license_document(
            "",
            existing_fields={
                "DateOfIssue": "21/05/2017",
                "DateOfExpiration": "28/11/2038",
            },
            document_type="driving_license_front",
        )
        self.assertEqual(data.get("license_from_date"), "2017-05-21")
        self.assertEqual(data.get("license_to_date"), "2038-11-28")

    def test_parse_document_front_only(self) -> None:
        """license_no is added only for driving_license_front."""
        front = parse_driving_license_document(
            "",
            existing_fields={"DocumentNumber": "123456"},
            document_type="driving_license_front",
        )
        back = parse_driving_license_document(
            "",
            existing_fields={"DocumentNumber": "123456"},
            document_type="driving_license_back",
        )
        self.assertEqual(front.get("license_no"), "123456")
        self.assertNotIn("license_no", back)
