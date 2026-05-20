"""Merge deal parser output into Azure OCR raw fields."""

from __future__ import annotations

from typing import Any

from apps.ocr.serialization import to_json_safe
from deals.services.ocr.extraction_service import extract_document_fields


def enrich_raw_fields_for_deal(
    raw_fields: dict[str, Any],
    confidence_scores: dict[str, float],
    *,
    document_type: str,
) -> dict[str, Any]:
    """Apply deal parsers/mappers and merge CRM fields into Azure output."""
    content = raw_fields.get("content")
    text = content if isinstance(content, str) else ""
    layout = raw_fields.get("_azure_layout")
    layout_dict = layout if isinstance(layout, dict) else None

    parsed = extract_document_fields(
        text,
        document_type,
        raw_fields=raw_fields,
        layout=layout_dict,
    )
    if not parsed:
        return raw_fields

    base_confidence = float(confidence_scores.get("content", 0.75))
    enriched = dict(raw_fields)
    doc_lower = (document_type or "").lower()

    if doc_lower in {"driving_license_front", "driving_license"}:
        if parsed.get("license_no"):
            enriched.pop("DocumentNumber", None)
        if parsed.get("license_from_date"):
            enriched["DateOfIssue"] = parsed["license_from_date"]
            confidence_scores.setdefault("DateOfIssue", base_confidence)
        if parsed.get("license_to_date"):
            enriched["DateOfExpiration"] = parsed["license_to_date"]
            confidence_scores.setdefault("DateOfExpiration", base_confidence)

    for key, value in parsed.items():
        safe_value = to_json_safe(value)
        if safe_value in (None, ""):
            continue
        enriched[key] = safe_value
        confidence_scores.setdefault(key, base_confidence)

    full_name = to_json_safe(
        parsed.get("name") or parsed.get("customer_name") or parsed.get("owner")
    )
    if full_name in (None, "") and "emirates_id" in doc_lower:
        azure_name = to_json_safe(raw_fields.get("Name") or raw_fields.get("name"))
        if azure_name not in (None, ""):
            full_name = azure_name
        else:
            first = to_json_safe(raw_fields.get("FirstName") or raw_fields.get("first_name"))
            last = to_json_safe(raw_fields.get("LastName") or raw_fields.get("last_name"))
            if first or last:
                full_name = f"{first or ''} {last or ''}".strip()

    if full_name not in (None, ""):
        enriched["name"] = full_name
        enriched["customer_name"] = full_name
        enriched["Name"] = full_name
        confidence_scores.setdefault("name", base_confidence)
        confidence_scores.setdefault("customer_name", base_confidence)
        confidence_scores.setdefault("Name", base_confidence)

    tcf = to_json_safe(
        parsed.get("tcf_number")
        or parsed.get("traffic_code")
        or parsed.get("tcf_no")
        or parsed.get("traffic_code_no")
    )
    if tcf not in (None, ""):
        enriched["tcf_number"] = tcf
        enriched["traffic_code"] = tcf
        enriched["tcf_no"] = tcf
        confidence_scores.setdefault("tcf_number", base_confidence)

    for source_key, target_key in (
        ("make_id", "make_id"),
        ("model_id", "model_id"),
        ("body_type_id", "body_type_id"),
    ):
        value = to_json_safe(parsed.get(source_key))
        if value in (None, ""):
            continue
        enriched[target_key] = value
        confidence_scores.setdefault(target_key, base_confidence)

    if "mulkiya" in doc_lower and parsed.get("plate_source"):
        plate_source = parsed["plate_source"]
        for alias_key in (
            "origin",
            "PlaceOfIssue",
            "place_of_issue",
            "LicensingAuthority",
            "licensing_authority",
            "plate_source",
        ):
            enriched[alias_key] = plate_source
            confidence_scores.setdefault(alias_key, base_confidence)

    if "mulkiya" in doc_lower and parsed.get("plate_code"):
        plate_code = parsed["plate_code"]
        for alias_key in ("plate_code", "traffic_plate_no", "plate_category"):
            enriched[alias_key] = plate_code
            confidence_scores.setdefault(alias_key, base_confidence)

    if "mulkiya" in doc_lower and parsed.get("nationality"):
        nationality = parsed["nationality"]
        for alias_key in ("nationality", "Nationality"):
            enriched[alias_key] = nationality
            confidence_scores.setdefault(alias_key, base_confidence)

    if "mulkiya" in doc_lower and parsed.get("registration_date"):
        registration_date = parsed["registration_date"]
        for alias_key in (
            "registration_date",
            "RegDate",
            "Reg_Date",
            "reg_date",
        ):
            enriched[alias_key] = registration_date
            confidence_scores.setdefault(alias_key, base_confidence)
        for expiry_key in (
            "expiry_date",
            "ExpiryDate",
            "DateOfExpiration",
            "expiration_date",
            "RegistrationDate",
            "reg_dt",
        ):
            enriched.pop(expiry_key, None)

    return enriched
