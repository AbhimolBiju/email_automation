"""Tests for OCR field mapper pass-through behaviour."""

from __future__ import annotations

from django.test import SimpleTestCase

from apps.ocr.services.azure_ocr_service import OCRResult
from apps.ocr.services.field_mapper import map_ocr_fields


class FieldMapperPassThroughTests(SimpleTestCase):
    """Ensure parser-enriched CRM keys are included in mapped output."""

    def test_maps_lowercase_nationality_from_enriched_fields(self) -> None:
        """Parser ``nationality`` key should map without Azure ``Nationality`` key."""
        ocr_result = OCRResult(
            raw_fields={"nationality": "IND"},
            confidence_scores={"nationality": 0.9},
            model_used="prebuilt-idDocument",
            page_count=1,
        )

        mapped = map_ocr_fields(ocr_result, "deal_create")
        extracted = {field.crm_field: field.value for field in mapped.extracted}

        self.assertEqual(extracted.get("nationality"), "IND")
