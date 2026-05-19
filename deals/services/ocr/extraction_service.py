"""Orchestrate parser → validator → mapper for deal document OCR."""

from __future__ import annotations

import logging
from typing import Any

from deals.services.ocr.mapper.base import parser_data
from deals.services.ocr.mapper.deal_create_mapper import map_parser_result_to_deal_create
from deals.services.ocr.parser.driving_license import parse_driving_license
from deals.services.ocr.parser.emirates_id import parse_emirates_id
from deals.services.ocr.parser.mulkiya_parser import parse_mulkiya
from deals.services.ocr.validator.driving_license_val import validate_driving_license
from deals.services.ocr.validator.emirate_validator import validate_emirates_id
from deals.services.ocr.validator.mulkiya_validator import validate_mulkiya

logger = logging.getLogger(__name__)


def _string_key_values(raw_fields: dict[str, Any] | None) -> dict[str, str]:
    """Build label-style key/value pairs from Azure structured fields."""
    if not raw_fields:
        return {}
    key_values: dict[str, str] = {}
    for key, value in raw_fields.items():
        if key.startswith("_") or key == "content":
            continue
        if isinstance(value, str) and value.strip():
            key_values[key] = value.strip()
    return key_values


def _layout_as_azure_json(layout: dict[str, Any] | None) -> dict[str, Any] | None:
    if not layout:
        return None
    lines = layout.get("lines") or []
    words = layout.get("words") or []
    if not lines and not words:
        return None
    return {
        "analyzeResult": {
            "readResults": [
                {
                    "lines": [
                        {"text": line.get("content", "")}
                        for line in lines
                        if line.get("content")
                    ],
                }
            ]
        }
    }


def _run_parser(
    text: str,
    document_type: str,
    *,
    raw_fields: dict[str, Any] | None = None,
    layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    doc_lower = (document_type or "").lower()
    key_values = _string_key_values(raw_fields)
    azure_json = _layout_as_azure_json(layout)

    if "emirates_id" in doc_lower:
        return parse_emirates_id(text, document_type=document_type)

    if "driving_license" in doc_lower:
        return parse_driving_license(
            text,
            document_type=document_type,
            key_values=key_values,
            azure_json=azure_json,
        )

    if "mulkiya" in doc_lower:
        return parse_mulkiya(text, key_values=key_values, document_type=document_type)

    return {"document_type": document_type, "data": {}}


def _run_validator(parsed: dict[str, Any]) -> dict[str, Any]:
    doc_type = str(parsed.get("document_type") or "").lower()
    try:
        if "emirates_id" in doc_type:
            return validate_emirates_id(parsed)
        if "driving_license" in doc_type:
            side = str(parsed.get("side") or parsed.get("driving_license_side") or "front")
            result = validate_driving_license(parser_data(parsed), side=side)
            return {
                "status": "VERIFIED" if not result else "PENDING",
                "errors": result,
            }
        if "mulkiya" in doc_type:
            return validate_mulkiya(parsed)
    except Exception as exc:
        logger.warning("OCR validation failed for %s: %s", doc_type, exc)
    return {"status": "SKIPPED", "errors": {}}


def _apply_validation(
    mapped: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    """Drop mapped fields that failed validation when status is not VERIFIED."""
    if validation.get("status") in {None, "VERIFIED", "SKIPPED"}:
        return mapped
    errors = validation.get("errors") or {}
    if not isinstance(errors, dict):
        return mapped

    field_error_map = {
        "emirates_id_number": "emirates_id",
        "license_no": "license_no",
        "registration_no": "registration_no",
        "tcf_no": "tcf_number",
        "chassis_no": "chassis_no",
        "plate_code": "plate_code",
        "place_of_issue": "plate_source",
    }

    for error_field in errors:
        crm_key = field_error_map.get(error_field, error_field)
        mapped.pop(crm_key, None)

    return mapped


def extract_document_fields(
    text: str,
    document_type: str,
    *,
    raw_fields: dict[str, Any] | None = None,
    layout: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Parse document text, validate, and return CRM-ready fields for enrichment.

    Returns a flat dict suitable for merging into Azure ``raw_fields``.
    """
    if not text or not text.strip():
        return {}

    parsed = _run_parser(
        text,
        document_type,
        raw_fields=raw_fields,
        layout=layout,
    )
    validation = _run_validator(parsed)
    mapped = map_parser_result_to_deal_create(parsed, document_type=document_type)
    mapped = _apply_validation(mapped, validation)

    if validation.get("errors"):
        mapped["_validation_errors"] = validation["errors"]
    if parsed.get("confidence_score") is not None:
        mapped["_parser_confidence"] = parsed["confidence_score"]

    return {key: value for key, value in mapped.items() if not key.startswith("_")}
