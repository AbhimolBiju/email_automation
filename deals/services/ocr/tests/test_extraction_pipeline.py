"""Tests for deal OCR extraction pipeline fixes."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.ocr.services.azure_ocr_service import OCRResult
from apps.ocr.services.field_mapper import map_ocr_fields
from deals.services.ocr.extraction_service import _apply_validation
from deals.services.ocr.validator.mulkiya_validator import validate_mulkiya


class MulkiyaValidatorTests(SimpleTestCase):
    def test_accepts_digits_only_registration_no(self) -> None:
        result = validate_mulkiya(
            {
                "document_type": "mulkiya_front",
                "data": {
                    "registration_no": "19033",
                    "plate_number": "19033",
                    "plate_code": "U",
                    "tcf_no": "1234567890",
                    "owner": "John Michael",
                    "registration_date": "2024-01-15",
                    "place_of_issue": "Dubai",
                },
            }
        )
        self.assertNotIn("registration_no", result["errors"])

    def test_accepts_slash_registration_no(self) -> None:
        result = validate_mulkiya(
            {
                "document_type": "mulkiya_front",
                "data": {
                    "registration_no": "U/19033",
                    "plate_number": "19033",
                    "plate_code": "U",
                    "tcf_no": "1234567890",
                    "owner": "John Michael",
                    "registration_date": "2024-01-15",
                    "place_of_issue": "Dubai",
                },
            }
        )
        self.assertNotIn("registration_no", result["errors"])


class FieldMapperParserFieldsTests(SimpleTestCase):
    def test_maps_parser_name_on_id_document_model(self) -> None:
        ocr_result = OCRResult(
            raw_fields={"name": "Ahmed Ali", "content": "x"},
            confidence_scores={"name": 0.9, "content": 0.5},
            model_used="prebuilt-idDocument",
            page_count=1,
        )
        mapped = map_ocr_fields(ocr_result, "deal_create")
        extracted = {field.crm_field: field.value for field in mapped.extracted}
        self.assertEqual(extracted.get("name"), "Ahmed Ali")

    def test_maps_tcf_number_on_driving_license_back(self) -> None:
        ocr_result = OCRResult(
            raw_fields={"tcf_number": "5090123456", "content": "x"},
            confidence_scores={"tcf_number": 0.85, "content": 0.5},
            model_used="prebuilt-idDocument",
            page_count=1,
        )
        mapped = map_ocr_fields(ocr_result, "deal_create")
        extracted = {field.crm_field: field.value for field in mapped.extracted}
        self.assertEqual(extracted.get("tcf_number"), "5090123456")


class ApplyValidationTests(SimpleTestCase):
    def test_keeps_fields_when_only_missing_errors(self) -> None:
        mapped = {"registration_no": "19033", "owner": "John Michael"}
        validation = {
            "status": "PENDING",
            "errors": {"plate_code": "Missing field"},
        }
        result = _apply_validation(mapped, validation)
        self.assertEqual(result.get("registration_no"), "19033")
        self.assertEqual(result.get("owner"), "John Michael")

    def test_drops_invalid_format_fields(self) -> None:
        mapped = {"emirates_id": "bad", "name": "Valid Name"}
        validation = {
            "status": "PENDING",
            "errors": {"emirates_id_number": "Invalid format"},
        }
        result = _apply_validation(mapped, validation)
        self.assertNotIn("emirates_id", result)
        self.assertEqual(result.get("name"), "Valid Name")
