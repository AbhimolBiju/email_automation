"""Orchestrate parser → validator → mapper for deal document OCR."""

from __future__ import annotations

import logging
from typing import Any

from deals.services.ocr.mappers.mapper import map_document_to_form
from deals.services.ocr.parsers.parser import parse_document
from deals.services.ocr.validation_maps import (
    VALIDATION_ERROR_CASCADE,
    VALIDATION_ERROR_TO_CRM,
)
from deals.services.ocr.validators.validator import validate_document

logger = logging.getLogger(__name__)

MULKIYA_UPLOAD_ALIASES = {
    "mulkiya_id_front": "mulkiya_front",
    "mulkiya_id_back": "mulkiya_back",
}


def _normalize_document_type(document_type: str) -> str:
    doc = (document_type or "").lower()
    return MULKIYA_UPLOAD_ALIASES.get(doc, doc)


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
    normalized_type = _normalize_document_type(document_type)
    key_values = _string_key_values(raw_fields)
    azure_json = _layout_as_azure_json(layout)

    return parse_document(
        text,
        document_type=normalized_type,
        key_values=key_values,
        azure_json=azure_json,
    )


def _run_validator(parsed: dict[str, Any]) -> dict[str, Any]:
    try:
        return validate_document(parsed)
    except Exception as exc:
        logger.warning(
            "OCR validation failed for %s: %s",
            parsed.get("document_type"),
            exc,
        )
    return {"status": "SKIPPED", "errors": {}}


def _apply_validation(
    mapped: dict[str, Any],
    validation: dict[str, Any],
) -> dict[str, Any]:
    """Drop mapped fields that failed format validation when status is not VERIFIED."""
    if validation.get("status") in {None, "VERIFIED", "SKIPPED"}:
        return mapped
    errors = validation.get("errors") or {}
    if not isinstance(errors, dict):
        return mapped

    for error_field, message in errors.items():
        if message == "Missing field":
            continue

        keys_to_remove = set(VALIDATION_ERROR_CASCADE.get(error_field, ()))
        crm_key = VALIDATION_ERROR_TO_CRM.get(error_field, error_field)
        keys_to_remove.add(crm_key)
        keys_to_remove.add(error_field)

        for key in keys_to_remove:
            mapped.pop(key, None)

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
    mapped = map_document_to_form(parsed)
    mapped = _apply_validation(mapped, validation)

    if validation.get("errors"):
        mapped["_validation_errors"] = validation["errors"]
    confidence = parsed.get("confidence")
    if isinstance(confidence, dict):
        overall = confidence.get("overall_confidence")
        if overall is not None:
            mapped["_parser_confidence"] = overall
    elif parsed.get("confidence_score") is not None:
        mapped["_parser_confidence"] = parsed["confidence_score"]

    return {key: value for key, value in mapped.items() if not key.startswith("_")}
