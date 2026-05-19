"""End-to-end deal document OCR: Azure + deal parsers + schema mapping."""

from __future__ import annotations

from typing import Any, BinaryIO

from apps.ocr.services.azure_ocr_service import AzureOCRService, OCRResult
from apps.ocr.services.confidence_filter import filter_by_confidence
from apps.ocr.services.field_mapper import map_ocr_fields
from apps.ocr.serialization import to_json_safe_dict
from deals.services.ocr.enrichment import enrich_raw_fields_for_deal


def analyze_azure_for_deal(
    file_obj: BinaryIO,
    *,
    document_type: str,
) -> OCRResult:
    """Run Azure OCR and apply deal-specific field enrichment."""
    service = AzureOCRService()
    ocr_result = service.analyze_document(file_obj, document_type=document_type)
    enriched_fields = enrich_raw_fields_for_deal(
        dict(ocr_result.raw_fields),
        dict(ocr_result.confidence_scores),
        document_type=document_type,
    )
    return OCRResult(
        raw_fields=enriched_fields,
        confidence_scores=ocr_result.confidence_scores,
        model_used=ocr_result.model_used,
        page_count=ocr_result.page_count,
        provider_payload=ocr_result.provider_payload,
    )


def map_and_filter_deal_fields(
    ocr_result: OCRResult,
    target_schema: str,
) -> tuple[dict[str, Any], dict[str, Any], dict[str, float]]:
    """Map OCR output to CRM schema and split by confidence threshold."""
    mapped = map_ocr_fields(ocr_result, target_schema)
    filtered = filter_by_confidence(mapped)
    extracted_fields = to_json_safe_dict(filtered.high_confidence)
    needs_review_fields = to_json_safe_dict(filtered.needs_review)
    return extracted_fields, needs_review_fields, filtered.confidence_scores


def extract_deal_document_from_upload(
    file_obj: BinaryIO,
    *,
    document_type: str,
    target_schema: str = "deal_create",
) -> tuple[OCRResult, dict[str, Any], dict[str, Any], dict[str, float]]:
    """Full pipeline used by deal OCR API views."""
    ocr_result = analyze_azure_for_deal(file_obj, document_type=document_type)
    extracted, needs_review, confidence_scores = map_and_filter_deal_fields(
        ocr_result,
        target_schema,
    )
    return ocr_result, extracted, needs_review, confidence_scores
